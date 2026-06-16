from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from . import config
from .cards import EntityStats, Team
from .vector import Vector2

if TYPE_CHECKING:
    from .game import Game


@dataclass
class DashState:
    target: "Entity | None" = None
    hit_ids: set[int] = field(default_factory=set)
    hits_left: int = 10
    forward_dash_dist: float = 3.5


class Entity:
    def __init__(self, entity_id: int, stats: EntityStats, team: Team, pos: Vector2, game: "Game") -> None:
        self.id = entity_id
        self.stats = stats
        self.team = team
        self.pos = pos
        self.hp = stats.hp
        self.game = game

        self.target: Entity | None = None
        self.attack_cooldown = 0.0
        self.action_frame_timer = -1.0
        self.is_attacking = False
        self.is_moving = False
        self.facing_direction = Vector2(0, 1)
        self.clone_group_id = game.random_group_id()
        self.was_nudged = False
        self.path_points: list[Vector2] = []

        self.activation_state = "asleep" if stats.name == "King Tower" else "awake"
        self.activation_timer = 0.0

        self.ability_cooldown = 0.0
        self.active_ability_timer = 0.0
        self.current_ability_effect = "none"
        self.dash_state: DashState | None = None

    def use_ability(self) -> bool:
        if not self.stats.ability or self.hp <= 0 or self.ability_cooldown > 0:
            return False

        ability = self.stats.ability
        self.ability_cooldown = ability.cooldown
        self.active_ability_timer = ability.duration
        self.current_ability_effect = ability.effect

        if self.current_ability_effect == "spawn_turret":
            spawn_dir = Vector2(0, -1 if self.team == "blue" else 1)
            self.game.add_entity_by_id("elite_turret", self.team, self.pos.add(spawn_dir.mul(3.0)))
        elif self.current_ability_effect == "throw_enemies":
            radius = ability.radius or 3.0
            for entity in self.game.entities:
                if entity.team != self.team and entity.stats.type == "troop" and entity.pos.distance_to(self.pos) <= radius:
                    entity.pos.x = config.ARENA_WIDTH - entity.pos.x
                    entity.take_damage(200)
        elif self.current_ability_effect == "dashing_dash":
            self.dash_state = DashState()

        return True

    def update(self, dt: float) -> None:
        if self.hp <= 0:
            return

        if self.stats.lifetime:
            self.hp -= (self.stats.hp / self.stats.lifetime) * dt
            if self.hp <= 0:
                self.hp = 0
                return

        if self.activation_state == "activating":
            self.activation_timer -= dt
            if self.activation_timer <= 0:
                self.activation_state = "awake"

        self.is_moving = False

        if self.ability_cooldown > 0:
            self.ability_cooldown -= dt
        if self.active_ability_timer > 0:
            self.active_ability_timer -= dt
            if self.active_ability_timer <= 0:
                self.current_ability_effect = "none"

        if self.current_ability_effect == "taunt_shield":
            radius = self.stats.ability.radius if self.stats.ability else 4.0
            for entity in self.game.entities:
                if entity.team != self.team and entity.pos.distance_to(self.pos) <= radius:
                    entity.target = self

        if self.current_ability_effect == "dashing_dash" and self.dash_state:
            self._update_dash(dt)
            return

        self.update_target()

        if not self.is_attacking and self.attack_cooldown > 0:
            scale = 1.8 if self.current_ability_effect == "cloaking_cape" else 1.0
            self.attack_cooldown -= dt * scale

        if self.target:
            dist = self.pos.distance_to(self.target.pos) - self.stats.radius - self.target.stats.radius
            if dist <= self.stats.range:
                self.path_points = []
                if self.target.pos.x != self.pos.x or self.target.pos.y != self.pos.y:
                    self.facing_direction = self.target.pos.sub(self.pos).normalize()

                if self.attack_cooldown <= 0 and not self.is_attacking:
                    self.is_attacking = True
                    self.action_frame_timer = self.stats.load_time or (self.stats.hit_speed * 0.5)

                if self.is_attacking:
                    scale = 1.8 if self.current_ability_effect == "cloaking_cape" else 1.0
                    self.action_frame_timer -= dt * scale
                    if self.action_frame_timer <= 0:
                        self.attack(self.target)
                        self.is_attacking = False
                        self.attack_cooldown = self.stats.hit_speed - (self.stats.load_time or 0)
                        if self.attack_cooldown < 0:
                            self.attack_cooldown = 0.1
            else:
                self.is_attacking = False
                self.action_frame_timer = -1
                self.move_towards(self.target.pos, dt)
                self.is_moving = True
        elif self.stats.speed > 0:
            self.is_attacking = False
            self.action_frame_timer = -1
            self.move_towards_default(dt)
            self.is_moving = True

    def _update_dash(self, dt: float) -> None:
        assert self.dash_state is not None
        state = self.dash_state

        if not state.target or state.target.hp <= 0:
            best_target = None
            best_dist = self.stats.ability.radius if self.stats.ability and self.stats.ability.radius else 5.5
            for entity in self.game.entities:
                if entity.team != self.team and not entity.stats.is_air and entity.hp > 0 and entity.id not in state.hit_ids:
                    dist = self.pos.distance_to(entity.pos)
                    if dist <= best_dist:
                        best_dist = dist
                        best_target = entity
            if best_target:
                state.target = best_target
                state.hit_ids.add(best_target.id)
            elif state.hit_ids or state.forward_dash_dist <= 0:
                self.current_ability_effect = "none"
                return

        dash_speed = 25.0
        move_dist = dash_speed * dt
        if state.target:
            direction = state.target.pos.sub(self.pos)
            dist = direction.mag()
            if dist <= move_dist + self.stats.radius + state.target.stats.radius:
                state.target.take_damage(self.stats.damage * 2.08)
                self.pos = state.target.pos.clone()
                state.hits_left -= 1
                state.target = None
                if state.hits_left <= 0:
                    self.current_ability_effect = "none"
            else:
                self.pos = self.pos.add(direction.normalize().mul(move_dist))
        elif state.forward_dash_dist > 0:
            direction_y = -1 if self.team == "blue" else 1
            dist_to_move = min(move_dist, state.forward_dash_dist)
            self.pos.y += direction_y * dist_to_move
            state.forward_dash_dist -= dist_to_move
            if state.forward_dash_dist <= 0:
                self.current_ability_effect = "none"
        self.is_moving = True

    def update_target(self) -> None:
        if self.activation_state != "awake":
            self.target = None
            return

        if self.target and self.target.hp <= 0:
            self.target = None
        if self.target and self.target.current_ability_effect == "cloaking_cape":
            self.target = None

        is_in_attack_range = False
        if self.target:
            dist = self.pos.distance_to(self.target.pos) - self.stats.radius - self.target.stats.radius
            if self.stats.speed == 0:
                if dist > self.stats.range:
                    self.target = None
                else:
                    is_in_attack_range = True
            elif dist > self.stats.sight_range + 2:
                self.target = None
            elif dist <= self.stats.range:
                is_in_attack_range = True

        if self.was_nudged:
            self.target = None
            self.was_nudged = False
            is_in_attack_range = False

        if not self.target or not is_in_attack_range:
            best_target = self.target
            best_dist = (
                self.pos.distance_to(self.target.pos) - self.stats.radius - self.target.stats.radius
                if self.target
                else self.stats.sight_range
            )
            for entity in self.game.entities:
                if entity.team == self.team or entity.hp <= 0 or entity is self.target:
                    continue
                if entity.current_ability_effect == "cloaking_cape":
                    continue
                if self.stats.is_building_targeter and entity.stats.type == "troop":
                    continue
                if self.stats.target_type == "ground" and entity.stats.is_air:
                    continue
                if self.stats.target_type == "air" and not entity.stats.is_air:
                    continue

                dist = self.pos.distance_to(entity.pos) - self.stats.radius - entity.stats.radius
                margin = 0.2 if self.target else 0.0
                if dist <= best_dist - margin:
                    best_dist = dist
                    best_target = entity

            if best_target is not self.target:
                self.target = best_target

    def is_line_clear(self, a: Vector2, b: Vector2) -> bool:
        if a.y <= config.RIVER_Y_START and b.y <= config.RIVER_Y_START:
            return True
        if a.y >= config.RIVER_Y_END and b.y >= config.RIVER_Y_END:
            return True

        y0 = max(config.RIVER_Y_START, min(a.y, b.y))
        y1 = min(config.RIVER_Y_END, max(a.y, b.y))

        if y0 == y1:
            if y0 in (config.RIVER_Y_START, config.RIVER_Y_END):
                return True
            min_x = min(a.x, b.x)
            max_x = max(a.x, b.x)
            safe_margin = self.stats.radius + 0.05
            in_left_bridge = min_x >= config.LEFT_BRIDGE_X + safe_margin and max_x <= config.LEFT_BRIDGE_X + config.BRIDGE_WIDTH - safe_margin
            in_right_bridge = min_x >= config.RIGHT_BRIDGE_X + safe_margin and max_x <= config.RIGHT_BRIDGE_X + config.BRIDGE_WIDTH - safe_margin
            return in_left_bridge or in_right_bridge
        if y0 > y1:
            return True

        def get_x(y: float) -> float:
            return a.x + (y - a.y) * (b.x - a.x) / (b.y - a.y)

        x0 = get_x(y0)
        x1 = get_x(y1)
        min_x = min(x0, x1)
        max_x = max(x0, x1)
        safe_margin = self.stats.radius + 0.05
        in_left_bridge = min_x >= config.LEFT_BRIDGE_X + safe_margin and max_x <= config.LEFT_BRIDGE_X + config.BRIDGE_WIDTH - safe_margin
        in_right_bridge = min_x >= config.RIGHT_BRIDGE_X + safe_margin and max_x <= config.RIGHT_BRIDGE_X + config.BRIDGE_WIDTH - safe_margin
        return in_left_bridge or in_right_bridge

    def find_path(self, start: Vector2, target: Vector2) -> list[Vector2]:
        if self.is_line_clear(start, target):
            return [target]

        waypoints = [
            Vector2(config.LEFT_BRIDGE_X + config.BRIDGE_WIDTH / 2, config.RIVER_Y_START),
            Vector2(config.LEFT_BRIDGE_X + config.BRIDGE_WIDTH / 2, config.RIVER_Y_END),
            Vector2(config.RIGHT_BRIDGE_X + config.BRIDGE_WIDTH / 2, config.RIVER_Y_START),
            Vector2(config.RIGHT_BRIDGE_X + config.BRIDGE_WIDTH / 2, config.RIVER_Y_END),
        ]
        nodes = [start, target, *waypoints]
        num_nodes = len(nodes)
        adj = [[float("inf")] * num_nodes for _ in range(num_nodes)]
        for i in range(num_nodes):
            for j in range(num_nodes):
                if i == j:
                    adj[i][j] = 0
                elif self.is_line_clear(nodes[i], nodes[j]):
                    adj[i][j] = nodes[i].distance_to(nodes[j])

        dist = [float("inf")] * num_nodes
        prev = [-1] * num_nodes
        unvisited = set(range(num_nodes))
        dist[0] = 0

        while unvisited:
            u = min(unvisited, key=lambda v: dist[v])
            if dist[u] == float("inf") or u == 1:
                break
            unvisited.remove(u)
            for v in list(unvisited):
                alt = dist[u] + adj[u][v]
                if alt < dist[v]:
                    dist[v] = alt
                    prev[v] = u

        if prev[1] == -1:
            return [target]

        path: list[Vector2] = []
        curr = 1
        while curr != 0:
            path.insert(0, nodes[curr])
            curr = prev[curr]
        return path

    def move_towards(self, target_pos: Vector2, dt: float) -> None:
        if self.stats.speed <= 0:
            return
        if not self.stats.is_air and not self.stats.jumps_river:
            self.path_points = self.find_path(self.pos, target_pos)
        else:
            self.path_points = [target_pos]

        if self.path_points:
            target_waypoint = self.path_points[0]
            if len(self.path_points) > 1 and self.pos.distance_squared_to(target_waypoint) < 1.0:
                target_waypoint = self.path_points[1]
            direction = target_waypoint.sub(self.pos).normalize()
            if direction.x != 0 or direction.y != 0:
                self.facing_direction = direction
            move_dir = self.path_points[0].sub(self.pos).normalize()
            self.pos = self.pos.add(move_dir.mul(self.stats.speed * dt))

    def move_towards_default(self, dt: float) -> None:
        best_tower = None
        best_dist = float("inf")
        for entity in self.game.entities:
            if entity.team != self.team and entity.stats.type in ("tower", "building"):
                dist = self.pos.distance_squared_to(entity.pos)
                if dist < best_dist:
                    best_dist = dist
                    best_tower = entity
        target_pos = best_tower.pos if best_tower else Vector2(self.pos.x, self.pos.y + (-10 if self.team == "blue" else 10))
        self.move_towards(target_pos, dt)

    def attack(self, target: "Entity") -> None:
        if self.stats.projectile_speed:
            spawn_pos = self.pos.clone()
            if self.stats.id == "king_tower":
                direction = target.pos.sub(self.pos).normalize()
                spawn_pos = spawn_pos.add(direction.mul(1.2))
            self.game.add_projectile(
                self.stats.id,
                spawn_pos,
                target,
                self.stats.damage,
                self.stats.projectile_speed,
                self.team,
                self.stats.splash_radius,
                self.stats.projectile_asset,
                self.stats.projectile_trajectory,
                lambda: self.on_deal_damage(target),
            )
        else:
            target.take_damage(self.stats.damage)
            self.on_deal_damage(target)

    def on_deal_damage(self, target: "Entity") -> None:
        if self.stats.id == "battle_healer":
            for entity in self.game.entities:
                if entity.team == self.team and entity.hp > 0 and entity.stats.type == "troop":
                    if entity.pos.distance_squared_to(self.pos) <= 16.0:
                        entity.hp = min(entity.hp + 84, entity.stats.hp)

        if self.stats.spawn_on_hit_id:
            clone_count = sum(1 for entity in self.game.entities if entity.clone_group_id == self.clone_group_id and entity.hp > 0)
            if self.stats.max_clones is None or clone_count < self.stats.max_clones:
                clone_stats = self.game.cards.get(self.stats.spawn_on_hit_id)
                if clone_stats:
                    spawn_offset = Vector2((self.game.rng.random() - 0.5) * 1.5, (self.game.rng.random() - 0.5) * 1.5)
                    clone = self.game.add_entity(clone_stats, self.team, self.pos.add(spawn_offset))
                    clone.clone_group_id = self.clone_group_id
                    clone.attack_cooldown = clone.stats.hit_speed

    def take_damage(self, amount: float) -> None:
        final_damage = amount
        if self.is_moving and self.stats.moving_shield_damage_reduction:
            final_damage *= 1 - self.stats.moving_shield_damage_reduction
        if self.current_ability_effect == "taunt_shield":
            final_damage *= 0.2

        self.hp -= final_damage
        if self.hp <= 0:
            self.hp = 0
            if self.stats.name == "Princess Tower":
                for entity in self.game.entities:
                    if entity.team == self.team and entity.stats.name == "King Tower" and entity.activation_state == "asleep":
                        entity.activation_state = "activating"
                        entity.activation_timer = 97 / 30.0
        elif self.stats.name == "King Tower" and self.activation_state == "asleep":
            self.activation_state = "activating"
            self.activation_timer = 97 / 30.0
