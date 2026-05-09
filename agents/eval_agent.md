# `eval-agent`

**One-line description**: Runs the evaluation harness against ground-truth QA data and reports retrieval and answer quality metrics.

## Responsibility

Loads a JSONL evaluation dataset, runs each question through the pipeline (retrieval only, answer only, or full), compares results against expected sources and reference answers, and produces a structured metrics report. Writes results to `evals/results/`. Does not modify application code or pipeline configuration.

## Inputs

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `dataset` | string | yes | Path to JSONL eval file (e.g., `evals/datasets/smoke_test.jsonl`) |
| `mode` | string | yes | `retrieval`, `answer`, or `full` |
| `config` | string | no | Path to pipeline config YAML to test a specific configuration |
| `tag` | string | no | Label for this eval run (used in output filename) |

### Dataset record format

```json
{
  "question": "What is the maximum operating temperature of the X200?",
  "role": "rd_engineer",
  "expected_sources": ["X200_datasheet.pdf"],
  "reference_answer": "The X200 has a maximum operating temperature of 85°C per section 4.1 of the datasheet."
}
```

## Outputs

Written to `evals/results/<timestamp>-<tag>.json` and `evals/results/<timestamp>-<tag>.md`:

**Retrieval metrics**:
- Hit rate @ k: fraction of questions where expected source appears in top-k results
- Mean Reciprocal Rank (MRR)
- Per-question retrieval result

**Answer metrics** (when mode is `answer` or `full`):
- Semantic similarity to reference answer (cosine similarity of embeddings)
- Citation accuracy: expected sources present in citations
- Per-question answer and score

## Preconditions

- Vector store is populated (`embedding-agent` has run)
- LLM is available (for `answer` and `full` modes)
- Eval dataset file exists and is valid JSONL

## Does NOT Do

- Modify chunking, embeddings, prompts, or any pipeline code
- Auto-tune parameters
- Delete or overwrite previous eval results (always appends with timestamp)

## Example Invocation

```
Agent({
  subagent_type: "eval-agent",
  prompt: "Run full evaluation on evals/datasets/smoke_test.jsonl with tag=baseline"
})
```

## Related

- Skill: `evaluation` (see `skills/evaluation.md`)
- Results: `evals/results/`
- Datasets: `evals/datasets/`
