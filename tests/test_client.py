from vignette_gen.client import GenerationClient


class _FakeMessages:
    def __init__(self):
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs

        class _Content:
            text = '{"code": "def f(x):\\n    return x\\n", "rationale": "none"}'

        class _Response:
            content = [_Content()]

        return _Response()


class _FakeAnthropic:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.messages = _FakeMessages()


def test_generate_calls_sdk_with_model_and_prompt(monkeypatch):
    monkeypatch.setattr("vignette_gen.client.anthropic.Anthropic", _FakeAnthropic)

    client = GenerationClient(model="claude-sonnet-5", api_key="fake-key")
    result = client.generate("hello prompt")

    assert result == '{"code": "def f(x):\\n    return x\\n", "rationale": "none"}'
    assert client._client.messages.last_kwargs["model"] == "claude-sonnet-5"
    assert client._client.messages.last_kwargs["messages"] == [
        {"role": "user", "content": "hello prompt"}
    ]
