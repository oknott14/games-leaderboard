"""Slack adapter (Bolt + Socket Mode). The only module that imports the Slack SDK.

See docs/plan/05-slack-adapter.md.
"""

from __future__ import annotations

import logging
import re
import ssl
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

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
            return label or f"@{target[1:].split('^')[0]}"
        if label:
            return label
        return target.removeprefix("mailto:")

    return _ANGLE.sub(replace, text).replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


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
        log.info("Slack auth OK: %s as %s", auth.get("team"), auth.get("user"))

    def fetch_history(self, channel_id: str, oldest: datetime) -> Iterator[ChatMessage]:
        raise NotImplementedError  # T-503

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

    def run(self, handler: ChatHandler) -> None:
        raise NotImplementedError  # T-504
