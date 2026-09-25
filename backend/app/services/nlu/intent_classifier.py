"""Local intent classifier (Section 4.1): Logistic Regression on bge-small embeddings,
calibrated for a usable confidence score, loaded as a process-wide singleton. Zero LLM tokens.
"""

from __future__ import annotations

import threading
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parents[4] / "models" / "intent_clf"
MODEL_PATH = MODELS_DIR / "model.joblib"

_model = None
_labels: list[str] | None = None
_lock = threading.Lock()


class IntentClassifierNotTrained(RuntimeError):
    pass


def _load() -> None:
    global _model, _labels
    if _model is not None:
        return
    with _lock:
        if _model is not None:
            return
        if not MODEL_PATH.exists():
            raise IntentClassifierNotTrained(
                f"No trained model at {MODEL_PATH}; run `python scripts/train_intent_classifier.py` first"
            )
        import joblib

        bundle = joblib.load(MODEL_PATH)
        _model = bundle["model"]
        # Read the fitted order directly from the estimator rather than the separately
        # stored `labels` list, so a predict_proba() column can never be paired with the
        # wrong intent name if the two orderings ever drift.
        _labels = list(_model.classes_)


def is_loaded() -> bool:
    return _model is not None


def predict_intent(text: str) -> tuple[str, float]:
    """Returns (top_intent, calibrated_probability)."""
    _load()
    from app.services.embeddings import embed_passages

    vector = embed_passages([text])[0]
    probabilities = _model.predict_proba([vector])[0]
    best_index = probabilities.argmax()
    return _labels[best_index], float(probabilities[best_index])


def predict_intent_topk(text: str, k: int = 3) -> list[tuple[str, float]]:
    _load()
    from app.services.embeddings import embed_passages

    vector = embed_passages([text])[0]
    probabilities = _model.predict_proba([vector])[0]
    ranked = sorted(zip(_labels, probabilities, strict=True), key=lambda p: p[1], reverse=True)
    return [(intent, float(p)) for intent, p in ranked[:k]]
