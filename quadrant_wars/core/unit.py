from abc import ABC, abstractmethod

from quadrant_wars import balance_config as cfg


class SoldierState:
    """One persistent soldier travelling between territories and battles."""

    def __init__(self, unit_id, hp, source_id):
        self.unit_id = unit_id
        self.hp = hp
        self.source_id = source_id

    def __eq__(self, other):
        return (
            isinstance(other, SoldierState)
            and self.unit_id == other.unit_id
            and self.hp == other.hp
            and self.source_id == other.source_id
        )


class DefenderState:
    """One persistent Fortress defender while deployed in a territory battle."""

    def __init__(self, unit_id, hp, source_id):
        self.unit_id = unit_id
        self.hp = hp
        self.source_id = source_id

    def __eq__(self, other):
        return (
            isinstance(other, DefenderState)
            and self.unit_id == other.unit_id
            and self.hp == other.hp
            and self.source_id == other.source_id
        )


class Unit(ABC):
    """Abstract stack of units with individual HP owned by a territory."""

    def __init__(self, count = 1):
        if count < 0:
            raise ValueError("Unit count cannot be negative")
        self._count = count
        self._hp_list = [float(self.max_hp)] * count

    # --- Abstract properties subclasses must define ---

    @property
    @abstractmethod
    def max_hp(self):
        """Maximum hit-points for one unit of this type."""

    @property
    @abstractmethod
    def atk(self):
        """Attack damage per hit for one unit of this type."""

    @property
    @abstractmethod
    def atk_speed(self):
        """Attacks per second for one unit of this type."""

    @property
    @abstractmethod
    def combat_value(self):
        """Legacy: how many attacking soldiers one unit can absorb (for bot AI)."""

    # --- Concrete properties ---

    @property
    def count(self):
        return self._count

    @property
    def is_alive(self):
        return self._count > 0

    @property
    def total_hp(self):
        """Sum of HP across all units in the stack."""
        return sum(self._hp_list)

    @property
    def total_combat_value(self):
        return self._count * self.combat_value

    @property
    def dps(self):
        """Total damage per second from this stack."""
        return self._count * self.atk * self.atk_speed

    @property
    def is_mobile(self):
        return False

    @property
    def front_hp(self):
        """HP of the frontmost unit (for display)."""
        return self._hp_list[0] if self._hp_list else 0.0

    # --- Methods ---

    @abstractmethod
    def update(self, dt, territory):
        """Polymorphic per-frame behavior."""

    def add(self, amount):
        if amount < 0:
            raise ValueError("Cannot add a negative amount")
        self._count += amount
        self._hp_list.extend([float(self.max_hp)] * amount)

    def remove(self, amount):
        if amount < 0:
            raise ValueError("Cannot remove a negative amount")
        removed = min(self._count, amount)
        self._count -= removed
        self._hp_list = self._hp_list[:self._count]
        return removed

    def detach_hp(self, amount):
        """Remove units from the back of the stack and preserve their HP."""
        if amount < 0:
            raise ValueError("Cannot detach a negative amount")
        removed = min(self._count, amount)
        if removed <= 0:
            return []
        detached = self._hp_list[-removed:]
        del self._hp_list[-removed:]
        self._count -= removed
        return detached

    def add_with_hp(self, hp_values):
        """Add individual units without healing survivors during transport."""
        valid = [max(0.01, min(float(self.max_hp), float(hp))) for hp in hp_values if hp > 0]
        self._hp_list.extend(valid)
        self._count += len(valid)

    def take_damage(self, damage):
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

    def heal(self, amount):
        """Heal the front unit, capped at max_hp."""
        if self._hp_list:
            self._hp_list[0] = min(float(self.max_hp), self._hp_list[0] + amount)

    def heal_all(self, amount):
        """Heal all units in the stack."""
        for i in range(len(self._hp_list)):
            self._hp_list[i] = min(float(self.max_hp), self._hp_list[i] + amount)


class Queen(Unit):
    @property
    def max_hp(self):
        return cfg.QUEEN_HP

    @property
    def atk(self):
        return cfg.QUEEN_ATK

    @property
    def atk_speed(self):
        return cfg.QUEEN_ATK_SPEED

    @property
    def combat_value(self):
        return cfg.QUEEN_COMBAT_VALUE

    def update(self, dt, territory):
        # Queen regenerates HP when not in combat
        if self.is_alive and self._hp_list[0] < self.max_hp:
            multiplier = float(getattr(territory, "queen_regen_multiplier", 1.0))
            regen = cfg.QUEEN_HP_REGEN * multiplier * dt
            self._hp_list[0] = min(float(self.max_hp), self._hp_list[0] + regen)

    def can_command_attack(self):
        return self.is_alive


class Worker(Unit):
    @property
    def max_hp(self):
        return cfg.WORKER_HP

    @property
    def atk(self):
        return cfg.WORKER_ATK

    @property
    def atk_speed(self):
        return 0.0

    @property
    def combat_value(self):
        return cfg.WORKER_COMBAT_VALUE

    def update(self, dt, territory):
        if self.is_alive and hasattr(territory, "add_food"):
            multiplier = float(getattr(territory, "worker_income_multiplier", 1.0))
            territory.add_food(self._count * cfg.FOOD_PER_WORKER_PER_SECOND * multiplier * dt)


class Soldier(Unit):
    @property
    def max_hp(self):
        return cfg.SOLDIER_HP

    @property
    def atk(self):
        return cfg.SOLDIER_ATK

    @property
    def atk_speed(self):
        return cfg.SOLDIER_ATK_SPEED

    @property
    def combat_value(self):
        return 1

    @property
    def is_mobile(self):
        return True

    def update(self, dt, territory):
        return None


class Defender(Unit):
    @property
    def max_hp(self):
        return cfg.DEFENDER_HP

    @property
    def atk(self):
        return cfg.DEFENDER_ATK

    @property
    def atk_speed(self):
        return cfg.DEFENDER_ATK_SPEED

    @property
    def combat_value(self):
        return cfg.DEFENDER_COMBAT_VALUE

    def update(self, dt, territory):
        if self.is_alive:
            self.heal_all(cfg.DEFENDER_HP_REGEN * dt)
