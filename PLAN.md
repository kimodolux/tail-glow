# Graph Refactor Implementation Plan

## Overview

Refactor the battle decision graph to include preprocessing nodes that reduce cognitive load on the final decision LLM. The new architecture introduces analysis nodes between data gathering and decision-making, with natural language summaries replacing raw data.

---

## New Architecture

### Graph Flow

```
TURN 1 ONLY:
  analyze_team → create_battle_strategy → END

EVERY TURN:
  format_state
    → fetch_opponent_sets
    → expected_opponent_move (LLM)
    → PARALLEL:
        - best_move_options
        - best_switch_options
        - tera_node (passthrough)
    → decision (simplified prompt)
    → parse_decision
    → battle_memory_update
    → END

BACKGROUND (continuous):
  matchup_calculator (pre-computes Pokemon pair matchups as team is revealed)
```

---

## New Nodes

### 1. Matchup Calculator Node (Background)

**Purpose**: Pre-compute win/lose/draw outcomes for all Pokemon pairs as they are revealed.

**Location**: `src/agent/nodes/matchup_calculator.py`

**Trigger**: Runs in background whenever a new Pokemon is revealed or HP/status changes.

**Input**:
- `battle_object` (our team, revealed opponent Pokemon)
- `opponent_sets` (randbats data for estimation)
- `damage_calc_raw` (existing damage calculations)
- `speed_calc_raw` (speed data)

**Logic**:
- For each pair (our Pokemon A vs their Pokemon B):
  1. Determine who outspeeds
  2. Calculate turns to KO for each side
  3. Simulate the exchange: faster attacks first, check if defender survives, defender retaliates, repeat
  4. Determine winner and remaining HP percentage
- Recalculate when:
  - New Pokemon revealed
  - HP changes significantly
  - Status condition applied
  - Stat boosts/drops occur

**Output** (stored in state):
```python
{
    "matchup_results": {
        ("our_pokemon", "their_pokemon"): {
            "outcome": "win" | "lose" | "draw",
            "our_remaining_hp_percent": float,  # if we win
            "their_remaining_hp_percent": float,  # if they win
            "turns_to_resolve": int,
            "notes": str  # e.g., "We outspeed and 2HKO, they 3HKO"
        }
    }
}
```

**State Addition**:
```python
matchup_results: Optional[dict[tuple[str, str], MatchupOutcome]]
```

---

### 2. Create Battle Strategy Node (Turn 1 Only)

**Purpose**: Create initial battle strategy based on team analysis.

**Location**: `src/agent/nodes/create_strategy.py`

**When**: Runs once on turn 1, after `analyze_team`.

**Input**:
- `team_analysis` (from analyze_team node)
- `battle_object` (our team info)

**LLM Call**: Yes

**Prompt Should Identify**:
- Win conditions (e.g., "Setup Dragonite and sweep", "Wear down their walls with hazards")
- Types not covered well by our team
- Key threats to our setup sweepers
- Type weaknesses across the team (e.g., "3 Pokemon weak to Ground")
- Priority Pokemon to preserve
- Pokemon that are expendable/sack fodder

**Output**:
```python
{
    "battle_strategy": str  # Strategic game plan document
}
```

**State Addition**:
```python
battle_strategy: Optional[str]
```

---

### 3. Expected Opponent Move Node

**Purpose**: Predict what the opponent will do this turn (move or switch).

**Location**: `src/agent/nodes/expected_move.py`

**Position in Graph**: After `fetch_opponent_sets`, before parallel analysis phase.

**Input**:
- `battle_object`
- `opponent_sets`
- `damage_calc_raw` (their moves vs us)
- `speed_calc_raw`
- `battle_memory` (previous turn patterns)

**LLM Call**: Yes

**Prediction Factors**:
- Highest damage move available
- KO potential (if they can KO, likely will)
- Switch signals:
  - We outspeed and can KO them
  - We wall them (low damage + we have recovery)
  - Type disadvantage severe
  - Low HP (may switch to preserve)
- Status moves if they can't threaten KO

