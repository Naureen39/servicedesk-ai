"""Phase 9 DoD: NLU evaluation report (accuracy, macro-F1, confusion matrix, escalation
precision/recall) against the held-out intent_test.parquet set, using the real trained
classifier from models/intent_clf/model.joblib. Writes docs/nlu-evaluation.md.

Escalation ground truth: examples the classifier's top prediction gets wrong. This is what
the confidence gate exists to catch -- explicit human-handoff intents (speak_to_human,
out_of_scope) are routed to a person whenever they're *correctly* classified, through the
dialog manager's direct intent handling, not through this gate; the gate's job is to hedge
against the classifier being confidently wrong on some other intent. Escalation prediction:
the model's own low-confidence gate (Section 4.3, threshold 0.55) on the same examples.
"""

from __future__ import annotations

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.embeddings import embed_passages, get_embedder  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = REPO_ROOT / "dataset" / "processed"
MODEL_PATH = REPO_ROOT / "models" / "intent_clf" / "model.joblib"
DOCS_PATH = REPO_ROOT / "docs" / "nlu-evaluation.md"
CONFIDENCE_THRESHOLD = 0.55


def main() -> int:
    bundle = joblib.load(MODEL_PATH)
    model = bundle["model"]
    labels = list(model.classes_)

    test_df = pd.read_parquet(PROCESSED_DIR / "intent_test.parquet")
    print(f"Evaluating on {len(test_df)} held-out examples, {test_df['intent'].nunique()} intents")

    get_embedder()
    X_test = np.array(embed_passages(test_df["utterance"].tolist()))
    y_true = test_df["intent"].to_numpy()

    proba = model.predict_proba(X_test)
    pred_idx = proba.argmax(axis=1)
    y_pred = np.array(labels)[pred_idx]
    confidence = proba.max(axis=1)

    accuracy = accuracy_score(y_true, y_pred)
    macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)

    cm = confusion_matrix(y_true, y_pred, labels=labels)

    predicted_escalate = confidence < CONFIDENCE_THRESHOLD
    should_escalate = y_true != y_pred
    esc_precision = precision_score(should_escalate, predicted_escalate, zero_division=0)
    esc_recall = recall_score(should_escalate, predicted_escalate, zero_division=0)
    esc_f1 = f1_score(should_escalate, predicted_escalate, zero_division=0)

    lines: list[str] = []
    lines.append("# NLU evaluation report")
    lines.append("")
    lines.append(
        "Evaluation of the local intent classifier (Section 4.1: Logistic Regression on "
        "bge-small embeddings, calibrated with CalibratedClassifierCV) against the held-out "
        f"test set (`dataset/processed/intent_test.parquet`, {len(test_df)} examples, "
        f"{test_df['intent'].nunique()} intents), which the model never saw during training."
    )
    lines.append("")
    lines.append("## Headline metrics")
    lines.append("")
    lines.append(f"- Accuracy: {accuracy:.4f}")
    lines.append(f"- Macro-F1: {macro_f1:.4f} (training target: >= 0.90)")
    lines.append("")
    lines.append("## Per-intent precision, recall, F1")
    lines.append("")
    lines.append("| Intent | Precision | Recall | F1 | Support |")
    lines.append("| --- | --- | --- | --- | --- |")
    per_intent_precision = precision_score(y_true, y_pred, labels=labels, average=None, zero_division=0)
    per_intent_recall = recall_score(y_true, y_pred, labels=labels, average=None, zero_division=0)
    per_intent_f1 = f1_score(y_true, y_pred, labels=labels, average=None, zero_division=0)
    support = pd.Series(y_true).value_counts().reindex(labels, fill_value=0)
    for i, label in enumerate(labels):
        lines.append(
            f"| {label} | {per_intent_precision[i]:.3f} | {per_intent_recall[i]:.3f} | "
            f"{per_intent_f1[i]:.3f} | {support[label]} |"
        )
    lines.append("")
    lines.append("## Confusion matrix")
    lines.append("")
    lines.append("Rows: true intent. Columns: predicted intent.")
    lines.append("")
    header = "| true \\\\ pred | " + " | ".join(labels) + " |"
    lines.append(header)
    lines.append("| --- | " + " | ".join(["---"] * len(labels)) + " |")
    for i, label in enumerate(labels):
        row = " | ".join(str(v) for v in cm[i])
        lines.append(f"| {label} | {row} |")
    lines.append("")
    lines.append("## Escalation precision/recall")
    lines.append("")
    lines.append(
        "Ground truth \"should escalate\": the classifier's top prediction is wrong. This "
        "isolates what the confidence gate actually exists to catch -- `speak_to_human` and "
        "`out_of_scope` are routed to a human through the dialog manager's direct intent "
        "handling whenever they're *correctly* classified (see the per-intent recall for "
        "those two rows above), not through this gate. Predicted \"escalate\": the "
        f"classifier's own confidence gate (top predicted-class probability below {CONFIDENCE_THRESHOLD})."
    )
    lines.append("")
    lines.append(f"- Precision: {esc_precision:.4f}")
    lines.append(f"- Recall: {esc_recall:.4f}")
    lines.append(f"- F1: {esc_f1:.4f}")
    lines.append(
        f"- Should-escalate examples in test set: {int(should_escalate.sum())} / {len(test_df)}"
    )
    lines.append(
        f"- Confidence-gate flagged: {int(predicted_escalate.sum())} / {len(test_df)}"
    )
    lines.append("")
    lines.append(
        "Note: the confidence gate is a single signal in a larger escalation policy "
        "(`app/services/dialog/policy.py`) that also escalates on repeated slot-filling "
        "failure and on a negative sentiment streak; those paths are exercised directly by "
        "`backend/tests/test_scripted_conversations.py` rather than this offline NLU eval, "
        "since they depend on multi-turn dialog state, not a single utterance's embedding."
    )
    lines.append("")

    DOCS_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Accuracy: {accuracy:.4f}, Macro-F1: {macro_f1:.4f}")
    print(f"Escalation precision: {esc_precision:.4f}, recall: {esc_recall:.4f}")
    print(f"Wrote {DOCS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
