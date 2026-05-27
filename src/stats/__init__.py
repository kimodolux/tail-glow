"""Meta-aware Pokemon stat resolution.

Provides a uniform `StatsResolver` interface that consumers (TeamsState,
DamageCalculator, SpeedCalculator, fetch_opponent_sets) call regardless of
battle format. Dispatch chooses between RandbatsResolver (random battles)
and NonRandomResolver (OU / customgame / etc.) at construction time.
"""

from .resolver import (
    NonRandomResolver,
    RandbatsResolver,
    Spread,
    StatsResolver,
)
from .factory import RANDOM_FORMATS, make_resolver
from .common_spreads import CommonSpreadsDB, load_common_spreads

__all__ = [
    "CommonSpreadsDB",
    "NonRandomResolver",
    "RANDOM_FORMATS",
    "RandbatsResolver",
    "Spread",
    "StatsResolver",
    "load_common_spreads",
    "make_resolver",
]
