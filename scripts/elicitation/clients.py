import json
from dataclasses import dataclass
from typing import Dict, Optional, Protocol

import anthropic
import openai


class ElicitationError(Exception):
    pass


SCALED_SCHEMA: Dict = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "description": "Integer from 1 to 7."},
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


@dataclass
class JudgeResponse:
    data: Dict
    raw_text: str
    model: str
    usage: Dict
    thinking: Optional[str]


class JudgeClient(Protocol):
    def ask(self, prompt: str, schema: Dict) -> JudgeResponse: ...


def _usage_dict(usage) -> Dict:
    if usage is None:
        return {}
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    return dict(usage)


def _parse(raw_text: str) -> Dict:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ElicitationError(f"response was not valid JSON: {exc}: {raw_text[:200]!r}") from exc


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
            output_config={"format": {"type": "json_schema", "schema": schema}},
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


class OpenAIJudgeClient:
    provider = "openai"

    def __init__(self, model: str):
        self.model = model
        self._client = openai.OpenAI()

    def ask(self, prompt: str, schema: Dict) -> JudgeResponse:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "judgment", "schema": schema, "strict": True},
            },
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
            thinking=None,
        )


def make_client(judge: Dict) -> JudgeClient:
    provider = judge["provider"]
    if provider == "anthropic":
        return AnthropicJudgeClient(model=judge["model"])
    if provider == "openai":
        return OpenAIJudgeClient(model=judge["model"])
    raise ValueError(f"unknown provider {provider!r}")
