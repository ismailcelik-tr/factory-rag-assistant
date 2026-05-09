# Skill: `rag-answering`

**Trigger**: When generating an answer to a user query using retrieved context. Invoked by `answer-agent`.

---

## Purpose

Assemble a complete, cited answer by combining retrieved chunks with a role-appropriate prompt and calling the LLM. This skill governs prompt construction and output validation — it does not govern retrieval or role template selection (see `role-based-prompting` for that).

---

## Steps

### 1. Validate inputs

Before assembling the prompt, verify:
- `query` is non-empty
- `role` is a known role identifier
- `retrieved_chunks` is non-empty — if the retrieval returned zero chunks, do not call the LLM; return a structured "no results" response instead:

```json
{
  "answer": null,
  "no_results": true,
  "message": "No relevant documents found for this query.",
  "citations": []
}
```

### 2. Select and trim context

From `retrieved_chunks`, take the highest-scoring chunks up to `max_context_tokens` (default: 3000). Always prefer chunks that:
- Come from multiple distinct source files (avoid single-source answers when breadth exists)
- Include the section heading most relevant to the query

Format each chunk for injection:

```
[Source: X200_user_manual.pdf | Page 12 | Section: 3.2 Motor Calibration]
The X200 motor must be calibrated to 1500 RPM before initial use...
```

### 3. Load role prompt template

Load `prompts/roles/<role>.md`. The template defines:
- Persona/voice for the role
- Instruction for citation format
- Length and tone constraints
- Any role-specific rules (e.g., safety warnings for `tech_service`)

If the template file is missing, raise an error — never fall back to a generic prompt silently.

### 4. Assemble the full prompt

```
[SYSTEM: role template content]

[CONTEXT:
  chunk 1 formatted block
  chunk 2 formatted block
  ...
]

[QUESTION: <query>]

Answer the question using only the provided context. Include citations for every factual claim. If the answer cannot be determined from the context, say so explicitly.
```

### 5. Call the LLM

Route through `app/llm/<provider>.py`. Pass:
- assembled prompt
- temperature: 0.1 (factual, low variance)
- max tokens: role-dependent (default 600)

### 6. Parse and validate the response

Extract from the LLM response:
- The answer text
- Citations (the model is instructed to embed them in a parseable format)

Citation format the model must produce (instruct in system prompt):
```
[cite: X200_user_manual.pdf, p.12, "3.2 Motor Calibration"]
```

If the response contains zero citations, do not return it as-is. Either:
1. Re-prompt once with an explicit instruction to add citations
2. Extract citations from the formatted context blocks used

### 7. Return structured output

```json
{
  "answer": "...",
  "citations": [
    {
      "source_file": "X200_user_manual.pdf",
      "page_number": 12,
      "section_heading": "3.2 Motor Calibration"
    }
  ],
  "role": "tech_service",
  "model": "gemma4:e4b",
  "context_chunks_used": 4,
  "prompt_tokens": 1842
}
```

---

## What Can Go Wrong

| Problem | How to handle |
|---------|--------------|
| LLM returns no citations | Re-prompt once; if still none, extract from context blocks used |
| LLM refuses to answer | Return the refusal text as `answer`, empty citations, flag `refused: true` |
| Context exceeds token limit | Trim lowest-scoring chunks until within limit — never truncate mid-chunk |
| Role template missing | Raise an error, do not default silently |
| Zero retrieved chunks | Return `no_results: true` without calling the LLM |

---

## Related

- Agent: `answer-agent`
- Skill: `role-based-prompting` (role template selection and persona logic)
- Templates: `prompts/roles/`, `prompts/system/`