**Output**:
```python
{
    "expected_opponent_action": {
        "predictions": [
            {
                "action_type": "move" | "switch",
                "action": str,  # Move name or Pokemon name
                "probability": float,  # 0.0 - 1.0
                "damage_to_us": str,  # e.g., "Pokemon takes ~40% from Earthquake"
                "reasoning": str
            }
        ],  # Top N predictions, ordered by probability
        "summary": str  # NL summary for decision node
    }
}
```

**State Addition**:
```python
expected_opponent_action: Optional[dict]
```

---

### 4. Best Move Options Node

**Purpose**: Rank our available moves with reasoning.

**Location**: `src/agent/nodes/best_moves.py`

**Position in Graph**: Parallel phase (after expected_opponent_move).

**Input**:
- `battle_object`
- `damage_calc_raw` (our moves vs their active, our moves vs their bench)
- `speed_calc_raw`
- `expected_opponent_action`
- `opponent_sets` (for potential switch-ins)

**LLM Call**: No (deterministic ranking)

**Logic**:
1. **If choice-locked**: Return only the locked move with explanation
2. **For each move**, calculate:
   - Damage to active opponent (use damage_calc_raw)
   - KO potential (guaranteed KO, likely KO, chip damage)
   - Damage to potential switch-ins (known bench Pokemon)
   - Accuracy factor (prefer higher accuracy if both KO)
3. **Rank moves** by:
   - KO on active > high damage on active > coverage on switches
   - Tie-breaker: accuracy
4. **For each ranked move**, generate reasoning

**Output**:
```python
{
    "best_moves": {
        "moves": [
            {
                "move": str,
                "rank": int,
                "damage_to_active": str,  # e.g., "87-102% (guaranteed KO)"
                "damage_to_switches": str,  # e.g., "Hits Corviknight for 45%, Ferrothorn for 120%"
                "accuracy": int,
                "reasoning": str
            }
        ],
        "choice_locked": bool,
        "locked_move": Optional[str],
        "summary": str  # NL summary for decision node
    }
}
```

**Example Summary**:
> "Earthquake is a guaranteed KO. Rock Tomb KOs Fearow if they switch. You're choice-locked into Outrage."

**State Addition**:
```python
best_moves: Optional[dict]
```

---

### 5. Best Switch Options Node

**Purpose**: Rank switch options based on survivability against expected move and ability to beat the opponent.

**Location**: `src/agent/nodes/best_switches.py`

**Position in Graph**: Parallel phase (after expected_opponent_move).

**Input**:
- `battle_object`
- `expected_opponent_action` (what move to tank)
- `matchup_results` (from background calculator)
- `damage_calc_raw` (their moves vs our bench)
- Entry hazards on our side

**LLM Call**: No (deterministic ranking)

**Logic**:
1. **For each available switch**:
   - Calculate damage taken from expected opponent move
   - Add entry hazard damage (Stealth Rock, Spikes, Toxic Spikes)
   - Check if survives the switch-in
   - Look up matchup result (can this Pokemon beat theirs?)
