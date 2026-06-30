from __future__ import annotations

from abc import ABC, abstractmethod

from quadrant_wars import balance_config as cfg


class Unit(ABC):
    """Abstract stack of units owned by a territory."""

    def __init__(self, count: int = 1) -> None:
        if count < 0:
            raise ValueError("Unit count cannot be negative")
        self._count = count

    @property
    def count(self) -> int:
        return self._count

    @property
    def is_alive(self) -> bool:
        return self._count > 0

    @property
    @abstractmethod
    def combat_value(self) -> int:
        """How many attacking soldiers one unit in this stack can absorb."""

    @property
    def total_combat_value(self) -> int:
        return self._count * self.combat_value

    @property
    def is_mobile(self) -> bool:
        return False

    @abstractmethod
    def update(self, dt: float, territory: object) -> None:
        """Polymorphic per-frame behavior."""

    def add(self, amount: int) -> None:
        if amount < 0:
            raise ValueError("Cannot add a negative amount")
        self._count += amount

    def remove(self, amount: int) -> int:
        if amount < 0:
            raise ValueError("Cannot remove a negative amount")
        removed = min(self._count, amount)
        self._count -= removed
        return removed


class Queen(Unit):
    @property
    def combat_value(self) -> int:
        return cfg.QUEEN_COMBAT_VALUE

    def update(self, dt: float, territory: object) -> None:
        return None

    def can_command_attack(self) -> bool:
        return self.is_alive


class Worker(Unit):
    @property
    def combat_value(self) -> int:
        return cfg.WORKER_COMBAT_VALUE

    def update(self, dt: float, territory: object) -> None:
        if self.is_alive and hasattr(territory, "add_food"):
            territory.add_food(self._count * cfg.FOOD_PER_WORKER_PER_SECOND * dt)


class Soldier(Unit):
    @property
    def combat_value(self) -> int:
        return 1

    @property
    def is_mobile(self) -> bool:
        return True

    def update(self, dt: float, territory: object) -> None:
        return None

