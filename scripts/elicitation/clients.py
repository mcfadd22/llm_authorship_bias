import json
import re
import os
from dataclasses import dataclass
from typing import Dict, Optional, Protocol

import anthropic
import openai


class ElicitationError(Exception):
    pass


SCALED_SCHEMA: Dict = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 1, "maximum": 7, "description": "Integer from 1 to 7."},
        "explanation": {"type": "string", "description": "Your explanation of the score."},
    },
    "required": ["score", "explanation"],
    "additionalProperties": False,
}

FREE_SCHEMA: Dict = {
    "type": "object",
    "properties": {
        "answer": {"type": "string", "description": "Your free-text answer."},
    },
    "required": ["answer"],
    "additionalProperties": False,
}

DETECT_SCHEMA: Dict = {
    "type": "object",
    "properties": {
        "has_bug": {"type": "boolean", "description": "true if the function has a bug."},
        "explanation": {"type": "string", "description": "Your explanation."},
    },
    "required": ["has_bug", "explanation"],
    "additionalProperties": False,
}

MAX_OUTPUT_TOKENS = 16000
# Hard cap for OpenAI-compatible gateways. Under a JSON-schema grammar whitespace is always a
# legal next token, and a model that slips into emitting it never stops; the trickle of bytes
# also keeps the read timeout from firing. Reasoning counts toward this (Qwen3 averages ~1.3k).
OPENAI_COMPAT_MAX_TOKENS = 4096


@dataclass
class JudgeResponse:
    data: Dict
    raw_text: str
    model: str
    usage: Dict
    thinking: Optional[str]
    provider: Optional[str] = None  # serving provider, where the gateway reports one (OpenRouter)


class JudgeClient(Protocol):
    def ask(self, prompt: str, schema: Dict) -> JudgeResponse: ...


def _usage_dict(usage) -> Dict:
    if usage is None:
        return {}
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    return dict(usage)


_FENCE_RE = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.DOTALL)


def _parse(raw_text: str) -> Dict:
    text = raw_text.strip()
    m = _FENCE_RE.match(text)
    if m:
        text = m.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ElicitationError(f"response was not valid JSON: {exc}: {raw_text[:200]!r}") from exc


def _anthropic_schema(schema: Dict) -> Dict:
    """Anthropic's structured output rejects numeric bounds on integers; the orchestrator
    validates the 1-7 range after parsing, so drop them for this provider only."""
    out = json.loads(json.dumps(schema))
    for prop in out.get("properties", {}).values():
        prop.pop("minimum", None)
        prop.pop("maximum", None)
    return out


class AnthropicJudgeClient:
    provider = "anthropic"

    def __init__(self, model: str):
        self.model = model
        self._client = anthropic.Anthropic()

    def ask(self, prompt: str, schema: Dict) -> JudgeResponse:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=MAX_OUTPUT_TOKENS,
            messages=[{"role": "user", "content": prompt}],
            output_config={"format": {"type": "json_schema", "schema": _anthropic_schema(schema)}},
        )
        if response.stop_reason == "refusal":
            raise ElicitationError(f"model returned stop_reason=refusal ({self.model})")
        text_block = next((b for b in response.content if b.type == "text"), None)
        if text_block is None or not text_block.text:
            raise ElicitationError(f"no text block in response (stop_reason={response.stop_reason})")
        thinking = next(
            (b.thinking for b in response.content if b.type == "thinking" and getattr(b, "thinking", "")),
            None,
        )
        return JudgeResponse(
            data=_parse(text_block.text),
            raw_text=text_block.text,
            model=response.model,
            usage=_usage_dict(response.usage),
            thinking=thinking,
        )


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
# Per-request ceiling. The SDK default (10 min, 2 retries) let hung gateway
# connections stall a whole worker pool for hours; a judge call that has not
# returned in 3 min is dead and is better retried.
REQUEST_TIMEOUT_S = 180
SDK_MAX_RETRIES = 2


def _fresh_connection_http_client():
    """An HTTP client that never reuses a connection.

    Pooled keep-alive sockets to the gateway go stale under sustained load; a worker
    that picks one up hangs until the read timeout. Each judge call takes tens of
    seconds, so a new TLS handshake per call costs nothing by comparison.
    """
    import httpx2

    return openai.DefaultHttpxClient(
        limits=httpx2.Limits(max_keepalive_connections=0, max_connections=256),
    )


