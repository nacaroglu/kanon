# ADR-003: LLM client approach and reference model

- **Status:** Proposed (awaiting the live structured-output run and confirmation of the reference model; see "Experiment")
- **Date:** 2026-11-20
- **Backlog / issue:** #34 (`LLM-001`)

## Context

Product Scope 1.3, Decision 18 (section 8.3) requires cloud and locally hosted models through **one OpenAI-compatible interface**, with a single *reference cloud model* used for initial quality validation, and local models evaluated separately. Section 9.3 lists "OpenAI-compatible endpoints" as the integration, and section 16 leaves the LLM orchestration framework undecided.

Every analysis stage (claim extraction, classification, proposal generation, independent review) calls a model and needs **structured output**: a finding must be parseable into a known shape, never free text to be scraped.

This is a learning project, so the approach should be one that can be explained line by line.

## Options considered

### Decision A: How Kanon talks to a model

| Option | Trade-off |
|---|---|
| Thin HTTP client over `POST /chat/completions` (one small module, `httpx2`) | The whole request and response are visible; one dependency already in the tree; exactly the OpenAI-compatible subset every provider and local server implements. We write timeouts and error mapping ourselves (a few dozen lines). |
| Official `openai` SDK pointed at a `base_url` | Typed models, built-in retries and streaming. Hides the wire format behind a large dependency; its retry and timeout defaults are decisions made for us; tracks OpenAI-specific features that other providers do not implement. |
| Official Anthropic SDK | Full Claude feature set (prompt caching, native structured outputs, thinking, citations). Not OpenAI-compatible, so it cannot serve local models and would break Decision 18 unless wrapped as a second client. |
| Orchestration framework (LangChain, LlamaIndex and similar) | Prebuilt chains and many providers. Several layers of abstraction between us and the prompt, fast-moving APIs, and the exact thing we need to learn (and later evaluate) is hidden. Scope section 16 leaves it undecided, and nothing in v1 needs it. |

### Decision B: Reference cloud model

| Option | Price per 1M tokens in / out | Trade-off |
|---|---|---|
| `claude-opus-5-5` | $4 / $20 | Most capable of the three; a strong baseline against which local models are judged. About twice the cost of Sonnet. |
| `claude-sonnet-5-5` | $2 / $10 | Roughly half the cost; may be enough for classification but gives a lower ceiling for "what is achievable". |
| `claude-haiku-5-5` | $0.10 / $0.50 | Very cheap; better suited as a later cost-saving stage than as the reference. |

Prices are from Anthropic's model table (cached 2026-11-03) and must be re-checked before relying on them. A non-Anthropic reference model was **not** evaluated: this ADR has no verified current information about those models, and evaluating one is a reasonable alternative if the owner prefers a provider whose OpenAI-compatible endpoint is its primary interface (see Consequences).

### Decision C: How a structured result is obtained

| Option | Trade-off |
|---|---|
| `response_format` with a strict JSON Schema, then validate the reply ourselves | Standard OpenAI field, works for hosted and (to varying degrees) local servers; our validation is the real guarantee. Schema features are limited. |
| Tool/function calling to force a JSON argument | Widely supported, but `strict` is ignored on Anthropic's compatible endpoint, and forced `tool_choice` is rejected by the newest Claude models (Opus 5.5 among them). |
| Ask for JSON in the prompt and parse | Works anywhere; least reliable, needs repair logic. |

## Decision

1. **Thin HTTP client** behind a small interface (`LLMClient`, issue `LLM-002`): one function that takes messages and returns text, with an explicit timeout on every call and a domain error for failures. A fake implements the same interface in tests. A native adapter (for example the Anthropic SDK, to gain prompt caching) can later sit behind the same interface without touching callers.
2. **Reference model: `claude-opus-5-5`**, called through Anthropic's OpenAI-compatible endpoint (`https://api.anthropic.com/v1/`). *To be confirmed by the owner.* Estimated cost per analysis is in the next section.
3. **Credentials** are supplied only through environment variables read by `Settings`: `KANON_LLM_BASE_URL`, `KANON_LLM_API_KEY` (a secret: never logged, never printed, never committed) and `KANON_LLM_MODEL`. Local inference uses the same three variables with a local base URL.
4. **Structured output** uses `response_format` with a strict JSON Schema **and** is validated by Kanon on every reply (parse, schema check, bounded retry). Server-side enforcement is treated as a hint, never a guarantee, because local servers differ.

