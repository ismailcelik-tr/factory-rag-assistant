# `answer-agent`

**One-line description**: Assembles a role-aware prompt from retrieved chunks and produces a cited answer via the configured LLM.

## Responsibility

Takes a query, a role identifier, and a ranked list of retrieved chunks from `retrieval-agent`. Loads the matching role prompt template from `prompts/roles/`, assembles the full prompt with context, calls the configured LLM provider, and returns a structured answer object with citations. Does not perform retrieval or chunking.

## Inputs

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | yes | The user's question |
| `role` | string | yes | One of: `rd_engineer`, `tech_service`, `sales`, `purchasing`, `production`, `customer_support` |
| `retrieved_chunks` | array | yes | Output from `retrieval-agent` |
| `llm_provider` | string | no | `ollama_gemma4` (default), `claude`, `openai` |
| `max_context_tokens` | int | no | Default: 3000 |

## Outputs

```json
{
  "answer": "The X200 motor must be calibrated to 1500 RPM before initial use...",
  "citations": [
    {
      "source_file": "X200_user_manual.pdf",
      "page_number": 12,
      "section_heading": "3.2 Motor Calibration"
    }
  ],
  "role": "tech_service",
  "model": "gemma4",
  "context_chunks_used": 4,
  "prompt_tokens": 1842
}
```

An answer with an empty `citations` array is a bug, not an acceptable response.

## Preconditions

- LLM provider is running and reachable (Ollama: `ollama serve`)
- Role template exists in `prompts/roles/<role>.md`
- Retrieved chunks are non-empty (retrieval should validate this before calling answer-agent)

## Does NOT Do

- Query the vector store
- Chunk or process documents
- Render or format output for the UI (returns raw JSON)
- Fall back silently to a generic role — if role template is missing, it raises an error

## Example Invocation

```
Agent({
  subagent_type: "answer-agent",
  prompt: "Answer 'How do I reset fault code E47?' for role=tech_service using the provided chunks"
})
```

## Related

- Upstream: `retrieval-agent` provides the chunks
- Skill: `rag-answering` (see `skills/rag_answering.md`)
- Skill: `role-based-prompting` (see `skills/role_based_prompting.md`)
- Templates: `prompts/roles/`
