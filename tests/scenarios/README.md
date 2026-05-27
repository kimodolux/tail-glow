# Scenario-based agent evaluation

End-to-end tests that pit the real LangGraph agent against a deterministic
scripted opponent on the local Pokemon Showdown server, then grade the
agent's chosen move against an expected answer.

## When to use this

- Regression-test prompt or graph changes against known matchups
- Probe a specific weakness (status-move usage, switch timing, KO recognition)
- Build a curated suite of decision-quality benchmarks

Each scenario costs roughly 3 LLM calls (turn-1 team analysis + predict +
decide) so the suite is not free. Scenarios are marked `scenario` and skipped
by the fast default test run.

## Running

Prereq: the local Showdown container must be up.

```bash
# from repo root
docker compose -f infra/docker-compose.yml up -d

# run only the scenario suite
pytest -m scenario -v

# run a single scenario
pytest tests/test_scenarios.py -k "Pikachu KOs" -v

# everything except scenarios (fast unit tests)
pytest -m "not scenario"
```

## Authoring a scenario

Drop a YAML file into `tests/scenarios/fixtures/`. Required fields:

| field | meaning |
|---|---|
| `name` | Human-readable identifier (shown in pytest output) |
| `player_team` | Showdown export format — the agent's team |
| `opponent_team` | Showdown export format — the scripted opponent's team |
| `opponent_script` | List of move ids (lowercased, no spaces) the opponent plays in order. If exhausted or unavailable, falls back to the first available move. |
| `evaluation` | Grading config — see below |

Get the Showdown export string from the Teambuilder on
play.pokemonshowdown.com → Teambuilder → "Import/Export".

### Evaluation types

**`move_match`** — pass if the agent's move on a given turn is in `expected`.

```yaml
evaluation:
  type: move_match
  turn: 1
  expected: [thunderbolt, thunder]   # any match passes
```

More evaluation types (outcome-based, multi-turn, reasoning-judge) are
planned — see the project plan for the upgrade path.

## How it works

```
ScenarioRunner
  ├── builds ConstantTeambuilder from each team string
  ├── spins up RecordingPlayer (real TailGlowPlayer + decision capture)
  ├── spins up ScriptedPlayer (deterministic opponent)
  ├── runs a single battle via battle_against()
  └── grades captured_decisions against evaluation criteria
```

The agent runs unmodified — same graph, same prompts, same LLM provider. The
only difference from production is the format (`gen9customgame`) and the
fixed teams.

## Caveats

- `gen9customgame` means randbats-data lookups and RAG strategy lookups return
  no data. This mirrors the agent's degraded path; if a scenario relies on
  randbats inference it will not exercise that code.
- Scenarios start at turn 1. To grade a mid-battle decision, lengthen
  `opponent_script` so the scripted moves walk the battle to the target
  state, then set `evaluation.turn` to the turn you care about.
- The agent and scripted opponent each get unique usernames per run, so
  re-runs do not collide on the server.
