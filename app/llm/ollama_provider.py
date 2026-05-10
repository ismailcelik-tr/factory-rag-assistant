"""Ollama LLM provider — calls /api/chat with stream=false.

Uses httpx directly (no LangChain) as decided in OD-006.
Timeout is 120 s to accommodate slower local hardware.
"""

import httpx

from app.config import settings
from app.llm.base import LLMProvider


class OllamaProvider(LLMProvider):
    def generate(self, system_prompt: str, user_message: str) -> str:
        payload = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "options": {
                "temperature": settings.llm_temperature,
                "num_predict": settings.llm_max_tokens,
            },
            "stream": False,
        }
        response = httpx.post(
            f"{settings.ollama_base_url}/api/chat",
            json=payload,
            timeout=120.0,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]
