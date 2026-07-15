from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterable

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.battlefield import territory_landmark_position
from quadrant_wars.core.unit import (
    Defender,
    DefenderState,
    Queen,
    Soldier,
    SoldierState,
    Unit,
    Worker,
)

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
    income_per_second: float = 0.0
    queen_hp: float = 0.0
    queen_max_hp: int = 0
    specialization: TerritorySpecialization = TerritorySpecialization.NONE
    specialization_level: int = 0
    defenders: int = 0
    defender_capacity: int = 0


class Territory:
    def __init__(self, territory_id: int, owner: object, polygon: Iterable[Point]) -> None:
        self._id = territory_id
        self._owner = owner
        self._polygon = list(polygon)
        self._food = cfg.STARTING_FOOD
        self._queen = Queen(cfg.STARTING_QUEENS)
        self._workers = Worker(cfg.STARTING_WORKERS)
        self._soldiers = Soldier(cfg.STARTING_SOLDIERS)
        self._defenders = Defender(0)
        self._defender_respawn_timers: list[float] = []
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
    def battle_position(self) -> Point:
        """Castle gate used as the shared march and combat destination."""
        return territory_landmark_position(self._id, self._polygon)

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
    def defenders(self) -> Defender:
        return self._defenders

    @property
    def units(self) -> list[Unit]:
        return [self._queen, self._workers, self._soldiers, self._defenders]

    @property
    def hp(self) -> int:
        return (
            self._queen.count
            + self._workers.count
            + self._soldiers.count
            + self._defenders.count
        )

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
    def worker_cost_multiplier(self) -> float:
        if self._specialization is TerritorySpecialization.ECONOMY:
            return max(
                0.1,
                1.0 - cfg.ECONOMY_WORKER_DISCOUNT_PER_LEVEL * self._specialization_level,
            )
        return 1.0

    @property
    def base_income_per_second(self) -> float:
        return cfg.BASE_TERRITORY_INCOME_PER_SECOND

    @property
    def worker_income_per_second(self) -> float:
        return (
            self._workers.count
            * cfg.FOOD_PER_WORKER_PER_SECOND
            * self.worker_income_multiplier
        )

    @property
    def income_per_second(self) -> float:
        if not self.can_recruit:
            return 0.0
        return self.base_income_per_second + self.worker_income_per_second

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
    def defender_capacity(self) -> int:
        if (
            self._specialization is TerritorySpecialization.FORTRESS
            and self._specialization_level > 0
        ):
            return cfg.FORTRESS_DEFENDERS_PER_LEVEL * self._specialization_level
        return 0

    @property
    def defender_respawn_count(self) -> int:
        return len(self._defender_respawn_timers)

    @property
    def next_defender_respawn(self) -> float | None:
        if not self._defender_respawn_timers:
            return None
        return min(self._defender_respawn_timers)

    @property
    def defense_value(self) -> float:
        """Total defense strength - sum of all unit HP for bot evaluation."""
        raw = (
            self._soldiers.total_hp
            + self._defenders.total_hp
            + self._workers.total_hp
            + (self._queen.total_hp if self._queen.is_alive else 0)
        )
        return raw / self.damage_taken_multiplier

    @property
    def defense_value_legacy(self) -> int:
        """Legacy combat-value based defense for bot ratio calculations."""
        raw = (
            self._soldiers.total_combat_value
            + self._defenders.total_combat_value
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
            income_per_second=self.income_per_second,
            queen_hp=self._queen.front_hp if self._queen.is_alive else 0.0,
            queen_max_hp=cfg.QUEEN_HP,
            specialization=self._specialization,
            specialization_level=self._specialization_level,
            defenders=self._defenders.count,
            defender_capacity=self.defender_capacity,
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
        normal_cost = cfg.WORKER_BASE_COST * (
            cfg.WORKER_COST_GROWTH ** self._workers.count
        )
        return max(1, int(round(normal_cost * self.worker_cost_multiplier)))

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
        previous_specialization = self._specialization
        previous_capacity = self.defender_capacity
        self._specialization = specialization
        self._specialization_level = quote.resulting_level
        if specialization is TerritorySpecialization.FORTRESS:
            if previous_specialization is not TerritorySpecialization.FORTRESS:
                self._defenders.remove(self._defenders.count)
                self._defender_respawn_timers.clear()
            added_slots = max(0, self.defender_capacity - previous_capacity)
            self._defenders.add(added_slots)
        elif previous_specialization is TerritorySpecialization.FORTRESS:
            self._defenders.remove(self._defenders.count)
            self._defender_respawn_timers.clear()
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

    def detach_soldiers(self, amount: int) -> list[SoldierState]:
        return [
            SoldierState(unit_id=-1, hp=hp, source_id=self._id)
            for hp in self._soldiers.detach_hp(amount)
        ]

    def receive_soldiers(self, soldiers: Iterable[SoldierState]) -> None:
        self._soldiers.add_with_hp([soldier.hp for soldier in soldiers])

    def detach_defenders(self) -> list[DefenderState]:
        return [
            DefenderState(unit_id=-1, hp=hp, source_id=self._id)
            for hp in self._defenders.detach_hp(self._defenders.count)
        ]

    def finish_defense(
        self,
        survivors: Iterable[DefenderState],
        deployed_count: int,
    ) -> None:
        states = list(survivors)
        self._defenders.add_with_hp([state.hp for state in states])
        casualties = max(0, int(deployed_count) - len(states))
        available_slots = max(
            0,
            self.defender_capacity
            - self._defenders.count
            - len(self._defender_respawn_timers),
        )
        self._defender_respawn_timers.extend(
            [cfg.DEFENDER_RESPAWN_DELAY] * min(casualties, available_slots)
        )

    def update(self, dt: float, in_combat: bool = False) -> None:
        if not self.can_recruit:
            return
        self.add_food(self.base_income_per_second * dt)
        if in_combat:
            self._spawn_effects = [t - dt for t in self._spawn_effects if t - dt > 0]
            for visual_spawn in self._visual_spawns:
                visual_spawn["progress"] += dt / 2.0
            self._visual_spawns = [
                visual_spawn
                for visual_spawn in self._visual_spawns
                if visual_spawn["progress"] < 1.0
            ]
            return
        for unit in self.units:
            unit.update(dt, self)

        self._update_defender_respawns(dt)

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
                if self._spawn_queue:
                    next_unit = self._spawn_queue[0]
                    self._spawn_timer = (
                        self.soldier_spawn_delay if next_unit == "soldier" else cfg.SPAWN_DELAY
                    )
                else:
                    self._spawn_timer = 0.0

    def _update_defender_respawns(self, dt: float) -> None:
        if self.defender_capacity <= 0:
            self._defender_respawn_timers.clear()
            return
        remaining: list[float] = []
        respawned = 0
        for timer in self._defender_respawn_timers:
            next_timer = timer - dt
            if next_timer <= 0.0 and self._defenders.count + respawned < self.defender_capacity:
                respawned += 1
            else:
                remaining.append(max(0.0, next_timer))
        self._defender_respawn_timers = remaining
        if respawned:
            start_index = self._defenders.count
            self._defenders.add(respawned)
            for offset in range(respawned):
                self._visual_spawns.append(
                    {
                        "role": "defender",
                        "progress": 0.0,
                        "index": start_index + offset,
                    }
                )
            self._spawn_effects.extend([1.0] * respawned)

    def eliminate_command_units(self) -> None:
        self._queen.remove(self._queen.count)
        self._workers.remove(self._workers.count)
        self._defenders.remove(self._defenders.count)
        self._defender_respawn_timers.clear()
        self._spawn_queue.clear()
        self._visual_spawns.clear()
        self._food = 0.0

    def reset_after_capture(
        self,
        new_owner: object,
        surviving_soldiers: int | Iterable[SoldierState],
    ) -> None:
        """Capture territory: new owner gets queen + survivors + workers + bonus food."""
        self._owner = new_owner
        # Kill old queen, spawn new one for new owner
        self._queen.remove(self._queen.count)
        self._queen = Queen(1)
        # Keep existing workers (reward for conquering!)
        # Reset soldiers to survivors
        self._soldiers.remove(self._soldiers.count)
        if isinstance(surviving_soldiers, int):
            self._soldiers.add(surviving_soldiers)
        else:
            self.receive_soldiers(surviving_soldiers)
        # Bonus food for conquering
        self._food = cfg.CAPTURE_FOOD_BONUS
        # Captured territory is not capital
        self._is_capital = False
        self._spawn_queue.clear()
        self._visual_spawns.clear()
        self._spawn_timer = 0.0
        self._defenders.remove(self._defenders.count)
        self._defender_respawn_timers.clear()
        if self._specialization is not TerritorySpecialization.NONE:
            self._specialization_level = max(0, self._specialization_level - 1)
        if (
            self._specialization is TerritorySpecialization.FORTRESS
            and self._specialization_level > 0
        ):
            self._defender_respawn_timers = [
                cfg.DEFENDER_RESPAWN_DELAY
            ] * self.defender_capacity
