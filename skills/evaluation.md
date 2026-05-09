# Skill: `evaluation`

**Trigger**: Before merging changes to chunking, embeddings, prompts, or retrieval parameters. Invoked by `eval-agent`.

---

## Purpose

Measure the quality of retrieval and answer generation against a ground-truth dataset. Produce objective metrics that justify or reject pipeline changes. No change to chunking strategy, embedding model, top-k, or prompt templates is merged without a passing eval run.

---

## Eval Dataset Format

All datasets live in `evals/datasets/`. Each JSONL record:

```json
{
  "id": "q001",
  "question": "What is the maximum operating temperature of the X200?",
  "role": "rd_engineer",
  "expected_sources": ["X200_datasheet.pdf"],
  "expected_page_numbers": [4],
  "reference_answer": "The X200 has a maximum operating temperature of 85°C as specified in section 4.1 of the datasheet.",
  "tags": ["thermal", "specifications", "X200"]
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `id` | yes | Unique stable identifier |
| `question` | yes | The query to run |
| `role` | yes | Role used for this question |
| `expected_sources` | yes | At least one expected source filename |
| `expected_page_numbers` | no | Specific pages; improves citation accuracy scoring |
| `reference_answer` | yes (for answer evals) | Human-authored gold answer |
| `tags` | no | Used to slice metrics by category |

---

## Evaluation Modes

### `retrieval` mode

Measures whether the right documents surface in the top-k results.

**Metrics computed**:

| Metric | Definition |
|--------|-----------|
| Hit Rate @ k | % of questions where ≥1 expected source appears in top-k chunks |
| MRR (Mean Reciprocal Rank) | Average of 1/rank of first relevant result |
| Precision @ k | % of returned chunks that are from expected sources |

**Minimum acceptable thresholds** (to be calibrated against first baseline run):

| Metric | Target |
|--------|--------|
| Hit Rate @ 5 | ≥ 0.80 |
| MRR | ≥ 0.65 |

These thresholds are placeholders until a baseline is established. Update this file after the first eval run.

---

### `answer` mode

Measures answer quality against reference answers.

**Metrics computed**:

| Metric | Method |
|--------|--------|
| Semantic similarity | Cosine similarity of embeddings (answer vs. reference) |
| Citation accuracy | % of expected sources present in `citations` field |
| Citation completeness | % of citations that point to an expected source (no hallucinated citations) |

**Scoring**:
- Semantic similarity ≥ 0.75: acceptable
- Citation accuracy ≥ 0.80: acceptable
- Any hallucinated citation (cites a source not in the retrieved chunks): flag immediately

---

### `full` mode

Runs retrieval eval first, then answer eval using the retrieved chunks from the retrieval step. Produces combined report.

---

## Steps

### 1. Prepare

- Confirm vector store is populated and up-to-date
- Confirm LLM is available (for `answer` / `full` modes)
- Load the dataset file and validate all records have required fields

### 2. Run queries

For each record:
1. Execute retrieval with the question and role
2. If mode includes answer: execute answer generation with retrieved chunks
3. Compare against expected values

### 3. Compute metrics

Aggregate across all records. Also compute per-tag slices (e.g., hit rate for `thermal` questions vs. `procedures`).

### 4. Write results

Output to `evals/results/<timestamp>-<tag>.json`:

```json
{
  "run_id": "2025-01-15T14:32:00Z-baseline",
  "dataset": "evals/datasets/smoke_test.jsonl",
  "mode": "full",
  "config": { "top_k": 5, "embedding_model": "nomic-embed-text", "llm": "gemma4:e4b" },
  "summary": {
    "hit_rate_at_5": 0.84,
    "mrr": 0.71,
    "citation_accuracy": 0.88,
    "semantic_similarity_mean": 0.79,
    "hallucinated_citations": 0
  },
  "per_question": [...]
}
```

Also write a human-readable summary to `evals/results/<timestamp>-<tag>.md`.

### 5. Compare to previous run (when applicable)

If a previous result exists for the same dataset, compute deltas and flag regressions:
- Any metric that drops > 5 percentage points is a regression — do not merge the change.

---

## Datasets to Maintain

| File | Purpose | Min size |
|------|---------|---------|
| `evals/datasets/smoke_test.jsonl` | Quick sanity check (run on every change) | 10 questions |
| `evals/datasets/full_suite.jsonl` | Comprehensive quality measurement | 50+ questions |
| `evals/datasets/role_coverage.jsonl` | At least 5 questions per role | 30 questions |

When adding new documents to the corpus, add at least 2 eval questions per document.

---

## What Can Go Wrong

| Problem | How to handle |
|---------|--------------|
| Vector store is stale | Re-run `embedding-agent` before eval |
| Reference answers are outdated | Review and update eval dataset when source documents are updated |
| Semantic similarity scorer unavailable | Fall back to BM25-based lexical overlap; note in results |
| Hallucinated citations appear | Flag immediately in results; investigate prompt template |

---

## Related

- Agent: `eval-agent`
- Results: `evals/results/`
- Datasets: `evals/datasets/`
