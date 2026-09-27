from __future__ import annotations

import logging
import ssl
from datetime import UTC, datetime

import pytest
from slack_sdk import WebClient
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


class StubClient(WebClient):
    """A WebClient (Bolt insists on the real type) whose API methods never touch the network."""

    def __init__(self, *, auth: object = None, users: dict | None = None) -> None:
        super().__init__(token="xoxb-test")
        self.retry_handlers = []
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


# ── fetch_history (T-503) ──


class HistoryClient(StubClient):
    def __init__(self, history_pages: list[list[dict]], replies: dict[str, list[list[dict]]]) -> None:
        super().__init__()
        self.history_pages, self.replies = history_pages, replies
        self.requests: list[tuple[str, dict]] = []

    def _page(self, pages: list[list[dict]], kw: dict) -> dict:
        index = int(kw.get("cursor", "0"))
        more = index + 1 < len(pages)
        return {"messages": pages[index], "response_metadata": {"next_cursor": str(index + 1) if more else ""}}

    def conversations_history(self, **kw: object) -> dict:
        self.requests.append(("history", kw))
        return self._page(self.history_pages, kw)

    def conversations_replies(self, **kw: object) -> dict:
        self.requests.append(("replies", kw))
        return self._page(self.replies[kw["ts"]], kw)  # type: ignore[index]


def msg_raw(ts: str, text: str = "hi", **kw: object) -> dict:
    return {"type": "message", "user": "U1", "ts": ts, "text": text} | kw


def test_fetch_history_pages_and_includes_thread_replies() -> None:
    client = HistoryClient(
        history_pages=[
            [msg_raw("5.0", "newest"), msg_raw("4.0", "parent", reply_count=2, thread_ts="4.0")],
            [msg_raw("3.0", "old"), msg_raw("2.5", subtype="channel_join")],
        ],
        replies={"4.0": [[msg_raw("4.0", "parent", thread_ts="4.0"), msg_raw("4.1", "reply 1", thread_ts="4.0")],
                         [msg_raw("4.2", "reply 2", thread_ts="4.0")]]},
    )
    oldest = datetime(1970, 1, 1, 0, 0, 1, tzinfo=UTC)
    messages = list(port(client).fetch_history("C1", oldest))
    assert [(m.message_id, m.text, m.thread_id) for m in messages] == [
        ("5.0", "newest", None), ("4.0", "parent", None), ("4.1", "reply 1", "4.0"),
        ("4.2", "reply 2", "4.0"), ("3.0", "old", None),
    ]
    history_calls = [kw for kind, kw in client.requests if kind == "history"]
    assert history_calls[0] == {"channel": "C1", "oldest": "1.000000", "limit": 200}
    assert history_calls[1]["cursor"] == "1"
    assert [kw["ts"] for kind, kw in client.requests if kind == "replies"] == ["4.0", "4.0"]


def test_fetch_history_empty_channel() -> None:
    client = HistoryClient(history_pages=[[]], replies={})
    assert list(port(client).fetch_history("C1", datetime(2026, 9, 1, tzinfo=UTC))) == []


# ── live events, mentions, /leaderboard (T-504) ──


class RecordingHandler:
    def __init__(self, reply: str = "the board", fail: bool = False) -> None:
        self.messages: list = []
        self.deleted: list = []
        self.commands: list[str] = []
        self.reply, self.fail = reply, fail

    def on_message(self, msg) -> None:  # noqa: ANN001
        if self.fail:
            raise RuntimeError("handler bug")
        self.messages.append(msg)

    def on_message_deleted(self, platform: str, channel_id: str, message_id: str) -> None:
        self.deleted.append((platform, channel_id, message_id))

    def on_command(self, text: str) -> str:
        self.commands.append(text)
        return self.reply


def test_new_message_event() -> None:
    handler = RecordingHandler()
    port().handle_message_event(handler, msg_raw("1.0", "Krillion #72", channel="C1"))
    (msg,) = handler.messages
    assert (msg.channel_id, msg.message_id, msg.text) == ("C1", "1.0", "Krillion #72")


def test_edit_event_uses_the_new_text() -> None:
    handler = RecordingHandler()
    event = {"type": "message", "subtype": "message_changed", "channel": "C1",
             "message": msg_raw("1.0", "Krillion #72 (fixed)"), "previous_message": msg_raw("1.0", "Krillion #72")}
    port().handle_message_event(handler, event)
    assert [m.text for m in handler.messages] == ["Krillion #72 (fixed)"]


