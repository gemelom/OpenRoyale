"""Headless Python simulator for OpenRoyale.

The package mirrors the TypeScript engine closely enough for reinforcement
learning and batch simulation use. It has no rendering dependency.
"""

from .cards import CARDS, EntityStats
from .env import OpenRoyaleEnv
from .game import Game
from .policies import HeuristicPolicy
from .vector import Vector2

__all__ = ["CARDS", "EntityStats", "Game", "HeuristicPolicy", "OpenRoyaleEnv", "Vector2"]
