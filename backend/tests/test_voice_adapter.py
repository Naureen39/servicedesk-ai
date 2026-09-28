"""Unit tests for VoiceAdapter (Section 4.7): text passthrough on the string path, real STT
on the bytes path (mocked here since the actual model is covered by test_voice_pipeline.py),
and the send() passthrough."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.channel.base import Response
from app.services.channel.voice import VoiceAdapter

pytestmark = pytest.mark.asyncio


async def test_receive_with_text_is_a_passthrough():
    adapter = VoiceAdapter()
    turn = await adapter.receive("how much is an oil change", "conv-1")
    assert turn.text == "how much is an oil change"
    assert turn.channel == "voice"
    assert turn.conversation_id == "conv-1"


async def test_receive_with_bytes_runs_stt():
    adapter = VoiceAdapter()
    with patch("app.services.channel.voice.transcribe_pcm16", return_value="book an appointment") as mock_stt:
        turn = await adapter.receive(b"\x00\x01\x02\x03", "conv-2")

    mock_stt.assert_called_once_with(b"\x00\x01\x02\x03")
    assert turn.text == "book an appointment"
    assert turn.channel == "voice"
    assert turn.conversation_id == "conv-2"


async def test_send_returns_response_text_unchanged():
    adapter = VoiceAdapter()
    result = await adapter.send(Response(text="your appointment is confirmed", escalated=False))
    assert result == "your appointment is confirmed"
