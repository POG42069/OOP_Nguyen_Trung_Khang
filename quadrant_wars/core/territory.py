from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterable

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.unit import Queen, Soldier, Unit, Worker

Point = tuple[float, float]


class TerritorySpecialization(Enum):
    NONE = auto()
    ECONOMY = auto()
    BARRACKS = auto()
    FORTRESS = auto()


@dataclass(frozen=True)
class DevelopmentQuote:
    specialization: TerritorySpecialization
    current_level: int
    resulting_level: int
    cost: int
    action: str
    allowed: bool
    reason: str = ""


@dataclass(frozen=True)
class DevelopmentResult:
    success: bool
    quote: DevelopmentQuote | None
    message: str


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
    specialization: TerritorySpecialization = TerritorySpecialization.NONE
    specialization_level: int = 0


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
        self._specialization = TerritorySpecialization.NONE
        self._specialization_level = 0

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
    def specialization(self) -> TerritorySpecialization:
        return self._specialization

    @property
    def specialization_level(self) -> int:
        return self._specialization_level

    @property
    def worker_income_multiplier(self) -> float:
        if self._specialization is TerritorySpecialization.ECONOMY:
            return 1.0 + cfg.ECONOMY_INCOME_BONUS_PER_LEVEL * self._specialization_level
        return 1.0

    @property
    def soldier_cost(self) -> int:
        discount = 0
        if self._specialization is TerritorySpecialization.BARRACKS:
            discount = cfg.BARRACKS_SOLDIER_DISCOUNT_PER_LEVEL * self._specialization_level
        return max(1, cfg.SOLDIER_COST - discount)

    @property
    def soldier_spawn_delay(self) -> float:
        reduction = 0.0
        if self._specialization is TerritorySpecialization.BARRACKS:
            reduction = cfg.BARRACKS_SPAWN_REDUCTION_PER_LEVEL * self._specialization_level
        return max(0.15, cfg.SPAWN_DELAY * (1.0 - reduction))

    @property
    def damage_taken_multiplier(self) -> float:
        reduction = 0.0
        if self._specialization is TerritorySpecialization.FORTRESS:
            reduction = cfg.FORTRESS_DAMAGE_REDUCTION_PER_LEVEL * self._specialization_level
        return max(0.1, 1.0 - reduction)

    @property
    def queen_regen_multiplier(self) -> float:
        if self._specialization is TerritorySpecialization.FORTRESS:
            return 1.0 + cfg.FORTRESS_QUEEN_REGEN_BONUS_PER_LEVEL * self._specialization_level
        return 1.0

    @property
    def defense_value(self) -> float:
        """Total defense strength - sum of all unit HP for bot evaluation."""
        raw = (
            self._soldiers.total_hp
            + self._workers.total_hp
            + (self._queen.total_hp if self._queen.is_alive else 0)
        )
        return raw / self.damage_taken_multiplier

    @property
    def defense_value_legacy(self) -> int:
        """Legacy combat-value based defense for bot ratio calculations."""
        raw = (
            self._soldiers.total_combat_value
            + self._workers.total_combat_value
            + (self._queen.total_combat_value if self._queen.is_alive else 0)
        )
        return int(round(raw / self.damage_taken_multiplier))

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
            specialization=self._specialization,
            specialization_level=self._specialization_level,
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

    def development_quote(self, specialization: TerritorySpecialization) -> DevelopmentQuote:
        if specialization is TerritorySpecialization.NONE:
            return DevelopmentQuote(
                specialization, self._specialization_level, self._specialization_level,
                0, "none", False, "Choose a development branch",
            )
        if not self.can_recruit:
            return DevelopmentQuote(
                specialization, self._specialization_level, self._specialization_level,
                0, "blocked", False, "This territory cannot be developed",
            )

        if self._specialization is TerritorySpecialization.NONE:
            cost = cfg.DEVELOPMENT_TIER_1_COST
            resulting_level = 1
            action = "build"
        elif specialization is self._specialization:
            if self._specialization_level >= cfg.DEVELOPMENT_MAX_LEVEL:
                return DevelopmentQuote(
                    specialization, self._specialization_level, self._specialization_level,
                    0, "max", False, "Maximum level reached",
                )
            resulting_level = self._specialization_level + 1
            cost = (
                cfg.DEVELOPMENT_TIER_1_COST
                if resulting_level == 1
                else cfg.DEVELOPMENT_TIER_2_COST
            )
            action = "repair" if self._specialization_level == 0 else "upgrade"
        else:
            cost = cfg.DEVELOPMENT_CONVERSION_COST
            resulting_level = 1
            action = "convert"

        allowed = self._food >= cost
        reason = "" if allowed else f"Need {cost} gold in this territory"
        return DevelopmentQuote(
            specialization=specialization,
            current_level=self._specialization_level,
            resulting_level=resulting_level,
            cost=cost,
            action=action,
            allowed=allowed,
            reason=reason,
        )

    def develop(self, specialization: TerritorySpecialization) -> DevelopmentResult:
        quote = self.development_quote(specialization)
        if not quote.allowed:
            return DevelopmentResult(False, quote, quote.reason)
        if not self.spend_food(quote.cost):
            return DevelopmentResult(False, quote, "Not enough local gold")
        self._specialization = specialization
        self._specialization_level = quote.resulting_level
        branch = specialization.name.title()
        return DevelopmentResult(True, quote, f"{branch} level {quote.resulting_level} ready")

    def buy_soldier(self, amount: int = 1) -> bool:
        if not self.can_recruit or amount <= 0:
            return False
        cost = self.soldier_cost * amount
        if not self.spend_food(cost):
            return False
        was_empty = not self._spawn_queue
        self._spawn_queue.extend(["soldier"] * amount)
        if was_empty:
            self._spawn_timer = self.soldier_spawn_delay
        return True

    def buy_worker(self) -> bool:
        if not self.can_buy_worker():
            return False
        cost = self.worker_cost()
        if not self.spend_food(cost):
            return False
        was_empty = not self._spawn_queue
        self._spawn_queue.append("worker")
        if was_empty:
            self._spawn_timer = cfg.SPAWN_DELAY
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
            extra_regen = cfg.CAPITAL_REGEN_BONUS * self.queen_regen_multiplier * dt
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
                if self._spawn_queue:
                    next_unit = self._spawn_queue[0]
                    self._spawn_timer = (
                        self.soldier_spawn_delay if next_unit == "soldier" else cfg.SPAWN_DELAY
                    )
                else:
                    self._spawn_timer = 0.0

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
        if self._specialization is not TerritorySpecialization.NONE:
            self._specialization_level = max(0, self._specialization_level - 1)
