import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx2
import pytest
from pydantic import ValidationError

from kanon.llm.client import (
    LLMClient,
    LLMError,
    Message,
    OpenAICompatibleClient,
    get_llm_client,
)
from kanon.llm.fake import FakeLLMClient
from kanon.settings import Settings

KEY = "sk-super-secret-key-12345"
BASE = "https://llm.example.test/v1/"
MESSAGES = [Message("system", "Be brief."), Message("user", "Say hello.")]


def completion(content="Hello!", finish="stop"):
    return {
        "id": "x",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content},
                     "finish_reason": finish}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 2},
    }  # fmt: skip


def client_with(handler, **kwargs):
    return OpenAICompatibleClient(
        BASE, KEY, "test-model", transport=httpx2.MockTransport(handler), **kwargs
    )


def answering(status=200, payload=None, text=None):
    def handler(request):
        if text is not None:
            return httpx2.Response(status, text=text)
        return httpx2.Response(status, json=completion() if payload is None else payload)

    return handler


# --- A call with valid credentials returns text --------------------------------------------


def test_returns_the_reply_text():
    assert client_with(answering()).chat(MESSAGES) == "Hello!"


def test_sends_a_standard_chat_completion_request():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json=completion())

    client_with(handler).chat(MESSAGES, max_tokens=50, response_format={"type": "json_schema"})

    assert seen["url"] == "https://llm.example.test/v1/chat/completions"
    assert seen["auth"] == f"Bearer {KEY}"
    assert seen["body"] == {
        "model": "test-model",
        "messages": [
            {"role": "system", "content": "Be brief."},
            {"role": "user", "content": "Say hello."},
        ],
        "max_tokens": 50,
        "response_format": {"type": "json_schema"},
    }


def test_optional_fields_are_omitted_when_unused():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json=completion())

    client_with(handler).chat(MESSAGES)

    assert set(seen["body"]) == {"model", "messages"}


@pytest.mark.parametrize("base", ["https://h/v1", "https://h/v1/", "https://h/v1//"])
def test_base_url_slashes_are_normalised(base):
    urls = []

    def handler(request):
        urls.append(str(request.url))
        return httpx2.Response(200, json=completion())

    OpenAICompatibleClient(base, KEY, "m", transport=httpx2.MockTransport(handler)).chat(MESSAGES)

    assert urls == ["https://h/v1/chat/completions"]


def test_unicode_round_trips():
    client = client_with(answering(payload=completion("Grüße ☕ 🙂")))

    assert client.chat([Message("user", "Größe?")]) == "Grüße ☕ 🙂"


# --- Timeouts and failures raise the domain error ------------------------------------------


def test_every_call_carries_an_explicit_timeout():
    seen = {}

    def handler(request):
        seen["timeout"] = request.extensions["timeout"]
        return httpx2.Response(200, json=completion())

    client_with(handler, timeout=12.5).chat(MESSAGES)

    assert seen["timeout"] == {"connect": 12.5, "read": 12.5, "write": 12.5, "pool": 12.5}


def test_the_default_timeout_is_finite():
    assert 0 < OpenAICompatibleClient(BASE, KEY, "m").timeout < 600


@pytest.mark.parametrize("error", [httpx2.ReadTimeout, httpx2.ConnectTimeout, httpx2.WriteTimeout])
def test_a_timeout_raises_the_domain_error(error):
    def handler(request):
        raise error("slow", request=request)

    with pytest.raises(LLMError, match="did not answer within 7s"):
        client_with(handler, timeout=7).chat(MESSAGES)


def test_a_connection_failure_raises_the_domain_error():
    def handler(request):
        raise httpx2.ConnectError("refused", request=request)

    with pytest.raises(LLMError, match="cannot reach the model endpoint: ConnectError"):
        client_with(handler).chat(MESSAGES)


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 500, 502, 503])
def test_a_non_success_response_raises_the_domain_error(status):
    handler = answering(status, {"error": {"message": "nope, because reasons"}})

    with pytest.raises(LLMError, match=rf"HTTP {status}: nope, because reasons"):
        client_with(handler).chat(MESSAGES)


def test_non_json_error_bodies_are_summarised_and_bounded():
    handler = answering(502, text="<html>" + "bad gateway " * 200 + "</html>")

    with pytest.raises(LLMError) as error:
        client_with(handler).chat(MESSAGES)

    assert "HTTP 502" in str(error.value)
    assert len(str(error.value)) < 400


