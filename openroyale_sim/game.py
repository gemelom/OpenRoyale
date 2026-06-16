from __future__ import annotations

from dataclasses import dataclass
import math
import random
import string
from typing import Callable, Literal

from . import config
from .cards import CARDS, EntityStats, Team
from .entity import Entity
from .vector import Vector2


@dataclass
class Projectile:
    id: int
    source_id: str
    start_pos: Vector2
    pos: Vector2
    target: Entity
    damage: float
    speed: float
    team: Team
    splash_radius: float | None = None
    asset: str | None = None
    trajectory: Literal["line", "parabola"] | None = None
    on_hit: Callable[[], None] | None = None


@dataclass
class VisualEffect:
    id: int
    name: str
    pos: Vector2
    start_time: float
    duration: float
    file_name: str | None = None


@dataclass
class AoeCircle:
    id: int
    pos: Vector2
    radius: float
    start_time: float
    duration: float


class Game:
    def __init__(self, seed: int | None = None, cards: dict[str, EntityStats] | None = None) -> None:
        self.rng = random.Random(seed)
        self.cards = cards or CARDS
        self.entities: list[Entity] = []
        self.projectiles: list[Projectile] = []
        self.effects: list[VisualEffect] = []
        self.aoe_circles: list[AoeCircle] = []
        self.next_entity_id = 1
        self.next_projectile_id = 1
        self.next_effect_id = 1
        self.time_elapsed = 0.0
        self.rivers = [
            {"x": -5.0, "y": config.RIVER_Y_START, "width": config.LEFT_BRIDGE_X + 5.0, "height": config.RIVER_Y_END - config.RIVER_Y_START},
            {
                "x": config.LEFT_BRIDGE_X + config.BRIDGE_WIDTH,
                "y": config.RIVER_Y_START,
                "width": config.RIGHT_BRIDGE_X - (config.LEFT_BRIDGE_X + config.BRIDGE_WIDTH),
                "height": config.RIVER_Y_END - config.RIVER_Y_START,
            },
            {
                "x": config.RIGHT_BRIDGE_X + config.BRIDGE_WIDTH,
                "y": config.RIVER_Y_START,
                "width": config.ARENA_WIDTH + 5.0 - (config.RIGHT_BRIDGE_X + config.BRIDGE_WIDTH),
                "height": config.RIVER_Y_END - config.RIVER_Y_START,
            },
        ]

    def random_group_id(self) -> str:
        return "".join(self.rng.choice(string.ascii_lowercase + string.digits) for _ in range(7))

    def start(self) -> None:
        self.add_entity(self.cards["king_tower"], "blue", Vector2(9, 29))
        self.add_entity(self.cards["princess_tower"], "blue", Vector2(3, 25))
        self.add_entity(self.cards["princess_tower"], "blue", Vector2(15, 25))
        self.add_entity(self.cards["king_tower"], "red", Vector2(9, 3))
        self.add_entity(self.cards["princess_tower"], "red", Vector2(3, 7))
        self.add_entity(self.cards["princess_tower"], "red", Vector2(15, 7))

    def add_entity(self, stats: EntityStats, team: Team, pos: Vector2) -> Entity:
        if stats.spawn_count and stats.spawn_count > 1:
            first_entity: Entity | None = None
            radius = stats.spawn_radius or 1.0
            swarm_group_id = self.random_group_id()
            for i in range(stats.spawn_count):
                angle = (i / stats.spawn_count) * math.pi * 2
                offset = Vector2(math.cos(angle) * radius, math.sin(angle) * radius)
                entity = Entity(self.next_entity_id, stats, team, pos.add(offset), self)
                self.next_entity_id += 1
                entity.clone_group_id = swarm_group_id
                self.entities.append(entity)
                if first_entity is None:
                    first_entity = entity
            assert first_entity is not None
            return first_entity

        entity = Entity(self.next_entity_id, stats, team, pos, self)
        self.next_entity_id += 1
        self.entities.append(entity)
        return entity

    def add_entity_by_id(self, card_id: str, team: Team, pos: Vector2) -> Entity | None:
        stats = self.cards.get(card_id)
        if not stats:
            return None
        return self.add_entity(stats, team, pos)

    def update(self, dt: float) -> None:
        self.time_elapsed += dt

        for entity in list(self.entities):
            entity.update(dt)

        for i in range(len(self.projectiles) - 1, -1, -1):
            projectile = self.projectiles[i]
            if projectile.target.hp <= 0:
                self.projectiles.pop(i)
                continue

            direction = projectile.target.pos.sub(projectile.pos)
            dist = direction.mag()
            move_dist = projectile.speed * dt
            if dist <= move_dist:
                if projectile.splash_radius:
                    for entity in self.entities:
                        if entity.team != projectile.team and entity.hp > 0:
                            if entity.pos.distance_to(projectile.pos) <= projectile.splash_radius + entity.stats.radius:
                                entity.take_damage(projectile.damage)
                    self.aoe_circles.append(AoeCircle(self.next_effect_id, projectile.pos.clone(), projectile.splash_radius, self.time_elapsed, 0.3))
                    self.next_effect_id += 1
                else:
                    projectile.target.take_damage(projectile.damage)
                if projectile.on_hit:
                    projectile.on_hit()
                self.projectiles.pop(i)
            else:
                self.projectiles[i].pos = projectile.pos.add(direction.normalize().mul(move_dist))

        for i in range(len(self.entities) - 1, -1, -1):
            entity = self.entities[i]
            if entity.hp <= 0:
                if entity.stats.name in ("Knight", "Elite Knight"):
                    self.spawn_effect("particle_sword", entity.pos, 1.4)
                elif entity.stats.name == "Princess Tower":
                    self.spawn_effect("Tower_destroyed_ground1", entity.pos, math.inf, "building_tower")
                elif entity.stats.name == "King Tower":
                    self.spawn_effect("Tower_destroyed_ground2", entity.pos, math.inf, "building_tower")
                else:
                    self.spawn_effect("death_ground_elixir1", entity.pos, 0.7)
                self.entities.pop(i)

        self.effects = [effect for effect in self.effects if self.time_elapsed - effect.start_time < effect.duration]
        self.aoe_circles = [circle for circle in self.aoe_circles if self.time_elapsed - circle.start_time < circle.duration]

        self.resolve_collisions()
        self.constrain_entities()

    def spawn_effect(self, name: str, pos: Vector2, duration: float = 1.0, file_name: str | None = None) -> None:
        self.effects.append(VisualEffect(self.next_effect_id, name, pos.clone(), self.time_elapsed, duration, file_name))
        self.next_effect_id += 1

    def add_projectile(
        self,
        source_id: str,
        pos: Vector2,
        target: Entity,
        damage: float,
        speed: float,
        team: Team,
        splash_radius: float | None = None,
        asset: str | None = None,
        trajectory: Literal["line", "parabola"] | None = None,
        on_hit: Callable[[], None] | None = None,
    ) -> None:
        self.projectiles.append(
            Projectile(
                self.next_projectile_id,
                source_id,
                pos.clone(),
                pos.clone(),
                target,
                damage,
                speed,
                team,
                splash_radius,
                asset,
                trajectory,
                on_hit,
            )
        )
        self.next_projectile_id += 1

    def constrain_entities(self) -> None:
        for entity in self.entities:
            entity.pos.x = max(entity.stats.radius, min(config.ARENA_WIDTH - entity.stats.radius, entity.pos.x))
            entity.pos.y = max(entity.stats.radius, min(config.ARENA_HEIGHT - entity.stats.radius, entity.pos.y))

            is_dashing = entity.current_ability_effect == "dashing_dash"
            if not entity.stats.is_air and not entity.stats.jumps_river and not is_dashing:
                for river in self.rivers:
                    closest_x = max(river["x"], min(entity.pos.x, river["x"] + river["width"]))
                    closest_y = max(river["y"], min(entity.pos.y, river["y"] + river["height"]))
                    dx = entity.pos.x - closest_x
                    dy = entity.pos.y - closest_y
                    dist_sq = dx * dx + dy * dy
                    if dist_sq < entity.stats.radius * entity.stats.radius:
                        if dist_sq == 0:
                            dist_to_left = entity.pos.x - river["x"]
                            dist_to_right = river["x"] + river["width"] - entity.pos.x
                            dist_to_top = entity.pos.y - river["y"]
                            dist_to_bottom = river["y"] + river["height"] - entity.pos.y
                            minimum = min(dist_to_left, dist_to_right, dist_to_top, dist_to_bottom)
                            if minimum == dist_to_left:
                                entity.pos.x = river["x"] - entity.stats.radius
                            elif minimum == dist_to_right:
                                entity.pos.x = river["x"] + river["width"] + entity.stats.radius
                            elif minimum == dist_to_top:
                                entity.pos.y = river["y"] - entity.stats.radius
                            else:
                                entity.pos.y = river["y"] + river["height"] + entity.stats.radius
                        else:
                            dist = math.sqrt(dist_sq)
                            overlap = entity.stats.radius - dist
                            entity.pos.x += (dx / dist) * overlap
                            entity.pos.y += (dy / dist) * overlap

    def resolve_collisions(self) -> None:
        for i in range(len(self.entities)):
            for j in range(i + 1, len(self.entities)):
                a = self.entities[i]
                b = self.entities[j]
                if a.stats.speed == 0 and b.stats.speed == 0:
                    continue
                if a.stats.is_air and b.stats.is_air:
                    continue
                if a.stats.is_air != b.stats.is_air:
                    continue

                dist_sq = a.pos.distance_squared_to(b.pos)
                min_dist = a.stats.radius + b.stats.radius
                if dist_sq < min_dist * min_dist and dist_sq > 0.0001:
                    if math.isinf(a.stats.mass) and math.isinf(b.stats.mass):
                        continue

                    dist = math.sqrt(dist_sq)
                    overlap = min_dist - dist
                    direction = a.pos.sub(b.pos).normalize()

                    ratio_a = 0.5
                    ratio_b = 0.5
                    if math.isinf(a.stats.mass):
                        ratio_a = 0
                        ratio_b = 1
                    elif math.isinf(b.stats.mass):
                        ratio_a = 1
                        ratio_b = 0
                    else:
                        total_mass = a.stats.mass + b.stats.mass
                        ratio_a = b.stats.mass / total_mass
                        ratio_b = a.stats.mass / total_mass
                        if a.stats.mass >= b.stats.mass * 3:
                            ratio_a = 0.05
                            ratio_b = 0.95
                        elif b.stats.mass >= a.stats.mass * 3:
                            ratio_a = 0.95
                            ratio_b = 0.05

                    if ratio_a > 0:
                        a.pos = a.pos.add(direction.mul(overlap * ratio_a))
                    if ratio_b > 0:
                        b.pos = b.pos.sub(direction.mul(overlap * ratio_b))

                    if math.isinf(a.stats.mass) or math.isinf(b.stats.mass):
                        troop = b if math.isinf(a.stats.mass) else a
                        building = a if math.isinf(a.stats.mass) else b
                        push_dir = troop.pos.sub(building.pos).normalize()
                        if abs(push_dir.x) < 0.1:
                            push_dir.x = 0.3 if push_dir.x >= 0 else -0.3
                            troop.pos = troop.pos.add(push_dir.normalize().mul(overlap))

                    if overlap * ratio_a > 0.1:
                        a.was_nudged = True
                    if overlap * ratio_b > 0.1:
                        b.was_nudged = True
