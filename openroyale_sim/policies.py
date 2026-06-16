from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import config as arena_config
from .cards import Team
from .env import MAX_ELIXIR


@dataclass(frozen=True)
class HeuristicPolicy:
    """Simple policy that leaks no elixir and plays the priciest card in hand.

    When the team's elixir is full, it deploys the highest-cost affordable card
    at the center back of that team's base deploy zone. Ties keep hand order.
    """

    team: Team
    full_elixir_threshold: float = 7

    def action(self, observation: dict[str, Any]) -> dict[str, object]:
        elixir = float(observation.get("elixir", {}).get(self.team, 0.0))
        if elixir < self.full_elixir_threshold:
            return {"type": "noop"}

        hand = observation.get("hands", {}).get(self.team, [])
        playable_cards = [
            card
            for card in hand
            if isinstance(card, dict) and float(card.get("elixir_cost", MAX_ELIXIR + 1)) <= elixir
        ]
        if not playable_cards:
            return {"type": "noop"}

        card = max(playable_cards, key=lambda candidate: float(candidate["elixir_cost"]))
        x, y = backline_deploy_position(self.team)
        return {"type": "deploy", "card": card["id"], "team": self.team, "x": x, "y": y}


def backline_deploy_position(team: Team) -> tuple[float, float]:
    x = arena_config.ARENA_WIDTH / 2
    if team == "blue":
        return x, arena_config.ARENA_HEIGHT - 1
    return x, 1.0
