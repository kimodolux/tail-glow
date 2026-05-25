"""Per-turn dynamic mechanics context.

Each chunk in `docs/strategy/general/mechanics/` declares:
  - keywords:    substrings that, if present in the effects analysis text,
                 cause the chunk to be included
  - triggers:    poke-env enum values (weather / field / side_condition)
                 that, if active in the battle, also cause inclusion

A chunk is included if EITHER its keywords match OR its triggers match.
This lets us drop the always-on 275-line mechanics dump and only feed the
LLM the sections actually relevant to this turn's matchup.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MECHANICS_DIR = Path(__file__).parent.parent.parent / "docs" / "strategy" / "general" / "mechanics"


@dataclass(frozen=True)
class MechanicsChunk:
    name: str
    keywords: tuple[str, ...]
    weather_triggers: frozenset[str]
    field_triggers: frozenset[str]
    side_condition_triggers: frozenset[str]
    body: str


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Tiny YAML-ish frontmatter parser.

    Supports the subset we need: top-level keys with list or nested-list values.
    Avoids pulling in PyYAML for this small use case.
    """
    if not text.startswith("---"):
        return {}, text

    end = text.find("\n---", 3)
    if end == -1:
        return {}, text

    header = text[3:end].strip()
    body = text[end + 4 :].lstrip("\n")

    meta: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in header.splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        if indent == 0 and ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                meta[key] = [v.strip() for v in value[1:-1].split(",") if v.strip()]
                current_key = None
            elif value == "":
                meta[key] = {}
                current_key = key
            else:
                meta[key] = value
                current_key = None
        elif indent > 0 and current_key and ":" in stripped:
            sub_key, _, sub_value = stripped.partition(":")
            sub_key = sub_key.strip()
            sub_value = sub_value.strip()
            if sub_value.startswith("[") and sub_value.endswith("]"):
                meta[current_key][sub_key] = [
                    v.strip() for v in sub_value[1:-1].split(",") if v.strip()
                ]
            else:
                meta[current_key][sub_key] = sub_value

    return meta, body


def _build_chunk(path: Path) -> MechanicsChunk | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning(f"Could not read mechanics chunk {path.name}: {exc}")
        return None

    meta, body = _parse_frontmatter(text)
    keywords = tuple(k.lower() for k in meta.get("keywords", []))
    triggers = meta.get("triggers", {}) or {}

    return MechanicsChunk(
        name=path.stem,
        keywords=keywords,
        weather_triggers=frozenset(triggers.get("weather", [])),
        field_triggers=frozenset(triggers.get("field", [])),
        side_condition_triggers=frozenset(triggers.get("side_condition", [])),
        body=body.strip(),
    )


@lru_cache(maxsize=1)
def load_mechanics_chunks() -> tuple[MechanicsChunk, ...]:
    """Load all mechanics chunks once and cache."""
    if not MECHANICS_DIR.exists():
        logger.warning(f"Mechanics chunks directory not found: {MECHANICS_DIR}")
        return ()

    chunks = []
    for path in sorted(MECHANICS_DIR.glob("*.md")):
        chunk = _build_chunk(path)
        if chunk:
            chunks.append(chunk)
    logger.debug(f"Loaded {len(chunks)} mechanics chunks")
    return tuple(chunks)


def clear_mechanics_cache() -> None:
    load_mechanics_chunks.cache_clear()


def _active_battle_state(battle) -> tuple[set[str], set[str], set[str]]:
    """Extract weather / field / side-condition enum names from a poke-env Battle."""
    weather_names: set[str] = set()
    field_names: set[str] = set()
    side_names: set[str] = set()

    if battle is None:
        return weather_names, field_names, side_names

    for w in getattr(battle, "weather", {}) or {}:
        name = getattr(w, "name", None)
        if name:
            weather_names.add(name)

    for f in getattr(battle, "fields", {}) or {}:
        name = getattr(f, "name", None)
        if name:
            field_names.add(name)

    for source in ("side_conditions", "opponent_side_conditions"):
        for sc in getattr(battle, source, {}) or {}:
            name = getattr(sc, "name", None)
            if name:
                side_names.add(name)

    return weather_names, field_names, side_names


def _chunk_matches(
    chunk: MechanicsChunk,
    effects_text_lower: str,
    weather: set[str],
    fields: set[str],
    side_conditions: set[str],
) -> bool:
    if chunk.weather_triggers & weather:
        return True
    if chunk.field_triggers & fields:
        return True
    if chunk.side_condition_triggers & side_conditions:
        return True
    if effects_text_lower and any(kw in effects_text_lower for kw in chunk.keywords):
        return True
    return False


def resolve_mechanics(effects_analysis: str | None, battle) -> str:
    """Return a markdown section with only the mechanics chunks relevant this turn.

    Returns an empty string if nothing is relevant (caller can substitute a placeholder).
    """
    chunks = load_mechanics_chunks()
    if not chunks:
        return ""

    effects_text_lower = (effects_analysis or "").lower()
    weather, fields, side_conditions = _active_battle_state(battle)

    matched = [
        chunk
        for chunk in chunks
        if _chunk_matches(chunk, effects_text_lower, weather, fields, side_conditions)
    ]

    if not matched:
        return ""

    parts = ["## Relevant Mechanics", ""]
    for chunk in matched:
        parts.append(chunk.body)
        parts.append("")

    logger.debug(f"Resolved {len(matched)} mechanics chunks: {[c.name for c in matched]}")
    return "\n".join(parts).rstrip() + "\n"
