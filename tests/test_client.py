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


def test_generate_strips_markdown_json_fence(monkeypatch):
    class _FencedMessage:
        content = '```json\n{"code": "def f(x):\\n    return x\\n", "rationale": "none"}\n```'

    class _FencedChoice:
        message = _FencedMessage()

    class _FencedResponse:
        choices = [_FencedChoice()]

    class _FencedCompletions:
        def create(self, **kwargs):
            return _FencedResponse()

    class _FencedChat:
        def __init__(self):
            self.completions = _FencedCompletions()

    class _FakeOpenAIFenced:
        def __init__(self, api_key=None, base_url=None):
            self.chat = _FencedChat()

    monkeypatch.setattr("vignette_gen.client.openai.OpenAI", _FakeOpenAIFenced)

    client = GenerationClient(model="anthropic/claude-sonnet-4.5", api_key="fake-key")
    result = client.generate("hello prompt")

    assert result == '{"code": "def f(x):\\n    return x\\n", "rationale": "none"}'
    assert not result.startswith("```")


def test_generate_leaves_unfenced_json_unchanged(monkeypatch):
    class _PlainMessage:
        content = '{"code": "def f(x):\\n    return x\\n", "rationale": "none"}'

    class _PlainChoice:
        message = _PlainMessage()

    class _PlainResponse:
        choices = [_PlainChoice()]

    class _PlainCompletions:
        def create(self, **kwargs):
            return _PlainResponse()

    class _PlainChat:
        def __init__(self):
            self.completions = _PlainCompletions()

    class _FakeOpenAIPlain:
        def __init__(self, api_key=None, base_url=None):
            self.chat = _PlainChat()

    monkeypatch.setattr("vignette_gen.client.openai.OpenAI", _FakeOpenAIPlain)

    client = GenerationClient(model="anthropic/claude-sonnet-4.5", api_key="fake-key")
    result = client.generate("hello prompt")

    assert result == '{"code": "def f(x):\\n    return x\\n", "rationale": "none"}'


def test_generate_strips_fence_from_real_captured_response(monkeypatch):
    import json

    real_response_text = '```json\n{\n  "code": "def compute_average(numbers):\\n    total = 0\\n    for num in numbers:\\n        total += num\\n    average = total / len(numbers)\\n    return average",\n  "rationale": "test"\n}\n```'

    class _RealMessage:
        content = real_response_text

    class _RealChoice:
        message = _RealMessage()

    class _RealResponse:
        choices = [_RealChoice()]

    class _RealCompletions:
        def create(self, **kwargs):
            return _RealResponse()

    class _RealChat:
        def __init__(self):
            self.completions = _RealCompletions()

    class _FakeOpenAIReal:
        def __init__(self, api_key=None, base_url=None):
            self.chat = _RealChat()

    monkeypatch.setattr("vignette_gen.client.openai.OpenAI", _FakeOpenAIReal)

    client = GenerationClient(model="anthropic/claude-sonnet-4.5", api_key="fake-key")
    result = client.generate("hello prompt")

    # Must be directly parseable now - this is the actual point of the fix
    parsed = json.loads(result)
    assert parsed["code"].startswith("def compute_average")
    assert not result.startswith("```")


def _client_returning(monkeypatch, content, finish_reason="stop"):
    class _Message:
        pass

    class _Choice:
        pass

    class _Response:
        pass

    msg, choice, resp = _Message(), _Choice(), _Response()
    msg.content = content
    choice.message = msg
    choice.finish_reason = finish_reason
    resp.choices = [choice]

    class _Completions:
        last_kwargs = None

        def create(self, **kwargs):
            _Completions.last_kwargs = kwargs
            return resp

    class _Chat:
        completions = _Completions()

    class _Fake:
        def __init__(self, api_key=None, base_url=None):
            self.chat = _Chat()

    monkeypatch.setattr("vignette_gen.client.openai.OpenAI", _Fake)
    return GenerationClient(model="m", api_key="k")


def test_generate_raises_when_the_response_is_truncated_at_the_cap(monkeypatch):
    """Reasoning tokens count against max_tokens. At 2048 a reasoning model spent
    ~1969 thinking and returned JSON cut off mid-string, which reached json.loads
    as an unclosed markdown fence and failed with a useless parse error."""
    truncated = '```json\n{\n  "code": "def f(x):\\n    ret'
    client = _client_returning(monkeypatch, truncated, finish_reason="length")
    with pytest.raises(GenerationError, match="truncated at the output cap"):
        client.generate("prompt")


def test_generate_accepts_a_complete_response(monkeypatch):
    client = _client_returning(monkeypatch, '{"code": "c", "rationale": "r"}')
    assert client.generate("prompt") == '{"code": "c", "rationale": "r"}'


def test_generate_sends_the_raised_output_cap(monkeypatch):
    from vignette_gen.client import MAX_OUTPUT_TOKENS

    client = _client_returning(monkeypatch, '{"code": "c", "rationale": "r"}')
    client.generate("prompt")
    assert client._client.chat.completions.last_kwargs["max_tokens"] == MAX_OUTPUT_TOKENS
    assert MAX_OUTPUT_TOKENS >= 16000
