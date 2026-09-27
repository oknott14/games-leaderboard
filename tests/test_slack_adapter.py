from __future__ import annotations

import logging
import ssl
from datetime import UTC, datetime

import pytest
from slack_sdk.errors import SlackApiError
from slack_sdk.http_retry.builtin_handlers import RateLimitErrorRetryHandler

from leaderboard.adapters import slack as slack_module
from leaderboard.adapters.slack import SlackPort, normalize_text, to_message


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


# ── SlackPort construction, post, display_name (T-502) ──


class StubClient:
    """Just enough of slack_sdk.WebClient."""

    def __init__(self, *, auth: object = None, users: dict | None = None) -> None:
        self.retry_handlers: list = []
        self.auth = auth if auth is not None else {"ok": True, "user_id": "UBOT", "team": "Acme", "user": "leaderboard"}
        self.users = users or {}
        self.posted: list[dict] = []
        self.user_lookups: list[str] = []
        self.calls: list[tuple[str, dict]] = []

    def auth_test(self) -> dict:
        if isinstance(self.auth, Exception):
            raise self.auth
        return self.auth  # type: ignore[return-value]

    def chat_postMessage(self, **kw: object) -> dict:  # noqa: N802
        self.posted.append(kw)
        return {"ok": True}

    def users_info(self, *, user: str) -> dict:
        self.user_lookups.append(user)
        found = self.users[user]
        if isinstance(found, Exception):
            raise found
        return {"ok": True, "user": found}


def port(client: StubClient | None = None) -> SlackPort:
    return SlackPort("xoxb-test", "xapp-test", client=client or StubClient())  # type: ignore[arg-type]


def test_construction_checks_auth_and_adds_retry(caplog: pytest.LogCaptureFixture) -> None:
    client = StubClient()
    with caplog.at_level(logging.INFO):
        slack = port(client)
    assert slack.bot_user_id == "UBOT" and slack.platform == "slack"
    assert any(isinstance(h, RateLimitErrorRetryHandler) and h.max_retry_count == 5 for h in client.retry_handlers)
    assert "Slack auth OK: Acme as leaderboard" in caplog.text


def test_bad_token_is_a_clear_error() -> None:
    error = SlackApiError("invalid_auth", {"ok": False, "error": "invalid_auth"})
    with pytest.raises(RuntimeError, match=r"Slack auth failed \(invalid_auth\); check SLACK_BOT_TOKEN"):
        port(StubClient(auth=error))


def test_network_error_points_at_proxy_settings() -> None:
    with pytest.raises(RuntimeError, match="HTTPS_PROXY and/or SSL_CERT_FILE"):
        port(StubClient(auth=OSError("CERTIFICATE_VERIFY_FAILED")))


def test_real_client_gets_proxy_and_ssl(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict = {}

    class FakeWebClient(StubClient):
        def __init__(self, **kw: object) -> None:
            super().__init__()
            seen.update(kw)

    monkeypatch.setattr(slack_module, "WebClient", FakeWebClient)
    context = ssl.create_default_context()
    SlackPort("xoxb-1", "xapp-1", proxy="http://proxy:8080", ssl_context=context)
    assert seen == {"token": "xoxb-1", "proxy": "http://proxy:8080", "ssl": context}


def test_post() -> None:
    client = StubClient()
    port(client).post("C1", "hello", thread_id="1.0")
    port(client).post("C1", "top level")
    assert client.posted == [{"channel": "C1", "text": "hello", "thread_ts": "1.0"},
                             {"channel": "C1", "text": "top level", "thread_ts": None}]


@pytest.mark.parametrize(
    ("user", "expected"),
    [
        ({"profile": {"display_name": "Ali", "real_name": "Alice Smith"}, "name": "alice"}, "Ali"),
        ({"profile": {"display_name": "", "real_name": "Alice Smith"}, "name": "alice"}, "Alice Smith"),
        ({"profile": {}, "real_name": "Alice S", "name": "alice"}, "Alice S"),
        ({"name": "alice"}, "alice"),
        ({}, "U1"),
    ],
)
def test_display_name_fallbacks(user: dict, expected: str) -> None:
    assert port(StubClient(users={"U1": user})).display_name("U1") == expected


def test_display_name_is_cached() -> None:
    client = StubClient(users={"U1": {"profile": {"display_name": "Ali"}}})
    slack = port(client)
    assert slack.display_name("U1") == slack.display_name("U1") == "Ali"
    assert client.user_lookups == ["U1"]


def test_display_name_api_error_returns_id_and_retries_later(caplog: pytest.LogCaptureFixture) -> None:
    client = StubClient(users={"U1": SlackApiError("user_not_found", {"ok": False, "error": "user_not_found"})})
    slack = port(client)
    with caplog.at_level(logging.WARNING):
        assert slack.display_name("U1") == "U1"
    client.users["U1"] = {"profile": {"display_name": "Ali"}}
    assert slack.display_name("U1") == "Ali"
    assert "Couldn't look up Slack user U1" in caplog.text


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("<!subteam^S1>", "@S1"), ("<!subteam^S1|@team>", "@team"), ("<!subteam^S1|team>", "@team"),
     ("<!here|here>", "@here"), ("<!everyone>", "@everyone"), ("<!date^1392734382^{date}|Feb 18>", "Feb 18")],
)
def test_special_mentions(raw: str, expected: str) -> None:
    assert normalize_text(raw) == expected
