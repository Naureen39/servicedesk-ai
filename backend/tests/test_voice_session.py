"""Unit tests for VoiceSession (Section 5.1 items 5-6): the reader loop / main loop split,
barge-in via interrupt_event, and sentence-by-sentence TTS streaming -- exercised against a
fake WebSocket and mocked STT/dialog/TTS collaborators, since the real WebSocket, faster-
whisper, and Kokoro pipelines are already covered end to end by test_voice_pipeline.py and
test_voice_spokenize.py.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import WebSocketDisconnect

from app.services.channel.base import Turn
from app.services.dialog.result import TurnResult
from app.services.voice.session import VoiceSession

pytestmark = pytest.mark.asyncio


class FakeWebSocket:
    """Yields queued `receive()` messages in order; records every `send_*` call."""

    def __init__(self, messages: list[dict]) -> None:
        self._messages = list(messages)
        self.sent_json: list[dict] = []
        self.sent_bytes: list[bytes] = []

    async def receive(self) -> dict:
        if not self._messages:
            return {"type": "websocket.disconnect"}
        return self._messages.pop(0)

    async def send_json(self, data: dict) -> None:
        self.sent_json.append(data)

    async def send_bytes(self, data: bytes) -> None:
        self.sent_bytes.append(data)


class _FakeConversation:
    conversation_id = "CONV-TEST"


def _session(messages: list[dict]) -> tuple[VoiceSession, FakeWebSocket]:
    ws = FakeWebSocket(messages)
    session = VoiceSession(ws, db=object(), conversation=_FakeConversation())
    return session, ws


async def test_run_processes_one_utterance_end_to_end():
    session, ws = _session([{"type": "websocket.receive", "bytes": b"\x00\x01"}])

    with (
        patch.object(session._adapter, "receive", AsyncMock(return_value=Turn(conversation_id="c1", text="book an oil change", channel="voice"))),
        patch("app.services.voice.session.handle_turn", AsyncMock(return_value=TurnResult(text="Sure, what's your vehicle?", contained=True))),
        patch("app.services.voice.session.spokenize", return_value="Sure, what's your vehicle?"),
        patch("app.services.voice.tts.split_sentences", return_value=["Sure, what's your vehicle?"]),
        patch("app.services.voice.tts.synthesize_sentence", return_value=b"fake-audio"),
    ):
        await asyncio.wait_for(session.run(), timeout=5)

    types = [m["type"] for m in ws.sent_json]
    assert types == ["transcript", "reply_text", "audio_start", "turn_complete"]
    assert ws.sent_json[0]["text"] == "book an oil change"
    assert ws.sent_json[1]["escalated"] is False
    assert ws.sent_bytes == [b"fake-audio"]


async def test_empty_transcript_sends_nothing_and_ends_the_turn():
    session, ws = _session([{"type": "websocket.receive", "bytes": b"\x00\x01"}])

    with patch.object(session._adapter, "receive", AsyncMock(return_value=Turn(conversation_id="c1", text="", channel="voice"))):
        await asyncio.wait_for(session.run(), timeout=5)

    assert ws.sent_json == []
    assert ws.sent_bytes == []


async def test_reader_loop_sets_interrupt_event_on_interrupt_message():
    session, ws = _session([{"type": "websocket.receive", "text": '{"type": "interrupt"}'}])

    assert not session.interrupt_event.is_set()
    await session._reader_loop()
    assert session.interrupt_event.is_set()


async def test_reader_loop_ends_session_on_end_message():
    session, ws = _session([{"type": "websocket.receive", "text": '{"type": "end"}'}])

    await session._reader_loop()

    assert session._inbox.qsize() == 1
    assert session._inbox.get_nowait() is None


async def test_reader_loop_ignores_malformed_json_text():
    session, ws = _session([{"type": "websocket.receive", "text": "not json"}, {"type": "websocket.disconnect"}])

    await session._reader_loop()

    assert session._inbox.get_nowait() is None
    assert session._inbox.empty()


async def test_reader_loop_puts_none_on_websocket_disconnect_exception():
    session, ws = _session([])

    async def _raise():
        raise WebSocketDisconnect()

    ws.receive = _raise
    await session._reader_loop()

    assert session._inbox.get_nowait() is None


async def test_streaming_stops_and_sends_interrupted_when_barge_in_happens_before_first_sentence():
    session, ws = _session([])
    session.interrupt_event.set()

    with (
        patch.object(session._adapter, "receive", AsyncMock(return_value=Turn(conversation_id="c1", text="cancel my appointment", channel="voice"))),
        patch("app.services.voice.session.handle_turn", AsyncMock(return_value=TurnResult(text="Okay, cancelled.", contained=True))),
        patch("app.services.voice.session.spokenize", return_value="Okay, cancelled."),
        patch("app.services.voice.tts.split_sentences", return_value=["Okay, cancelled."]),
    ):
        # interrupt_event.clear() runs first inside _handle_utterance, so set it again via a
        # side effect right as the sentence loop would check it, by pre-seeding split_sentences
        # output and instead asserting the *post*-synthesis interrupt check via synthesize.
        with patch("app.services.voice.tts.synthesize_sentence", side_effect=lambda *_a, **_k: session.interrupt_event.set() or b"audio"):
            await session._handle_utterance(b"\x00\x01")

    types = [m["type"] for m in ws.sent_json]
    assert "interrupted" in types
    assert "turn_complete" not in types