def test_a_2xx_other_than_200_is_not_treated_as_a_reply():
    with pytest.raises(LLMError, match="HTTP 204"):
        client_with(lambda request: httpx2.Response(204)).chat(MESSAGES)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"choices": []},
        {"choices": [{}]},
        {"choices": [{"message": {}}]},
        {"choices": [{"message": {"content": None}}]},
        {"choices": [{"message": {"content": ""}}]},
        {"choices": [{"message": {"content": ["a", "b"]}}]},
        {"choices": "nope"},
        [1, 2, 3],
    ],
)
def test_an_unusable_reply_raises_the_domain_error(payload):
    with pytest.raises(LLMError, match="unexpected format|no text"):
        client_with(answering(payload=payload)).chat(MESSAGES)


def test_a_reply_that_is_not_json_raises_the_domain_error():
    with pytest.raises(LLMError, match="unexpected format"):
        client_with(answering(text="not json")).chat(MESSAGES)


# --- Real network behaviour ----------------------------------------------------------------


@pytest.fixture
def local_server():
    """A real HTTP server on localhost whose behaviour the test sets."""
    state = {"delay": 0.0, "status": 200, "body": completion(), "requests": []}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            state["requests"].append(dict(self.headers))
            self.rfile.read(int(self.headers["Content-Length"]))
            time.sleep(state["delay"])
            payload = json.dumps(state["body"]).encode()
            self.send_response(state["status"])
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    ).start()
    state["url"] = f"http://127.0.0.1:{server.server_port}/v1"
    yield state
    server.shutdown()


def test_a_slow_server_hits_the_timeout(local_server):
    local_server["delay"] = 1.5
    client = OpenAICompatibleClient(local_server["url"], KEY, "m", timeout=0.2)
    started = time.monotonic()

    with pytest.raises(LLMError, match="did not answer within 0.2s"):
        client.chat(MESSAGES)

    assert time.monotonic() - started < 1.2  # gave up at the timeout, did not wait for the reply


def test_a_real_round_trip(local_server):
    client = OpenAICompatibleClient(local_server["url"], KEY, "m", timeout=5)

    assert client.chat(MESSAGES) == "Hello!"
    assert local_server["requests"][0]["Authorization"] == f"Bearer {KEY}"


def test_nothing_listening_raises_the_domain_error():
    client = OpenAICompatibleClient("http://127.0.0.1:1/v1", KEY, "m", timeout=2)

    with pytest.raises(LLMError, match="cannot reach"):
        client.chat(MESSAGES)


# --- The API key never appears in logs -----------------------------------------------------


def everything_logged(caplog):
    return "\n".join(f"{r.name} {r.getMessage()} {r.__dict__}" for r in caplog.records) + "\n".join(
        record.exc_text or "" for record in caplog.records
    )


def test_the_key_is_not_logged_on_success(local_server, caplog):
    caplog.set_level(logging.DEBUG)

    OpenAICompatibleClient(local_server["url"], KEY, "m", timeout=5).chat(MESSAGES)

    assert caplog.records  # something was logged...
    assert KEY not in everything_logged(caplog)  # ...but never the key


@pytest.mark.parametrize("scenario", ["http_error", "timeout", "unreachable", "bad_reply"])
def test_the_key_is_not_logged_or_raised_on_failure(local_server, caplog, scenario):
    caplog.set_level(logging.DEBUG)
    url, timeout = local_server["url"], 5
    if scenario == "http_error":
        local_server["status"] = 401
        # A provider that echoes the credential back must not leak it through our error.
        local_server["body"] = {"error": {"message": f"invalid key {KEY}"}}
    elif scenario == "timeout":
        local_server["delay"], timeout = 1.0, 0.1
    elif scenario == "unreachable":
        url = "http://127.0.0.1:1/v1"
    else:
        local_server["body"] = {"unexpected": KEY}

    with pytest.raises(LLMError) as error:
        OpenAICompatibleClient(url, KEY, "m", timeout=timeout).chat(MESSAGES)

    assert KEY not in str(error.value)
    assert KEY not in repr(error.value)
    assert KEY not in everything_logged(caplog)
    assert error.value.__cause__ is None or KEY not in str(error.value.__cause__)


def test_the_key_is_not_in_the_client_repr_or_str():
    client = OpenAICompatibleClient(BASE, KEY, "test-model")

    assert KEY not in repr(client) and KEY not in str(client)
    assert "test-model" in repr(client)


def test_log_records_carry_metadata_only(local_server, caplog):
    caplog.set_level(logging.INFO, logger="kanon.llm")

    OpenAICompatibleClient(local_server["url"], KEY, "the-model", timeout=5).chat(
        [Message("user", "a private question")]
    )

    (record,) = [r for r in caplog.records if r.name == "kanon.llm"]
    assert (record.model, record.outcome) == ("the-model", "200")
    assert record.duration_ms >= 0
    assert "a private question" not in everything_logged(caplog)


