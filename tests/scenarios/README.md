# Scenario-based agent evaluation

End-to-end tests that pit the real LangGraph agent against a deterministic
scripted opponent on the local Pokemon Showdown server, then grade the
agent's chosen move against an expected answer.

## Philosophy: scenarios drive the rebuild (TDD)

We are rebuilding the agent feature by feature. Scenarios are written **ahead
of** the features they need, test-driven-development style: a scenario for a
capability the agent doesn't have yet is expected to **fail** until that
feature lands. A red scenario is a feature you've committed to; a scenario
flipping green is the acceptance test for that feature.

Because grading only checks the move the agent actually played, a scenario has
no dependency on any particular feature — it just asks "did the bot make the
obvious-correct play?" The bot picking the wrong move is a legitimate failing
test, not a broken one.

Start with obviously-correct plays; add subtler ones (speed tiers, prediction,
hazards) as the corresponding features come back online.

## When to use this

- Regression-test prompt or graph changes against known matchups
- Probe a specific weakness (status-move usage, switch timing, KO recognition)
- Pin down the acceptance criteria for a feature before you build it
- Build a curated suite of decision-quality benchmarks

Each scenario costs roughly 1 LLM call per turn (currently just the decide
call) so the suite is not free. Scenarios are marked `scenario` and skipped by
the fast default test run.

## Running

Prereq: the local Showdown container must be up.

```bash
# from repo root
docker compose -f infra/docker-compose.yml up -d

# run only the scenario suite
pytest -m scenario -v

# run a single scenario
pytest tests/test_scenarios.py -k "Lycanroc" -v

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
| `opponent_spreads` | Optional — per-scenario opponent prior overrides. Dormant until the stats feature is rebuilt (see below). |

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

**`switch_match`** — pass if the agent switches on a given turn and the
incoming Pokémon's species is in `expected`. Species ids are lowercased
(see poke-env's `Pokemon.species`).

```yaml
evaluation:
  type: switch_match
  turn: 1
  expected: [heatran]
```

Both are backed by `ActionMatchGrader` in `graders.py` — extend that class
(or add another type to `make_grader`) to cover more action shapes. More
evaluation types (outcome-based, multi-turn, reasoning-judge) are planned.

### Pinning opponent priors (`opponent_spreads`) — not active yet

In non-random formats the agent doesn't see the opponent's EVs/nature/item; it
infers them from `src/data/smogon-common.json` via a stats resolver. That
resolver has **not been rebuilt on this branch yet**. Fixtures may still carry
an `opponent_spreads` block — it is parsed and preserved but currently has no
effect (the runner logs a warning and runs with default priors). The moment
`src.stats` is rebuilt, these overrides activate automatically with no fixture
changes required. See `_build_resolver_override` in `runner.py`.

The block's shape (kept for forward-compatibility):

```yaml
opponent_spreads:
  charizard:
    spreads:
      - name: Choice Specs
        evs: {hp: 0, atk: 0, def: 4, spa: 252, spd: 0, spe: 252}
        ivs: {hp: 31, atk: 31, def: 31, spa: 31, spd: 31, spe: 31}
        nature: timid
        level: 100
        item: choicespecs
        ability: solarpower
        moves: [weatherball, solarbeam, aurasphere, flamethrower]
    default_spread_idx: 0
```

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
only difference from production is the format (`gen9customgame`) and the fixed
teams. `RecordingPlayer` mirrors the base client's graph invocation so it can
capture the played action and the LLM's reasoning without a second LLM call.

## Caveats

- `gen9customgame` means randbats-data and RAG lookups return no data. On this
  branch neither feature exists yet, so this matches the agent's real path.
- Scenarios start at turn 1. To grade a mid-battle decision, lengthen
  `opponent_script` so the scripted moves walk the battle to the target state,
  then set `evaluation.turn` to the turn you care about.
- The agent and scripted opponent each get unique usernames per run, so
  re-runs do not collide on the server.
