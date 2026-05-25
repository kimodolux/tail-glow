# Core Battle Mechanics

These mechanics are referenced on essentially every turn. Conditional mechanics (weather, terrain, hazards, screens, priority, etc.) are loaded into the prompt only when triggered by the matchup.

## Terastallization

**When to Tera:**
- Gain extra damage on move for KO. Changing Tera Type increases damage by 50%.
- Survive a hit you'd otherwise die to. Changing to a type that resists or is immunne to the expected move.

**When NOT to Tera:**
- Early game (save for crucial moment)
- When opponent still has checks to your Tera type
- Just to resist one hit if you'll still lose the mon

**Tera Type Selection:**
- Offensive: Match strong coverage move (Tera Normal on Dragonite for Extreme Speed)
- Defensive: Cover key weakness (Tera Fairy on Gholdengo vs Dark types)
- Surprise: Unexpected type to bait switches

## Status Conditions

**Burn**
- Damage: 1/16 max HP per turn
- Halves physical attack damage
- Fire types immune
- Guts: Ignores attack reduction, 1.5x Attack
- Facade: Doubles to 140 BP when burned
- Key moves: Will-O-Wisp, Scald (30% chance)

**Poison**
- Regular: 1/8 max HP per turn
- Toxic (bad poison): Starts at 1/16, increases by 1/16 each turn
- Poison/Steel types immune
- Poison Heal: Restores 1/8 HP instead
- Key moves: Toxic, Poison Jab, Sludge Bomb

**Sleep**
- Duration: 1-3 turns (random)
- Rest: Always 2 turns
- Can only use Sleep Talk or Snore while asleep
- Insomnia/Vital Spirit: Immune
- Electric Terrain: Prevents sleep (grounded)

**Freeze**
- 20% chance to thaw each turn
- Fire moves thaw user: Flame Wheel, Flare Blitz, Sacred Fire, Scald
- Being hit by Fire move thaws target
- Ice types immune (except Tri Attack)
- Rarest status (no guaranteed move)

**Paralysis**
- Reduces Speed by 75%
- 25% chance to be fully paralyzed (lose turn)
- Electric types immune, Ground types immune to Thunder Wave
- Limber ability prevents paralysis

## Stat Stages

**Stage Multipliers**
- +1: 1.5x | -1: 0.67x
- +2: 2.0x | -2: 0.5x
- +3: 2.5x | -3: 0.4x
- +4: 3.0x | -4: 0.33x
- +5: 3.5x | -5: 0.29x
- +6: 4.0x | -6: 0.25x

**Reset Conditions**
- Switching out
- Haze (resets all Pokemon)
- Clear Smog (resets target only)

**Critical Hits**
- Ignore attacker's negative stat stages
- Ignore defender's positive stat stages
- 1.5x damage multiplier

**Key Abilities**
- Intimidate: -1 Attack on switch-in
- Competitive: +2 Sp.Atk when stats lowered
- Defiant: +2 Attack when stats lowered
- Clear Body/White Smoke: Prevents stat drops
