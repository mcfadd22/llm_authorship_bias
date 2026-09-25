import pytest

from elicitation.clients import (
    DETECT_SCHEMA,
    SCALED_SCHEMA,
    AnthropicJudgeClient,
    ElicitationError,
    OpenAIJudgeClient,
    make_client,
)


# ---------------------------------------------------------------- Anthropic

class _Block:
    def __init__(self, type_, **kw):
        self.type = type_
        for k, v in kw.items():
            setattr(self, k, v)


class _Usage:
    def model_dump(self):
        return {"input_tokens": 10, "output_tokens": 5}


class _AnthropicResponse:
    def __init__(self, content, stop_reason="end_turn"):
        self.content = content
        self.stop_reason = stop_reason
        self.model = "claude-opus-5-served"
        self.usage = _Usage()


class _FakeMessages:
    def __init__(self, response):
        self._response = response
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return self._response


class _FakeAnthropic:
    instances = []

    def __init__(self, response):
        self.messages = _FakeMessages(response)


def _patch_anthropic(monkeypatch, response):
    holder = {}

    def factory():
        inst = _FakeAnthropic(response)
        holder["inst"] = inst
        return inst

    monkeypatch.setattr("elicitation.clients.anthropic.Anthropic", factory)
    return holder


def test_anthropic_client_builds_request_and_parses_json(monkeypatch):
    response = _AnthropicResponse([
        _Block("thinking", thinking="hmm"),
        _Block("text", text='{"score": 3, "explanation": "meh"}'),
    ])
    holder = _patch_anthropic(monkeypatch, response)

    client = AnthropicJudgeClient(model="claude-opus-5")
    result = client.ask("the prompt", SCALED_SCHEMA)

    kwargs = holder["inst"].messages.last_kwargs
    assert kwargs["model"] == "claude-opus-5"
    assert kwargs["messages"] == [{"role": "user", "content": "the prompt"}]
    assert kwargs["output_config"]["format"] == {"type": "json_schema", "schema": SCALED_SCHEMA}
    assert "system" not in kwargs

    assert result.data == {"score": 3, "explanation": "meh"}
    assert result.raw_text == '{"score": 3, "explanation": "meh"}'
    assert result.model == "claude-opus-5-served"
    assert result.usage == {"input_tokens": 10, "output_tokens": 5}
    assert result.thinking == "hmm"


def test_anthropic_client_raises_on_refusal(monkeypatch):
    response = _AnthropicResponse([_Block("text", text="")], stop_reason="refusal")
    _patch_anthropic(monkeypatch, response)
    client = AnthropicJudgeClient(model="claude-opus-5")
    with pytest.raises(ElicitationError, match="refusal"):
        client.ask("p", SCALED_SCHEMA)


def test_anthropic_client_raises_when_no_text_block(monkeypatch):
    response = _AnthropicResponse([_Block("thinking", thinking="only")])
    _patch_anthropic(monkeypatch, response)
    client = AnthropicJudgeClient(model="claude-opus-5")
    with pytest.raises(ElicitationError, match="no text"):
        client.ask("p", SCALED_SCHEMA)


# ------------------------------------------------------------------ OpenAI

class _OAIMessage:
    def __init__(self, content, refusal=None):
        self.content = content
        self.refusal = refusal


class _OAIChoice:
    def __init__(self, message, finish_reason="stop"):
        self.message = message
        self.finish_reason = finish_reason


class _OAIResponse:
    def __init__(self, choice):
        self.choices = [choice]
        self.model = "gpt-5-served"
        self.usage = _Usage()


class _OAICompletions:
    def __init__(self, response):
        self._response = response
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return self._response


class _OAIChat:
    def __init__(self, response):
        self.completions = _OAICompletions(response)


class _FakeOpenAI:
    def __init__(self, response):
        self.chat = _OAIChat(response)


def _patch_openai(monkeypatch, response):
    holder = {}

    def factory(**kwargs):
        inst = _FakeOpenAI(response)
        inst.init_kwargs = kwargs
        holder["inst"] = inst
        return inst

    monkeypatch.setattr("elicitation.clients.openai.OpenAI", factory)
    return holder


def test_openai_client_builds_request_and_parses_json(monkeypatch):
    response = _OAIResponse(_OAIChoice(_OAIMessage('{"score": 6, "explanation": "bad"}')))
    holder = _patch_openai(monkeypatch, response)

    client = OpenAIJudgeClient(model="gpt-5")
    result = client.ask("the prompt", SCALED_SCHEMA)

    kwargs = holder["inst"].chat.completions.last_kwargs
    assert kwargs["model"] == "gpt-5"
    assert kwargs["messages"] == [{"role": "user", "content": "the prompt"}]
    rf = kwargs["response_format"]
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["schema"] == SCALED_SCHEMA
    assert rf["json_schema"]["strict"] is True

    assert result.data == {"score": 6, "explanation": "bad"}
    assert result.model == "gpt-5-served"
    assert result.thinking is None


def test_openai_client_raises_on_refusal(monkeypatch):
    response = _OAIResponse(_OAIChoice(_OAIMessage(None, refusal="no")))
    _patch_openai(monkeypatch, response)
    client = OpenAIJudgeClient(model="gpt-5")
    with pytest.raises(ElicitationError, match="refus"):
        client.ask("p", SCALED_SCHEMA)


def test_openai_client_raises_on_empty_content(monkeypatch):
    response = _OAIResponse(_OAIChoice(_OAIMessage(None), finish_reason="length"))
    _patch_openai(monkeypatch, response)
    client = OpenAIJudgeClient(model="gpt-5")
    with pytest.raises(ElicitationError, match="no content"):
        client.ask("p", SCALED_SCHEMA)


def test_detect_schema_shape():
    assert DETECT_SCHEMA["properties"]["has_bug"]["type"] == "boolean"
    assert DETECT_SCHEMA["required"] == ["has_bug", "explanation"]


# --------------------------------------------------------------- factory

def test_make_client_dispatches_on_provider(monkeypatch):
    monkeypatch.setattr("elicitation.clients.anthropic.Anthropic", lambda **kw: object())
    monkeypatch.setattr("elicitation.clients.openai.OpenAI", lambda **kw: object())
    assert isinstance(make_client({"provider": "anthropic", "model": "m"}), AnthropicJudgeClient)
    assert isinstance(make_client({"provider": "openai", "model": "m"}), OpenAIJudgeClient)
    with pytest.raises(ValueError):
        make_client({"provider": "nope", "model": "m"})


def test_make_client_routes_openrouter_through_the_openai_compatible_client(monkeypatch):
    """One OpenRouter key should reach every generator, so an item and its twin
    can share a provider without needing a second vendor account."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")
    captured = {}

    def fake_openai(base_url=None, api_key=None):
        captured["base_url"] = base_url
        captured["api_key"] = api_key
        return object()

    monkeypatch.setattr("elicitation.clients.openai.OpenAI", fake_openai)
    client = make_client({"provider": "openrouter", "model": "google/gemini-2.5-pro"})

    assert client.model == "google/gemini-2.5-pro"
    assert captured["base_url"] == "https://openrouter.ai/api/v1"
    assert captured["api_key"] == "test-key-not-real"


def test_make_client_openrouter_fails_fast_without_a_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        make_client({"provider": "openrouter", "model": "google/gemini-2.5-pro"})
