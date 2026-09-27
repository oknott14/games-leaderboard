"""Slack adapter (Bolt + Socket Mode). The only module that imports the Slack SDK.

See docs/plan/05-slack-adapter.md.
"""

from __future__ import annotations

import logging
import re
import ssl
from collections.abc import Callable, Iterator, Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_bolt.authorization import AuthorizeResult
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.http_retry.builtin_handlers import RateLimitErrorRetryHandler

from leaderboard.ports import ChatMessage

if TYPE_CHECKING:
    from leaderboard.ports import ChatHandler


log = logging.getLogger(__name__)

_ANGLE = re.compile(r"<([^<>|]*)(?:\|([^<>]*))?>")

# Message subtypes that carry a person's words; everything else (joins, topic changes, bot
# posts, …) is ignored.
KEPT_SUBTYPES = frozenset({"thread_broadcast", "file_share", "me_message"})


def normalize_text(text: str) -> str:
    """Turn Slack message markup into the plain text people see.

    `<http://maptap.gg|maptap.gg>` → `maptap.gg`, `<https://x>` → `https://x`, `<#C1|general>` →
    `#general`, `<!here>` → `@here`, and `&amp; &lt; &gt;` are unescaped (after the links, so an
    escaped `&lt;` can't form a new link). User mentions `<@U123>` are kept. Emoji stay as
    `:shortcodes:`; game configs match them in that form.
    """

    def replace(match: re.Match[str]) -> str:
        target, label = match.group(1), match.group(2)
        if target.startswith("@"):
            return match.group(0)
        if target.startswith("#"):
            return f"#{label or target[1:]}"
        if target.startswith("!"):
            return _special(target[1:], label)
        if label:
            return label
        return target.removeprefix("mailto:")

    return _ANGLE.sub(replace, text).replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


def _special(target: str, label: str | None) -> str:
    """`<!here>`/`<!channel>`/`<!everyone>` → `@here`…, `<!subteam^ID|@team>` → `@team` (or
    `@ID` without a label); other specials (`<!date^…|fallback>`) show their fallback text."""
    kind, _, rest = target.partition("^")
    if kind in ("here", "channel", "everyone"):
        return f"@{kind}"
    if kind == "subteam":
        name = label or rest.split("^")[0]
        return name if name.startswith("@") else f"@{name}"
    return label or target


def to_message(channel_id: str, raw: Mapping[str, Any]) -> ChatMessage | None:
    """A Slack message payload → `ChatMessage`, or `None` if it isn't a person's message."""
    subtype = raw.get("subtype")
    if (subtype is not None and subtype not in KEPT_SUBTYPES) or raw.get("bot_id"):
        return None
    user, ts = raw.get("user"), raw.get("ts")
    if not user or not ts:
        return None
    thread_ts = raw.get("thread_ts")
    return ChatMessage(
        platform="slack",
        channel_id=channel_id,
        message_id=ts,
        user_id=user,
        text=normalize_text(raw.get("text") or ""),
        posted_at=datetime.fromtimestamp(float(ts), UTC),
        thread_id=thread_ts if thread_ts and thread_ts != ts else None,
    )


