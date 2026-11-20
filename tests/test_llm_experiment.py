"""Tests the experiment script against a local fake endpoint.

This proves the script sends the right request and judges replies correctly. It says nothing about
any real model: that needs the live run described in ADR-003.
"""

import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "llm_structured_output_experiment.py"
spec = importlib.util.spec_from_file_location("llm_experiment", SCRIPT)
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)

VALID = {"outcome": "contradiction", "evidence_quote": "30 days", "explanation": "differs"}


def reply(content, finish="stop", usage=None):
    return {
        "choices": [
            {"message": {"role": "assistant", "content": content}, "finish_reason": finish}
        ],
        "usage": usage or {"prompt_tokens": 100, "completion_tokens": 20},
    }


@pytest.fixture
def fake_endpoint():
    """A local OpenAI-compatible server whose next answers the test controls."""
    state = {"requests": [], "answers": [], "default": (200, reply(json.dumps(VALID)))}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["requests"].append(
                {"path": self.path, "headers": dict(self.headers), "body": body}
            )
            status, payload = state["answers"].pop(0) if state["answers"] else state["default"]
            data = json.dumps(payload).encode() if not isinstance(payload, bytes) else payload
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    state["url"] = f"http://127.0.0.1:{server.server_port}/v1/"
    yield state
    server.shutdown()


def configure(monkeypatch, url):
    monkeypatch.setenv("KANON_LLM_BASE_URL", url)
    monkeypatch.setenv("KANON_LLM_API_KEY", "sk-secret-test-key")
    monkeypatch.setenv("KANON_LLM_MODEL", "test-model")


def test_request_shape(fake_endpoint, monkeypatch):
    configure(monkeypatch, fake_endpoint["url"])

    assert experiment.main() == 0

    first = fake_endpoint["requests"][0]
    assert first["path"] == "/v1/chat/completions"
    assert first["headers"]["Authorization"] == "Bearer sk-secret-test-key"
    body = first["body"]
    assert body["model"] == "test-model"
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["response_format"]["json_schema"]["schema"]["additionalProperties"] is False
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert len(fake_endpoint["requests"]) == len(experiment.CASES)


def test_the_api_key_is_never_printed(fake_endpoint, monkeypatch, capsys):
    configure(monkeypatch, fake_endpoint["url"])
    fake_endpoint["default"] = (401, {"error": {"message": "bad key"}})

    experiment.main()

    captured = capsys.readouterr()
    assert "sk-secret-test-key" not in captured.out + captured.err


def test_missing_configuration_is_a_usage_error(monkeypatch, capsys):
    for name in ("KANON_LLM_BASE_URL", "KANON_LLM_API_KEY", "KANON_LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)

    assert experiment.main() == 2
    assert "KANON_LLM_BASE_URL" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("content", "finish", "fragment"),
    [
        ("not json at all", "stop", "not valid JSON"),
        (json.dumps({"outcome": "contradiction"}), "stop", "missing field"),
        (json.dumps({**VALID, "extra": 1}), "stop", "unexpected field"),
        (json.dumps({**VALID, "outcome": "maybe"}), "stop", "not one of"),
        (json.dumps({**VALID, "explanation": 5}), "stop", "not a string"),
        (json.dumps([VALID]), "stop", "expected an object"),
        ("```json\n" + json.dumps(VALID) + "\n```", "stop", "not valid JSON"),
        (json.dumps(VALID)[:20], "length", "not valid JSON"),
    ],
)
def test_invalid_replies_fail_the_trial(fake_endpoint, monkeypatch, content, finish, fragment):
    fake_endpoint["default"] = (200, reply(content, finish))

    result = experiment.run_trial(fake_endpoint["url"], "k", "m", "a claim")

    assert result["ok"] is False
    assert fragment in " ".join(result["problems"])


def test_a_reply_cut_off_by_the_token_limit_fails_even_if_it_parses(fake_endpoint):
    fake_endpoint["default"] = (200, reply(json.dumps(VALID), finish="length"))

    assert experiment.run_trial(fake_endpoint["url"], "k", "m", "c")["ok"] is False


def test_http_errors_are_reported_not_raised(fake_endpoint):
    fake_endpoint["default"] = (429, {"error": {"message": "slow down"}})

    result = experiment.run_trial(fake_endpoint["url"], "k", "m", "c")

    assert result["ok"] is False and "HTTP 429" in result["problems"][0]


def test_an_unreachable_endpoint_is_reported_not_raised():
    result = experiment.run_trial("http://127.0.0.1:1/v1/", "k", "m", "c")

    assert result["ok"] is False and "cannot reach" in result["problems"][0]


def test_an_unexpected_reply_shape_is_reported(fake_endpoint):
    fake_endpoint["default"] = (200, {"unexpected": True})

    result = experiment.run_trial(fake_endpoint["url"], "k", "m", "c")

    assert result["ok"] is False and "unexpected reply shape" in result["problems"][0]


def test_exit_code_is_one_if_any_trial_fails(fake_endpoint, monkeypatch):
    configure(monkeypatch, fake_endpoint["url"])
    fake_endpoint["answers"] = [(200, reply("garbage"))]

    assert experiment.main() == 1


def test_a_valid_reply_passes_and_usage_is_captured(fake_endpoint):
    result = experiment.run_trial(fake_endpoint["url"], "k", "m", "c")

    assert result["ok"] and result["parsed"] == VALID
    assert result["usage"]["prompt_tokens"] == 100


def test_all_four_scope_outcomes_are_allowed():
    assert experiment.OUTCOMES == ["contradiction", "no_contradiction", "uncertain", "not_covered"]