class OpenAIJudgeClient:
    provider = "openai"

    def __init__(self, model: str, base_url=None, api_key=None, extra_body: Optional[Dict] = None,
                 timeout_s: float = REQUEST_TIMEOUT_S, max_retries: int = SDK_MAX_RETRIES,
                 max_tokens: int = OPENAI_COMPAT_MAX_TOKENS):
        self.model = model
        self._extra_body = extra_body or {}
        self._max_tokens = max_tokens
        # Both None falls back to the SDK defaults: OPENAI_API_KEY and OpenAI's
        # own endpoint. Passing a base_url lets the same client reach any
        # OpenAI-compatible gateway, OpenRouter included.
        self._client = openai.OpenAI(
            base_url=base_url, api_key=api_key,
            timeout=timeout_s, max_retries=max_retries,
            http_client=_fresh_connection_http_client(),
        )

    def ask(self, prompt: str, schema: Dict) -> JudgeResponse:
        # schema=None: no constrained decoding; the prompt must ask for JSON and the reply is parsed.
        fmt = ({"response_format": {"type": "json_schema",
                                    "json_schema": {"name": "judgment", "schema": schema, "strict": True}}}
               if schema is not None else {})
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self._max_tokens,
            **fmt,
            **({"extra_body": self._extra_body} if self._extra_body else {}),
        )
        choice = response.choices[0]
        message = choice.message
        if getattr(message, "refusal", None):
            raise ElicitationError(f"model refused: {message.refusal!r}")
        if not message.content:
            raise ElicitationError(f"no content in response (finish_reason={choice.finish_reason})")
        return JudgeResponse(
            data=_parse(message.content),
            raw_text=message.content,
            model=response.model,
            usage=_usage_dict(response.usage),
            # Thinking, where the server exposes it: vLLM (--reasoning-parser) uses
            # `reasoning_content`, OpenRouter uses `reasoning`; OpenAI itself returns neither.
            thinking=getattr(message, "reasoning_content", None) or getattr(message, "reasoning", None) or None,
            provider=getattr(response, "provider", None),
        )


VLLM_BASE_URL_ENV = "VLLM_BASE_URL"


def make_client(judge: Dict) -> JudgeClient:
    provider = judge["provider"]
    if provider == "anthropic":
        return AnthropicJudgeClient(model=judge["model"])
    if provider == "openai":
        return OpenAIJudgeClient(model=judge["model"],
                                 max_tokens=judge.get("max_tokens", OPENAI_COMPAT_MAX_TOKENS))
    if provider == "openrouter":
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is required for provider 'openrouter'")
        # Optional per-judge routing, e.g. {"provider": {"ignore": [...], "require_parameters": true}}.
        # SDK retries stay on by default: they back off on 429 from an overloaded upstream provider.
        # A judge under an account-level request cap sets "sdk_max_retries": 0 so that every
        # request passes the caller's rate limiter (SDK retries would bypass it, and honour
        # retry-after waits long enough to outlive the per-call deadline).
        return OpenAIJudgeClient(
            model=judge["model"], base_url=OPENROUTER_BASE_URL, api_key=api_key,
            extra_body=judge.get("openrouter"), timeout_s=120,
            max_retries=judge.get("sdk_max_retries", SDK_MAX_RETRIES),
            max_tokens=judge.get("max_tokens", OPENAI_COMPAT_MAX_TOKENS),
        )
    if provider == "vllm":
        # Any OpenAI-compatible server (vLLM, SGLang, ...) reachable at VLLM_BASE_URL,
        # e.g. http://host:8000/v1. Such servers ignore the key; the SDK requires one.
        base_url = os.environ.get(VLLM_BASE_URL_ENV)
        if not base_url:
            raise ValueError(f"{VLLM_BASE_URL_ENV} is required for provider 'vllm'")
        return OpenAIJudgeClient(model=judge["model"], base_url=base_url, api_key="EMPTY")
    raise ValueError(f"unknown provider {provider!r}")
