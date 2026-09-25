"""Phase 6 item 9 / DoD: STT word-error-rate benchmark on an automotive sample.

Honesty note (read before trusting these numbers): there is no physical microphone or human
speaker available in this environment, so the "30 self-recorded automotive utterances" the
plan describes are not literal human recordings here. This script instead synthesizes 30 real
automotive customer utterances with Kokoro TTS (a real, independent model from the STT model
under test -- not a circular "whisper transcribing whisper" setup) and runs the real
faster-whisper small.en model against that real audio, computing WER against the known ground
truth with jiwer. That is a legitimate, reproducible proxy for STT accuracy on this domain's
vocabulary, but it is optimistic relative to real human speech (no accent variation,
disfluency, background noise, or mic quality artifacts) -- treat the number as a ceiling, not
a guarantee, on real caller audio. The CallCenterEN benchmark named in the plan (arXiv
2507.02958) was not run: it isn't available through a pip-installable or directly downloadable
source from this environment, and fabricating results for a dataset never actually loaded
would defeat the purpose of measuring anything. This is a documented gap, not a silent one.

Usage: .venv/Scripts/python.exe scripts/voice_wer_benchmark.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

AUTOMOTIVE_UTTERANCES = [
    "I need to book an oil change for my 2019 Honda Civic",
    "Does my 2020 Toyota Camry have any open recalls",
    "I'd like a tire rotation next Tuesday morning",
    "Can you check for complaints on a 2021 Ford F-150",
    "My brakes are making a grinding noise",
    "What's the cost of a sixty thousand mile service",
    "I need to reschedule my appointment for next Friday",
    "My reference code is MRD-482913",
    "The phone number on file ends in four five one two",
    "Is there a recall on the Takata airbag inflator",
    "I want to cancel my appointment tomorrow",
    "Can I get a quote for brake pad replacement",
    "My check engine light just came on",
    "What time does the Riverside location open on Saturday",
    "I have a 2018 Toyota Corolla with a hundred thousand miles",
    "The technician said my alignment needs adjustment",
    "Is a battery replacement covered under warranty",
    "I smell something burning near the engine",
    "Can you look up my VIN 4T1BF1FK5CU123456",
    "I'd like an oil change and tire rotation together",
    "What's included in the sixty thousand mile service",
    "My airbag warning light stays on",
    "I need a same day appointment if possible",
    "The steering wheel shakes at highway speed",
    "Can I bring in my Honda Civic for a recall repair",
    "How long does a brake inspection usually take",
    "I'd like to speak with a service advisor",
    "My tire pressure sensor keeps triggering",
    "Please confirm my appointment for next Monday at nine thirty",
    "The transmission is slipping when I accelerate",
]


def synth_16khz_pcm(text: str) -> bytes:
    from kokoro_onnx import Kokoro

    from app.services.voice.tts import DEFAULT_VOICE, MODEL_PATH, VOICES_PATH

    engine = synth_16khz_pcm._engine
    if engine is None:
        engine = Kokoro(str(MODEL_PATH), str(VOICES_PATH))
        synth_16khz_pcm._engine = engine

    samples, sr = engine.create(text, voice=DEFAULT_VOICE, speed=1.0, lang="en-us")
    if sr != 16000:
        n_out = int(len(samples) * 16000 / sr)
        samples = np.interp(np.linspace(0, len(samples), n_out, endpoint=False), np.arange(len(samples)), samples)
    return (np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes()


synth_16khz_pcm._engine = None


NORMALIZE = None


def _normalizer():
    global NORMALIZE
    if NORMALIZE is None:
        import jiwer

        NORMALIZE = jiwer.Compose(
            [
                jiwer.ExpandCommonEnglishContractions(),
                jiwer.RemovePunctuation(),
                jiwer.ToLowerCase(),
                jiwer.RemoveMultipleSpaces(),
                jiwer.Strip(),
                jiwer.ReduceToListOfListOfWords(),
            ]
        )
    return NORMALIZE


def main() -> None:
    import jiwer

    from app.services.voice import stt

    stt.warm_up()

    references: list[str] = []
    hypotheses: list[str] = []
    per_utterance_wer: list[tuple[str, str, float, float]] = []
    latencies: list[float] = []

    for text in AUTOMOTIVE_UTTERANCES:
        pcm = synth_16khz_pcm(text)
        t0 = time.monotonic()
        hyp = stt.transcribe_pcm16(pcm)
        latencies.append(time.monotonic() - t0)
        references.append(text)
        hypotheses.append(hyp)
        raw_wer = jiwer.wer(text.lower(), hyp.lower())
        norm_wer = jiwer.wer(text, hyp, reference_transform=_normalizer(), hypothesis_transform=_normalizer())
        per_utterance_wer.append((text, hyp, raw_wer, norm_wer))

    raw_overall = jiwer.wer([r.lower() for r in references], [h.lower() for h in hypotheses])
    norm_overall = jiwer.wer(references, hypotheses, reference_transform=_normalizer(), hypothesis_transform=_normalizer())

    print(f"\n{'=' * 78}")
    print(f"Raw WER (naive string compare) on {len(AUTOMOTIVE_UTTERANCES)} utterances: {raw_overall * 100:.2f}%")
    print(f"Normalized WER (case/punctuation-insensitive, the standard ASR convention): {norm_overall * 100:.2f}%")
    print(f"Mean STT latency (4 cpu_threads): {sum(latencies) / len(latencies):.3f}s")
    print(f"{'=' * 78}\n")
    for text, hyp, raw_wer, norm_wer in per_utterance_wer:
        flag = "  " if norm_wer < 0.12 else "**"
        print(f"{flag} raw={raw_wer * 100:5.1f}%  norm={norm_wer * 100:5.1f}%  ref={text!r}")
        if hyp.lower().strip(".,!? ") != text.lower().strip(".,!? "):
            print(f"      hyp={hyp!r}")


if __name__ == "__main__":
    main()
