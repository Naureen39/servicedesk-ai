"""Section 4.1: train the local intent classifier.

Logistic Regression on bge-small embeddings (same embedding function used at inference,
app.services.embeddings.embed_passages -- no query instruction prefix, since this is
classification, not asymmetric retrieval), wrapped in CalibratedClassifierCV so predicted
probabilities are usable as a confidence score for the escalation gate (Section 4.3).

Trains on dataset/processed/intent_train.parquet, evaluates macro-F1 on intent_test.parquet
(target >= 0.90), and saves the fitted pipeline + label list to models/intent_clf/model.joblib.
"""

from __future__ import annotations

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.embeddings import embed_passages, get_embedder

REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = REPO_ROOT / "dataset" / "processed"
MODELS_DIR = REPO_ROOT / "models" / "intent_clf"
MACRO_F1_TARGET = 0.90


def embed_dataframe(df: pd.DataFrame, batch_size: int = 256) -> np.ndarray:
    utterances = df["utterance"].tolist()
    vectors: list[list[float]] = []
    for start in range(0, len(utterances), batch_size):
        batch = utterances[start : start + batch_size]
        vectors.extend(embed_passages(batch))
        print(f"  embedded {min(start + batch_size, len(utterances))}/{len(utterances)}", end="\r")
    print()
    return np.array(vectors)


def main() -> int:
    train_df = pd.read_parquet(PROCESSED_DIR / "intent_train.parquet")
    test_df = pd.read_parquet(PROCESSED_DIR / "intent_test.parquet")
    print(f"Train: {len(train_df)} rows, Test: {len(test_df)} rows, {train_df['intent'].nunique()} intents")

    print("Loading embedding model...")
    get_embedder()

    print("Embedding training set...")
    X_train = embed_dataframe(train_df)
    y_train = train_df["intent"].to_numpy()

    print("Embedding test set...")
    X_test = embed_dataframe(test_df)
    y_test = test_df["intent"].to_numpy()

    # Rare intents (as few as ~32 train examples) need class_weight="balanced" so the loss
    # doesn't just learn to always predict the dominant Bitext-derived intents (out_of_scope,
    # speak_to_human, service_faq, ...). cv=3 keeps every class's smallest fold non-empty.
    base = LogisticRegression(max_iter=2000, class_weight="balanced", C=2.0)
    min_class_count = train_df["intent"].value_counts().min()
    cv_folds = max(2, min(3, int(min_class_count)))
    calibrated = CalibratedClassifierCV(base, method="sigmoid", cv=cv_folds)

    print(f"Fitting CalibratedClassifierCV(cv={cv_folds})...")
    calibrated.fit(X_train, y_train)

    y_pred = calibrated.predict(X_test)
    macro_f1 = f1_score(y_test, y_pred, average="macro")
    print(f"\nMacro-F1 on test set: {macro_f1:.4f} (target >= {MACRO_F1_TARGET})")
    print(classification_report(y_test, y_pred, zero_division=0))

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    labels = sorted(train_df["intent"].unique().tolist())
    joblib.dump({"model": calibrated, "labels": labels, "macro_f1": macro_f1}, MODELS_DIR / "model.joblib")
    print(f"Saved model to {MODELS_DIR / 'model.joblib'}")

    return 0 if macro_f1 >= MACRO_F1_TARGET else 1


if __name__ == "__main__":
    raise SystemExit(main())
