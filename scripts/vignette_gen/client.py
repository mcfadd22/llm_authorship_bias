from typing import Optional

import anthropic


class GenerationClient:
    def __init__(self, model: str, api_key: Optional[str] = None):
        self.model = model
        self._client = anthropic.Anthropic(api_key=api_key)

    def generate(self, prompt: str) -> str:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
