#!/usr/bin/env python3
"""Does the configured model return schema-valid JSON through an OpenAI-compatible endpoint?

This is the experiment behind ADR-003. It sends a handful of contradiction-classification
prompts (the shape Kanon needs, Product Scope 3.3) with `response_format` set to a strict JSON
schema, then checks every reply parses and matches the schema. It uses only the standard
library so every line can be read and nothing hides the request.

Configuration (environment variables, never command-line arguments, so the key stays out of
shell history and process listings):

    KANON_LLM_BASE_URL   e.g. https://api.anthropic.com/v1/   (the "/chat/completions" is appended)
    KANON_LLM_API_KEY    the provider key; sent only as "Authorization: Bearer ..."; never printed
    KANON_LLM_MODEL      e.g. claude-opus-5-5

Run:   uv run python scripts/llm_structured_output_experiment.py
Exit:  0 if every trial returned valid structured output, 1 if any did not, 2 on bad usage.
Each run makes TRIALS paid requests of a few hundred tokens each.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

TIMEOUT_SECONDS = 120
OUTCOMES = ["contradiction", "no_contradiction", "uncertain", "not_covered"]

SCHEMA = {
    "type": "object",
    "properties": {
        "outcome": {"type": "string", "enum": OUTCOMES},
        "evidence_quote": {"type": "string"},
        "explanation": {"type": "string"},
    },
    "required": ["outcome", "evidence_quote", "explanation"],
    "additionalProperties": False,
}

SYSTEM = (
    "You compare a claim from a new document with an approved procedure. "
    "Answer only with the requested JSON. evidence_quote must be copied exactly from the "
    "procedure, or be an empty string when the outcome is not_covered."
)

PROCEDURE = (
    "## Submission deadline\n\nSubmit each expense report within 30 days of the expense date.\n\n"
    "## Approval\n\nReports under 500 EUR are approved by the employee's manager.\n"
)

# (claim, the outcome a careful reader would give). The expected outcome is printed for context
# but not scored: this experiment tests the *shape* of the output, not the model's accuracy.
CASES = [
    ("Expense reports must now be submitted within 45 days.", "contradiction"),
    ("Employees submit expense reports within 30 days.", "no_contradiction"),
    ("Managers approve reports under 500 EUR.", "no_contradiction"),
    ("Reports are approved by the CFO whatever the amount.", "contradiction"),
    ("Travel must be booked through the corporate portal.", "not_covered"),
]


def build_request(model: str, claim: str) -> dict:
    return {
        "model": model,
        "max_tokens": 1024,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": f"Approved procedure:\n{PROCEDURE}\nClaim: {claim}\nClassify the claim.",
            },
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "finding", "strict": True, "schema": SCHEMA},
        },
    }


def post(base_url: str, api_key: str, body: dict) -> dict:
    """POST to <base_url>/chat/completions and return the decoded JSON reply."""
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.load(response)


def schema_problems(value: object) -> list[str]:
    """Why `value` does not match SCHEMA; an empty list means it does."""
    if not isinstance(value, dict):
        return [f"expected an object, got {type(value).__name__}"]
    problems = [f"missing field {name!r}" for name in SCHEMA["required"] if name not in value]
    problems += [f"unexpected field {name!r}" for name in value if name not in SCHEMA["properties"]]
    for name in ("evidence_quote", "explanation"):
        if name in value and not isinstance(value[name], str):
            problems.append(f"{name!r} is not a string")
    if "outcome" in value and value["outcome"] not in OUTCOMES:
        problems.append(f"outcome {value['outcome']!r} is not one of {OUTCOMES}")
    return problems


def run_trial(base_url: str, api_key: str, model: str, claim: str) -> dict:
    """One request; returns what happened without raising."""
    started = time.monotonic()
    result = {"claim": claim, "ok": False, "problems": [], "seconds": 0.0, "usage": None}
    try:
        reply = post(base_url, api_key, build_request(model, claim))
        choice = reply["choices"][0]
        result["usage"] = reply.get("usage")
        result["finish_reason"] = choice.get("finish_reason")
        content = choice["message"]["content"]
        parsed = json.loads(content)
        result["parsed"] = parsed
        result["problems"] = schema_problems(parsed)
    except urllib.error.HTTPError as error:
        result["problems"] = [f"HTTP {error.code}: {error.read().decode(errors='replace')[:300]}"]
    except urllib.error.URLError as error:
        result["problems"] = [f"cannot reach the endpoint: {error.reason}"]
    except (KeyError, IndexError, TypeError) as error:
        result["problems"] = [f"unexpected reply shape: {type(error).__name__}: {error}"]
    except json.JSONDecodeError as error:
        result["problems"] = [f"reply is not valid JSON: {error}"]
    except TimeoutError:
        result["problems"] = [f"no reply within {TIMEOUT_SECONDS}s"]
    result["ok"] = not result["problems"] and result.get("finish_reason") != "length"
    result["seconds"] = round(time.monotonic() - started, 2)
    return result


def main() -> int:
    base_url = os.environ.get("KANON_LLM_BASE_URL")
    api_key = os.environ.get("KANON_LLM_API_KEY")
    model = os.environ.get("KANON_LLM_MODEL")
    if not (base_url and api_key and model):
        print(
            "Set KANON_LLM_BASE_URL, KANON_LLM_API_KEY and KANON_LLM_MODEL "
            "(see this file's docstring).",
            file=sys.stderr,
        )
        return 2

    print(f"endpoint: {base_url}\nmodel:    {model}\ntrials:   {len(CASES)}\n")
    results = []
    for claim, expected in CASES:
        result = run_trial(base_url, api_key, model, claim)
        results.append(result)
        outcome = result.get("parsed", {}).get("outcome") if result["ok"] else "-"
        print(
            f"[{'ok' if result['ok'] else 'FAIL'}] {result['seconds']:>5}s  expected={expected:<17}"
            f" got={outcome}  usage={result['usage']}"
        )
        print(f"       claim: {claim}")
        for problem in result["problems"]:
            print(f"       problem: {problem}")

    passed = sum(r["ok"] for r in results)
    print(f"\n{passed}/{len(results)} trials returned schema-valid structured output")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
