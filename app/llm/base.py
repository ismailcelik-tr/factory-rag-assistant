"""Abstract LLM provider interface.

All LLM calls in this project go through this interface. Concrete
implementations (Ollama, cloud providers) are interchangeable.
"""

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, user_message: str) -> str:
        """Call the model and return the response text.

        Args:
            system_prompt: assembled from base.md + role template
            user_message: context blocks + user question

        Returns:
            Raw model response text (may contain [cite: ...] markers).
        """
