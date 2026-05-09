# AGENTS.md

This file defines the subagent roles used in this project's AI-native development workflow. Each agent has a bounded responsibility, a set of inputs it expects, and a set of outputs it produces. Claude Code orchestrates these agents when running complex multi-step tasks.

---

## How Agents Work Here

Agents in this project are Claude Code subagents invoked via the `Agent` tool (or directly as slash commands where a matching skill exists). They are defined here so that:

1. Any Claude Code session can understand what agent to call for a given task.
2. Future contributors know who is responsible for what.
3. Agent boundaries are explicit — one agent does not silently take on another's scope.

---

## Agent Roster

### `ingestion-agent`

**File**: `agents/ingestion_agent.md`

**Responsibility**: Take raw factory documents from `data/raw/`, extract and clean text, apply semantic chunking, attach metadata, and write processed chunks to `data/processed/`.

**Inputs**:
- Path to one or more files in `data/raw/`
- Optional: document type override (`manual`, `datasheet`, `service`, `installation`, `troubleshooting`, `spec`)
- Optional: product family tag

**Outputs**:
- JSONL file(s) in `data/processed/` — one record per chunk with fields: `chunk_id`, `text`, `source_file`, `page_number`, `section_heading`, `document_type`, `product_family`, `token_count`

**Does NOT do**: embedding generation, vector store writes, answer generation.

**When to invoke**: After adding new documents to `data/raw/` or when chunking strategy changes and a reprocess is needed.

---

### `embedding-agent`

**File**: `agents/embedding_agent.md`

**Responsibility**: Read processed chunks from `data/processed/`, generate embeddings via the configured embedding model, and upsert to the vector store.

**Inputs**:
- Path to processed JSONL file(s) or `--all` flag to reprocess everything
- Embedding model name (default: `nomic-embed-text` via Ollama)
- Vector store target (default: local ChromaDB)

**Outputs**:
- Updated vector store in `data/embeddings/`
- Embedding run log: timestamp, model, chunk count, any errors

**Does NOT do**: chunking, retrieval, answer generation.

**When to invoke**: After `ingestion-agent` completes, or when switching embedding models.

---

### `retrieval-agent`

**File**: `agents/retrieval_agent.md`

**Responsibility**: Given a query and role, retrieve the most relevant chunks from the vector store and return them with scores and metadata for use in answer generation.

**Inputs**:
- `query`: string
- `role`: one of `rd_engineer`, `tech_service`, `sales`, `purchasing`, `production`, `customer_support`
- `top_k`: integer (default 5)
- Optional: `product_family` filter

**Outputs**:
- Ranked list of chunks: `[{chunk_id, text, score, source_file, page_number, section_heading}]`

**Does NOT do**: prompt assembly, LLM inference, answer formatting.

**When to invoke**: As part of the RAG pipeline or standalone during retrieval quality debugging.

---

### `answer-agent`

**File**: `agents/answer_agent.md`

**Responsibility**: Assemble a role-aware prompt from retrieved chunks and role template, call the configured LLM, and return a structured answer with citations.

**Inputs**:
- `query`: string
- `role`: role identifier
- `retrieved_chunks`: output from `retrieval-agent`
- `llm_provider`: `ollama` (default) | `claude` | `openai`

**Outputs**:
```json
{
  "answer": "...",
  "citations": [
    {"source_file": "...", "page_number": 12, "section_heading": "..."}
  ],
  "role": "...",
  "model": "..."
}
```

**Does NOT do**: retrieval, chunking, UI rendering.

**When to invoke**: As the final stage of a RAG query, or during answer quality evaluation.

---

### `eval-agent`

**File**: `agents/eval_agent.md`

**Responsibility**: Run the evaluation harness against a ground-truth QA dataset and produce quality metrics for retrieval and answer generation.

**Inputs**:
- Path to eval dataset (JSONL, each record: `{question, role, expected_sources, reference_answer}`)
- Eval mode: `retrieval` | `answer` | `full`
- Optional: specific pipeline configuration to test (model, chunk size, top-k)

**Outputs**:
- Metrics report (JSON + Markdown): hit rate, MRR, answer similarity scores
- Per-question breakdown for failure analysis
- Written to `evals/results/`

**Does NOT do**: modify application code, make assumptions about quality without data.

**When to invoke**: Before merging any change to chunking strategy, embedding model, prompt templates, or retrieval parameters.

---

### `doc-review-agent`

**File**: `agents/doc_review_agent.md`

**Responsibility**: Review code or documentation changes for consistency with `PROJECT_CONTEXT.md` principles and architectural decisions in `architecture/decisions/`.

**Inputs**:
- Git diff or file path(s) to review
- Review scope: `architecture` | `prompts` | `code` | `docs`

**Outputs**:
- Markdown review report: issues found, ADR conflicts, suggestions
- Does not auto-fix — outputs findings only

**When to invoke**: Before merging significant changes. Can be run as a pre-PR checklist step.

---

## Orchestration Patterns

### Full ingestion-to-index pipeline
```
ingestion-agent → embedding-agent
```

### Single RAG query
```
retrieval-agent → answer-agent
```

### Quality gate before prompt change
```
eval-agent (retrieval) → [change prompts] → eval-agent (answer) → compare
```

### New document onboarding
```
ingestion-agent (new file) → embedding-agent (new file only) → eval-agent (retrieval, smoke test)
```

---

## Adding a New Agent

1. Create `agents/<agent_name>.md` using the template in `agents/TEMPLATE.md`.
2. Add an entry to this file under the Agent Roster.
3. Define inputs, outputs, and explicit boundaries — especially what the agent does NOT do.
4. If the agent requires a skill, add the skill definition to `skills/`.
