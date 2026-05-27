"""Deterministic opponent that picks moves from a pre-defined script."""

import logging

from poke_env.player import Player

logger = logging.getLogger(__name__)


def _normalize(name: str) -> str:
    return name.lower().replace("-", "").replace(" ", "").replace("'", "")


class ScriptedPlayer(Player):
    """Opponent that executes a fixed list of move names, one per turn.

    Falls back to the first available move if:
    - the script is exhausted
    - the requested move is not in available_moves (e.g. PP zero, disabled)

    Switches are not currently scriptable; the player will only switch when
    forced to (no moves available).
    """

    def __init__(self, *args, script: list[str] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._script: list[str] = list(script or [])
        self._turn_idx: int = 0

    def choose_move(self, battle):
        wanted = self._script[self._turn_idx] if self._turn_idx < len(self._script) else None
        self._turn_idx += 1

        if not battle.available_moves:
            if battle.available_switches:
                return self.create_order(battle.available_switches[0])
            return self.choose_random_move(battle)

        if wanted is not None:
            wanted_norm = _normalize(wanted)
            for move in battle.available_moves:
                if _normalize(move.id) == wanted_norm:
                    return self.create_order(move)
            logger.warning(
                "ScriptedPlayer: requested move %r not available on turn %d; "
                "falling back to %s",
                wanted,
                battle.turn,
                battle.available_moves[0].id,
            )

        return self.create_order(battle.available_moves[0])

    def teampreview(self, battle):
        return "/team 123456"
