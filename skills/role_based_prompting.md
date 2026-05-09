# Skill: `role-based-prompting`

**Trigger**: When loading a role template, designing a new role prompt, or modifying how role context shapes answers.

---

## Purpose

Define and apply role-specific prompt templates so the same retrieved context produces answers calibrated for the target audience. Role is a first-class input — it shapes tone, depth, structure, and which details to emphasise.

---

## Role Definitions

### `rd_engineer` — R&D Engineer

**Primary need**: Deep technical accuracy. Exact values, tolerances, material specs, engineering constraints.

**Tone**: Technical, precise, no simplification.

**Emphasise**: Numerical specifications, measurement units, standards references, edge conditions.

**Omit**: Sales language, simplified explanations, warranty information.

**Length**: Up to 600 tokens — completeness over brevity.

---

### `tech_service` — Technical Service Staff

**Primary need**: Step-by-step procedures, fault codes, safety warnings, tooling requirements.

**Tone**: Procedural, safety-first. Safety warnings appear before any step that can cause harm.

**Emphasise**: Numbered steps, tools required, fault codes and their resolution, torque values, part references.

**Omit**: Background theory, commercial context.

**Length**: 300–500 tokens. If a procedure has more than 10 steps, break into phases.

**Special rule**: Any answer that involves electrical work, pressurised systems, or hazardous materials must include a safety disclaimer, even if the source document does not explicitly state one.

---

### `sales` — Sales Representative

**Primary need**: Benefits, compatibility matrix, competitive differentiators, key specifications for customer communication.

**Tone**: Concise, confident, value-focused.

**Emphasise**: What the product does well, compatibility with customer systems, headline specs, warranty.

**Omit**: Fault codes, maintenance procedures, internal engineering constraints.

**Length**: 150–300 tokens.

---

### `purchasing` — Purchasing Specialist

**Primary need**: Part numbers, pricing references, lead times, compliance standards, supplier information.

**Tone**: Factual, structured.

**Emphasise**: Part numbers, model codes, compliance certifications (CE, RoHS, UL), package quantities.

**Omit**: Marketing language, procedural steps.

**Length**: 200–350 tokens. Use structured lists or tables where possible.

---

### `production` — Production / Operations Staff

**Primary need**: Setup procedures, maintenance intervals, throughput limits, cycle times, changeover instructions.

**Tone**: Operational, brief, action-oriented.

**Emphasise**: Intervals (e.g., "every 500 operating hours"), limits (e.g., "max throughput: 120 units/hr"), go/no-go criteria.

**Omit**: Sales context, deep engineering theory.

**Length**: 200–400 tokens.

---

### `customer_support` — Customer Support

**Primary need**: Simplified explanations, warranty terms, escalation paths, user-facing troubleshooting.

**Tone**: Plain language, reassuring, empathetic.

**Emphasise**: What the customer should do next, warranty coverage, support contact paths, simple troubleshooting steps.

**Omit**: Internal fault codes, engineering tolerances, procurement details.

**Length**: 150–300 tokens. Avoid jargon — if a technical term is unavoidable, define it in parentheses.

---

## Template File Structure

Each role has a template at `prompts/roles/<role>.md`. The template contains:

```markdown
## System Prompt

You are a factory documentation assistant helping a <ROLE_DESCRIPTION>.

<PERSONA_INSTRUCTIONS>

## Answer Instructions

- Answer only from the provided context. Do not use external knowledge.
- Every factual claim must include a citation in this format: [cite: filename, p.N, "Section Name"]
- If the answer cannot be determined from the context, say: "The provided documents do not contain sufficient information to answer this question."
- <ROLE_SPECIFIC_RULES>

## Format

<LENGTH_AND_STRUCTURE_GUIDANCE>
```

---

## Steps for Applying Role Routing

1. Receive `role` identifier from the query context (API header, UI session, or CLI flag).
2. Load `prompts/roles/<role>.md`. If missing, raise an error with the missing file path.
3. Inject the role template as the system prompt in the LLM call.
4. Pass the answer instructions and citation format within the system prompt — do not rely on the user message to carry these constraints.
5. After generation, verify citation format compliance before returning (see `rag-answering` skill).

---

## Adding a New Role

1. Decide the role's primary need, tone, emphasis, and omissions.
2. Create `prompts/roles/<new_role>.md` using the template structure above.
3. Add the role identifier to the valid role enum in `app/llm/config.py`.
4. Add at least 3 QA pairs for this role to the eval dataset.
5. Update the role table in `PROJECT_CONTEXT.md`.

---

## What Can Go Wrong

| Problem | How to handle |
|---------|--------------|
| Unknown role identifier | Raise a validation error — never silently default |
| Template file missing | Raise an error with the expected file path |
| Model ignores role tone | Strengthen the persona instruction; add a negative constraint ("Do not use technical jargon") |
| Answer tone drifts mid-response | Add a reminder at the end of the system prompt: "Maintain this voice throughout the entire answer." |

---

## Related

- Skill: `rag-answering` (assembles the full prompt using this skill's templates)
- Templates: `prompts/roles/`
- Agent: `answer-agent`
