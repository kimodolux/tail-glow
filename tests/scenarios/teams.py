"""Convert a Showdown-export team string into a poke-env ConstantTeambuilder."""

from poke_env.teambuilder import ConstantTeambuilder, Teambuilder


def build_team(showdown_export: str) -> ConstantTeambuilder:
    """Parse a Showdown-export team string and wrap it for poke-env.

    The local Showdown server must run with --no-security for the resulting
    teambuilder to be accepted (already set in infra/showdown.Dockerfile).
    """
    packed = Teambuilder.join_team(Teambuilder.parse_showdown_team(showdown_export))
    return ConstantTeambuilder(packed)
