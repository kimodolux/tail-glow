# Tail Glow: Pokémon AI Agent - MVP Technical Specification

**Version:** 0.1.0  
**Last Updated:** December 27, 2024  
**Project Name:** Tail Glow (named after the Pokémon move that sharply raises Special Attack)

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [MVP Scope](#mvp-scope)
3. [System Architecture](#system-architecture)
4. [Technical Stack](#technical-stack)
5. [Project Structure](#project-structure)
6. [Component Specifications](#component-specifications)
7. [Data Models](#data-models)
8. [Setup Instructions](#setup-instructions)
9. [Testing Strategy](#testing-strategy)
10. [Success Criteria](#success-criteria)
11. [Future Extensibility](#future-extensibility)
12. [Development Timeline](#development-timeline)

---

## Project Overview

### Vision

Build an AI agent that plays competitive Pokémon Random Battles autonomously by:
1. Connecting to Pokémon Showdown via WebSocket
2. Processing game state through a LangGraph agent
3. Using LLM reasoning to make strategic decisions
4. Executing moves and switches in real-time

### MVP Goal

Create a minimal viable bot that can complete Pokémon Random Battles without crashing, make valid decisions every turn, and achieve a win rate better than random moves.

### Design Philosophy

- **Simplicity First:** Get the core loop working before adding complexity
- **Extensible Architecture:** Design for easy addition of features (RAG, damage calculator)
- **Local Development:** Zero cost during MVP development
- **Fast Iteration:** Minimal dependencies, quick testing cycles

---

## MVP Scope

### In Scope ✅

- Connect to Pokémon Showdown WebSocket (local or official server)
- Parse battle state from poke-env
- Format game state for LLM consumption
- Use LangGraph to orchestrate decision-making
- Call LLM (Ollama or Claude) for strategic reasoning
- Parse LLM response into valid action
- Execute move/switch on Showdown
- Complete 10+ battles successfully
- Achieve >40% win rate

### Out of Scope ❌

- RAG system (no learning from past battles)
- Battle report generation (no post-game analysis)
- Database persistence (no PostgreSQL)
- Damage calculator tool
- Complex state compression
- Team preview strategy (just pick first Pokémon)
- Cloud deployment
- Monitoring/metrics dashboard
- Advanced multi-step reasoning

### Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Battles Completed** | 10/10 | No crashes, all battles finish |
| **Valid Moves** | 100% | All turns execute valid actions |
| **Win Rate** | >40% | Better than random moves (~50% baseline) |
| **Parse Errors** | <10% | LLM responses correctly parsed |
| **Avg Decision Time** | <5 seconds | Fast enough for Showdown timeout |

---

## System Architecture

### High-Level Architecture
```
┌─────────────────────────────────────────────────┐
│   Pokémon Showdown Server (WebSocket)          │
│   - Local: localhost:8000                       │
│   - Official: sim3.psim.us:8000                 │
└────────────────┬────────────────────────────────┘
                 │ Battle events
                 │ (move, switch, damage, KO, etc.)
                 ▼
┌─────────────────────────────────────────────────┐
│         Showdown Client (poke-env)              │
│  - Maintain WebSocket connection                │
│  - Parse incoming Showdown messages             │
│  - Track battle state (HP, status, field)       │
│  - Execute chosen actions                       │
└────────────────┬────────────────────────────────┘
                 │ Structured game state
                 ▼
┌─────────────────────────────────────────────────┐
│       LangGraph Agent (Decision Engine)         │
│  ┌──────────────────────────────────────────┐  │
│  │ State Graph (3 nodes):                   │  │
│  │                                           │  │
│  │  1. format_state                         │  │
│  │     ↓                                     │  │
│  │  2. decide_action (calls LLM)            │  │
│  │     ↓                                     │  │
│  │  3. parse_decision                       │  │
│  │                                           │  │
│  └──────────────────────────────────────────┘  │
└────────────────┬────────────────────────────────┘
                 │ LLM API call
                 ▼
┌─────────────────────────────────────────────────┐
│          LLM Provider                           │
│  - Ollama (local, free): llama3.1:8b           │
│  - OR Claude Sonnet 4.5 (paid)                 │
│                                                 │
│  Input: Formatted game state                    │
│  Output: "Use Earthquake" / "Switch to M3"     │
└─────────────────────────────────────────────────┘
```

### Data Flow
```
1. Showdown sends battle event
   → "switch|p2a: Weavile|Weavile, L78"
   
2. poke-env parses and updates battle state
   → Battle object with active Pokemon, HP, moves, etc.
   
3. Formatter converts to human-readable text
   → "## Active Pokemon\n- Your Pokemon: Garchomp (72% HP)..."
   
4. LangGraph agent processes state
   → format_state → decide_action → parse_decision
   
5. LLM generates strategic response
   → "ACTION: Earthquake" or "ACTION: Switch to Rotom-Wash"
   
6. Parser extracts action
   → {type: "move", target: "earthquake"}
   
7. Client executes on Showdown
   → battle.choose_move(earthquake)
   
8. Repeat for next turn
```

---

## Technical Stack

### Core Dependencies

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Language** | Python | 3.11+ | Primary language |
| **Agent Framework** | LangGraph | 0.2.x | State graph orchestration |
| **LLM Integration** | LangChain Core | 0.3.x | LLM abstraction |
| **Showdown Client** | poke-env | 0.9.x | WebSocket client & battle state |
| **LLM Provider** | Ollama / Anthropic | Latest | Local or cloud LLM |
| **Dependency Management** | Poetry | 1.7+ | Python package management |

### Development Tools

| Tool | Purpose |
|------|---------|
| **pytest** | Unit and integration testing |
| **black** | Code formatting |
| **ruff** | Linting |
| **VS Code** | IDE |
| **Docker** | Local Showdown server (optional) |

### Why These Choices?

**Python over Go/Rust:**
- LangChain/LangGraph ecosystem is Python-native
- poke-env is the best Showdown client (Python only)
- Faster iteration for spare-time development
- LLM API latency >> Python overhead

**Ollama for MVP:**
- Free, runs locally
- No API costs during development
- Good enough for testing workflow
- Can switch to Claude later for better quality

**poke-env over raw WebSocket:**
- Handles Showdown protocol complexity
- Tracks battle state automatically
- Well-documented, active community
- Saves ~1 week of development time

---

## Project Structure
```
tail-glow/
├── README.md                  # Project overview, quick start
├── pyproject.toml            # Poetry dependencies
├── poetry.lock
├── .env.example              # Environment variables template
├── .gitignore
│
├── docker/
│   ├── docker-compose.yml   # Local Showdown server (optional)
│   └── showdown/
│       └── Dockerfile
│
├── src/
│   ├── __init__.py
│   ├── main.py              # Entry point
│   ├── config.py            # Configuration management
│   │
│   ├── agent/               # LangGraph agent
│   │   ├── __init__.py
│   │   ├── graph.py        # State graph definition
│   │   ├── state.py        # State schemas (Pydantic)
│   │   └── prompts.py      # System/user prompt templates
│   │
│   ├── showdown/            # Pokémon Showdown client
│   │   ├── __init__.py
│   │   ├── client.py       # poke-env player wrapper
│   │   └── formatter.py    # State → LLM format conversion
│   │
│   └── llm/                 # LLM provider abstraction
│       ├── __init__.py
│       └── provider.py     # Ollama/Anthropic providers
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py         # pytest fixtures
│   └── test_formatter.py   # Test state formatting
│
└── scripts/
    └── run_battle.py       # Convenience script to run battles
```

### File Responsibilities

| File | Responsibility | Lines (Est.) |
|------|----------------|--------------|
| `config.py` | Environment-based configuration | ~50 |
| `agent/state.py` | State schema definition | ~30 |
| `agent/graph.py` | LangGraph workflow | ~80 |
| `agent/prompts.py` | LLM prompt templates | ~60 |
| `showdown/formatter.py` | State formatting for LLM | ~100 |
| `showdown/client.py` | poke-env player implementation | ~120 |
| `llm/provider.py` | LLM provider abstraction | ~60 |
| `main.py` | Entry point & orchestration | ~40 |
| **Total** | | **~540 lines** |

---

## Component Specifications

### 1. Configuration (`src/config.py`)

**Purpose:** Centralized configuration via environment variables

**Key Settings:**
```python
class Config:
    # LLM Provider
    LLM_PROVIDER: str = "ollama"  # ollama | anthropic
    
    # Anthropic Settings
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    
    # Ollama Settings  
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"
    
    # Pokémon Showdown
    SHOWDOWN_SERVER: str = "sim3.psim.us:8000"
    SHOWDOWN_USERNAME: str = "TailGlowBot"
    SHOWDOWN_PASSWORD: str = ""  # Optional
    
    # Battle Settings
    BATTLE_FORMAT: str = "gen9randombattle"
    MAX_TURNS: int = 100
    
    # Feature Flags (for extensibility)
    ENABLE_DAMAGE_CALC: bool = False
    ENABLE_RAG: bool = False
    
    # Logging
    LOG_LEVEL: str = "INFO"
```

**Design Principles:**
- All configuration via environment variables
- No hardcoded values
- Easy to switch between local/cloud
- Feature flags for future additions

---

### 2. State Schema (`src/agent/state.py`)

**Purpose:** Define state that flows through LangGraph
```python
from typing import TypedDict, Optional, Literal, Any

class AgentState(TypedDict):
    """State for LangGraph agent - designed for extensibility"""
    
    # Battle context
    battle_tag: str              # Unique battle ID
    battle_object: Optional[Any] # Reference to poke-env Battle
    turn: int                    # Current turn number
    
    # Formatted state for LLM
    formatted_state: str         # Human-readable game state
    
    # Tool results (extensible dictionary)
    tool_results: dict[str, Any] # All tool outputs
    # Example: {"damage_calc": {...}, "rag_retrieval": [...]}
    
    # LLM interaction
    llm_response: str            # Raw LLM output
    
    # Parsed decision
    action_type: Optional[Literal["move", "switch"]]
    action_target: Optional[str] # Move name or Pokemon slot
    
    # Error handling
    error: Optional[str]         # Error message if any
```

**Key Design Decisions:**

1. **`battle_object` field:** Enables tools to access full battle data
2. **`tool_results` dict:** Clean way to add tool outputs without schema changes
3. **`error` field:** Graceful error handling without crashes

---

### 3. State Formatter (`src/showdown/formatter.py`)

**Purpose:** Convert poke-env Battle object to LLM-readable text

**Key Function:**
```python
def format_battle_state(battle: Battle) -> str:
    """
    Format battle state for LLM consumption.
    
    Returns formatted text with:
    - Active Pokemon matchup
    - Available moves
    - Available switches
    - Field conditions
    """
```

**Output Example:**
```
# Turn 5

## Active Pokemon
- **Your Pokemon**: Garchomp (72% HP)
  - Type: Dragon/Ground
  - Status: Healthy
  
- **Opponent Pokemon**: Weavile (100% HP)
  - Type: Dark/Ice
  - Status: Healthy

## Available Moves
1. **Earthquake** (Type: Ground, Power: 100, PP: 16/16)
2. **Stone Edge** (Type: Rock, Power: 100, PP: 8/8)
3. **Outrage** (Type: Dragon, Power: 120, PP: 16/16)
4. **Fire Fang** (Type: Fire, Power: 65, PP: 15/15)

## Available Switches
5. **Rotom-Wash** (45% HP, Type: Electric/Water)
6. **Magnezone** (100% HP, Type: Electric/Steel)

## Field Conditions
- Weather: Rain (3 turns left)
- Hazards on my side: Stealth Rock

**What should you do?** Choose a move (1-4) or switch (5-6).
```

**Design Principles:**
- Human-readable format
- All information needed for decision
- Numbered actions for easy parsing
- MVP: Simple, no compression needed

---

### 4. LLM Provider (`src/llm/provider.py`)

**Purpose:** Abstract interface for different LLM providers

**Abstract Interface:**
```python
class LLMProvider(ABC):
    """Abstract LLM interface"""
    
    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate response from LLM"""
        pass
```

**Implementations:**

1. **OllamaProvider** (Local, Free)
   - Uses Ollama API locally
   - Default model: llama3.1:8b
   - Zero cost, good for testing

2. **AnthropicProvider** (Cloud, Paid)
   - Uses Claude Sonnet 4.5
   - Better reasoning quality
   - ~$0.02-0.05 per battle

**Factory Function:**
```python
def get_llm_provider() -> LLMProvider:
    """Factory function based on config"""
    if Config.LLM_PROVIDER == "ollama":
        return OllamaProvider()
    elif Config.LLM_PROVIDER == "anthropic":
        return AnthropicProvider()
```

---

### 5. System Prompt (`src/agent/prompts.py`)

**Purpose:** Instruct LLM on how to play Pokémon

**Key Elements:**
```python
SYSTEM_PROMPT = """You are a competitive Pokemon battler playing Random Battles.

Your job is to analyze the current battle state and choose the best move or switch.

# RULES
1. You must respond with EXACTLY ONE ACTION
2. Format: "ACTION: [move name]" or "ACTION: Switch to [pokemon name]"
3. Choose from available moves/switches shown
4. Consider type matchups, HP, status conditions
5. Keep response concise

# EXAMPLES
Good:
- "ACTION: Earthquake"
- "ACTION: Switch to Toxapex"

Bad:
- "I think we should..." (too verbose)
- "Use move 1" (must use move name)

# STRATEGY
- Super effective moves are usually good
- Don't stay in at low HP if threatened
- Switching can preserve Pokemon for later
- Pay attention to type matchups

Now analyze the battle and choose your action!"""
```

**Design Philosophy:**
- Clear, direct instructions
- Structured output format for parsing
- Basic strategy tips
- MVP: Simple, room to improve later

---

### 6. LangGraph Agent (`src/agent/graph.py`)

**Purpose:** Orchestrate decision-making flow

**Graph Structure:**
```
format_state → decide_action → parse_decision → END
```

**Node Implementations:**

**Node 1: format_state**
```python
def format_state_node(state: AgentState) -> AgentState:
    """
    Pass-through node for future extensibility.
    In MVP, formatting happens before graph.
    """
    return state
```

**Node 2: decide_action**
```python
def decide_action_node(state: AgentState) -> AgentState:
    """
    Call LLM to decide action.
    Handles errors gracefully.
    """
    llm = get_llm_provider()
    
    try:
        response = llm.generate(
            SYSTEM_PROMPT, 
            state["formatted_state"]
        )
        state["llm_response"] = response
    except Exception as e:
        state["error"] = f"LLM error: {e}"
        state["llm_response"] = "ACTION: Tackle"  # Fallback
    
    return state
```

**Node 3: parse_decision**
```python
def parse_decision_node(state: AgentState) -> AgentState:
    """
    Parse LLM response into structured action.
    Uses regex to extract action.
    """
    response = state["llm_response"]
    
    # Look for "ACTION: [move/switch]"
    match = re.search(r'ACTION:\s*(.+?)(?:\n|$)', response, re.IGNORECASE)
    
    if match:
        action_text = match.group(1).strip()
        
        if "switch" in action_text.lower():
            state["action_type"] = "switch"
            # Extract Pokemon name
            pokemon_match = re.search(r'switch to\s+(\w+)', action_text, re.IGNORECASE)
            state["action_target"] = pokemon_match.group(1).lower() if pokemon_match else None
        else:
            state["action_type"] = "move"
            state["action_target"] = action_text.lower().replace(" ", "")
    else:
        state["error"] = "Could not parse response"
        state["action_type"] = "move"
        state["action_target"] = "tackle"
    
    return state
```

**Graph Creation:**
```python
def create_agent() -> StateGraph:
    """Build the LangGraph state machine"""
    
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("format_state", format_state_node)
    workflow.add_node("decide_action", decide_action_node)
    workflow.add_node("parse_decision", parse_decision_node)
    
    # Define edges (sequential)
    workflow.set_entry_point("format_state")
    workflow.add_edge("format_state", "decide_action")
    workflow.add_edge("decide_action", "parse_decision")
    workflow.add_edge("parse_decision", END)
    
    return workflow.compile()
```

---

### 7. Showdown Client (`src/showdown/client.py`)

**Purpose:** Interface with Pokémon Showdown using poke-env

**Key Class:**
```python
class TailGlowPlayer(Player):
    """
    Custom poke-env player using LangGraph agent.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.agent = create_agent()
        self.battles_played = 0
        self.battles_won = 0
    
    def choose_move(self, battle):
        """
        Called by poke-env when it's our turn.
        
        Flow:
        1. Format battle state
        2. Run through LangGraph agent
        3. Execute decided action
        """
        
        # Format state
        formatted_state = format_battle_state(battle)
        
        # Build initial state
        initial_state = {
            "battle_tag": battle.battle_tag,
            "battle_object": battle,
            "turn": battle.turn,
            "formatted_state": formatted_state,
            "tool_results": {},
            "llm_response": "",
            "action_type": None,
            "action_target": None,
            "error": None
        }
        
        # Run agent
        result = self.agent.invoke(initial_state)
        
        # Execute action
        return self._execute_action(battle, result)
    
    def _execute_action(self, battle, result):
        """Execute the decided action"""
        
        if result["error"]:
            logger.warning(f"Agent error: {result['error']}")
        
        action_type = result["action_type"]
        action_target = result["action_target"]
        
        logger.info(f"Turn {battle.turn}: {action_type} {action_target}")
        
        if action_type == "switch":
            # Find matching Pokemon
            for pokemon in battle.available_switches:
                if pokemon.species.lower() in action_target.lower():
                    return self.create_order(pokemon)
            
            # Fallback: switch to first available
            if battle.available_switches:
                return self.create_order(battle.available_switches[0])
        
        # Default: use a move
        for move in battle.available_moves:
            if move.id.lower() in action_target.lower():
                return self.create_order(move)
        
        # Fallback: use first available move
        if battle.available_moves:
            return self.create_order(battle.available_moves[0])
        
        # Last resort: random
        return self.choose_random_move(battle)
    
    def teampreview(self, battle):
        """Team preview - MVP just picks first Pokemon"""
        return "/team 1"
    
    def on_battle_end(self, battle, won):
        """Track win rate"""
        self.battles_played += 1
        if won:
            self.battles_won += 1
        
        win_rate = self.battles_won / self.battles_played * 100
        logger.info(f"Battle ended: {'WON' if won else 'LOST'} (Win rate: {win_rate:.1f}%)")
```

**Run Battles Function:**
```python
async def run_battles(n_battles: int = 1):
    """Run N battles using the agent"""
    
    # Create player
    player = TailGlowPlayer(
        player_configuration=PlayerConfiguration(
            Config.SHOWDOWN_USERNAME,
            Config.SHOWDOWN_PASSWORD
        ),
        server_configuration=ServerConfiguration(
            *Config.SHOWDOWN_SERVER.split(':')
        ),
        max_concurrent_battles=1
    )
    
    # Play battles
    logger.info(f"Starting {n_battles} battle(s)...")
    await player.ladder(n_battles)
    
    # Print stats
    logger.info(f"Final Stats:")
    logger.info(f"  Battles: {player.battles_played}")
    logger.info(f"  Wins: {player.battles_won}")
    logger.info(f"  Win Rate: {player.battles_won / max(player.battles_played, 1) * 100:.1f}%")
```

---

### 8. Main Entry Point (`src/main.py`)

**Purpose:** Application entry point
```python
import asyncio
import logging
from src.config import Config
from src.showdown.client import run_battles

# Set up logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

async def main():
    """Main entry point"""
    logger.info("Starting Tail Glow MVP...")
    
    # Validate config
    Config.validate()
    
    logger.info(f"LLM Provider: {Config.LLM_PROVIDER}")
    logger.info(f"Showdown Server: {Config.SHOWDOWN_SERVER}")
    
    # Run battles
    await run_battles(n_battles=10)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Data Models

### AgentState (Core State)
```python
class AgentState(TypedDict):
    # Battle context
    battle_tag: str              # "battle-gen9randombattle-12345"
    battle_object: Optional[Any] # poke-env Battle object
    turn: int                    # 1, 2, 3, ...
    
    # LLM input
    formatted_state: str         # Formatted text for LLM
    
    # Tool results
    tool_results: dict[str, Any] # Extensible dict for tools
    
    # LLM output
    llm_response: str            # Raw LLM response
    
    # Parsed decision
    action_type: Optional[Literal["move", "switch"]]
    action_target: Optional[str]
    
    # Error handling
    error: Optional[str]
```

### Config (Configuration)
```python
class Config:
    # LLM
    LLM_PROVIDER: str
    ANTHROPIC_API_KEY: str
    ANTHROPIC_MODEL: str
    OLLAMA_BASE_URL: str
    OLLAMA_MODEL: str
    
    # Showdown
    SHOWDOWN_SERVER: str
    SHOWDOWN_USERNAME: str
    SHOWDOWN_PASSWORD: str
    BATTLE_FORMAT: str
    MAX_TURNS: int
    
    # Features
    ENABLE_DAMAGE_CALC: bool
    ENABLE_RAG: bool
    
    # Logging
    LOG_LEVEL: str
```

---

## Setup Instructions

### Prerequisites

**1. Install Homebrew (macOS)**
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

**2. Install Python 3.11+**
```bash
brew install python@3.11
```

**3. Install Poetry**
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

**4. Install Ollama (for local LLM)**
```bash
brew install ollama

# Start Ollama service
ollama serve

# Download model
ollama pull llama3.1:8b
```

### Project Setup
```bash
# 1. Create project directory
mkdir tail-glow
cd tail-glow

# 2. Initialize Git
git init
echo "__pycache__/
*.py[cod]
.env
.venv/
*.log
.pytest_cache/" > .gitignore

# 3. Initialize Poetry
poetry init --no-interaction

# 4. Add dependencies
poetry add langgraph langchain-core poke-env anthropic ollama python-dotenv
poetry add --group dev pytest pytest-asyncio black ruff

# 5. Create directory structure
mkdir -p src/{agent,showdown,llm}
mkdir -p tests scripts docker/showdown

# 6. Create .env file
cat > .env << 'EOF'
# LLM Provider (ollama or anthropic)
LLM_PROVIDER=ollama

# Anthropic (if using Claude)
ANTHROPIC_API_KEY=

# Ollama settings
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b

# Showdown settings
SHOWDOWN_SERVER=sim3.psim.us:8000
SHOWDOWN_USERNAME=TailGlowBot
SHOWDOWN_PASSWORD=

# Feature flags
ENABLE_DAMAGE_CALC=false
ENABLE_RAG=false

# Logging
LOG_LEVEL=INFO
EOF

# 7. Create .env.example (for Git)
cp .env .env.example
echo "" > .env.example  # Clear sensitive data
```

### First Run
```bash
# 1. Activate Poetry environment
poetry shell

# 2. Verify Ollama is running
ollama list  # Should show llama3.1:8b

# 3. Run first battle
python src/main.py
```

**Expected Output:**
```
2024-12-27 10:00:00 - root - INFO - Starting Tail Glow MVP...
2024-12-27 10:00:00 - root - INFO - LLM Provider: ollama
2024-12-27 10:00:00 - root - INFO - Showdown Server: sim3.psim.us:8000
2024-12-27 10:00:05 - poke_env - INFO - Connected to Showdown
2024-12-27 10:00:10 - src.showdown.client - INFO - Turn 1: move earthquake
...
2024-12-27 10:02:30 - src.showdown.client - INFO - Battle ended: WON (Win rate: 100.0%)
```

---

## Testing Strategy

### Testing Levels

| Level | Scope | Tool | Coverage |
|-------|-------|------|----------|
| **Unit** | Individual functions | pytest | Formatter, parser |
| **Integration** | Graph flow | pytest | Agent graph end-to-end |
| **Manual** | Full battles | CLI | Actual gameplay |

### Unit Tests

**Test Formatter:**
```python
# tests/test_formatter.py

def test_format_battle_state_includes_pokemon_names(mock_battle):
    """Test that formatted state includes Pokemon names"""
    formatted = format_battle_state(mock_battle)
    
    assert "Your Pokemon" in formatted
    assert "Opponent Pokemon" in formatted
    assert "Available Moves" in formatted

def test_format_battle_state_includes_turn_number(mock_battle):
    """Test turn number is included"""
    formatted = format_battle_state(mock_battle)
    assert f"Turn {mock_battle.turn}" in formatted
```

**Run Tests:**
```bash
poetry run pytest tests/ -v
```

### Integration Tests

**Test Graph Execution:**
```python
# tests/integration/test_graph.py

def test_agent_graph_completes(sample_state):
    """Test that agent graph runs without errors"""
    agent = create_agent()
    result = agent.invoke(sample_state)
    
    assert result["action_type"] in ["move", "switch"]
    assert result["action_target"] is not None
```

### Manual Testing Checklist
```bash
# Test 1: Connection
python src/main.py
# ✓ Expected: "Connected to Showdown" in logs

# Test 2: Single Battle
python src/main.py
# ✓ Expected: Battle completes, shows win/loss

# Test 3: Multiple Battles (modify main.py)
# Change: await run_battles(n_battles=10)
python src/main.py
# ✓ Expected: 10 battles complete, win rate printed

# Test 4: LLM Provider Switch
export LLM_PROVIDER=anthropic
export ANTHROPIC_API_KEY=your_key
python src/main.py
# ✓ Expected: Uses Claude instead of Ollama
```

### Debugging Tools

**Enable Debug Logging:**
```bash
export LOG_LEVEL=DEBUG
python src/main.py
```

**Print Full LLM Responses:**
```python
# In decide_action_node():
print(f"LLM Response: {response}")
```

**Inspect Battle State:**
```python
# In choose_move():
print(f"Battle State: {formatted_state}")
```

---

## Success Criteria

### Quantitative Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| **Battles Completed** | 10/10 | Count completed battles |
| **Valid Moves Rate** | 100% | No "invalid move" errors |
| **Win Rate** | >40% | Wins / Total Battles |
| **Parse Success Rate** | >90% | Successful action parsing |
| **Avg Decision Time** | <5s | Time per turn |
| **Crash Rate** | 0% | No unhandled exceptions |

### Qualitative Criteria

- [ ] Bot connects to Showdown successfully
- [ ] Bot makes strategic decisions (not random)
- [ ] Bot handles all battle phases (team preview, moves, switches, KOs)
- [ ] Code is readable and well-organized
- [ ] Easy to run (clear setup instructions)

### MVP Validation Checklist

After running 10 battles, verify:
```
✓ All 10 battles completed without crashes
✓ <10% parsing errors in logs
✓ Win rate >40% (better than random)
✓ Bot responds within Showdown timeout (30s)
✓ No invalid move errors
✓ Clean error handling (graceful fallbacks)
✓ Logs are readable and informative
```

**MVP Success = All criteria met**

---

## Future Extensibility

### Designed for Easy Extension

The MVP architecture is intentionally designed to make adding features easy:

| Feature | Difficulty | Time Estimate | Changes Required |
|---------|-----------|---------------|------------------|
| **Damage Calculator** | ⭐ Easy | 1-2 hours | Add tool node, update state |
| **Battle Logging** | ⭐ Easy | 2-3 hours | Add file writer |
| **Database Layer** | ⭐⭐ Medium | 4-6 hours | Add SQLAlchemy models |
| **RAG System** | ⭐⭐⭐ Medium | 8-12 hours | Add embeddings + retrieval |
| **Battle Reports** | ⭐⭐⭐ Medium | 6-8 hours | Add report generator |
| **Cloud Deployment** | ⭐⭐ Medium | 3-4 hours | Dockerfile + deploy script |

### Extension Points

**1. Adding a Tool (Example: Damage Calculator)**
```python
# Step 1: Add to state
class AgentState(TypedDict):
    # ... existing fields ...
    tool_results: dict[str, Any]  # ← Already present

# Step 2: Create tool function
def calculate_damage(battle: Battle) -> dict:
    # Implementation
    return {"earthquake": {"min": 85, "max": 100}}

# Step 3: Add node to graph
def calculate_damage_node(state: AgentState) -> AgentState:
    battle = state["battle_object"]
    state["tool_results"]["damage_calc"] = calculate_damage(battle)
    return state

# Step 4: Add to graph
workflow.add_node("calculate_damage", calculate_damage_node)
workflow.add_edge("format_state", "calculate_damage")
workflow.add_edge("calculate_damage", "decide_action")
```

**2. Adding RAG (High Level)**
```python
# Step 1: Add database layer
# - PostgreSQL with pgvector
# - SQLAlchemy models

# Step 2: Add embedding generation
def generate_embedding(text: str) -> list[float]:
    # Use sentence-transformers

# Step 3: Add retrieval node
def retrieve_context_node(state: AgentState) -> AgentState:
    query = state["formatted_state"][:200]
    results = vector_search(query, k=3)
    state["tool_results"]["rag_retrieval"] = results
    return state

# Step 4: Add to graph
workflow.add_node("retrieve_context", retrieve_context_node)
workflow.add_edge("format_state", "retrieve_context")
```

**3. Feature Flags Enable/Disable**
```python
# In graph.py
def create_agent() -> StateGraph:
    workflow = StateGraph(AgentState)
    
    workflow.add_node("format_state", format_state_node)
    
    # Conditionally add nodes based on config
    if Config.ENABLE_DAMAGE_CALC:
        workflow.add_node("calculate_damage", calculate_damage_node)
    
    if Config.ENABLE_RAG:
        workflow.add_node("retrieve_context", retrieve_context_node)
    
    workflow.add_node("decide_action", decide_action_node)
    workflow.add_node("parse_decision", parse_decision_node)
    
    # Build edge chain dynamically
    # ...
```

### Design Principles for Extension

1. **State is extensible:** Add fields to `AgentState` without breaking existing code
2. **Nodes are independent:** Each node is self-contained
3. **Graph is composable:** Add nodes by inserting into edge chain
4. **Config-driven features:** Enable/disable via environment variables
5. **Tool results dictionary:** Clean namespace for tool outputs

---

## Development Timeline

### Phase 1: MVP (Week 1-2)

**Goal:** Get core loop working
```
Day 1-2:  Setup project structure, dependencies
Day 3-4:  Implement formatter and LLM provider
Day 5-6:  Implement LangGraph agent
Day 7:    Integrate with poke-env client
Day 8-9:  Testing and bug fixes
Day 10:   Run 10+ battles, validate success criteria
```

**Deliverables:**
- Bot completes 10 battles
- Win rate >40%
- Clean logs, no crashes

### Phase 2: Add Damage Calculator (Week 3)

**Goal:** Improve decision quality with damage calculations
```
Day 11:   Implement damage calculator tool
Day 12:   Add tool node to graph
Day 13:   Update prompts to use damage info
Day 14:   Test and validate improvement
```

**Deliverables:**
- Damage calculations in decision process
- Win rate improvement (target: >50%)

### Phase 3: Add Battle Storage (Week 4)

**Goal:** Prepare for RAG by storing battle data
```
Day 15-16: Set up PostgreSQL locally
Day 17:    Add database models
Day 18:    Add battle storage on completion
Day 19-20: Verify data quality
```

**Deliverables:**
- 50+ battles stored in database
- Data ready for RAG system

### Phase 4: Add RAG System (Week 5-6)

**Goal:** Enable learning from past battles
```
Day 21-22: Implement embedding generation
Day 23-24: Implement retrieval logic
Day 25:    Add retrieval node to graph
Day 26-27: Test RAG retrieval quality
Day 28:    Measure win rate improvement
```

**Deliverables:**
- RAG retrieval working
- Win rate improvement (target: >55%)

### Phase 5: Add Battle Reports (Week 7)

**Goal:** Post-game analysis and learning
```
Day 29-30: Implement report generator
Day 31:    Add report storage
Day 32:    Generate embeddings from reports
Day 33-34: Test full learning loop
Day 35:    Final evaluation
```

**Deliverables:**
- Detailed battle reports
- Full learning loop operational
- Win rate stable >55%

---

## Troubleshooting

### Common Issues

**Issue 1: "Connection refused to Showdown"**
```bash
# Solution: Check server URL
export SHOWDOWN_SERVER=sim3.psim.us:8000  # Official server
# OR
export SHOWDOWN_SERVER=localhost:8000      # Local server

# Test connection
curl http://sim3.psim.us:8000/crossdomain.php
```

**Issue 2: "Ollama connection failed"**
```bash
# Solution: Ensure Ollama is running
ollama serve  # Keep running in separate terminal

# Test Ollama
ollama run llama3.1:8b "Hello"
# Should respond with greeting
```

**Issue 3: "Could not parse LLM response"**
```bash
# Solution: Check LLM output format
# Enable debug logging
export LOG_LEVEL=DEBUG
python src/main.py

# Look for "LLM Response: ..." in logs
# Verify format matches "ACTION: [move name]"

# Alternative: Use Claude (better at following format)
export LLM_PROVIDER=anthropic
export ANTHROPIC_API_KEY=your_key_here
```

**Issue 4: "Import error: No module named 'poke_env'"**
```bash
# Solution: Activate Poetry environment
poetry shell

# Or run with poetry prefix
poetry run python src/main.py
```

**Issue 5: "Battle timeout / No response"**
```bash
# Solution: LLM taking too long
# Use faster model
export OLLAMA_MODEL=llama3.1:8b  # Instead of 70b

# Or increase timeout (if possible)
# Check Showdown timeout settings
```

### Debug Commands
```bash
# Check Python version
python --version  # Should be 3.11+

# Check Poetry installation
poetry --version

# Check dependencies
poetry show

# Check Ollama models
ollama list

# Test LLM directly
ollama run llama3.1:8b "What is Pokemon?"

# Run with verbose logging
LOG_LEVEL=DEBUG python src/main.py

# Run single test
poetry run pytest tests/test_formatter.py -v

# Check poke-env installation
poetry run python -c "import poke_env; print(poke_env.__version__)"
```

---

## Appendix

### Dependencies (pyproject.toml)
```toml
[tool.poetry]
name = "tail-glow"
version = "0.1.0"
description = "AI-powered Pokemon battle agent using LangGraph"
authors = ["Your Name <your.email@example.com>"]
readme = "README.md"
packages = [{include = "src"}]

[tool.poetry.dependencies]
python = "^3.11"
langgraph = "^0.2.0"
langchain-core = "^0.3.0"
poke-env = "^0.9.0"
anthropic = "^0.39.0"
ollama = "^0.4.0"
python-dotenv = "^1.0.0"

[tool.poetry.group.dev.dependencies]
pytest = "^8.0.0"
pytest-asyncio = "^0.24.0"
black = "^24.0.0"
ruff = "^0.7.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

[tool.black]
line-length = 100

[tool.ruff]
line-length = 100

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

### Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `ollama` | LLM provider (ollama, anthropic) |
| `ANTHROPIC_API_KEY` | `""` | Claude API key |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | Claude model |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.1:8b` | Ollama model name |
| `SHOWDOWN_SERVER` | `sim3.psim.us:8000` | Showdown server |
| `SHOWDOWN_USERNAME` | `TailGlowBot` | Bot username |
| `SHOWDOWN_PASSWORD` | `""` | Bot password (optional) |
| `BATTLE_FORMAT` | `gen9randombattle` | Battle format |
| `MAX_TURNS` | `100` | Max turns per battle |
| `ENABLE_DAMAGE_CALC` | `false` | Enable damage calculator |
| `ENABLE_RAG` | `false` | Enable RAG system |
| `LOG_LEVEL` | `INFO` | Logging level |

### Useful Commands
```bash
# Development
poetry shell                    # Activate virtual environment
poetry install                  # Install dependencies
poetry add <package>            # Add new dependency
poetry run python src/main.py   # Run without shell activation

# Testing
poetry run pytest               # Run all tests
poetry run pytest -v            # Verbose output
poetry run pytest tests/test_formatter.py  # Single file
poetry run pytest -k "test_name"  # Single test

# Code Quality
poetry run black src/           # Format code
poetry run ruff check src/      # Lint code
poetry run mypy src/            # Type checking (if added)

# Ollama
ollama serve                    # Start server
ollama list                     # List models
ollama pull llama3.1:8b        # Download model
ollama run llama3.1:8b "test"  # Test model

# Git
git add .
git commit -m "message"
git push
```

### Resources

**Documentation:**
- [LangGraph Docs](https://langchain-ai.github.io/langgraph/)
- [poke-env Docs](https://poke-env.readthedocs.io/)
- [Pokémon Showdown Protocol](https://github.com/smogon/pokemon-showdown/blob/master/PROTOCOL.md)
- [Anthropic API Docs](https://docs.anthropic.com/)
- [Ollama Docs](https://ollama.ai/)

**Community:**
- [Pokémon Showdown Discord](https://discord.gg/pokemonshowdown)
- [LangChain Discord](https://discord.gg/langchain)
- [Smogon Forums](https://www.smogon.com/forums/)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2024-12-27 | Initial MVP specification |

---

**Document Status:** Ready for Implementation  
**Last Review:** December 27, 2024  
**Next Review:** After MVP completion