class SlackPort:
    """Satisfies `ChatPort`. One `WebClient` (with proxy, SSL context and rate-limit retries) is
    shared by history, posting, name lookups and the Bolt app."""

    platform = "slack"

    def __init__(
        self,
        bot_token: str,
        app_token: str,
        *,
        proxy: str | None = None,
        ssl_context: ssl.SSLContext | None = None,
        client: WebClient | None = None,  # injectable for tests
    ) -> None:
        self.client = client or WebClient(token=bot_token, proxy=proxy, ssl=ssl_context)
        self.client.retry_handlers.append(RateLimitErrorRetryHandler(max_retry_count=5))  # back off on 429s
        self._app_token = app_token
        self._proxy = proxy
        self._names: dict[str, str] = {}

        try:
            auth = self.client.auth_test()
        except SlackApiError as exc:
            raise RuntimeError(
                f"Slack auth failed ({exc.response.get('error')}); check SLACK_BOT_TOKEN"
            ) from exc
        except OSError as exc:  # includes ssl.SSLError and URLError
            raise RuntimeError(
                f"Can't reach Slack: {exc}. On a corporate network, set HTTPS_PROXY and/or "
                "SSL_CERT_FILE (see README troubleshooting)"
            ) from exc
        self.bot_user_id: str = auth["user_id"]
        self._auth = AuthorizeResult(
            enterprise_id=auth.get("enterprise_id"), team_id=auth.get("team_id"), team=auth.get("team"),
            bot_user_id=auth["user_id"], bot_id=auth.get("bot_id"), bot_token=bot_token,
        )
        log.info("Slack auth OK: %s as %s", auth.get("team"), auth.get("user"))

    def fetch_history(self, channel_id: str, oldest: datetime) -> Iterator[ChatMessage]:
        """Every person's message since `oldest`, including thread replies (order not guaranteed;
        ingest is idempotent). Known gap: a new reply in a thread whose parent is older than
        `oldest` is only seen live."""
        since = f"{oldest.timestamp():.6f}"
        for raw in self._pages(self.client.conversations_history, channel=channel_id, oldest=since):
            if (msg := to_message(channel_id, raw)) is not None:
                yield msg
            if raw.get("reply_count"):
                parent = raw["ts"]
                for reply in self._pages(self.client.conversations_replies, channel=channel_id, ts=parent, oldest=since):
                    if reply.get("ts") != parent and (msg := to_message(channel_id, reply)) is not None:
                        yield msg

    @staticmethod
    def _pages(method: Callable[..., Any], **kwargs: Any) -> Iterator[Mapping[str, Any]]:
        """All `messages` across a cursor-paginated conversations.* call."""
        cursor: str | None = None
        while True:
            response = method(**kwargs, limit=200, **({"cursor": cursor} if cursor else {}))
            yield from response.get("messages") or []
            cursor = (response.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                return

    def post(self, channel_id: str, text: str, thread_id: str | None = None) -> None:
        self.client.chat_postMessage(channel=channel_id, text=text, thread_ts=thread_id)

    def display_name(self, user_id: str) -> str:
        """Display name → real name → username → the id. Cached; never raises."""
        if user_id in self._names:
            return self._names[user_id]
        try:
            user = self.client.users_info(user=user_id)["user"]
        except Exception:
            log.warning("Couldn't look up Slack user %s; showing the id", user_id, exc_info=True)
            return user_id  # not cached: retry next time
        profile = user.get("profile") or {}
        name = profile.get("display_name") or profile.get("real_name") or user.get("real_name") or user.get("name")
        self._names[user_id] = name or user_id
        return self._names[user_id]

    # ── live events ──

    def build_app(self, handler: ChatHandler) -> App:
        """A Bolt app wired to `handler`. Authorisation reuses the startup auth.test result."""
        app = App(client=self.client, authorize=lambda **_: self._auth)

        @app.event("message")
        def on_message(event: dict[str, Any]) -> None:
            self._safely(self.handle_message_event, handler, event)

        @app.event("app_mention")
        def on_mention(event: dict[str, Any]) -> None:
            self._safely(self.handle_mention, handler, event)

        @app.command("/leaderboard")
        def on_command(ack: Callable[[], None], command: dict[str, Any], respond: Callable[..., Any]) -> None:
            ack()  # within Slack's 3-second limit, before doing any work
            self._safely(self.handle_command, handler, command, respond)

        return app

    def run(self, handler: ChatHandler) -> None:
        """Connect over Socket Mode and dispatch events to `handler` until stopped. Blocks."""
        SocketModeHandler(self.build_app(handler), self._app_token, proxy=self._proxy).start()

    def handle_message_event(self, handler: ChatHandler, event: Mapping[str, Any]) -> None:
        """New messages and edits → `on_message`; deletions → `on_message_deleted`."""
        channel = event.get("channel", "")
        subtype = event.get("subtype")
        if subtype == "message_deleted":
            handler.on_message_deleted(self.platform, channel, event["deleted_ts"])
            return
        raw = event.get("message") if subtype == "message_changed" else event
        if raw and (msg := to_message(channel, raw)) is not None:
            handler.on_message(msg)

    def handle_mention(self, handler: ChatHandler, event: Mapping[str, Any]) -> None:
        """`@leaderboard weekly` → the reply, in a thread under the mention."""
        text = re.sub(rf"<@{re.escape(self.bot_user_id)}(\|[^>]*)?>", " ", event.get("text") or "")
        reply = handler.on_command(normalize_text(text).strip())
        self.post(event["channel"], reply, thread_id=event.get("thread_ts") or event["ts"])

    def handle_command(self, handler: ChatHandler, command: Mapping[str, Any], respond: Callable[..., Any]) -> None:
        """`/leaderboard weekly` → the reply, visible to the whole channel."""
        reply = handler.on_command(normalize_text(command.get("text") or "").strip())
        respond(text=reply, response_type="in_channel")

    @staticmethod
    def _safely(func: Callable[..., None], *args: Any) -> None:
        """One bad event must never take down the socket."""
        try:
            func(*args)
        except Exception:
            log.exception("Error handling a Slack event in %s", func.__name__)
