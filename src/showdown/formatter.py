"""Format battle state for LLM consumption."""

from poke_env.battle import Battle, Pokemon


def _format_pokemon(pokemon: Pokemon, is_opponent: bool = False) -> str:
    """Format a Pokemon's information."""
    # HP display
    if is_opponent:
        hp_str = f"{pokemon.current_hp_fraction * 100:.0f}% HP"
    else:
        hp_str = f"{pokemon.current_hp}/{pokemon.max_hp} HP ({pokemon.current_hp_fraction * 100:.0f}%)"

    # Type display
    types = "/".join(t.name.capitalize() for t in pokemon.types if t is not None)

    # Status condition
    status = "Healthy"
    if pokemon.status:
        status_map = {
            "brn": "Burned",
            "par": "Paralyzed",
            "slp": "Asleep",
            "frz": "Frozen",
            "psn": "Poisoned",
            "tox": "Badly Poisoned",
        }
        status = status_map.get(pokemon.status.name, pokemon.status.name)

    # Boosts
    boosts = []
    for stat, value in pokemon.boosts.items():
        if value != 0:
            sign = "+" if value > 0 else ""
            boosts.append(f"{stat} {sign}{value}")
    boost_str = f" [{', '.join(boosts)}]" if boosts else ""

    species = pokemon.species.replace("-", " ").title()
    return f"**{species}** ({hp_str}, Type: {types}, Status: {status}){boost_str}"


def _format_move(move, index: int) -> str:
    """Format a move's information."""
    power = move.base_power if move.base_power > 0 else "-"
    accuracy = f"{move.accuracy}%" if move.accuracy else "-"
    move_type = move.type.name.capitalize()
    category = move.category.name.capitalize()

    return f"{index}. **{move.id.replace('-', ' ').title()}** (Type: {move_type}, Power: {power}, Acc: {accuracy}, {category})"


def format_battle_state(battle: Battle) -> str:
    """
    Format battle state for LLM consumption.

    Returns formatted text with:
    - Active Pokemon matchup
    - Available moves
    - Available switches
    - Field conditions
    """
    lines = []

    # Turn header
    lines.append(f"# Turn {battle.turn}")
    lines.append("")

    # Active Pokemon section
    lines.append("## Active Pokemon")

    # Our active Pokemon
    if battle.active_pokemon:
        lines.append(f"- **Your Pokemon**: {_format_pokemon(battle.active_pokemon)}")
    else:
        lines.append("- **Your Pokemon**: None (must switch)")

    # Opponent's active Pokemon
    if battle.opponent_active_pokemon:
        lines.append(
            f"- **Opponent Pokemon**: {_format_pokemon(battle.opponent_active_pokemon, is_opponent=True)}"
        )
    else:
        lines.append("- **Opponent Pokemon**: Unknown")

    lines.append("")

    # Available moves section
    lines.append("## Available Moves")
    if battle.available_moves:
        for i, move in enumerate(battle.available_moves, start=1):
            lines.append(_format_move(move, i))
    else:
        lines.append("No moves available (must switch)")

    lines.append("")

    # Available switches section
    lines.append("## Available Switches")
    if battle.available_switches:
        switch_start = len(battle.available_moves) + 1 if battle.available_moves else 1
        for i, pokemon in enumerate(battle.available_switches, start=switch_start):
            hp_pct = pokemon.current_hp_fraction * 100
            types = "/".join(t.name.capitalize() for t in pokemon.types if t is not None)
            species = pokemon.species.replace("-", " ").title()
            lines.append(f"{i}. **{species}** ({hp_pct:.0f}% HP, Type: {types})")
    else:
        lines.append("No switches available")

    lines.append("")

    # Field conditions section
    lines.append("## Field Conditions")
    conditions = []

    # Weather
    if battle.weather:
        weather_name = list(battle.weather.keys())[0].name.replace("_", " ").title()
        conditions.append(f"- Weather: {weather_name}")

    # Terrain
    if battle.fields:
        for field in battle.fields:
            field_name = field.name.replace("_", " ").title()
            conditions.append(f"- Terrain: {field_name}")

    # Our side conditions (hazards on our side)
    if battle.side_conditions:
        for condition in battle.side_conditions:
            condition_name = condition.name.replace("_", " ").title()
            conditions.append(f"- Hazard on your side: {condition_name}")

    # Opponent side conditions
    if battle.opponent_side_conditions:
        for condition in battle.opponent_side_conditions:
            condition_name = condition.name.replace("_", " ").title()
            conditions.append(f"- Hazard on opponent side: {condition_name}")

    if conditions:
        lines.extend(conditions)
    else:
        lines.append("- None")

    lines.append("")
    lines.append("**What should you do?** Choose a move or switch.")

    return "\n".join(lines)
