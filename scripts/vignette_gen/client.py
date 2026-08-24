from typing import Optional

import openai


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
        return response.choices[0].message.content
