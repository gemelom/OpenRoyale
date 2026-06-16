from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from . import config as arena_config
from .cards import CARDS, Team
from .game import Game
from .vector import Vector2

STARTING_ELIXIR = 5.0
MAX_ELIXIR = 10.0
ELIXIR_REGEN_SECONDS = 2.8
LANE_WIDTH = arena_config.ARENA_WIDTH / 2
ADVANCED_DEPLOY_DEPTH = 5.0


@dataclass
class EnvConfig:
    max_time: float = 180.0
    tick_rate: int = 60
    frame_skip: int = 1
    start_with_towers: bool = True


class OpenRoyaleEnv:
    """Small Gymnasium-style wrapper around :class:`openroyale_sim.game.Game`.

    Actions are intentionally plain dictionaries so training code can choose its
    own action encoding. A step accepts one action dict or an iterable of them:

    ``{"type": "deploy", "card": "knight", "team": "blue", "x": 9, "y": 24}``
    ``{"type": "ability", "entity_id": 12}``
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        max_time: float = 180.0,
        tick_rate: int = 60,
        frame_skip: int = 1,
        start_with_towers: bool = True,
        cards=None,
    ) -> None:
        self.config = EnvConfig(max_time=max_time, tick_rate=tick_rate, frame_skip=frame_skip, start_with_towers=start_with_towers)
        self.cards = cards or CARDS
        self.game = Game(cards=self.cards)
        self._previous_tower_hp = {"blue": 0.0, "red": 0.0}
        self.elixir = {"blue": STARTING_ELIXIR, "red": STARTING_ELIXIR}

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
        del options
        self.game = Game(seed=seed, cards=self.cards)
        if self.config.start_with_towers:
            self.game.start()
        self._previous_tower_hp = self._tower_hp()
        self.elixir = {"blue": STARTING_ELIXIR, "red": STARTING_ELIXIR}
        return self.observe(), {"seed": seed}

    def step(self, actions: dict[str, Any] | Iterable[dict[str, Any]] | None = None) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]:
        if actions is None:
            action_list: list[dict[str, Any]] = []
        elif isinstance(actions, dict):
            action_list = [actions]
        else:
            action_list = list(actions)

        invalid_actions = []
        for action in action_list:
            ok, reason = self._apply_action(action)
            if not ok:
                invalid_actions.append({"action": action, "reason": reason})

        before = self._previous_tower_hp
        dt = 1.0 / self.config.tick_rate
        for _ in range(self.config.frame_skip):
            self.game.update(dt)
            self._regenerate_elixir(dt)
        after = self._tower_hp()
        self._previous_tower_hp = after

        reward = (before["red"] - after["red"]) - (before["blue"] - after["blue"])
        winner = self._winner()
        terminated = winner is not None
        truncated = self.game.time_elapsed >= self.config.max_time
        info = {
            "time": self.game.time_elapsed,
            "invalid_actions": invalid_actions,
            "tower_hp": after,
            "elixir": dict(self.elixir),
            "winner": winner,
        }
        return self.observe(), reward, terminated, truncated, info

    def observe(self) -> dict[str, Any]:
        return {
            "time": self.game.time_elapsed,
            "elixir": dict(self.elixir),
            "entities": [
                {
                    "id": entity.id,
                    "card": entity.stats.id,
                    "name": entity.stats.name,
                    "team": entity.team,
                    "type": entity.stats.type,
                    "x": entity.pos.x,
                    "y": entity.pos.y,
                    "hp": entity.hp,
                    "max_hp": entity.stats.hp,
                    "target_id": entity.target.id if entity.target else None,
                    "is_moving": entity.is_moving,
                    "is_attacking": entity.is_attacking,
                    "ability_cooldown": entity.ability_cooldown,
                    "effect": entity.current_ability_effect,
                    "elixir_cost": entity.stats.elixir_cost,
                }
                for entity in self.game.entities
            ],
            "projectiles": [
                {
                    "id": projectile.id,
                    "source": projectile.source_id,
                    "team": projectile.team,
                    "x": projectile.pos.x,
                    "y": projectile.pos.y,
                    "target_id": projectile.target.id,
                    "damage": projectile.damage,
                }
                for projectile in self.game.projectiles
            ],
        }

    def legal_cards(self) -> list[str]:
        return [card_id for card_id, stats in self.cards.items() if stats.type == "troop"]

    def _apply_action(self, action: dict[str, Any]) -> tuple[bool, str | None]:
        action_type = action.get("type", "deploy")
        if action_type == "noop":
            return True, None
        if action_type == "deploy":
            card_id = action.get("card")
            team = action.get("team", "blue")
            if team not in ("blue", "red"):
                return False, "team must be 'blue' or 'red'"
            if not isinstance(card_id, str) or card_id not in self.cards:
                return False, f"unknown card: {card_id}"
            stats = self.cards[card_id]
            if stats.type == "tower":
                return False, "tower cards cannot be deployed"
            try:
                x = float(action["x"])
                y = float(action["y"])
            except (KeyError, TypeError, ValueError):
                return False, "deploy requires numeric x and y"

            if not self.is_legal_deploy_position(team, x, y):
                return False, "deploy position is not legal"
            if self.elixir[team] < stats.elixir_cost:
                return False, "not enough elixir"

            self.elixir[team] -= stats.elixir_cost
            self.game.add_entity_by_id(card_id, team, Vector2(x, y))
            return True, None
        if action_type == "ability":
            entity_id = action.get("entity_id")
            entity = next((candidate for candidate in self.game.entities if candidate.id == entity_id), None)
            if not entity:
                return False, f"unknown entity_id: {entity_id}"
            if not entity.use_ability():
                return False, "ability not available"
            return True, None
        return False, f"unknown action type: {action_type}"

    def is_legal_deploy_position(self, team: Team, x: float, y: float) -> bool:
        if team not in ("blue", "red"):
            return False
        if x < 0 or x > arena_config.ARENA_WIDTH or y < 0 or y > arena_config.ARENA_HEIGHT:
            return False
        if self._in_base_deploy_zone(team, y):
            return True
        return self._in_advanced_deploy_zone(team, x, y)

    def legal_deploy_zones(self, team: Team) -> list[dict[str, float | str]]:
        zones: list[dict[str, float | str]] = []
        if team == "blue":
            zones.append({"lane": "base", "x_min": 0.0, "x_max": arena_config.ARENA_WIDTH, "y_min": arena_config.RIVER_Y_END, "y_max": arena_config.ARENA_HEIGHT})
        else:
            zones.append({"lane": "base", "x_min": 0.0, "x_max": arena_config.ARENA_WIDTH, "y_min": 0.0, "y_max": arena_config.RIVER_Y_START})

        for lane in ("left", "right"):
            if self._enemy_princess_tower_destroyed(team, lane):
                x_min, x_max = self._lane_bounds(lane)
                if team == "blue":
                    y_min = arena_config.RIVER_Y_START - ADVANCED_DEPLOY_DEPTH
                    y_max = arena_config.RIVER_Y_START
                else:
                    y_min = arena_config.RIVER_Y_END
                    y_max = arena_config.RIVER_Y_END + ADVANCED_DEPLOY_DEPTH
                zones.append({"lane": lane, "x_min": x_min, "x_max": x_max, "y_min": y_min, "y_max": y_max})
        return zones

    def _regenerate_elixir(self, dt: float) -> None:
        amount = dt / ELIXIR_REGEN_SECONDS
        self.elixir["blue"] = min(MAX_ELIXIR, self.elixir["blue"] + amount)
        self.elixir["red"] = min(MAX_ELIXIR, self.elixir["red"] + amount)

    def _in_base_deploy_zone(self, team: Team, y: float) -> bool:
        if team == "blue":
            return y >= arena_config.RIVER_Y_END
        return y <= arena_config.RIVER_Y_START

    def _in_advanced_deploy_zone(self, team: Team, x: float, y: float) -> bool:
        lane = "left" if x < LANE_WIDTH else "right"
        if not self._enemy_princess_tower_destroyed(team, lane):
            return False
        x_min, x_max = self._lane_bounds(lane)
        if x < x_min or x > x_max:
            return False
        if team == "blue":
            return arena_config.RIVER_Y_START - ADVANCED_DEPLOY_DEPTH <= y <= arena_config.RIVER_Y_START
        return arena_config.RIVER_Y_END <= y <= arena_config.RIVER_Y_END + ADVANCED_DEPLOY_DEPTH

    def _lane_bounds(self, lane: str) -> tuple[float, float]:
        if lane == "left":
            return 0.0, LANE_WIDTH
        return LANE_WIDTH, arena_config.ARENA_WIDTH

    def _enemy_princess_tower_destroyed(self, team: Team, lane: str) -> bool:
        enemy_team = "red" if team == "blue" else "blue"
        return self._princess_tower_destroyed(enemy_team, lane)

    def _princess_tower_destroyed(self, team: Team, lane: str) -> bool:
        if not self.config.start_with_towers:
            return False
        for entity in self.game.entities:
            if entity.team != team or entity.stats.id != "princess_tower" or entity.hp <= 0:
                continue
            entity_lane = "left" if entity.pos.x < LANE_WIDTH else "right"
            if entity_lane == lane:
                return False
        return True

    def _tower_hp(self) -> dict[str, float]:
        totals = {"blue": 0.0, "red": 0.0}
        for entity in self.game.entities:
            if entity.stats.type == "tower" and entity.hp > 0:
                totals[entity.team] += entity.hp
        return totals

    def _king_dead(self, team: Team) -> bool:
        return not any(entity.team == team and entity.stats.id == "king_tower" and entity.hp > 0 for entity in self.game.entities)

    def _winner(self) -> Team | None:
        if self._king_dead("blue"):
            return "red"
        if self._king_dead("red"):
            return "blue"
        return None
