"""Slack adapter (Bolt + Socket Mode). The only module that imports the Slack SDK.

See docs/plan/05-slack-adapter.md.
"""

from __future__ import annotations

import re
import ssl
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from leaderboard.ports import ChatMessage

if TYPE_CHECKING:
    from leaderboard.ports import ChatHandler


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
    """Satisfies `ChatPort`."""

    platform = "slack"

    def __init__(
        self,
        bot_token: str,
        app_token: str,
        *,
        proxy: str | None = None,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        raise NotImplementedError  # T-502

    def fetch_history(self, channel_id: str, oldest: datetime) -> Iterator[ChatMessage]:
        raise NotImplementedError  # T-503

    def post(self, channel_id: str, text: str, thread_id: str | None = None) -> None:
        raise NotImplementedError  # T-502

    def display_name(self, user_id: str) -> str:
        raise NotImplementedError  # T-502

    def run(self, handler: ChatHandler) -> None:
        raise NotImplementedError  # T-504
