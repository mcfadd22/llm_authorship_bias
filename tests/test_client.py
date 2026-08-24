import pytest

from vignette_gen.client import GenerationClient, GenerationError


class _FakeCompletions:
    def __init__(self):
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs

        class _Message:
            content = '{"code": "def f(x):\\n    return x\\n", "rationale": "none"}'

        class _Choice:
            message = _Message()

        class _Response:
            choices = [_Choice()]

        return _Response()


class _FakeChat:
    def __init__(self):
        self.completions = _FakeCompletions()


class _FakeOpenAI:
    def __init__(self, api_key=None, base_url=None):
        self.api_key = api_key
        self.base_url = base_url
        self.chat = _FakeChat()


def test_generate_calls_sdk_with_model_and_prompt(monkeypatch):
    monkeypatch.setattr("vignette_gen.client.openai.OpenAI", _FakeOpenAI)

    client = GenerationClient(model="anthropic/claude-sonnet-4.5", api_key="fake-key")
    result = client.generate("hello prompt")

    assert result == '{"code": "def f(x):\\n    return x\\n", "rationale": "none"}'
    assert client._client.chat.completions.last_kwargs["model"] == "anthropic/claude-sonnet-4.5"
    assert client._client.chat.completions.last_kwargs["messages"] == [
        {"role": "user", "content": "hello prompt"}
    ]
    assert client._client.base_url == "https://openrouter.ai/api/v1"


def test_generate_raises_generation_error_when_content_is_none(monkeypatch):
    class _EmptyMessage:
        content = None

    class _EmptyChoice:
        message = _EmptyMessage()
        finish_reason = "error"

    class _EmptyResponse:
        choices = [_EmptyChoice()]

    class _EmptyCompletions:
        def create(self, **kwargs):
            return _EmptyResponse()

    class _EmptyChat:
        def __init__(self):
            self.completions = _EmptyCompletions()

    class _FakeOpenAIEmpty:
        def __init__(self, api_key=None, base_url=None):
            self.chat = _EmptyChat()

    monkeypatch.setattr("vignette_gen.client.openai.OpenAI", _FakeOpenAIEmpty)

    client = GenerationClient(model="anthropic/claude-sonnet-4.5", api_key="fake-key")
    with pytest.raises(GenerationError):
        client.generate("hello prompt")