2. **Rank by**:
   - Must survive switch-in (eliminate if doesn't)
   - Can win the matchup (from matchup_results)
   - HP remaining after switch higher = better
3. **Generate reasoning** for each option

**Output**:
```python
{
    "best_switches": {
        "switches": [
            {
                "pokemon": str,
                "rank": int,
                "damage_on_switch": str,  # e.g., "Takes 25% from SR + 35% from Earthquake = 60%"
                "survives": bool,
                "matchup_result": str,  # e.g., "Wins with 45% HP remaining"
                "reasoning": str
            }
        ],
        "summary": str  # NL summary for decision node
    }
}
```

**Example Summary**:
> "Corviknight is your best switch - takes 30% on switch-in, wins the matchup with 65% HP. Ferrothorn survives but loses the 1v1."

**State Addition**:
```python
best_switches: Optional[dict]
```

---

### 6. Tera Node (Passthrough)

**Purpose**: Placeholder for future Terastallization analysis.

**Location**: `src/agent/nodes/tera.py`

**Position in Graph**: Parallel phase.

**Input**:
- `battle_object` (track if Tera used by either side)

**Current Implementation**:
- Track Tera availability (has_tera_available for us, opponent_has_tera)
- Return empty analysis

**Output**:
```python
{
    "tera_analysis": {
        "our_tera_available": bool,
        "opponent_tera_available": bool,
        "recommendation": None,  # Future: "Tera to Steel to wall their attacks"
        "summary": "Tera analysis not yet implemented."
    }
}
```

**State Addition**:
```python
tera_analysis: Optional[dict]
```

---

### 7. Battle Memory Update Node

**Purpose**: Track battle history and update strategy based on revealed information.

**Location**: `src/agent/nodes/battle_memory.py`

**Position in Graph**: After `parse_decision` (end of turn).

**Input**:
- `battle_object` (full battle state, previous turns)
- `battle_strategy` (initial strategy from turn 1)
- `battle_log` (previous turns' summary)
- `battle_analysis` (previous strategic analysis)
- `action_type`, `action_target` (what we just chose)

**LLM Call**: Yes (for analysis update)

**Tracking (Deterministic)**:
- Turn-by-turn log: "Turn 3: Our Garchomp used Earthquake. Their Corviknight switched in."
- Fainted Pokemon (ours and theirs)
- Revealed information:
  - Opponent's revealed moves per Pokemon
  - Opponent's revealed items (or deduced: "No Leftovers heal → likely Choice item")
  - Opponent's revealed abilities
- Entry hazards on each side

**Analysis (LLM)**:
- Take full battle log + previous analysis
- Generate updated analysis:
  - Current game state assessment
  - What we've learned about opponent's team
  - How strategy should adapt
  - Updated threat assessment

**Output**:
```python
{
    "battle_log": str,  # Append-only turn summaries
    "battle_analysis": str,  # LLM-generated strategic analysis
    "revealed_sets": {
        "pokemon_name": {
            "revealed_moves": list[str],
            "revealed_item": Optional[str],
            "deduced_item": Optional[str],  # e.g., "Choice Band (no Leftovers recovery)"
            "revealed_ability": Optional[str],
            "fainted": bool
        }
    }
}
```

**State Additions**:
```python
battle_log: Optional[str]
battle_analysis: Optional[str]
revealed_sets: Optional[dict[str, dict]]
```

---

## State Changes Summary

### New State Fields

```python
class AgentState(TypedDict):
    # ... existing fields ...

    # New fields
    battle_strategy: Optional[str]  # Turn 1 strategy document

    matchup_results: Optional[dict]  # Background matchup calculations

    expected_opponent_action: Optional[dict]  # Predicted opponent move/switch

    best_moves: Optional[dict]  # Ranked move options with reasoning

    best_switches: Optional[dict]  # Ranked switch options with reasoning

    tera_analysis: Optional[dict]  # Tera tracking and future recommendations

    battle_log: Optional[str]  # Turn-by-turn history
    battle_analysis: Optional[str]  # Strategic analysis updated each turn
    revealed_sets: Optional[dict]  # Tracked opponent information
```

---

## Prompt Changes

### Decision Node (Simplified)

**Current**: Receives raw damage calcs, speed data, type matchups, effects, strategy context.

**New**: Receives natural language summaries from preprocessing nodes.

**New Prompt Structure**:
```
## Battle State
{formatted_state}

## Speed
{speed_summary}  # e.g., "You don't outspeed. They have priority Aqua Jet."

## Expected Opponent Action
{expected_opponent_action.summary}

## Your Best Moves
{best_moves.summary}
Ranked:
1. {move1} - {reasoning1}
2. {move2} - {reasoning2}
3. {move3} - {reasoning3}

## Your Best Switches
{best_switches.summary}
Ranked:
1. {switch1} - {reasoning1}
2. {switch2} - {reasoning2}

## Battle Context
{battle_analysis}  # Updated strategic context

## Team Strategy
{battle_strategy}  # Original game plan

Available moves: {move_list}
Available switches: {switch_list}
```

---

## New Files to Create

```
src/agent/nodes/
├── matchup_calculator.py    # Background matchup pre-computation
├── create_strategy.py       # Turn 1 battle strategy
├── expected_move.py         # Opponent move prediction (LLM)
├── best_moves.py            # Move ranking (deterministic)
├── best_switches.py         # Switch ranking (deterministic)
├── tera.py                  # Tera passthrough
├── battle_memory.py         # Battle history + analysis (LLM)

src/agent/prompts/
├── create_strategy.py       # Prompt for initial strategy
├── expected_move.py         # Prompt for opponent prediction
├── battle_memory.py         # Prompt for turn analysis
```

---

## Files to Modify

1. **`src/agent/state.py`** - Add new state fields
2. **`src/agent/graph.py`** - Restructure graph with new nodes
3. **`src/agent/nodes/__init__.py`** - Export new nodes
4. **`src/agent/prompts/__init__.py`** - Export new prompts
5. **`src/agent/prompts/decision.py`** - Simplify decision prompt
6. **`src/agent/nodes/decide.py`** - Update to use new summaries

---

## Implementation Order

### Phase 1: State & Infrastructure
1. Update `state.py` with new fields
2. Create `matchup_calculator.py` (background task infrastructure)

### Phase 2: Turn 1 Nodes
3. Create `create_strategy.py` node and prompt
4. Update graph to include create_battle_strategy after analyze_team

### Phase 3: Core Analysis Nodes
5. Create `expected_move.py` node and prompt
6. Create `best_moves.py` node
7. Create `best_switches.py` node
8. Create `tera.py` passthrough node

### Phase 4: Battle Memory
9. Create `battle_memory.py` node and prompt

### Phase 5: Integration
10. Update `graph.py` with new flow
11. Update `decide.py` to consume new summaries
12. Update `decision.py` prompt for simplified input
13. Update `__init__.py` exports

### Phase 6: Testing & Refinement
14. Test full flow
15. Tune prompts based on output quality

---

## Background Matchup Calculator Design

Since this runs continuously and shouldn't block the graph:

**Option: State-based caching with lazy refresh**

```python
class MatchupCache:
    """Stores pre-computed matchup results."""

    def __init__(self):
        self._cache: dict[tuple[str, str], MatchupOutcome] = {}
        self._computation_state: dict[tuple[str, str], str] = {}  # "pending", "complete"

    def get_matchup(self, our_pokemon: str, their_pokemon: str) -> Optional[MatchupOutcome]:
        """Get cached matchup, returns None if not computed."""
        return self._cache.get((our_pokemon, their_pokemon))

    def needs_refresh(self, our_pokemon: str, their_pokemon: str,
                      current_hp: int, current_status: str) -> bool:
        """Check if matchup needs recalculation due to state change."""
        # Compare against stored computation context
        pass

    def compute_matchup(self, our_pokemon: Pokemon, their_pokemon: Pokemon,
                        damage_calc: DamageCalculator, speed_calc: SpeedCalculator) -> MatchupOutcome:
        """Compute and cache a single matchup."""
        pass
```

**Integration**:
- Before the parallel phase, check which matchups are stale
- Compute only stale matchups (incremental)
- `best_switches` node reads from cache, handles missing gracefully

---

## Open Questions for Implementation

1. **Battle object compactness**: Need to inspect `battle_object` to determine if its log is suitable or if we build our own.

2. **LLM provider for new nodes**: Use same provider as decide node, or allow different models for analysis vs decision?

3. **Matchup cache persistence**: Store in state (simpler) or separate cache object (cleaner)?

---

## Summary

| Node | Type | LLM Call | Position |
|------|------|----------|----------|
| create_battle_strategy | New | Yes | Turn 1, after analyze_team |
| matchup_calculator | New | No | Background/incremental |
| expected_opponent_move | New | Yes | After fetch_opponent_sets |
| best_move_options | New | No | Parallel phase |
| best_switch_options | New | No | Parallel phase |
| tera_node | New | No | Parallel phase (passthrough) |
| battle_memory_update | New | Yes | After parse_decision |
| decide_action | Modified | Yes | After parallel phase (simplified prompt) |
