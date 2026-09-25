import re
from typing import Optional

import openai


class GenerationError(Exception):
    pass


# Reasoning tokens are billed and counted as output. At 2048 a reasoning model
# spent ~1969 of the budget thinking and had ~75 left for the answer, so GPT-5
# returned no content and Gemini returned JSON truncated mid-string. Matches
# MAX_OUTPUT_TOKENS in elicitation/clients.py, raised for the same reason.
MAX_OUTPUT_TOKENS = 16000


_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*\n(.*)\n```$", re.DOTALL)


def _strip_markdown_fence(text: str) -> str:
    match = _CODE_FENCE_RE.match(text.strip())
    if match:
        return match.group(1)
    return text


class GenerationClient:
    def __init__(self, model: str, api_key: Optional[str] = None):
        self.model = model
        self._client = openai.OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")

    def generate(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            max_tokens=MAX_OUTPUT_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        choice = response.choices[0]
        content = choice.message.content
        if not content:
            detail = getattr(choice, "error", None) or getattr(choice, "finish_reason", "unknown")
            raise GenerationError(f"OpenRouter returned no content (detail: {detail!r})")
        if getattr(choice, "finish_reason", None) == "length":
            raise GenerationError(
                f"response truncated at the output cap ({MAX_OUTPUT_TOKENS} tokens); "
                f"content began {content[:80]!r}"
            )
        return _strip_markdown_fence(content)