### What "OpenAI-compatible" does and does not cover

Standard, and relied on: `POST {base_url}/chat/completions`; `model`; `messages` with `system`/`user`/`assistant` roles; `max_tokens`; `temperature`; `stream`; `response_format` with `json_schema`; `choices[0].message.content`, `choices[0].finish_reason` and `usage` in the reply; `Authorization: Bearer <key>`.

Provider-specific, so **not** relied on: reasoning and thinking controls (Anthropic's layer takes a non-standard `thinking` field, ignores `reasoning_effort`, and does not return thinking); prompt caching (not available through the compatible layer); `seed`, `logprobs`, penalties (ignored); the semantics of `strict` on tools; extra headers such as `anthropic-workspace-id`; and how strictly each server enforces `json_schema`.

### Known limitations of the chosen reference path

Anthropic documents its OpenAI-compatible layer as "primarily intended to test and compare model capabilities, and … not considered a long-term or production-ready solution for most use cases". For Kanon this means: no prompt caching (so repeated procedure text is billed in full), no returned reasoning, `response_format` accepts only `json_schema` with `strict: true` and only a JSON Schema subset (no recursive schemas, no `minimum`/`maxLength`-style constraints, `additionalProperties` must be `false`), forced tool choice is rejected on `claude-opus-5-5`, and system messages are hoisted into one system prompt. These are acceptable for a reference run whose job is to validate quality, and the narrow interface keeps the option of a native adapter open. If they prove limiting, the owner can choose a different reference provider without changing the client design.

## Rough cost per analysis

One analysis of a typical submitted document, order of magnitude only:

| Stage | Calls | Input tokens | Output tokens |
|---|---|---|---|
| Claim extraction | 1 | 3,000 | 1,000 |
| Retrieval classification (about 8 claims, 4 candidate sections each) | 8 | 16,000 | 4,000 |
| Proposal generation (about 3 contradictions) | 3 | 9,000 | 3,000 |
| Independent review of proposals | 3 | 12,000 | 1,500 |
| **Total** | **15** | **about 40,000** | **about 10,000** |

| Model | Estimate |
|---|---|
| `claude-opus-5-5` | 40k × $4/M + 10k × $20/M ≈ **$0.36** |
| `claude-sonnet-5-5` | ≈ $0.18 |
| `claude-haiku-5-5` | ≈ $0.01 |

These ignore reasoning tokens (billed as output and potentially large), retries, and prompt caching, so treat **$0.2 to $1** as the realistic band for the reference model. The token counts are assumptions, to be replaced by measured `usage` from the first real run.

## Experiment: structured output on the chosen model

`scripts/llm_structured_output_experiment.py` (standard library only) sends five contradiction-classification requests with a strict JSON Schema (`outcome` is one of the four outcomes from Product Scope 3.3, plus `evidence_quote` and `explanation`), then checks that each reply parses, matches the schema exactly and was not cut off. It prints per-trial results and token usage, never prints the key, and exits non-zero if any trial fails.

```bash
export KANON_LLM_BASE_URL=https://api.anthropic.com/v1/
export KANON_LLM_MODEL=claude-opus-5-5
export KANON_LLM_API_KEY=...        # not on the command line
uv run python scripts/llm_structured_output_experiment.py
```

**Status of the run: not yet performed.** The environment this ADR was written in had no LLM credentials, so no real model has been called and **no claim about the model's behaviour is made here**. What has been verified: the script sends the intended request (path, bearer header, strict `response_format`) and classifies replies correctly, using a local fake endpoint in `tests/test_llm_experiment.py` (18 tests; invalid JSON, missing/extra fields, wrong enum values, truncation, HTTP errors and unreachable hosts all fail the trial, and the key never appears in output). The acceptance criterion "structured-output support is confirmed by a small experiment" stays **open** until the script's output from a real run is added to this ADR and the status changes to Accepted.

## Consequences

- One small, readable module owns all model traffic; tests use a fake. Timeouts, error mapping and validation are ours to get right.
- Because Kanon validates every reply, a local model that ignores `response_format` still works, at the price of retries.
- Prompt caching is unavailable on this path, so costs are higher than the native API would give; revisit with a native adapter if analysis cost matters.
- The reference model is a configuration value, not code, so changing it (or the provider) is cheap.
- Revisit this decision if the OpenAI-compatible layer proves unreliable for strict output, if a stage needs a feature only a native API offers (citations, caching), or if the experiment fails on the reference model.
