"""Configuration management for Tail Glow."""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Centralized configuration via environment variables."""

    # LLM Provider
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")

    # Anthropic Settings
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    # Ollama Settings
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

    # Pokémon Showdown
    SHOWDOWN_SERVER: str = os.getenv("SHOWDOWN_SERVER", "sim3.psim.us:8000")
    SHOWDOWN_USERNAME: str = os.getenv("SHOWDOWN_USERNAME", "TailGlowBot")
    SHOWDOWN_PASSWORD: str = os.getenv("SHOWDOWN_PASSWORD", "")

    # Battle Settings
    BATTLE_FORMAT: str = os.getenv("BATTLE_FORMAT", "gen9randombattle")
    MAX_TURNS: int = int(os.getenv("MAX_TURNS", "100"))

    # Feature Flags (for extensibility)
    ENABLE_DAMAGE_CALC: bool = os.getenv("ENABLE_DAMAGE_CALC", "false").lower() == "true"
    ENABLE_RAG: bool = os.getenv("ENABLE_RAG", "false").lower() == "true"

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def validate(cls) -> None:
        """Validate configuration settings."""
        if cls.LLM_PROVIDER not in ("ollama", "anthropic"):
            raise ValueError(f"Invalid LLM_PROVIDER: {cls.LLM_PROVIDER}")

        if cls.LLM_PROVIDER == "anthropic" and not cls.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY required when using anthropic provider")

        if not cls.SHOWDOWN_USERNAME:
            raise ValueError("SHOWDOWN_USERNAME is required")
