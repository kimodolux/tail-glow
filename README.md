# Tail Glow

AI-powered Pokemon battle agent using LangGraph. Named after the Pokemon move that sharply raises Special Attack.

## Overview

Tail Glow is an autonomous bot that plays competitive Pokemon Random Battles on [Pokemon Showdown](https://pokemonshowdown.com) by:

1. Connecting to Pokemon Showdown via WebSocket
2. Analyzing team composition on turn 1
3. Gathering battle intelligence in parallel (damage, speed, types, effects)
4. Retrieving relevant strategy from RAG system
5. Analysing the above to choose a move
6. Executing moves and switches in real-time

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
cd infra
docker compose up -d --build

# 2. Wait a few seconds for server to start, then run battles
cd ..
uv run python scripts/local_battle.py -n 5
```

This creates two TailGlow bots that battle each other locally. You can watch battles live at http://localhost:8000.

To stop the server:
```bash
cd infra && docker compose down
```

## Architecture

### Multi-Graph System

The bot uses two LangGraph workflows:

**Team Analysis Graph** (Turn 1 only):
```
analyze_team [LLM #1] → END
```

**Battle Graph** (Every turn):
```
format_state → fetch_opponent_sets
                      ↓
     ┌────────────────┼────────────────┐────────────────┐
     ↓                ↓                ↓                ↓
  damage           speed            types           effects   (PARALLEL)
     ↓                ↓                ↓                ↓
     └────────────────┼────────────────┴────────────────┘
                      ↓
              strategy_rag (RAG)
                      ↓
           compile_context [LLM #2]
                      ↓
            decide_action [LLM #3]
                      ↓
              parse_decision
```

### LLM Calls Per Turn

| Call | Node | Purpose |
|------|------|---------|
| #1 | `analyze_team` | Catalog team roles, strengths, weaknesses (turn 1 only) |
| #2 | `compile_context` | Synthesize all gathered info into focused analysis |
| #3 | `decide_action` | Make final move/switch decision |

### Data Gathering Nodes (No LLM)

| Node | Purpose |
|------|---------|
| `format_state` | Format battle state for display |
| `fetch_opponent_sets` | Get possible sets from randbats data |
| `calculate_damage` | Damage calculations for all moves |
| `calculate_speed` | Speed comparison + priority analysis |
| `get_type_matchups` | Offensive/defensive type effectiveness |
| `get_effects` | Relevant item/ability/move effects |
| `lookup_strategy` | RAG retrieval from strategy docs |

## Features

### Damage Calculator

Accurate damage predictions using poke-env's damage calculation:

- Your moves vs opponent (active + bench)
- Opponent's threats to you
- KO probability analysis
- Random Battles accuracy (85 EVs, 31 IVs)

### Speed Calculator

Determines turn order with support for:

- Base speed comparison
- Speed modifiers (paralysis, Choice Scarf, Tailwind, Trick Room)
- Stat boosts
- Priority move detection

### Type Matchup Analysis

Uses poke-env's built-in type chart:

- Offensive matchups (your moves vs them)
- Defensive matchups (their STAB vs you)
- 4x weakness/immunity detection

### Effects Database

Curated competitive item/ability effects:

- Choice items, Life Orb, Focus Sash
- Intimidate, Levitate, Magic Guard
- Priority moves, weather, terrain

### RAG Strategy System

ChromaDB-powered retrieval for strategy documents:

- Index markdown files from `docs/strategy/`
- Query by Pokemon matchup
- Include relevant tips in LLM context

To add strategy documents:
```bash
mkdir -p docs/strategy/pokemon
# Create markdown files following POKEMON_TEMPLATE.md
```

### Battle Chat

The bot sends its reasoning as chat messages during battles, showing its thought process each turn.

### Langfuse Tracing (Optional)

LLM observability via LiteLLM integration:

```bash
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

## Project Structure

```
tail-glow/
├── src/
│   ├── config.py              # Configuration management
│   ├── main.py                # Entry point
│   │
│   ├── agent/
│   │   ├── graph.py           # LangGraph workflows (battle + team analysis)
│   │   ├── state.py           # AgentState TypedDict
│   │   ├── prompts.py         # Legacy prompts (backward compat)
│   │   ├── nodes/             # Individual graph nodes
│   │   │   ├── team_analysis.py   # LLM Call #1
│   │   │   ├── compile.py         # LLM Call #2
│   │   │   ├── decide.py          # LLM Call #3
│   │   │   ├── damage.py
│   │   │   ├── speed.py
│   │   │   ├── types.py
│   │   │   ├── effects.py
│   │   │   ├── fetch_sets.py
│   │   │   ├── strategy_rag.py
│   │   │   ├── format_state.py
│   │   │   └── parse.py
│   │   └── prompts/           # Prompt templates
│   │       ├── team_analysis.py
│   │       ├── compile.py
│   │       └── decision.py
│   │
│   ├── damage_calc/
│   │   └── calculator.py      # Damage calculations
│   │
│   ├── speed/
│   │   └── calculator.py      # Speed comparison logic
│   │
│   ├── data/
│   │   ├── randbats.py        # Random battles set data
│   │   └── effects.py         # Curated competitive effects
│   │
│   ├── rag/
│   │   ├── store.py           # ChromaDB vector store
│   │   └── retriever.py       # Strategy retrieval
│   │
│   ├── showdown/
│   │   ├── client.py          # poke-env Player + turn logic
│   │   └── formatter.py       # Battle state formatter
│   │
│   └── llm/
│       └── provider.py        # LiteLLM abstraction
│
├── docs/
│   └── strategy/              # RAG strategy documents (user-created)
│
├── scripts/
│   └── local_battle.py        # Bot vs bot testing
│
├── infra/
│   ├── showdown.Dockerfile
│   └── docker-compose.yml
│
├── POKEMON_TEMPLATE.md        # Template for strategy docs
└── tests/
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