# --- Configuration -------------------------------------------------------------------------


def test_incomplete_configuration_is_a_domain_error():
    for args in [("", KEY, "m"), (BASE, "", "m"), (BASE, KEY, "")]:
        with pytest.raises(LLMError, match="not fully configured"):
            OpenAICompatibleClient(*args)


def test_get_llm_client_names_the_missing_settings():
    with pytest.raises(LLMError) as error:
        get_llm_client(Settings(database_url="postgresql://x/y"))

    for name in ("KANON_LLM_BASE_URL", "KANON_LLM_API_KEY", "KANON_LLM_MODEL"):
        assert name in str(error.value)


def test_get_llm_client_builds_from_settings():
    settings = Settings(
        database_url="postgresql://x/y",
        llm_base_url=BASE,
        llm_api_key=KEY,
        llm_model="m",
        llm_timeout_seconds=9,
    )

    client = get_llm_client(settings)

    assert (client.model, client.timeout) == ("m", 9)
    assert KEY not in repr(client)


def test_settings_read_the_llm_environment(monkeypatch):
    monkeypatch.setenv("KANON_DATABASE_URL", "postgresql://x/y")
    monkeypatch.setenv("KANON_LLM_BASE_URL", BASE)
    monkeypatch.setenv("KANON_LLM_API_KEY", KEY)
    monkeypatch.setenv("KANON_LLM_MODEL", "claude-opus-5-5")

    settings = Settings()

    assert settings.llm_api_key.get_secret_value() == KEY
    assert settings.llm_model == "claude-opus-5-5"
    assert settings.llm_timeout_seconds == 60


def test_the_key_is_masked_in_the_settings_repr():
    settings = Settings(database_url="postgresql://x/y", llm_api_key=KEY)

    assert KEY not in repr(settings) and KEY not in str(settings)
    assert KEY not in settings.model_dump_json()


def test_blank_llm_settings_mean_unset(monkeypatch):
    # Docker Compose passes unset variables through as empty strings.
    monkeypatch.setenv("KANON_DATABASE_URL", "postgresql://x/y")
    for name in ("BASE_URL", "API_KEY", "MODEL"):
        monkeypatch.setenv(f"KANON_LLM_{name}", "  ")

    settings = Settings()

    assert (settings.llm_base_url, settings.llm_api_key, settings.llm_model) == (None, None, None)


def test_the_app_starts_without_a_model_configured(monkeypatch):
    from kanon.api.app import create_app

    monkeypatch.setenv("KANON_DATABASE_URL", "postgresql://x/y")

    assert create_app() is not None


@pytest.mark.parametrize("url", ["llm.example.test", "ftp://x", "/v1"])
def test_the_base_url_must_be_http(url):
    with pytest.raises(ValidationError, match="http"):
        Settings(database_url="postgresql://x/y", llm_base_url=url)


@pytest.mark.parametrize("timeout", [0, -1])
def test_the_timeout_must_be_positive(timeout):
    with pytest.raises(ValidationError):
        Settings(database_url="postgresql://x/y", llm_timeout_seconds=timeout)


# --- The interface and the fake ------------------------------------------------------------


def shout(client: LLMClient, text: str) -> str:
    """Stands in for any stage of the pipeline: it only knows the interface."""
    return client.chat([Message("user", text)]).upper()


def test_code_written_against_the_interface_runs_on_the_fake():
    fake = FakeLLMClient(["hello", "again"])

    assert shout(fake, "hi") == "HELLO"
    assert shout(fake, "hi") == "AGAIN"
    assert fake.calls[0]["messages"] == [Message("user", "hi")]


def test_the_fake_records_options_and_raises_queued_errors():
    fake = FakeLLMClient([LLMError("down")])

    with pytest.raises(LLMError, match="down"):
        fake.chat(MESSAGES, max_tokens=5, response_format={"type": "json_schema"})

    assert fake.calls[0]["max_tokens"] == 5
    assert fake.calls[0]["response_format"] == {"type": "json_schema"}


def test_the_fake_fails_loudly_when_no_reply_is_queued():
    with pytest.raises(LLMError, match="no reply queued"):
        FakeLLMClient().chat(MESSAGES)


def test_the_real_client_satisfies_the_same_interface():
    client: LLMClient = client_with(answering())

    assert shout(client, "x") == "HELLO!"
