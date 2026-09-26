"""Slack adapter (Bolt + Socket Mode). The only module that imports the Slack SDK.

See docs/plan/05-slack-adapter.md.
"""

from __future__ import annotations

import ssl
from collections.abc import Iterator
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from leaderboard.ports import ChatHandler, ChatMessage


def normalize_text(text: str) -> str:
    """Turn Slack message markup (`<url|label>`, `&amp;`, …) into plain text."""
    raise NotImplementedError  # T-501


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
