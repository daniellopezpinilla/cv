from app.state import (
    PollState,
    ensure_watching_since,
    is_after_watching_since,
    is_chat_active_since,
    is_newer_than_state,
    parse_graph_datetime,
)
from app.teams.parse import graph_message_to_incoming, is_user_chat_message, strip_html


def test_strip_html() -> None:
    assert "hola mundo" in strip_html("<p>hola <b>mundo</b></p>").lower()


def test_graph_message_to_incoming_user() -> None:
    raw = {
        "id": "msg-1",
        "createdDateTime": "2026-03-20T23:10:00.000Z",
        "body": {"contentType": "html", "content": "<p>Necesito ayuda</p>"},
        "from": {"user": {"id": "u1", "displayName": "Ana"}},
    }
    msg = graph_message_to_incoming(raw)
    assert msg.id == "msg-1"
    assert "Necesito ayuda" in msg.text
    assert msg.from_name == "Ana"
    assert msg.is_from_app is False


def test_graph_message_to_incoming_app() -> None:
    raw = {
        "id": "msg-2",
        "createdDateTime": "2026-03-20T23:11:00.000Z",
        "body": {"contentType": "text", "content": "auto"},
        "from": {"application": {"id": "app1", "displayName": "Bot"}},
    }
    msg = graph_message_to_incoming(raw)
    assert msg.is_from_app is True


def test_is_newer_than_state() -> None:
    state = PollState(
        last_message_id="a",
        last_created="2026-03-20T23:00:00.000Z",
        bootstrapped=True,
    )
    assert is_newer_than_state(
        message_id="b",
        created="2026-03-20T23:05:00.000Z",
        state=state,
    )
    assert not is_newer_than_state(
        message_id="a",
        created="2026-03-20T22:00:00.000Z",
        state=state,
    )


def test_parse_graph_datetime() -> None:
    dt = parse_graph_datetime("2026-03-20T23:00:00.000Z")
    assert dt is not None
    assert dt.tzinfo is not None or dt.utcoffset() is not None


def test_ensure_watching_since_sets_once() -> None:
    state = PollState()
    updated = ensure_watching_since(state)
    assert updated.watching_since
    again = ensure_watching_since(updated)
    assert again.watching_since == updated.watching_since


def test_is_user_chat_message() -> None:
    assert is_user_chat_message({"messageType": "message"})
    assert not is_user_chat_message({"messageType": "systemEventMessage"})


def test_is_after_watching_since() -> None:
    since = "2026-08-27T14:00:00.000Z"
    assert is_after_watching_since("2026-08-27T14:01:00.000Z", since)
    assert not is_after_watching_since("2026-08-27T13:59:00.000Z", since)


def test_is_chat_active_since() -> None:
    since = "2026-08-27T14:00:00.000Z"
    active = {
        "lastMessagePreview": {"createdDateTime": "2026-08-27T15:00:00.000Z"},
    }
    inactive = {
        "lastMessagePreview": {"createdDateTime": "2026-08-27T10:00:00.000Z"},
    }
    stale_updated_only = {
        "lastUpdatedDateTime": "2026-08-27T10:00:00.000Z",
    }
    assert is_chat_active_since(active, since)
    assert not is_chat_active_since(inactive, since)
    assert is_chat_active_since(stale_updated_only, since)
