from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import threading
from typing import Any, Iterable
from urllib.parse import urlencode
import webbrowser

from . import config as arena_config
from .cards import CARDS, Team
from .game import Game
from .vector import Vector2

STARTING_ELIXIR = 5.0
MAX_ELIXIR = 10.0
ELIXIR_REGEN_SECONDS = 2.8
DECK_SIZE = 8
HAND_SIZE = 4
LANE_WIDTH = arena_config.ARENA_WIDTH / 2
ADVANCED_DEPLOY_DEPTH = 5.0
DEFAULT_HUMAN_RENDERER_URL = "http://localhost:5174/OpenRoyale/sim.html"
DEFAULT_DECK_IDS = ("knight", "archers", "giant", "pekka", "musketeer", "hog_rider", "skeletons", "wizard")


@dataclass
class EnvConfig:
    max_time: float = 180.0
    tick_rate: int = 60
    frame_skip: int = 1
    start_with_towers: bool = True


class _HumanRenderBridge:
    def __init__(self, renderer_url: str = DEFAULT_HUMAN_RENDERER_URL) -> None:
        self.renderer_url = renderer_url
        self._state: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._opened = False

    @property
    def endpoint(self) -> str:
        if not self._server:
            self.start()
        assert self._server is not None
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}/state"

    def start(self) -> None:
        if self._server:
            return

        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path.split("?", 1)[0] == "/state":
                    with bridge._lock:
                        payload = json.dumps(bridge._state).encode("utf-8")
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                if self.path.split("?", 1)[0] == "/health":
                    payload = b"ok"
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "text/plain")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                self.send_error(HTTPStatus.NOT_FOUND)

            def log_message(self, format: str, *args: Any) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def show(self) -> None:
        if self._opened:
            return
        self.start()
        url = f"{self.renderer_url}?{urlencode({'state': self.endpoint})}"
        webbrowser.open(url)
        self._opened = True

    def publish(self, state: dict[str, Any]) -> None:
        self.start()
        with self._lock:
            self._state = state

    def close(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        if self._thread:
            self._thread.join(timeout=1)
        self._server = None
        self._thread = None


class OpenRoyaleEnv:
    """Small Gymnasium-style wrapper around :class:`openroyale_sim.game.Game`.

    Actions are intentionally plain dictionaries so training code can choose its
    own action encoding. A step accepts one action dict or an iterable of them:

    ``{"type": "deploy", "card": "knight", "team": "blue", "x": 9, "y": 24}``
    ``{"type": "ability", "entity_id": 12}``
    """

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        max_time: float = 180.0,
        tick_rate: int = 60,
        frame_skip: int = 1,
        start_with_towers: bool = True,
        cards=None,
        decks: dict[Team, Iterable[str]] | Iterable[str] | None = None,
        render_mode: str | None = None,
        human_renderer_url: str = DEFAULT_HUMAN_RENDERER_URL,
    ) -> None:
        if render_mode not in (None, "human"):
            raise ValueError("render_mode must be None or 'human'")
        self.config = EnvConfig(max_time=max_time, tick_rate=tick_rate, frame_skip=frame_skip, start_with_towers=start_with_towers)
        self.cards = cards or CARDS
        self.decks = self._normalize_decks(decks)
        self.card_cycle = {team: list(deck) for team, deck in self.decks.items()}
        self.game = Game(cards=self.cards)
        self.render_mode = render_mode
        self._human_bridge = _HumanRenderBridge(human_renderer_url) if render_mode == "human" else None
        self._previous_tower_hp = {"blue": 0.0, "red": 0.0}
        self.elixir = {"blue": STARTING_ELIXIR, "red": STARTING_ELIXIR}

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
        del options
        self.game = Game(seed=seed, cards=self.cards)
        if self.config.start_with_towers:
            self.game.start()
        self._previous_tower_hp = self._tower_hp()
        self.elixir = {"blue": STARTING_ELIXIR, "red": STARTING_ELIXIR}
        self.card_cycle = {team: list(deck) for team, deck in self.decks.items()}
        observation = self.observe()
        if self.render_mode == "human":
            self.render()
        return observation, {"seed": seed}

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
        observation = self.observe()
        if self.render_mode == "human":
            self.render()
        return observation, reward, terminated, truncated, info

    def render(self) -> None:
        if self.render_mode != "human":
            return None
        assert self._human_bridge is not None
        self._human_bridge.publish(self._render_snapshot())
        self._human_bridge.show()
        return None

    def close(self) -> None:
        if self._human_bridge:
            self._human_bridge.close()

    def observe(self) -> dict[str, Any]:
        return {
            "time": self.game.time_elapsed,
            "elixir": dict(self.elixir),
            "hands": self._hands_snapshot(),
            "decks": self._decks_snapshot(),
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

    def _render_snapshot(self) -> dict[str, Any]:
        return {
            "time": self.game.time_elapsed,
            "elixir": dict(self.elixir),
            "hands": self._hands_snapshot(),
            "decks": self._decks_snapshot(),
            "arena": {
                "width": arena_config.ARENA_WIDTH,
                "height": arena_config.ARENA_HEIGHT,
                "river_y_start": arena_config.RIVER_Y_START,
                "river_y_end": arena_config.RIVER_Y_END,
                "left_bridge_x": arena_config.LEFT_BRIDGE_X,
                "right_bridge_x": arena_config.RIGHT_BRIDGE_X,
                "bridge_width": arena_config.BRIDGE_WIDTH,
            },
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
                    "radius": entity.stats.radius,
                    "target_id": entity.target.id if entity.target else None,
                    "is_moving": entity.is_moving,
                    "is_attacking": entity.is_attacking,
                    "attack_cooldown": entity.attack_cooldown,
                    "action_frame_timer": entity.action_frame_timer,
                    "hit_speed": entity.stats.hit_speed,
                    "load_time": entity.stats.load_time,
                    "facing_direction": {"x": entity.facing_direction.x, "y": entity.facing_direction.y},
                    "activation_state": entity.activation_state,
                    "activation_timer": entity.activation_timer,
                    "ability_cooldown": entity.ability_cooldown,
                    "effect": entity.current_ability_effect,
                    "path_points": [{"x": point.x, "y": point.y} for point in entity.path_points],
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
                    "start_x": projectile.start_pos.x,
                    "start_y": projectile.start_pos.y,
                    "target_x": projectile.target.pos.x,
                    "target_y": projectile.target.pos.y,
                    "target_id": projectile.target.id,
                    "asset": projectile.asset,
                    "trajectory": projectile.trajectory,
                }
                for projectile in self.game.projectiles
            ],
            "effects": [
                {
                    "id": effect.id,
                    "name": effect.name,
                    "x": effect.pos.x,
                    "y": effect.pos.y,
                    "start_time": effect.start_time,
                    "duration": effect.duration if math.isfinite(effect.duration) else None,
                    "file_name": effect.file_name,
                }
                for effect in self.game.effects
            ],
            "aoe_circles": [
                {
                    "id": circle.id,
                    "x": circle.pos.x,
                    "y": circle.pos.y,
                    "radius": circle.radius,
                    "start_time": circle.start_time,
                    "duration": circle.duration,
                }
                for circle in self.game.aoe_circles
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
            if card_id not in self.card_cycle[team][:HAND_SIZE]:
                return False, "card not in hand"
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
            self._cycle_card(team, card_id)
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

    def _normalize_decks(self, decks: dict[Team, Iterable[str]] | Iterable[str] | None) -> dict[Team, list[str]]:
        if decks is None:
            deck_by_team: dict[Team, Iterable[str]] = {"blue": DEFAULT_DECK_IDS, "red": DEFAULT_DECK_IDS}
        elif isinstance(decks, dict):
            deck_by_team = {"blue": decks.get("blue", DEFAULT_DECK_IDS), "red": decks.get("red", DEFAULT_DECK_IDS)}
        else:
            deck_by_team = {"blue": decks, "red": decks}

        return {team: self._validate_deck(team, deck) for team, deck in deck_by_team.items()}

    def _validate_deck(self, team: Team, deck: Iterable[str]) -> list[str]:
        card_ids = list(deck)
        if len(card_ids) != DECK_SIZE:
            raise ValueError(f"{team} deck must contain exactly {DECK_SIZE} cards")
        if len(set(card_ids)) != DECK_SIZE:
            raise ValueError(f"{team} deck must not contain duplicate cards")
        for card_id in card_ids:
            if card_id not in self.cards:
                raise ValueError(f"{team} deck contains unknown card: {card_id}")
            if self.cards[card_id].type == "tower":
                raise ValueError(f"{team} deck cannot contain tower card: {card_id}")
        return card_ids

    def _cycle_card(self, team: Team, card_id: str) -> None:
        cycle = self.card_cycle[team]
        hand_slot = cycle[:HAND_SIZE].index(card_id)
        next_card = cycle.pop(HAND_SIZE)
        cycle[hand_slot] = next_card
        cycle.append(card_id)

    def _hands_snapshot(self) -> dict[Team, list[dict[str, Any]]]:
        return {team: [self._card_snapshot(card_id) for card_id in cycle[:HAND_SIZE]] for team, cycle in self.card_cycle.items()}

    def _decks_snapshot(self) -> dict[Team, list[dict[str, Any]]]:
        return {team: [self._card_snapshot(card_id) for card_id in deck] for team, deck in self.decks.items()}

    def _card_snapshot(self, card_id: str) -> dict[str, Any]:
        stats = self.cards[card_id]
        return {"id": stats.id, "name": stats.name, "elixir_cost": stats.elixir_cost}

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