def test_delete_event() -> None:
    handler = RecordingHandler()
    port().handle_message_event(handler, {"type": "message", "subtype": "message_deleted", "channel": "C1",
                                          "deleted_ts": "1.0"})
    assert handler.deleted == [("slack", "C1", "1.0")] and handler.messages == []


def test_system_and_bot_events_are_ignored() -> None:
    handler = RecordingHandler()
    port().handle_message_event(handler, msg_raw("1.0", subtype="channel_join", channel="C1"))
    port().handle_message_event(handler, msg_raw("2.0", bot_id="B1", channel="C1"))
    assert handler.messages == []


def test_mention_strips_the_bot_and_replies_in_a_thread() -> None:
    client, handler = StubClient(), RecordingHandler("🥇 Alice")
    port(client).handle_mention(handler, {"type": "app_mention", "channel": "C1", "ts": "5.0", "user": "U1",
                                          "text": "<@UBOT> weekly <http://maptap.gg|maptap>"})
    assert handler.commands == ["weekly maptap"]
    assert client.posted == [{"channel": "C1", "text": "🥇 Alice", "thread_ts": "5.0"}]


def test_mention_inside_a_thread_replies_in_that_thread() -> None:
    client = StubClient()
    port(client).handle_mention(RecordingHandler(), {"channel": "C1", "ts": "6.0", "thread_ts": "4.0",
                                                     "text": "<@UBOT|leaderboard> help"})
    assert client.posted[0]["thread_ts"] == "4.0"


def test_slash_command_responds_in_channel() -> None:
    responses: list[dict] = []
    handler = RecordingHandler("the board")
    port().handle_command(handler, {"command": "/leaderboard", "text": " weekly  maptap "},
                          lambda **kw: responses.append(kw))
    assert handler.commands == ["weekly  maptap"]  # passed through as typed; the parser splits on whitespace
    assert responses == [{"text": "the board", "response_type": "in_channel"}]


def test_handler_exceptions_are_logged_not_raised(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR):
        SlackPort._safely(port().handle_message_event, RecordingHandler(fail=True), msg_raw("1.0", channel="C1"))
    assert "Error handling a Slack event in handle_message_event" in caplog.text


# ── the wired Bolt app, dispatched offline ──


def dispatch(app, event: dict) -> None:  # noqa: ANN001
    import json
    import time

    from slack_bolt.request import BoltRequest

    body = {"type": "event_callback", "team_id": "T1", "event": event, "event_id": "Ev1", "event_time": 1}
    response = app.dispatch(BoltRequest(body=json.dumps(body), mode="socket_mode"))
    assert response.status == 200
    time.sleep(0.2)  # Bolt runs listeners on a worker thread after acknowledging


def test_bolt_app_routes_message_events() -> None:
    handler, slack = RecordingHandler(), port()
    dispatch(slack.build_app(handler), msg_raw("1.0", "Krillion #72", channel="C1"))
    assert [m.text for m in handler.messages] == ["Krillion #72"]


def test_bolt_app_routes_mentions() -> None:
    client, handler = StubClient(), RecordingHandler("reply")
    slack = port(client)
    dispatch(slack.build_app(handler), {"type": "app_mention", "channel": "C1", "ts": "5.0", "user": "U1",
                                        "text": "<@UBOT> help"})
    assert handler.commands == ["help"]
    assert client.posted == [{"channel": "C1", "text": "reply", "thread_ts": "5.0"}]


def test_run_starts_socket_mode_with_the_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    started: dict = {}

    class FakeSocketMode:
        def __init__(self, app, app_token: str, proxy: str | None = None) -> None:  # noqa: ANN001
            started.update(app=app, token=app_token, proxy=proxy)

        def start(self) -> None:
            started["started"] = True

    monkeypatch.setattr(slack_module, "SocketModeHandler", FakeSocketMode)
    slack = SlackPort("xoxb", "xapp-123", proxy="http://proxy:8080", client=StubClient())  # type: ignore[arg-type]
    slack.run(RecordingHandler())
    assert (started["token"], started["proxy"], started["started"]) == ("xapp-123", "http://proxy:8080", True)
