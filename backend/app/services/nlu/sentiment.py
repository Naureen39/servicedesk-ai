"""Sentiment scorer (Section 4.1): distilbert-base-uncased-finetuned-sst-2-english via ONNX
Runtime on CPU, used as an escalation signal (Section 4.3: "sentiment strongly negative on two
consecutive turns"). Exported to ONNX on first use via optimum and cached under
models/sentiment_onnx/ so subsequent process starts skip the export step.
"""

from __future__ import annotations

import threading
from pathlib import Path

MODEL_NAME = "distilbert-base-uncased-finetuned-sst-2-english"
MODELS_DIR = Path(__file__).resolve().parents[4] / "models" / "sentiment_onnx"

NEGATIVE_THRESHOLD = -0.85
"""Score below this counts as "strongly negative" for the escalation gate. SST-2 is a movie-
review classifier applied out of domain here, and its softmax is nearly always saturated near
+-1.0 even on neutral text, so a loose threshold (e.g. -0.5) misfires constantly on ordinary
service requests. -0.85 keeps the gate reserved for text that reads as clearly upset even
against this classifier's noisy baseline; see also manager.py, which skips sentiment scoring
entirely for narrow data-answer turns (phone, date, reference code) where it's both unreliable
and not meaningful."""

_model = None
_tokenizer = None
_lock = threading.Lock()


def _load() -> None:
    global _model, _tokenizer
    if _model is not None:
        return
    with _lock:
        if _model is not None:
            return
        from optimum.onnxruntime import ORTModelForSequenceClassification
        from transformers import AutoTokenizer

        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        already_exported = (MODELS_DIR / "model.onnx").exists()
        _model = ORTModelForSequenceClassification.from_pretrained(
            MODELS_DIR if already_exported else MODEL_NAME,
            export=not already_exported,
            provider="CPUExecutionProvider",
        )
        _tokenizer = AutoTokenizer.from_pretrained(MODELS_DIR if already_exported else MODEL_NAME)
        if not already_exported:
            _model.save_pretrained(MODELS_DIR)
            _tokenizer.save_pretrained(MODELS_DIR)


def is_loaded() -> bool:
    return _model is not None


def score_sentiment(text: str) -> float:
    """Returns a signed score in [-1, 1]: positive is positive sentiment, negative is
    negative sentiment (SST-2 is binary POSITIVE/NEGATIVE; the label's own confidence becomes
    the magnitude, so "very confidently negative" is closer to -1 than a borderline call)."""
    _load()
    import numpy as np

    inputs = _tokenizer(text, return_tensors="np", truncation=True, max_length=128)
    outputs = _model(**inputs)
    logits = outputs.logits[0]
    exp = np.exp(logits - logits.max())
    probs = exp / exp.sum()

    # id2label is {0: "NEGATIVE", 1: "POSITIVE"} for this checkpoint.
    id2label = _model.config.id2label
    negative_id = next(i for i, label in id2label.items() if label.upper().startswith("NEG"))
    positive_id = next(i for i, label in id2label.items() if label.upper().startswith("POS"))

    return float(probs[positive_id] - probs[negative_id])


def is_strongly_negative(text: str) -> bool:
    return score_sentiment(text) <= NEGATIVE_THRESHOLD
