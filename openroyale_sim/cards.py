from __future__ import annotations

from dataclasses import dataclass, replace
from math import inf
from typing import Literal

Team = Literal["blue", "red"]
TargetType = Literal["ground", "air", "building", "all"]
EntityType = Literal["troop", "building", "tower"]
AbilityEffect = Literal[
    "taunt_shield",
    "spawn_turret",
    "throw_enemies",
    "dashing_dash",
    "cloaking_cape",
    "summon_skeletons",
    "none",
]


@dataclass(frozen=True)
class AbilityStats:
    name: str
    cooldown: float
    elixir_cost: float
    effect: AbilityEffect
    duration: float = 0.0
    radius: float = 0.0


@dataclass(frozen=True)
class EntityStats:
    id: str
    name: str
    type: EntityType
    hp: float
    damage: float
    hit_speed: float
    load_time: float
    speed: float
    range: float
    sight_range: float
    radius: float
    mass: float
    target_type: TargetType
    is_air: bool
    elixir_cost: int = 0
    is_building_targeter: bool = False
    spawn_count: int = 1
    spawn_radius: float = 1.0
    jumps_river: bool = False
    projectile_speed: float | None = None
    projectile_asset: str | None = None
    projectile_trajectory: Literal["line", "parabola"] | None = None
    splash_radius: float | None = None
    moving_shield_damage_reduction: float | None = None
    spawn_on_hit_id: str | None = None
    max_clones: int | None = None
    ability: AbilityStats | None = None
    lifetime: float | None = None

    def with_overrides(self, **kwargs: object) -> "EntityStats":
        return replace(self, **kwargs)


CARDS: dict[str, EntityStats] = {
    "knight": EntityStats(
        id="knight",
        name="Knight",
        type="troop",
        hp=1666,
        damage=202,
        hit_speed=1.2,
        load_time=0.7,
        speed=1.0,
        range=0.8,
        sight_range=5.5,
        radius=0.5,
        mass=6,
        is_air=False,
        target_type="ground",
        elixir_cost=3,
    ),
    "archers": EntityStats(
        id="archers",
        name="Archers",
        type="troop",
        hp=304,
        damage=107,
        hit_speed=0.9,
        load_time=1.1,
        speed=1.0,
        range=5.0,
        sight_range=5.5,
        radius=0.5,
        mass=3,
        is_air=False,
        target_type="all",
        elixir_cost=3,
        projectile_speed=10,
        projectile_asset="projectile_arrow_basic",
        projectile_trajectory="parabola",
        spawn_count=2,
        spawn_radius=0.8,
    ),
    "giant": EntityStats(
        id="giant",
        name="Giant",
        type="troop",
        hp=4091,
        damage=254,
        hit_speed=1.5,
        load_time=1.0,
        speed=0.75,
        range=0.8,
        sight_range=5.5,
        radius=0.75,
        mass=18,
        is_air=False,
        target_type="building",
        elixir_cost=5,
        is_building_targeter=True,
    ),
    "pekka": EntityStats(
        id="pekka",
        name="P.E.K.K.A",
        type="troop",
        hp=3760,
        damage=816,
        hit_speed=1.8,
        load_time=1.3,
        speed=0.75,
        range=0.8,
        sight_range=5.5,
        radius=0.8,
        mass=18,
        is_air=False,
        target_type="ground",
        elixir_cost=7,
    ),
    "musketeer": EntityStats(
        id="musketeer",
        name="Musketeer",
        type="troop",
        hp=720,
        damage=218,
        hit_speed=1.1,
        load_time=0.6,
        speed=1.0,
        range=6.0,
        sight_range=6.0,
        radius=0.5,
        mass=4,
        is_air=False,
        target_type="all",
        elixir_cost=4,
        projectile_speed=10,
        projectile_asset="projectile_cannonball_small",
        projectile_trajectory="line",
    ),
    "hog_rider": EntityStats(
        id="hog_rider",
        name="Hog Rider",
        type="troop",
        hp=1696,
        damage=318,
        hit_speed=1.6,
        load_time=1.0,
        speed=2.0,
        range=0.8,
        sight_range=5.5,
        radius=0.6,
        mass=8,
        is_air=False,
        target_type="building",
        elixir_cost=4,
        is_building_targeter=True,
        jumps_river=True,
    ),
    "skeletons": EntityStats(
        id="skeletons",
        name="Skeletons",
        type="troop",
        hp=81,
        damage=81,
        hit_speed=1.0,
        load_time=0.5,
        speed=1.5,
        range=0.8,
        sight_range=5.5,
        radius=0.4,
        mass=1,
        is_air=False,
        target_type="ground",
        elixir_cost=1,
        spawn_count=3,
        spawn_radius=0.5,
    ),
    "barbarians": EntityStats(
        id="barbarians",
        name="Barbarians",
        type="troop",
        hp=670,
        damage=191,
        hit_speed=1.4,
        load_time=1.0,
        speed=1.0,
        range=0.8,
        sight_range=5.5,
        radius=0.5,
        mass=4,
        is_air=False,
        target_type="ground",
        elixir_cost=5,
        spawn_count=5,
        spawn_radius=1.0,
    ),
    "minions": EntityStats(
        id="minions",
        name="Minions",
        type="troop",
        hp=230,
        damage=105,
        hit_speed=1.0,
        load_time=1.0,
        speed=1.5,
        range=1.5,
        sight_range=5.5,
        radius=0.4,
        mass=2,
        is_air=True,
        target_type="all",
        elixir_cost=3,
        spawn_count=3,
        spawn_radius=0.8,
    ),
    "wizard": EntityStats(
        id="wizard",
        name="Wizard",
        type="troop",
        hp=720,
        damage=281,
        hit_speed=1.4,
        load_time=1.0,
        speed=1.0,
        range=5.5,
        sight_range=6.0,
        radius=0.5,
        mass=4,
        is_air=False,
        target_type="all",
        elixir_cost=5,
        projectile_speed=10,
        projectile_asset="fireball_projectile1",
        projectile_trajectory="line",
        splash_radius=1.5,
    ),
    "princess": EntityStats(
        id="princess",
        name="Princess",
        type="troop",
        hp=261,
        damage=169,
        hit_speed=3.0,
        load_time=1.0,
        speed=1.0,
        range=9.0,
        sight_range=9.5,
        radius=0.4,
        mass=2,
        is_air=False,
        target_type="all",
        elixir_cost=3,
        projectile_speed=10,
        projectile_asset="projectile_princess",
        projectile_trajectory="parabola",
        splash_radius=2.0,
    ),
    "princess_tower": EntityStats(
        id="princess_tower",
        name="Princess Tower",
        type="tower",
        hp=2534,
        damage=90,
        hit_speed=0.8,
        load_time=0.5,
        speed=0,
        range=7.5,
        sight_range=7.5,
        radius=1.5,
        mass=inf,
        is_air=False,
        target_type="all",
        projectile_speed=10,
        projectile_asset="projectile_arrow_basic",
        projectile_trajectory="parabola",
    ),
    "king_tower": EntityStats(
        id="king_tower",
        name="King Tower",
        type="tower",
        hp=4008,
        damage=90,
        hit_speed=1.0,
        load_time=0.2,
        speed=0,
        range=7.0,
        sight_range=7.0,
        radius=2.0,
        mass=inf,
        is_air=False,
        target_type="all",
        projectile_speed=15,
        projectile_asset="projectile_cannonball_large",
        projectile_trajectory="line",
    ),
}
