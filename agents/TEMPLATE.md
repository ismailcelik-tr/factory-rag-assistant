# Agent Template

Copy this file to `agents/<agent_name>.md` and fill in each section. Remove this header block.

---

# `<agent-name>`

**One-line description**: What this agent does in a single sentence.

## Responsibility

Two to four sentences describing the agent's bounded scope. Be explicit about what it does AND what it does NOT do.

## Inputs

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `param1` | string | yes | ... |
| `param2` | int | no | default: N |

## Outputs

Describe the output format. Include a JSON example if the output is structured.

```json
{
  "field": "value"
}
```

## Preconditions

What must be true before this agent runs (e.g., "Processed JSONL files must exist in `data/processed/`").

## Does NOT Do

Explicit list of things outside this agent's scope to prevent scope creep.

## Example Invocation

```
Agent({
  subagent_type: "<agent-name>",
  prompt: "Process all PDFs in data/raw/manuals/ with document_type=manual and product_family=X200"
})
```

## Related Agents / Skills

- Links to upstream agents that feed this one
- Links to downstream agents that consume its output
- Links to skills this agent uses
