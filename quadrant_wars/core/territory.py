from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.unit import Queen, Soldier, Unit, Worker

Point = tuple[float, float]


@dataclass(frozen=True)
class TerritoryView:
    id: int
    owner_id: int
    soldiers: int
    workers: int
    queen_alive: bool
    food: float


class Territory:
    def __init__(self, territory_id: int, owner: object, polygon: Iterable[Point]) -> None:
        self._id = territory_id
        self._owner = owner
        self._polygon = list(polygon)
        self._food = cfg.STARTING_FOOD
        self._queen = Queen(cfg.STARTING_QUEENS)
        self._workers = Worker(cfg.STARTING_WORKERS)
        self._soldiers = Soldier(cfg.STARTING_SOLDIERS)

    @property
    def id(self) -> int:
        return self._id

    @property
    def owner(self) -> object:
        return self._owner

    @owner.setter
    def owner(self, value: object) -> None:
        self._owner = value

    @property
    def polygon(self) -> list[Point]:
        return list(self._polygon)

    @property
    def centroid(self) -> Point:
        xs = [p[0] for p in self._polygon]
        ys = [p[1] for p in self._polygon]
        return (sum(xs) / len(xs), sum(ys) / len(ys))

    @property
    def food(self) -> float:
        return self._food

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
    def units(self) -> list[Unit]:
        return [self._queen, self._workers, self._soldiers]

    @property
    def hp(self) -> int:
        return self._queen.count + self._workers.count + self._soldiers.count

    @property
    def defense_value(self) -> int:
        return (
            self._soldiers.total_combat_value
            + self._workers.total_combat_value
            + self._queen.total_combat_value
        )

    @property
    def can_recruit(self) -> bool:
        return self._queen.is_alive and getattr(self._owner, "is_alive", True)

    def snapshot(self) -> TerritoryView:
        return TerritoryView(
            id=self._id,
            owner_id=getattr(self._owner, "id", -1),
            soldiers=self._soldiers.count,
            workers=self._workers.count,
            queen_alive=self._queen.is_alive,
            food=self._food,
        )

    def add_food(self, amount: float) -> None:
        if amount > 0:
            self._food += amount

    def spend_food(self, amount: float) -> bool:
        if amount <= self._food:
            self._food -= amount
            return True
        return False

    def worker_cost(self) -> int:
        return int(round(cfg.WORKER_BASE_COST * (cfg.WORKER_COST_GROWTH ** self._workers.count)))

    def buy_soldier(self, amount: int = 1) -> bool:
        if not self.can_recruit or amount <= 0:
            return False
        cost = cfg.SOLDIER_COST * amount
        if not self.spend_food(cost):
            return False
        self._soldiers.add(amount)
        return True

    def buy_worker(self) -> bool:
        if not self.can_recruit:
            return False
        cost = self.worker_cost()
        if not self.spend_food(cost):
            return False
        self._workers.add(1)
        return True

    def remove_soldiers(self, amount: int) -> int:
        return self._soldiers.remove(amount)

    def add_soldiers(self, amount: int) -> None:
        self._soldiers.add(amount)

    def update(self, dt: float) -> None:
        if not self.can_recruit:
            return
        for unit in self.units:
            unit.update(dt, self)

    def eliminate_command_units(self) -> None:
        self._queen.remove(self._queen.count)
        self._workers.remove(self._workers.count)
        self._food = 0.0

    def reset_after_capture(self, new_owner: object, surviving_soldiers: int) -> None:
        self._owner = new_owner
        self._queen.remove(self._queen.count)
        self._workers.remove(self._workers.count)
        self._soldiers.remove(self._soldiers.count)
        self._soldiers.add(surviving_soldiers)
        self._food = 0.0

