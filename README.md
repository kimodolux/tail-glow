# Tail Glow

AI-powered Pokemon battle agent using LangGraph. Named after the Pokemon move that sharply raises Special Attack.

## Overview

Tail Glow is an autonomous bot that plays competitive Pokemon Random Battles on [Pokemon Showdown](https://pokemonshowdown.com) by:

1. Connecting to Pokemon Showdown via WebSocket
2. Processing game state through a LangGraph agent
3. Using LLM reasoning (Ollama or Claude) to make strategic decisions
4. Executing moves and switches in real-time

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- [Ollama](https://ollama.ai/) (for local LLM) or Anthropic API key

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/tail-glow.git
cd tail-glow

# Install dependencies
uv sync --extra dev

# Copy environment template
cp .env.example .env
```

### Configuration

Edit `.env` with your settings:

```bash
# LLM Provider (ollama or anthropic)
LLM_PROVIDER=ollama

# Ollama settings (if using local LLM)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b

# Anthropic settings (if using Claude)
ANTHROPIC_API_KEY=your_key_here
ANTHROPIC_MODEL=claude-sonnet-4-20250514

# Showdown settings
SHOWDOWN_USERNAME=YourBotName
SHOWDOWN_PASSWORD=  # Optional for unregistered accounts
```

### Running the Bot

```bash
# Start Ollama (if using local LLM)
ollama serve
ollama pull llama3.1:8b

# Run 10 battles on official server (default)
uv run python -m src.main

# Run specific number of battles
uv run python -m src.main -n 5
```

## Local Testing (Bot vs Bot)

Run two bots against each other on a local Pokemon Showdown server:

```bash
# 1. Start the local Showdown server (requires Docker)
cd local-showdown-server
docker compose up -d --build

# 2. Wait a few seconds for server to start, then run battles
cd ..
uv run python scripts/local_battle.py -n 5
```

This creates two TailGlow bots that battle each other locally. You can watch battles live at http://localhost:8000.

To stop the server:
```bash
cd local-showdown-server && docker compose down
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│   Pokemon Showdown Server (WebSocket)           │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│         Showdown Client (poke-env)              │
│  - WebSocket connection                         │
│  - Battle state tracking                        │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│       LangGraph Agent (Decision Engine)         │
│  ┌──────────────────────────────────────────┐   │
│  │ format_state → decide_action → parse     │   │
│  └──────────────────────────────────────────┘   │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│          LLM Provider                           │
│  - Ollama (local, free)                         │
│  - Anthropic Claude (cloud)                     │
└─────────────────────────────────────────────────┘
```

## Project Structure

```
tail-glow/
├── src/
│   ├── config.py            # Configuration management
│   ├── main.py              # Entry point
│   ├── agent/
│   │   ├── state.py         # AgentState TypedDict
│   │   ├── prompts.py       # System prompt
│   │   └── graph.py         # LangGraph workflow
│   ├── showdown/
│   │   ├── formatter.py     # Battle state formatter
│   │   └── client.py        # poke-env Player
│   └── llm/
│       └── provider.py      # LLM abstraction
├── scripts/
│   └── local_battle.py      # Bot vs bot testing
├── local-showdown-server/
│   ├── Dockerfile           # Pokemon Showdown server
│   └── docker-compose.yml
└── tests/
    └── test_formatter.py    # Unit tests
```

## Development

```bash
# Run tests
uv run pytest tests/ -v

# Format code
uv run black src/ tests/

# Lint code
uv run ruff check src/ tests/
```

## License

MIT
