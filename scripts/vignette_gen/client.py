from typing import Optional

import openai


class GenerationError(Exception):
    pass


class GenerationClient:
    def __init__(self, model: str, api_key: Optional[str] = None):
        self.model = model
        self._client = openai.OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")

    def generate(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        choice = response.choices[0]
        content = choice.message.content
        if not content:
            detail = getattr(choice, "error", None) or getattr(choice, "finish_reason", "unknown")
            raise GenerationError(f"OpenRouter returned no content (detail: {detail!r})")
        return content
