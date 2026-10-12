"""Randbats set data: fetched from pkmn.github.io and cached on disk.

The data is downloaded once and cached under ``.cache/randbats/`` so it survives
across runs (and is shared by every battle in a run via an in-memory cache). If
the network is unavailable and there is no cache, callers get an empty mapping
and fall back to neutral estimates.
"""

from __future__ import annotations

import functools
import json
import logging
import urllib.request
from pathlib import Path

from poke_env.data import to_id_str

logger = logging.getLogger(__name__)

_BASE_URL = "https://pkmn.github.io/randbats/data"
_CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "randbats"
_FETCH_TIMEOUT = 15


def _cache_path(format_id: str) -> Path:
    return _CACHE_DIR / f"{format_id}.json"


def _fetch(format_id: str) -> dict:
    """Download the data for a format and write it to the on-disk cache."""
    url = f"{_BASE_URL}/{format_id}.json"
    with urllib.request.urlopen(url, timeout=_FETCH_TIMEOUT) as response:
        raw = response.read().decode()
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(format_id).write_text(raw)
    return json.loads(raw)


@functools.lru_cache(maxsize=4)
def load_randbats(format_id: str) -> dict:
    """Load randbats data for a format, indexed by normalised species id.

    Uses the disk cache if present, otherwise fetches and caches it. Returns an
    empty dict if the data is unavailable (no cache and no network).
    """
    path = _cache_path(format_id)
    try:
        raw = json.loads(path.read_text()) if path.exists() else _fetch(format_id)
    except Exception as e:
        logger.warning(f"Could not load randbats data for {format_id}: {e}")
        return {}
    return {to_id_str(name): entry for name, entry in raw.items()}
