"""LLM provider using LiteLLM for unified model access."""

import logging
import os

import litellm
from litellm import completion

from src.config import Config

logger = logging.getLogger(__name__)

# Configure LiteLLM
litellm.drop_params = True  # Ignore unsupported params per provider

class LLMProvider:
    """Unified LLM provider using LiteLLM."""

    def __init__(self):
        self.model = self._get_model_string()
        self.callbacks = self._setup_callbacks()

    def _get_model_string(self) -> str:
        """Get the LiteLLM model string based on config.

        LiteLLM uses prefixes to identify providers:
        - ollama/model-name for Ollama
        - anthropic/model-name or just model-name for Anthropic
        """
        if Config.LLM_PROVIDER == "ollama":
            # Set base URL for Ollama
            litellm.api_base = Config.OLLAMA_BASE_URL
            return f"ollama/{Config.OLLAMA_MODEL}"
        elif Config.LLM_PROVIDER == "anthropic":
            return Config.ANTHROPIC_MODEL
        else:
            raise ValueError(f"Unknown LLM provider: {Config.LLM_PROVIDER}")

    def _setup_callbacks(self) -> list:
        """Set up Langfuse callback for tracing if configured."""
        callbacks = []

        if Config.LANGFUSE_PUBLIC_KEY and Config.LANGFUSE_SECRET_KEY:
            callbacks.append("langfuse")
            logger.info("Langfuse tracing enabled for LLM calls")

        return callbacks

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        user: str | None = None,
        trace_id: str | None = None,
        generation_name: str | None = None,
        turn: int | None = None,
        battle_tag: str | None = None,
    ) -> str:
        """Generate response from LLM.

        Args:
            system_prompt: The system prompt for the LLM
            user_prompt: The user prompt for the LLM
            user: Optional user identifier for Langfuse tracking (e.g., TailGlow1, TailGlow2)
            trace_id: Optional parent trace ID for nesting this call under a Langfuse trace
            generation_name: Optional name for this generation in Langfuse (e.g., "team_analysis", "decide_action")
            turn: Optional turn number for Langfuse tagging
            battle_tag: Optional battle tag for Langfuse session tracking
        """
        logger.debug(f"Calling LiteLLM model: {self.model}")

        # Build metadata for Langfuse tracing
        metadata = {}
        tags = []

        if user:
            metadata["trace_user_id"] = user
        if trace_id:
            metadata["trace_id"] = trace_id
        if generation_name:
            metadata["generation_name"] = generation_name
        if battle_tag:
            metadata["session_id"] = battle_tag
        if turn is not None:
            metadata["turn"] = turn
            tags.append(f"turn:{turn}")

        if tags:
            metadata["tags"] = tags

        response = completion(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=512,
            success_callback=self.callbacks,
            failure_callback=self.callbacks,
            metadata=metadata if metadata else None,
        )

        return response.choices[0].message.content


def get_llm_provider() -> LLMProvider:
    """Factory function to get LLM provider."""
    return LLMProvider()
