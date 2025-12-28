"""Damage calculator module using poke-env's built-in damage calculation."""

from .calculator import (
    DamageCalculator,
    DamageResult,
    MatchupResult,
    format_damage_calculations,
)

__all__ = [
    "DamageCalculator",
    "DamageResult",
    "MatchupResult",
    "format_damage_calculations",
]
