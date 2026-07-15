from __future__ import annotations

from enum import Enum, auto
from typing import Iterable

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.unit import Queen, Soldier, SoldierState, Worker


class WorldObjectiveType(Enum):
    CARAVAN = auto()
    WAR_BANNER = auto()
    ANCIENT_SHRINE = auto()


class WorldObjectiveState(Enum):
    TELEGRAPHING = auto()
    ACTIVE = auto()
    CONTESTED = auto()
    RESOLVED = auto()


class NeutralGuardian:
    name = "Neutral Guardians"
    color = (143, 132, 105)
    is_alive = True
    attack_multiplier = 1.0


class WorldObjective:
    """A persistent neutral combat target that never becomes territory."""

    def __init__(
        self,
        objective_id: int,
        objective_type: WorldObjectiveType,
        position: tuple[float, float],
    ) -> None:
        self._id = objective_id
        self._objective_type = objective_type
        self._position = position
        self._state = WorldObjectiveState.TELEGRAPHING
        self._owner = NeutralGuardian()
        self._queen = Queen(1)
        self._queen.take_damage(max(0.0, self._queen.front_hp - cfg.OBJECTIVE_CORE_HP))
        self._workers = Worker(0)
        self._soldiers = Soldier(cfg.OBJECTIVE_GUARDS)
        self._elapsed = 0.0
        self._captured_by: object | None = None
        self._surviving_attackers = 0

    @property
    def id(self) -> int:
        return self._id

    @property
    def objective_type(self) -> WorldObjectiveType:
        return self._objective_type

    @property
    def state(self) -> WorldObjectiveState:
        return self._state

    @property
    def active(self) -> bool:
        return self._state in (WorldObjectiveState.ACTIVE, WorldObjectiveState.CONTESTED)

    @property
    def elapsed(self) -> float:
        return self._elapsed

    @property
    def centroid(self) -> tuple[float, float]:
        return self._position

    @property
    def polygon(self) -> list[tuple[float, float]]:
        x, y = self._position
        return [(x - 28, y - 20), (x + 28, y - 20), (x + 28, y + 20), (x - 28, y + 20)]

    @property
    def owner(self) -> NeutralGuardian:
        return self._owner

    @owner.setter
    def owner(self, value: object) -> None:
        return None

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
    def damage_taken_multiplier(self) -> float:
        return 1.0

    @property
    def core_hp(self) -> float:
        return self._queen.front_hp

    @property
    def core_max_hp(self) -> int:
        return cfg.OBJECTIVE_CORE_HP

    @property
    def captured_by(self) -> object | None:
        return self._captured_by

    @property
    def surviving_attackers(self) -> int:
        return self._surviving_attackers

    @property
    def display_name(self) -> str:
        return self._objective_type.name.replace("_", " ").title()

    @property
    def defense_value_legacy(self) -> int:
        return self._soldiers.total_combat_value + 2

    def update(self, dt: float) -> None:
        self._elapsed += dt

    def activate(self) -> None:
        if self._state is WorldObjectiveState.TELEGRAPHING:
            self._state = WorldObjectiveState.ACTIVE

    def start_contest(self) -> None:
        if self.active:
            self._state = WorldObjectiveState.CONTESTED

    def end_contest(self) -> None:
        if self._state is WorldObjectiveState.CONTESTED:
            self._state = WorldObjectiveState.ACTIVE

    def add_soldiers(self, amount: int) -> None:
        self._soldiers.add(amount)

    def remove_soldiers(self, amount: int) -> int:
        return self._soldiers.remove(amount)

    def detach_soldiers(self, amount: int) -> list[SoldierState]:
        return [
            SoldierState(unit_id=-1, hp=hp, source_id=-1)
            for hp in self._soldiers.detach_hp(amount)
        ]

    def receive_soldiers(self, soldiers: Iterable[SoldierState]) -> None:
        self._soldiers.add_with_hp([soldier.hp for soldier in soldiers])

    def reset_after_capture(
        self,
        new_owner: object,
        surviving_soldiers: int | Iterable[SoldierState],
    ) -> None:
        self._captured_by = new_owner
        if isinstance(surviving_soldiers, int):
            self._surviving_attackers = surviving_soldiers
        else:
            self._surviving_attackers = sum(1 for _ in surviving_soldiers)
        self._state = WorldObjectiveState.RESOLVED
