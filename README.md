# Tail Glow

AI-powered Pokemon battle agent using LangGraph. Named after the Pokemon move that sharply raises Special Attack.

## Overview

Tail Glow is an autonomous bot that plays competitive Pokemon Random Battles on [Pokemon Showdown](https://pokemonshowdown.com) by:

1. Connecting to Pokemon Showdown via WebSocket
2. Analyzing team composition on turn 1
3. Maintaining per-battle memory and cached team state across turns
4. Reviewing the previous turn for mistakes and opponent patterns
5. Gathering battle intelligence in parallel (damage, speed, types, effects)
6. Retrieving optional matchup strategy from the RAG system
7. Analyzing the battle plan and choosing a move or switch
8. Executing moves and switches in real-time

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

## Scenario Testing

Scripted scenarios pit the real agent against a deterministic opponent on
the local Showdown server and grade the agent's chosen move against an
expected answer. Useful for regression-testing prompt or graph changes and
probing specific weaknesses (KO recognition, status-move usage, etc.).

```bash
# Start the local server (same one used for bot vs bot)
cd infra && docker compose up -d && cd ..

# Run the scenario suite
uv run pytest -m scenario -v

# Run a single scenario by name
uv run pytest tests/test_scenarios.py -k "Pikachu KOs" -v
```

Scenarios live as YAML files in [tests/scenarios/fixtures/](tests/scenarios/fixtures/);
see [tests/scenarios/README.md](tests/scenarios/README.md) for the author
guide and full file format. Format is `gen9customgame`, so randbats / RAG
lookups will be no-ops during scenario runs.

## Architecture

### Multi-Graph System

The bot uses two LangGraph workflows:

**Team Analysis Graph** (Turn 1 only):
```
analyze_team [LLM #1] → END
```

**Battle Graph** (Every turn):
```
format_state
     ↓
update_game_memory
     ↓
analyze_turn [LLM, skipped on turn 1]
     ↓
update_teams_state
     ↓
fetch_opponent_sets
     ↓
┌──────────────┬──────────────┬──────────────┬──────────────┐
↓              ↓              ↓              ↓
damage         speed          types          effects        (PARALLEL)
↓              ↓              ↓              ↓
└──────────────┴──────────────┴──────────────┴──────────────┘
     ↓
lookup_strategy (optional RAG)
     ↓
analyze_strategy [LLM, static fallback on turn 1]
     ↓
decide_action [LLM]
     ↓
parse_decision
```

### LLM Calls Per Turn

| Call | Node | Purpose |
|------|------|---------|
| #1 | `analyze_team` | Catalog team roles, strengths, weaknesses (turn 1 only) |
| #2 | `analyze_turn` | Review the previous turn for mistakes and lessons (skipped on turn 1) |
| #3 | `analyze_strategy` | Review battle history, strategy docs, and current plan (skips LLM on turn 1) |
| #4 | `decide_action` | Make final move/switch decision using all gathered info |
| Post-game | `analyze_game_end` | Extract matchup learnings and mistakes after the battle ends |

Typical turn 1 uses team analysis plus decision. Later turns usually use turn analysis, strategy analysis, and decision.

### Data Gathering Nodes (No LLM)

| Node | Purpose |
|------|---------|
| `format_state` | Format battle state for display |
| `update_game_memory` | Parse previous-turn events into per-game memory |
| `update_teams_state` | Maintain cached stats, HP, status, boosts, and revealed team info |
| `fetch_opponent_sets` | Get possible sets via the meta-aware [StatsResolver](#stats-resolution-meta-aware) (randbats for random formats, curated spreads otherwise) |
| `calculate_damage` | Damage calculations for all moves |
| `calculate_speed` | Speed comparison + priority analysis |
| `get_type_matchups` | Offensive/defensive type effectiveness |
| `get_effects` | Relevant item/ability/move effects |
| `lookup_strategy` | Optional RAG retrieval from strategy docs and learned outcomes |

## Features

### Damage Calculator

Accurate damage predictions using poke-env's damage calculation:

- Your moves vs opponent (active + bench)
- Opponent's threats to you
- KO probability analysis
- Stats come from the meta-aware [StatsResolver](#stats-resolution-meta-aware) — randbats spreads in Random Battles, curated Smogon priors in OU / customgame

### Speed Calculator

Determines turn order with support for:

- Base speed comparison
- Speed modifiers (paralysis, Choice Scarf, Tailwind, Trick Room)
- Stat boosts
- Priority move detection
- Format-aware stat source (see [Stats Resolution](#stats-resolution-meta-aware))

### Stats Resolution (Meta-Aware)

Different metagames expose different amounts of information about each
Pokemon's spread, so the agent dispatches stat lookups to a
format-appropriate `StatsResolver` at battle start. Every consumer
(`TeamsState`, `DamageCalculator`, `SpeedCalculator`, `fetch_opponent_sets`)
goes through this single seam.

| Format | Resolver | Own team | Opponent |
|---|---|---|---|
| `gen9randombattle`, `gen8randombattle`, etc. | `RandbatsResolver` | randbats spread (85-ish EVs, 31 IVs) | same — randbats spread per species |
| `gen9ou`, `gen9customgame`, anything non-random | `NonRandomResolver` | trusts `pokemon.stats` from the server (exact EVs/nature applied) | curated prior from `src/data/smogon-common.json` → role-based fallback if uncovered |

**Why this matters**: before this seam, every stat fell back to a hardcoded
`[85, 85, 85, 85, 85, 85]` spread when randbats data was missing. That meant
in a custom-team scenario the agent's own 252-SpA Pikachu was modeled as
85-SpA, badly underestimating its own damage.

**Curated priors (`src/data/smogon-common.json`)**: hand-picked common Smogon
sets per Pokemon, used as the opponent's prior in non-random formats.
Schema is documented in the file's `_schema` key. Add a new species:

```json
{
  "pokemon": {
    "garchomp": {
      "spreads": [
        {
          "name": "Swords Dance",
          "evs": {"hp": 0, "atk": 252, "def": 0, "spa": 0, "spd": 4, "spe": 252},
          "ivs": {"hp": 31, "atk": 31, "def": 31, "spa": 31, "spd": 31, "spe": 31},
          "nature": "jolly",
          "level": 100,
          "item": "lifeorb",
          "ability": "roughskin",
          "moves": ["swordsdance", "earthquake", "dragonclaw", "stoneedge"]
        }
      ],
      "default_spread_idx": 0
    }
  }
}
```

For species not in the file, `NonRandomResolver` falls back to a role-based
heuristic: 252 EVs in each of the two highest base stats, 4 in the third,
neutral nature. Better than 85-across-the-board but loses nature-driven
speed tiers — populate the JSON for any Pokemon that matters to a scenario.

**Per-scenario overrides**: scenario tests can pin a specific opponent
spread per fixture via the `opponent_spreads` field in YAML — see
[tests/scenarios/README.md](tests/scenarios/README.md#pinning-opponent-priors).

**Phase 2 hook**: `CommonSpreadsDB.lookup_all(species)` returns the full
candidate list (not just the default), so a future inference engine can
narrow the posterior by eliminating spreads inconsistent with observed
damage rolls. Not implemented yet.

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

ChromaDB-powered retrieval is optional and controlled by `ENABLE_RAG=true`.
When enabled, the retriever can combine static strategy documents with learned
matchup and mistake records:

- Index markdown files from `docs/strategy/`
- Query by Pokemon matchup
- Query learned matchup outcomes and mistake lessons
- Include relevant tips in LLM context

General strategy documents in `docs/strategy/general/` are also loaded directly
into the strategy analysis prompt, even when Chroma RAG is disabled.

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
│   │   ├── nodes/             # Individual graph nodes
│   │   │   ├── damage.py          # Damage calculations
│   │   │   ├── decide.py          # Final decision LLM call
│   │   │   ├── effects.py
│   │   │   ├── fetch_sets.py
│   │   │   ├── strategy_rag.py
│   │   │   ├── strategy_analysis.py
│   │   │   ├── team_analysis.py
│   │   │   ├── teams.py
│   │   │   ├── turn_analysis.py
│   │   │   ├── format_state.py
│   │   │   ├── game_analysis.py
│   │   │   ├── memory.py
│   │   │   ├── speed.py
│   │   │   ├── type_matchups.py
│   │   │   └── parse.py
│   │   └── prompts/           # Prompt templates
│   │       ├── decision.py
│   │       ├── game_analysis.py
│   │       ├── strategy_analysis.py
│   │       ├── team_analysis.py
│   │       └── turn_analysis.py
│   │
│   ├── battle/
│   │   ├── event_parser.py    # Parse poke-env observations
│   │   ├── game_memory.py     # Per-game memory and opponent patterns
│   │   ├── log_formatter.py   # Battle history formatting
│   │   └── teams_state.py     # Cached team state and revealed info
│   │
│   ├── damage_calc/
│   │   └── calculator.py      # Damage calculations (uses StatsResolver)
│   │
│   ├── speed/
│   │   └── calculator.py      # Speed comparison logic (uses StatsResolver)
│   │
│   ├── stats/                 # Meta-aware stat resolution
│   │   ├── resolver.py        # StatsResolver protocol + Randbats/NonRandom impls
│   │   ├── factory.py         # Format → resolver dispatch
│   │   └── common_spreads.py  # Curated JSON loader + role-based fallback
│   │
│   ├── data/
│   │   ├── randbats.py            # Random battles set data
│   │   ├── effects.py             # Curated competitive effects
│   │   └── smogon-common.json     # Curated opponent priors for non-random formats
│   │
│   ├── rag/
│   │   ├── models.py          # Learned matchup/mistake data models
│   │   ├── strategy_loader.py # Direct general strategy loading
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
    ├── scenarios/             # Scripted agent-evaluation scenarios
    │   ├── runner.py          # ScenarioRunner orchestration
    │   ├── graders.py         # Pass/fail evaluation
    │   ├── recording_player.py  # TailGlowPlayer wrapper that captures decisions
    │   ├── scripted_player.py   # Deterministic opponent
    │   └── fixtures/*.yaml    # Author one YAML per scenario
    └── test_scenarios.py      # Pytest entry (gated by `scenario` marker)
```

## Development

```bash
# Fast unit tests (skips scenarios)
uv run pytest -m "not scenario" -v

# Run scenario suite (requires local Showdown server + LLM credentials)
uv run pytest -m scenario -v

# Format code
uv run black src/ tests/

# Lint code
uv run ruff check src/ tests/
```

## License

MIT
