# Evaluations

This directory contains the evaluation harness and ground-truth datasets for measuring pipeline quality.

## Structure

```
evals/
├── datasets/        Ground-truth QA datasets (JSONL)
├── results/         Eval run outputs (JSON + Markdown) — gitignored
└── README.md        This file
```

## Datasets

| File | Description | Size |
|------|-------------|------|
| `datasets/smoke_test.jsonl` | Quick sanity check — run after any pipeline change | 10 questions |
| `datasets/full_suite.jsonl` | Comprehensive quality suite | 50+ questions (to be built) |
| `datasets/role_coverage.jsonl` | Role-specific coverage — 5+ questions per role | 30 questions (to be built) |

Datasets are committed to the repository. Results are not.

## Running Evals

```bash
# Smoke test (retrieval only)
python evals/run_evals.py --dataset evals/datasets/smoke_test.jsonl --mode retrieval

# Full pipeline test
python evals/run_evals.py --dataset evals/datasets/full_suite.jsonl --mode full --tag baseline

# Compare two runs
python evals/compare_runs.py evals/results/baseline.json evals/results/new_chunking.json
```

## Adding Questions

When adding new documents to `data/raw/`, add at least 2 QA pairs to `datasets/full_suite.jsonl`. See the dataset record format in `skills/evaluation.md`.

## Thresholds

Quality thresholds are defined in `skills/evaluation.md`. A run that drops any metric by more than 5 percentage points vs. the previous baseline is a regression.
