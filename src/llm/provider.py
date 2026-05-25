"""LLM provider using LiteLLM for unified model access."""

import logging
import os
import threading
import time
from collections import deque

import litellm
from litellm import completion

from src.config import Config

logger = logging.getLogger(__name__)

# Configure LiteLLM
litellm.drop_params = True  # Ignore unsupported params per provider


class _InputTokenRateLimiter:
    """Process-wide sliding-window limiter for hosted LLM input tokens."""

    def __init__(self) -> None:
        self._events: deque[tuple[float, int]] = deque()
        self._lock = threading.Lock()

    def wait_for_capacity(self, estimated_tokens: int, limit_per_minute: int) -> None:
        if estimated_tokens <= 0 or limit_per_minute <= 0:
            return

        # A single oversized prompt cannot be made safe by waiting.
        if estimated_tokens >= limit_per_minute:
            logger.warning(
                "Estimated prompt size (%s input tokens) exceeds configured per-minute limit (%s)",
                estimated_tokens,
                limit_per_minute,
            )
            return

        while True:
            with self._lock:
                now = time.monotonic()
                self._discard_expired(now)
                used = sum(tokens for _, tokens in self._events)

                if used + estimated_tokens <= limit_per_minute:
                    self._events.append((now, estimated_tokens))
                    return

                oldest_ts, _ = self._events[0]
                wait_seconds = max(0.1, 60 - (now - oldest_ts))

            logger.info(
                "LLM input-token throttle sleeping %.1fs (%s/%s TPM used, next prompt ~%s)",
                wait_seconds,
                used,
                limit_per_minute,
                estimated_tokens,
            )
            time.sleep(wait_seconds)

    def _discard_expired(self, now: float) -> None:
        while self._events and now - self._events[0][0] >= 60:
            self._events.popleft()


_input_token_rate_limiter = _InputTokenRateLimiter()


def _estimate_input_tokens(*parts: str) -> int:
    """Estimate input tokens without adding a tokenizer dependency."""
    text = "\n".join(part or "" for part in parts)
    return max(1, len(text) // 4)


def _is_rate_limit_error(error: Exception) -> bool:
    error_name = type(error).__name__.lower()
    error_text = str(error).lower()
    return "ratelimit" in error_name or "rate_limit" in error_text or "rate limit" in error_text


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

        if Config.LLM_RATE_LIMIT_ENABLED and Config.LLM_PROVIDER == "anthropic":
            estimated_input_tokens = _estimate_input_tokens(system_prompt, user_prompt)
            _input_token_rate_limiter.wait_for_capacity(
                estimated_input_tokens,
                Config.LLM_INPUT_TOKENS_PER_MINUTE,
            )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        last_error = None
        for attempt in range(Config.LLM_RATE_LIMIT_RETRIES + 1):
            try:
                response = completion(
                    model=self.model,
                    messages=messages,
                    max_tokens=512,
                    success_callback=self.callbacks,
                    failure_callback=self.callbacks,
                    metadata=metadata if metadata else None,
                )
                return response.choices[0].message.content
            except Exception as e:
                last_error = e
                if not _is_rate_limit_error(e) or attempt >= Config.LLM_RATE_LIMIT_RETRIES:
                    raise

                logger.warning(
                    "LLM rate limit hit; retrying in %.1fs (attempt %s/%s)",
                    Config.LLM_RATE_LIMIT_RETRY_DELAY_SECONDS,
                    attempt + 1,
                    Config.LLM_RATE_LIMIT_RETRIES,
                )
                time.sleep(Config.LLM_RATE_LIMIT_RETRY_DELAY_SECONDS)

        raise last_error


def get_llm_provider() -> LLMProvider:
    """Factory function to get LLM provider."""
    return LLMProvider()
