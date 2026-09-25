"""Manual real end-to-end smoke test for the Phase 6 voice pipeline: issues a real voice
session token against a running dev server, synthesizes a real spoken utterance with Kokoro,
sends it as real PCM16 audio over the real WS /voice/session, and prints every real server
event (transcript, reply text, audio chunk sizes) plus end-to-end timing.

Usage: BACKEND=http://localhost:8000 .venv/Scripts/python.exe scripts/voice_e2e_smoke.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time

import httpx
import numpy as np
import websockets

BACKEND = os.environ.get("BACKEND", "http://localhost:8000")
WS_BACKEND = BACKEND.replace("http", "ws")


def synth_utterance(text: str) -> bytes:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from kokoro_onnx import Kokoro

    from app.services.voice.tts import DEFAULT_VOICE, MODEL_PATH, VOICES_PATH

    k = Kokoro(str(MODEL_PATH), str(VOICES_PATH))
    samples, sr = k.create(text, voice=DEFAULT_VOICE, speed=1.0, lang="en-us")
    if sr != 16000:
        n_out = int(len(samples) * 16000 / sr)
        samples = np.interp(np.linspace(0, len(samples), n_out, endpoint=False), np.arange(len(samples)), samples)
    pcm16 = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    return pcm16.tobytes()


async def main() -> None:
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BACKEND}/api/v1/chat/session", params={"channel": "voice"})
        resp.raise_for_status()
        session = resp.json()
    print("session:", session["conversation_id"])

    utterances = [
        "I need to book an oil change for my 2019 Honda Civic",
        "next Tuesday",
        "Alicia Gomez",
        "6145550101",
        "yes that is correct",
        "the first one",
    ]

    async with websockets.connect(f"{WS_BACKEND}/api/v1/voice/session?token={session['session_token']}") as ws:
        for text in utterances:
            audio = synth_utterance(text)
            print(f"\n>>> sending {len(audio)} bytes of synthesized audio for: {text!r}")
            t0 = time.monotonic()
            await ws.send(audio)

            first_audio_at = None
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=30)
                elapsed = time.monotonic() - t0
                if isinstance(msg, bytes):
                    if first_audio_at is None:
                        first_audio_at = elapsed
                    print(f"    [t={elapsed:.3f}s] audio chunk, {len(msg)} bytes")
                    continue
                payload = json.loads(msg)
                print(f"    [t={elapsed:.3f}s]", payload)
                if payload.get("type") == "turn_complete":
                    break
            print(f"    total turn time: {time.monotonic() - t0:.3f}s")


if __name__ == "__main__":
    asyncio.run(main())
