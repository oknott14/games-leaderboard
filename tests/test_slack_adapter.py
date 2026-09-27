from __future__ import annotations

from datetime import UTC, datetime

import pytest

from leaderboard.adapters.slack import normalize_text, to_message


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("<http://www.maptap.gg|www.maptap.gg> September 24", "www.maptap.gg September 24"),
        ("<https://example.com>", "https://example.com"),
        ("<mailto:a@b.c|a@b.c>", "a@b.c"),
        ("<mailto:a@b.c>", "a@b.c"),
        ("<#C123|general>", "#general"),
        ("<#C123>", "#C123"),
        ("<@U123> nice one", "<@U123> nice one"),
        ("<@U123|alice>", "<@U123|alice>"),
        ("<!here> results", "@here results"),
        ("<!channel>", "@channel"),
        ("<!subteam^S123|@team>", "@team"),
        ("Tom &amp; Jerry &lt;3 &gt;_&lt;", "Tom & Jerry <3 >_<"),
        ("&lt;https://x|y&gt;", "<https://x|y>"),  # escaped brackets never become a link
        ("93:trophy: 88:fire:", "93:trophy: 88:fire:"),
        ("", ""),
    ],
)
def test_normalize_text(raw: str, expected: str) -> None:
    assert normalize_text(raw) == expected


def payload(**kw: object) -> dict:
    return {"type": "message", "user": "U1", "ts": "1727193600.000100", "text": "Krillion #72"} | kw


def test_plain_message() -> None:
    msg = to_message("C1", payload(text="<http://maptap.gg|maptap.gg> 862"))
    assert msg is not None
    assert (msg.platform, msg.channel_id, msg.message_id, msg.user_id) == ("slack", "C1", "1727193600.000100", "U1")
    assert msg.text == "maptap.gg 862"
    assert msg.posted_at == datetime(2024, 9, 24, 16, 0, 0, 100, tzinfo=UTC) and msg.posted_at.tzinfo is UTC
    assert msg.thread_id is None


@pytest.mark.parametrize("subtype", ["thread_broadcast", "file_share", "me_message"])
def test_kept_subtypes(subtype: str) -> None:
    assert to_message("C1", payload(subtype=subtype)) is not None


@pytest.mark.parametrize(
    "subtype", ["bot_message", "channel_join", "channel_leave", "channel_topic", "channel_purpose",
                "pinned_item", "message_changed", "message_deleted"],
)
def test_dropped_subtypes(subtype: str) -> None:
    assert to_message("C1", payload(subtype=subtype)) is None


def test_bot_posts_dropped() -> None:
    assert to_message("C1", payload(bot_id="B1")) is None


@pytest.mark.parametrize("missing", ["user", "ts"])
def test_requires_user_and_ts(missing: str) -> None:
    raw = payload()
    del raw[missing]
    assert to_message("C1", raw) is None


def test_thread_reply_has_thread_id_but_parent_does_not() -> None:
    reply = to_message("C1", payload(ts="2.0", thread_ts="1.0"))
    parent = to_message("C1", payload(ts="1.0", thread_ts="1.0"))
    assert reply is not None and reply.thread_id == "1.0"
    assert parent is not None and parent.thread_id is None


def test_missing_text_is_empty() -> None:
    msg = to_message("C1", payload(text=None))
    assert msg is not None and msg.text == ""
