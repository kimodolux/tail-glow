"""Pick the right StatsResolver for a given battle format."""

from poke_env.data import GenData

from .common_spreads import load_common_spreads
from .resolver import NonRandomResolver, RandbatsResolver, StatsResolver

# Formats where the server generates teams and randbats data applies.
RANDOM_FORMATS: frozenset[str] = frozenset(
    {
        "gen9randombattle",
        "gen9randomdoublesbattle",
        "gen9randombattleblitz",
        "gen9randombattlemayhem",
        "gen9unratedrandombattle",
        "gen8randombattle",
        "gen8randomdoublesbattle",
        "gen7randombattle",
    }
)


def is_random_format(battle_format: str) -> bool:
    return battle_format.lower().replace(" ", "") in RANDOM_FORMATS


def make_resolver(
    battle_format: str,
    randbats_data,
    gen: int = 9,
) -> StatsResolver:
    """Construct the appropriate resolver for the given format."""
    gen_data = GenData.from_gen(gen)
    if is_random_format(battle_format):
        return RandbatsResolver(randbats_data, gen_data)
    return NonRandomResolver(load_common_spreads(), gen_data)
