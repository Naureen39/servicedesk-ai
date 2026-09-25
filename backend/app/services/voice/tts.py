"""TTS with Kokoro (Phase 6 item 5): one professional voice (`af_heart`, American English
female), splitting the response by sentence so the session layer can stream and start
playback on the first sentence's audio well before the rest of a multi-sentence reply has
synthesized.

Piper fallback: not wired up in this phase -- Kokoro's CPU latency (see docs/voice-benchmark.md)
already meets the templated-response budget, so there was nothing forcing the extra fallback
engine's install/model footprint before a real gap in coverage showed up. If Kokoro fails to
load or throws mid-synthesis, `synthesize_sentence` returns `None` and the voice session sends
the caption text only, which the browser's `speechSynthesis` (the plan's documented
last-resort) speaks client-side -- so the fallback chain's final rung is already live even
though the middle one (Piper) isn't.
"""

from __future__ import annotations

import io
import re
import threading
from pathlib import Path

MODEL_PATH = Path(__file__).resolve().parents[4] / "models" / "tts_kokoro" / "kokoro-v1.0.onnx"
VOICES_PATH = Path(__file__).resolve().parents[4] / "models" / "tts_kokoro" / "voices-v1.0.bin"
DEFAULT_VOICE = "af_heart"
SAMPLE_RATE = 24000

_engine = None
_lock = threading.Lock()

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENTENCE_SPLIT_RE.split(text.strip()) if p.strip()]
    return parts or ([text.strip()] if text.strip() else [])


def _load():
    global _engine
    if _engine is not None:
        return _engine
    with _lock:
        if _engine is not None:
            return _engine
        if not MODEL_PATH.exists() or not VOICES_PATH.exists():
            return None
        from kokoro_onnx import Kokoro

        _engine = Kokoro(str(MODEL_PATH), str(VOICES_PATH))
        return _engine


def is_loaded() -> bool:
    return _engine is not None


def warm_up() -> None:
    engine = _load()
    if engine is not None:
        engine.create("warm up", voice=DEFAULT_VOICE, speed=1.0, lang="en-us")


def synthesize_sentence(text: str, voice: str = DEFAULT_VOICE) -> bytes | None:
    """Returns 16-bit PCM WAV bytes for one sentence, or None if the TTS engine is
    unavailable (caller falls back to browser `speechSynthesis` on the caption text)."""
    engine = _load()
    if engine is None:
        return None
    try:
        samples, sr = engine.create(text, voice=voice, speed=1.0, lang="en-us")
    except Exception:
        return None

    import soundfile as sf

    buf = io.BytesIO()
    sf.write(buf, samples, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()
