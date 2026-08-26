from datetime import datetime, timezone
from pathlib import Path

from app.state import PollState, is_newer_than_state, parse_graph_datetime
from app.teams.parse import graph_message_to_incoming, strip_html


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
