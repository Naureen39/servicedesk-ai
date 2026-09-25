# Retrieval Evaluation (Phase 3)

Evaluation set: `dataset/reference/eval/kb_retrieval_questions.csv` (60 questions)
Model: `BAAI/bge-small-en-v1.5`, top-k=3, min similarity 0.55

## Results

- Hit rate @3: **98.3%** (59/60), target >= 90%
- p95 latency: **55.5 ms**, target < 60 ms
- p50 latency: 49.6 ms, mean: 54.2 ms, max: 188.2 ms
- Overall: **PASSED**

## Misses

| Question | Expected | Retrieved |
|---|---|---|
| How much for a 60K scheduled service? | pricing-guide.md | maintenance-schedule.md, maintenance-schedule.md, maintenance-schedule.md |
