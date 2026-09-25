"""Phase 6: real STT/TTS round-trip (no mocks -- actual faster-whisper and Kokoro models),
and real dialog-manager tests for the voice-only phone read-back confirmation gate, including
the regression this session found: a confirmation answer like "yes that is correct" must not
be hijacked by the global-interrupt check even when the intent classifier scores it as
something like "goodbye".
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import numpy as np
from sqlalchemy import text

from app.db.base import async_session_factory
from app.db.models.assistant import Conversation
from app.services.dialog.manager import handle_turn
from app.services.voice import stt, tts

# asyncio_mode = "auto" (pyproject.toml) detects the async tests below on its own; this file
# mixes them with plain sync tests, so no module-level `pytestmark` here (unlike files that
# are all-async), which would incorrectly flag the sync ones.


def test_tts_synthesizes_real_audio_for_a_short_sentence():
    audio = tts.synthesize_sentence("Your appointment is confirmed.")
    assert audio is not None
    assert audio[:4] == b"RIFF"  # real WAV header
    assert len(audio) > 1000


def test_stt_transcribes_synthesized_speech_round_trip():
    """No audio recording available in CI -- so, like the rest of this project's real-data
    discipline, this proves the real pipeline end to end using real TTS-synthesized audio fed
    through the real STT model, not a mock."""
    wav_bytes = tts.synthesize_sentence("I need to book an oil change for my Honda Civic.")
    assert wav_bytes is not None

    import io

    import soundfile as sf

    samples, sr = sf.read(io.BytesIO(wav_bytes), dtype="float32")
    if sr != 16000:
        n_out = int(len(samples) * 16000 / sr)
        samples = np.interp(np.linspace(0, len(samples), n_out, endpoint=False), np.arange(len(samples)), samples)
    pcm16 = (np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes()

    text_out = stt.transcribe_pcm16(pcm16)
    lowered = text_out.lower()
    assert "oil change" in lowered
    assert "civic" in lowered


async def _fresh_conversation() -> Conversation:
    conversation_id = f"CONV-{uuid.uuid4().hex[:10].upper()}"
    async with async_session_factory() as db:
        conv = Conversation(conversation_id=conversation_id, channel="voice", started_at=datetime.now(UTC), location_id=1)
        db.add(conv)
        await db.commit()
    return conv


async def test_voice_channel_confirms_phone_by_readback_before_booking():
    conv = await _fresh_conversation()
    async with async_session_factory() as db:
        turns = [
            "I need to book an oil change",
            "2020 Toyota Camry",
            "next Tuesday",
            "Voice Test Customer",
            "614-555-0188",
        ]
        result = None
        for message in turns:
            result = await handle_turn(db, conv, message, None, channel="voice")

        assert "ending in" in result.text.lower()
        assert "0 1 8 8" in result.text

        # The confirmation regression this session found: a short affirmative answer must
        # reach the confirm-phone handler, not get hijacked as a global-interrupt intent.
        result = await handle_turn(db, conv, "yes that is correct", None, channel="voice")
        assert "available times" in result.text.lower() or "slot" in result.text.lower()
        assert result.escalate_reason is None


async def test_voice_channel_reprompts_phone_on_no_confirmation():
    conv = await _fresh_conversation()
    async with async_session_factory() as db:
        for message in ["I need to book an oil change", "2020 Toyota Camry", "next Tuesday", "Voice Test Customer", "614-555-0199"]:
            result = await handle_turn(db, conv, message, None, channel="voice")
        assert "ending in" in result.text.lower()

        result = await handle_turn(db, conv, "no that's wrong", None, channel="voice")
        assert "phone number" in result.text.lower()

        result = await handle_turn(db, conv, "614-555-0100", None, channel="voice")
        assert "ending in" in result.text.lower()
        assert "0 1 0 0" in result.text


async def test_voice_channel_cleanup():
    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM customers WHERE first_name = 'Voice' AND last_name LIKE 'Test%'"))
        await db.commit()
