"""LLM provider abstraction for Ollama and Anthropic."""

import logging
from abc import ABC, abstractmethod

import ollama
import anthropic

from src.config import Config

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract LLM interface."""

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate response from LLM."""
        pass


class OllamaProvider(LLMProvider):
    """Local Ollama LLM provider."""

    def __init__(self):
        self.client = ollama.Client(host=Config.OLLAMA_BASE_URL)
        self.model = Config.OLLAMA_MODEL

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate response using Ollama."""
        logger.debug(f"Calling Ollama model: {self.model}")

        response = self.client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        return response["message"]["content"]


class AnthropicProvider(LLMProvider):
    """Anthropic Claude LLM provider."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.model = Config.ANTHROPIC_MODEL

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate response using Claude."""
        logger.debug(f"Calling Anthropic model: {self.model}")

        response = self.client.messages.create(
            model=self.model,
            max_tokens=256,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        return response.content[0].text


def get_llm_provider() -> LLMProvider:
    """Factory function to get LLM provider based on config."""
    if Config.LLM_PROVIDER == "ollama":
        return OllamaProvider()
    elif Config.LLM_PROVIDER == "anthropic":
        return AnthropicProvider()
    else:
        raise ValueError(f"Unknown LLM provider: {Config.LLM_PROVIDER}")
