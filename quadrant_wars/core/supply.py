from __future__ import annotations

import math
from typing import Iterable

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.unit import Queen, Soldier, Worker


class SupplyDrop:
    """A 'Thính' that players can capture for rewards."""

    def __init__(self, drop_id: int, position: tuple[float, float]) -> None:
        self._id = drop_id
        self._position = position
        self._owner = None
        # Fake units to duck-type with CombatZone
        self._queen = Queen(1)
        # Drop is fragile so it doesn't take long to open once defenders are cleared
        self._queen.take_damage(self._queen.front_hp - 10) 
        self._workers = Worker(0)
        self._soldiers = Soldier(0)
        self._elapsed = 0.0
        self._active = False

    @property
    def id(self) -> int:
        return self._id

    @property
    def centroid(self) -> tuple[float, float]:
        return self._position

    @property
    def polygon(self) -> list[tuple[float, float]]:
        # Dummy small polygon for rendering selection if needed
        cx, cy = self._position
        return [(cx - 10, cy - 10), (cx + 10, cy - 10), (cx + 10, cy + 10), (cx - 10, cy + 10)]

    @property
    def owner(self) -> object:
        return self._owner

    @owner.setter
    def owner(self, value: object) -> None:
        pass  # Cannot be owned until captured

    @property
    def queen(self) -> Queen:
        return self._queen

    @property
    def workers(self) -> Worker:
        return self._workers

    @property
    def soldiers(self) -> Soldier:
        return self._soldiers

    @property
    def active(self) -> bool:
        return self._active

    @property
    def elapsed(self) -> float:
        return self._elapsed

    def add_soldiers(self, amount: int) -> None:
        self._soldiers.add(amount)

    def remove_soldiers(self, amount: int) -> int:
        return self._soldiers.remove(amount)

    def update(self, dt: float) -> None:
        self._elapsed += dt
        if self._elapsed > cfg.SUPPLY_DROP_DELAY:
            self._active = True

    def reset_after_capture(self, new_owner: object, surviving_soldiers: int) -> None:
        """Called by CombatResolver when the drop is captured."""
        # Instead of becoming a territory, it's just marked as dead (queen dead)
        # The game_manager will detect this and apply rewards.
        self._queen.take_damage(9999) 
        # Keep survivors so game_manager can read them if needed
        self._soldiers.remove(self._soldiers.count)
        self._soldiers.add(surviving_soldiers)
