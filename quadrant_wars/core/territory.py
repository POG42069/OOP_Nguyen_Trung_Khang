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
    queen_hp: float = 0.0
    queen_max_hp: int = 0


class Territory:
    def __init__(self, territory_id: int, owner: object, polygon: Iterable[Point]) -> None:
        self._id = territory_id
        self._owner = owner
        self._polygon = list(polygon)
        self._food = cfg.STARTING_FOOD
        self._queen = Queen(cfg.STARTING_QUEENS)
        self._workers = Worker(cfg.STARTING_WORKERS)
        self._soldiers = Soldier(cfg.STARTING_SOLDIERS)
        self._is_capital = True
        self._spawn_queue: list[str] = []
        self._spawn_timer = 0.0
        self._spawn_effects: list[float] = []
        self._visual_spawns: list[dict[str, any]] = []

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
    def is_capital(self) -> bool:
        return self._is_capital

    @is_capital.setter
    def is_capital(self, value: bool) -> None:
        self._is_capital = value

    @property
    def spawn_effects(self) -> list[float]:
        return self._spawn_effects

    @property
    def spawn_queue_size(self) -> int:
        return len(self._spawn_queue)

    @property
    def visual_spawns(self) -> list[dict[str, any]]:
        return self._visual_spawns

    @property
    def defense_value(self) -> float:
        """Total defense strength - sum of all unit HP for bot evaluation."""
        return (
            self._soldiers.total_hp
            + self._workers.total_hp
            + (self._queen.total_hp if self._queen.is_alive else 0)
        )

    @property
    def defense_value_legacy(self) -> int:
        """Legacy combat-value based defense for bot ratio calculations."""
        return (
            self._soldiers.total_combat_value
            + self._workers.total_combat_value
            + (self._queen.total_combat_value if self._queen.is_alive else 0)
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
            queen_hp=self._queen.front_hp if self._queen.is_alive else 0.0,
            queen_max_hp=cfg.QUEEN_HP,
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

    def can_buy_worker(self) -> bool:
        if not self.can_recruit:
            return False
        if self._workers.count >= cfg.MAX_WORKERS_PER_TERRITORY:
            return False
        return self._food >= self.worker_cost()

    def buy_soldier(self, amount: int = 1) -> bool:
        if not self.can_recruit or amount <= 0:
            return False
        cost = cfg.SOLDIER_COST * amount
        if not self.spend_food(cost):
            return False
        self._spawn_queue.extend(["soldier"] * amount)
        return True

    def buy_worker(self) -> bool:
        if not self.can_buy_worker():
            return False
        cost = self.worker_cost()
        if not self.spend_food(cost):
            return False
        self._spawn_queue.append("worker")
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

        # Capital queen regens faster
        if self._is_capital and self._queen.is_alive:
            extra_regen = cfg.CAPITAL_REGEN_BONUS * dt
            if self._queen.front_hp < self._queen.max_hp:
                self._queen.heal(extra_regen)

        # Process spawn queue
        self._spawn_effects = [t - dt for t in self._spawn_effects if t - dt > 0]
        
        # Process visual spawns
        for vs in self._visual_spawns:
            vs["progress"] += dt / 2.0  # 2 seconds animation
        self._visual_spawns = [vs for vs in self._visual_spawns if vs["progress"] < 1.0]

        if self._spawn_queue:
            self._spawn_timer -= dt
            if self._spawn_timer <= 0:
                unit_type = self._spawn_queue.pop(0)
                if unit_type == "soldier":
                    self._soldiers.add(1)
                elif unit_type == "worker":
                    self._workers.add(1)
                
                self._visual_spawns.append({
                    "role": unit_type,
                    "progress": 0.0,
                    "index": self._soldiers.count - 1 if unit_type == "soldier" else self._workers.count - 1
                })
                self._spawn_effects.append(1.0)
                self._spawn_timer = cfg.SPAWN_DELAY

    def eliminate_command_units(self) -> None:
        self._queen.remove(self._queen.count)
        self._workers.remove(self._workers.count)
        self._spawn_queue.clear()
        self._visual_spawns.clear()
        self._food = 0.0

    def reset_after_capture(self, new_owner: object, surviving_soldiers: int) -> None:
        """Capture territory: new owner gets queen + survivors + workers + bonus food."""
        self._owner = new_owner
        # Kill old queen, spawn new one for new owner
        self._queen.remove(self._queen.count)
        self._queen = Queen(1)
        # Keep existing workers (reward for conquering!)
        # Reset soldiers to survivors
        self._soldiers.remove(self._soldiers.count)
        self._soldiers.add(surviving_soldiers)
        # Bonus food for conquering
        self._food = cfg.CAPTURE_FOOD_BONUS
        # Captured territory is not capital
        self._is_capital = False
        self._spawn_queue.clear()
        self._visual_spawns.clear()
        self._spawn_timer = 0.0
