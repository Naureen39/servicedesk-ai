"""Server-side STT with faster-whisper (Section 5/6, Phase 6 item 3): `small.en`, int8, greedy
decoding (`beam_size=1`), `vad_filter=True` as a second-pass safety net behind the client-side
VAD. An initial prompt seeded with common make/model/service vocabulary biases the decoder
toward automotive terms it would otherwise misrecognize (e.g. "F-150" vs "F one fifty").

Item 8: the raw PCM bytes handed to `transcribe_pcm16` are converted to a numpy float32 array
in memory, passed directly to the model (never written to disk), and go out of scope the
moment this function returns -- only the resulting transcript is ever persisted.
"""

from __future__ import annotations

import threading
from pathlib import Path

import numpy as np

MODEL_SIZE = "small.en"
MODELS_DIR = Path(__file__).resolve().parents[4] / "models" / "stt_whisper"
CPU_THREADS = 4
"""Matches the Phase 6 DoD's benchmark condition ("under 2.5 s on a 4-core CPU"); see
docs/voice-benchmark.md for the real measured numbers against this exact setting."""

INITIAL_PROMPT = (
    "Toyota Camry Corolla, Honda Civic, Ford F-150, oil change, tire rotation, brake pads, "
    "60k service, recall, VIN, appointment, reschedule, reference code."
)

_model = None
_lock = threading.Lock()


def _load():
    global _model
    if _model is not None:
        return _model
    with _lock:
        if _model is not None:
            return _model
        from faster_whisper import WhisperModel

        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        _model = WhisperModel(
            MODEL_SIZE, device="cpu", compute_type="int8", cpu_threads=CPU_THREADS, download_root=str(MODELS_DIR)
        )
        return _model


def is_loaded() -> bool:
    return _model is not None


def warm_up() -> None:
    """Called once at app startup so the first real customer utterance doesn't pay the
    model-load cost (Phase 6 DoD is about per-turn latency, not cold start)."""
    model = _load()
    silence = np.zeros(8000, dtype=np.float32)
    list(model.transcribe(silence, beam_size=1)[0])


def transcribe_pcm16(audio_bytes: bytes, sample_rate: int = 16000) -> str:
    """`audio_bytes` is raw little-endian 16-bit mono PCM, matching what the client's VAD
    sends over the WebSocket (Phase 6 item 2)."""
    if not audio_bytes:
        return ""
    model = _load()
    samples = np.frombuffer(audio_bytes, dtype="<i2").astype(np.float32) / 32768.0
    if sample_rate != 16000:
        raise ValueError(f"expected 16 kHz PCM, got sample_rate={sample_rate}")

    segments, _info = model.transcribe(
        samples,
        beam_size=1,
        vad_filter=True,
        condition_on_previous_text=False,
        initial_prompt=INITIAL_PROMPT,
        word_timestamps=False,
    )
    text = " ".join(s.text.strip() for s in segments).strip()
    del samples
    return text
