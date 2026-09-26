"""Platform-neutral chat interfaces.

The core (service, commands, boards, scheduler) depends only on these types and never imports a
chat SDK. Each platform gets an adapter implementing `ChatPort` (see `leaderboard.adapters`).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class ChatMessage:
    platform: str  # e.g. "slack"
    channel_id: str
    message_id: str  # unique within the channel (Slack: ts)
    user_id: str
    text: str  # normalised plain text; normalising is the adapter's job
    posted_at: datetime  # tz-aware UTC
    thread_id: str | None = None


class ChatHandler(Protocol):
    """Receives chat events from an adapter. Implemented by `LeaderboardService`."""

    def on_message(self, msg: ChatMessage) -> None:
        """Handle a new or edited message (upsert)."""
        ...

    def on_message_deleted(self, platform: str, channel_id: str, message_id: str) -> None: ...

    def on_command(self, text: str) -> str:
        """Handle the text after a mention or slash command; return the reply."""
        ...


class ChatPort(Protocol):
    """A chat platform the bot can read from and post to."""

    platform: str

    def fetch_history(self, channel_id: str, oldest: datetime) -> Iterator[ChatMessage]: ...

    def post(self, channel_id: str, text: str, thread_id: str | None = None) -> None: ...

    def display_name(self, user_id: str) -> str:
        """Never raises; falls back to `user_id`."""
        ...

    def run(self, handler: ChatHandler) -> None:
        """Block, dispatching live events to `handler`."""
        ...
