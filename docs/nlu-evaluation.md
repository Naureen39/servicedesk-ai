# NLU evaluation report

Evaluation of the local intent classifier (Section 4.1: Logistic Regression on bge-small embeddings, calibrated with CalibratedClassifierCV) against the held-out test set (`dataset/processed/intent_test.parquet`, 1270 examples, 17 intents), which the model never saw during training.

## Headline metrics

- Accuracy: 0.9906
- Macro-F1: 0.9575 (training target: >= 0.90)

## Per-intent precision, recall, F1

| Intent | Precision | Recall | F1 | Support |
| --- | --- | --- | --- | --- |
| appointment_status | 1.000 | 0.990 | 0.995 | 104 |
| book_service | 0.714 | 1.000 | 0.833 | 5 |
| cancel_appointment | 1.000 | 0.980 | 0.990 | 149 |
| complaint | 1.000 | 1.000 | 1.000 | 104 |
| complaint_history | 0.800 | 1.000 | 0.889 | 4 |
| goodbye | 1.000 | 1.000 | 1.000 | 4 |
| greeting | 0.714 | 1.000 | 0.833 | 5 |
| out_of_scope | 0.993 | 0.986 | 0.989 | 281 |
| parts_inquiry | 0.800 | 1.000 | 0.889 | 4 |
| pricing_estimate | 1.000 | 1.000 | 1.000 | 4 |
| recall_check | 1.000 | 0.800 | 0.889 | 5 |
| reschedule_appointment | 0.968 | 0.989 | 0.978 | 91 |
| safety_concern | 1.000 | 1.000 | 1.000 | 4 |
| service_faq | 0.995 | 0.990 | 0.992 | 195 |
| speak_to_human | 1.000 | 1.000 | 1.000 | 204 |
| thanks | 1.000 | 1.000 | 1.000 | 103 |
| warranty_question | 1.000 | 1.000 | 1.000 | 4 |

## Confusion matrix

Rows: true intent. Columns: predicted intent.

| true \\ pred | appointment_status | book_service | cancel_appointment | complaint | complaint_history | goodbye | greeting | out_of_scope | parts_inquiry | pricing_estimate | recall_check | reschedule_appointment | safety_concern | service_faq | speak_to_human | thanks | warranty_question |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| appointment_status | 103 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| book_service | 0 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| cancel_appointment | 0 | 0 | 146 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 0 |
| complaint | 0 | 0 | 0 | 104 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| complaint_history | 0 | 0 | 0 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| goodbye | 0 | 0 | 0 | 0 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| greeting | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| out_of_scope | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 277 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| parts_inquiry | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| pricing_estimate | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| recall_check | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 0 |
| reschedule_appointment | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 90 | 0 | 0 | 0 | 0 | 0 |
| safety_concern | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 4 | 0 | 0 | 0 | 0 |
| service_faq | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 193 | 0 | 0 | 0 |
| speak_to_human | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 204 | 0 | 0 |
| thanks | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 103 | 0 |
| warranty_question | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 4 |

## Escalation precision/recall

Ground truth "should escalate": the classifier's top prediction is wrong. This isolates what the confidence gate actually exists to catch -- `speak_to_human` and `out_of_scope` are routed to a human through the dialog manager's direct intent handling whenever they're *correctly* classified (see the per-intent recall for those two rows above), not through this gate. Predicted "escalate": the classifier's own confidence gate (top predicted-class probability below 0.55).

- Precision: 0.5000
- Recall: 0.2500
- F1: 0.3333
- Should-escalate examples in test set: 12 / 1270
- Confidence-gate flagged: 6 / 1270

Note: the confidence gate is a single signal in a larger escalation policy (`app/services/dialog/policy.py`) that also escalates on repeated slot-filling failure and on a negative sentiment streak; those paths are exercised directly by `backend/tests/test_scripted_conversations.py` rather than this offline NLU eval, since they depend on multi-turn dialog state, not a single utterance's embedding.
