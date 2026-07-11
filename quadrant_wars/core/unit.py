from __future__ import annotations

from abc import ABC, abstractmethod

from quadrant_wars import balance_config as cfg


class Unit(ABC):
    """Abstract stack of units with individual HP owned by a territory."""

    def __init__(self, count: int = 1) -> None:
        if count < 0:
            raise ValueError("Unit count cannot be negative")
        self._count = count
        self._hp_list: list[float] = [float(self.max_hp)] * count

    # --- Abstract properties subclasses must define ---

    @property
    @abstractmethod
    def max_hp(self) -> int:
        """Maximum hit-points for one unit of this type."""

    @property
    @abstractmethod
    def atk(self) -> int:
        """Attack damage per hit for one unit of this type."""

    @property
    @abstractmethod
    def atk_speed(self) -> float:
        """Attacks per second for one unit of this type."""

    @property
    @abstractmethod
    def combat_value(self) -> int:
        """Legacy: how many attacking soldiers one unit can absorb (for bot AI)."""

    # --- Concrete properties ---

    @property
    def count(self) -> int:
        return self._count

    @property
    def is_alive(self) -> bool:
        return self._count > 0

    @property
    def total_hp(self) -> float:
        """Sum of HP across all units in the stack."""
        return sum(self._hp_list)

    @property
    def total_combat_value(self) -> int:
        return self._count * self.combat_value

    @property
    def dps(self) -> float:
        """Total damage per second from this stack."""
        return self._count * self.atk * self.atk_speed

    @property
    def is_mobile(self) -> bool:
        return False

    @property
    def front_hp(self) -> float:
        """HP of the frontmost unit (for display)."""
        return self._hp_list[0] if self._hp_list else 0.0

    # --- Methods ---

    @abstractmethod
    def update(self, dt: float, territory: object) -> None:
        """Polymorphic per-frame behavior."""

    def add(self, amount: int) -> None:
        if amount < 0:
            raise ValueError("Cannot add a negative amount")
        self._count += amount
        self._hp_list.extend([float(self.max_hp)] * amount)

    def remove(self, amount: int) -> int:
        if amount < 0:
            raise ValueError("Cannot remove a negative amount")
        removed = min(self._count, amount)
        self._count -= removed
        self._hp_list = self._hp_list[:self._count]
        return removed

    def take_damage(self, damage: float) -> float:
        """Apply damage to front units. Returns actual damage dealt."""
        if damage <= 0 or not self._hp_list:
            return 0.0
        total_dealt = 0.0
        remaining = damage
        while remaining > 0 and self._hp_list:
            dealt = min(remaining, self._hp_list[0])
            self._hp_list[0] -= dealt
            total_dealt += dealt
            remaining -= dealt
            if self._hp_list[0] <= 0:
                self._hp_list.pop(0)
                self._count -= 1
        return total_dealt

    def heal(self, amount: float) -> None:
        """Heal the front unit, capped at max_hp."""
        if self._hp_list:
            self._hp_list[0] = min(float(self.max_hp), self._hp_list[0] + amount)

    def heal_all(self, amount: float) -> None:
        """Heal all units in the stack."""
        for i in range(len(self._hp_list)):
            self._hp_list[i] = min(float(self.max_hp), self._hp_list[i] + amount)


class Queen(Unit):
    @property
    def max_hp(self) -> int:
        return cfg.QUEEN_HP

    @property
    def atk(self) -> int:
        return cfg.QUEEN_ATK

    @property
    def atk_speed(self) -> float:
        return cfg.QUEEN_ATK_SPEED

    @property
    def combat_value(self) -> int:
        return cfg.QUEEN_COMBAT_VALUE

    def update(self, dt: float, territory: object) -> None:
        # Queen regenerates HP when not in combat
        if self.is_alive and self._hp_list[0] < self.max_hp:
            regen = cfg.QUEEN_HP_REGEN * dt
            self._hp_list[0] = min(float(self.max_hp), self._hp_list[0] + regen)

    def can_command_attack(self) -> bool:
        return self.is_alive


class Worker(Unit):
    @property
    def max_hp(self) -> int:
        return cfg.WORKER_HP

    @property
    def atk(self) -> int:
        return cfg.WORKER_ATK

    @property
    def atk_speed(self) -> float:
        return 0.0

    @property
    def combat_value(self) -> int:
        return cfg.WORKER_COMBAT_VALUE

    def update(self, dt: float, territory: object) -> None:
        if self.is_alive and hasattr(territory, "add_food"):
            territory.add_food(self._count * cfg.FOOD_PER_WORKER_PER_SECOND * dt)


class Soldier(Unit):
    @property
    def max_hp(self) -> int:
        return cfg.SOLDIER_HP

    @property
    def atk(self) -> int:
        return cfg.SOLDIER_ATK

    @property
    def atk_speed(self) -> float:
        return cfg.SOLDIER_ATK_SPEED

    @property
    def combat_value(self) -> int:
        return 1

    @property
    def is_mobile(self) -> bool:
        return True

    def update(self, dt: float, territory: object) -> None:
        return None
