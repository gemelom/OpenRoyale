from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass
class Vector2:
    x: float
    y: float

    def add(self, v: "Vector2") -> "Vector2":
        return Vector2(self.x + v.x, self.y + v.y)

    def sub(self, v: "Vector2") -> "Vector2":
        return Vector2(self.x - v.x, self.y - v.y)

    def mul(self, scalar: float) -> "Vector2":
        return Vector2(self.x * scalar, self.y * scalar)

    def div(self, scalar: float) -> "Vector2":
        return Vector2(self.x / scalar, self.y / scalar)

    def mag(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y)

    def normalize(self) -> "Vector2":
        magnitude = self.mag()
        if magnitude == 0:
            return Vector2(0, 0)
        return self.div(magnitude)

    def distance_to(self, v: "Vector2") -> float:
        return self.sub(v).mag()

    def distance_squared_to(self, v: "Vector2") -> float:
        dx = self.x - v.x
        dy = self.y - v.y
        return dx * dx + dy * dy

    def dot(self, v: "Vector2") -> float:
        return self.x * v.x + self.y * v.y

    def clone(self) -> "Vector2":
        return Vector2(self.x, self.y)
