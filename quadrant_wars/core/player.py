from __future__ import annotations

import math
import random
from abc import ABC, abstractmethod

from quadrant_wars import balance_config as cfg


class Player(ABC):
    def __init__(self, player_id: int, name: str, color: tuple[int, int, int]) -> None:
        self._id = player_id
        self._name = name
        self._color = color
        self._is_alive = True
        self._supply_buff = 0.0

    @property
    def id(self) -> int:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def color(self) -> tuple[int, int, int]:
        return self._color

    @property
    def is_alive(self) -> bool:
        return self._is_alive

    @property
    def has_buff(self) -> bool:
        return self._supply_buff > 0.0

    @property
    def buff_time(self) -> float:
        return self._supply_buff

    def apply_buff(self, duration: float) -> None:
        self._supply_buff = max(self._supply_buff, duration)

    def eliminate(self) -> None:
        self._is_alive = False

    @abstractmethod
    def update(self, match: object, dt: float) -> None:
        """Per-player decision hook."""


class HumanPlayer(Player):
    def update(self, match: object, dt: float) -> None:
        if self._supply_buff > 0:
            self._supply_buff -= dt
        return None


class BotStrategy(ABC):
    name = "Bot"
    worker_target_ratio = 0.14
    max_workers = 7
    attack_margin = 0.75
    attack_ratio = 0.9
    reserve_ratio = cfg.BOT_DEFENSE_RESERVE_RATIO
    early_probe_after = 11.0
    probe_ratio = 0.50
    late_min_margin = 0.56
    late_attack_ratio = 0.80

    def should_buy_worker(self, home: object) -> bool:
        if home.workers.count >= cfg.MAX_WORKERS_PER_TERRITORY:
            return False
        total = max(1, home.workers.count + home.soldiers.count)
        return home.workers.count / total < self.worker_target_ratio

    def choose_target(self, match: object, bot: "BotPlayer", source: object) -> object | None:
        enemies = [
            t for t in match.territories
            if t.owner is not bot and getattr(t.owner, "is_alive", False) and t.queen.is_alive
        ]
        if not enemies:
            return None
        sx, sy = source.centroid
        return min(
            enemies,
            key=lambda t: (
                t.defense_value_legacy,
                math.hypot(t.centroid[0] - sx, t.centroid[1] - sy) * 0.015,
            ),
        )

    def attack_amount(self, source: object, target: object) -> int:
        reserve = max(1, int(source.soldiers.count * self.reserve_ratio))
        hard_available = max(0, source.soldiers.count - 1)
        soft_available = max(0, source.soldiers.count - reserve)
        required = math.ceil(target.defense_value_legacy * self.attack_margin)
        if hard_available < required:
            return 0
        wanted = max(required, int(source.soldiers.count * self.attack_ratio), soft_available)
        return max(0, min(hard_available, wanted))

    def probe_amount(self, source: object, target: object) -> int:
        hard_available = max(0, source.soldiers.count - 2)
        if hard_available < 3:
            return 0
        weak_target = target.soldiers.count <= 2
        if weak_target:
            return min(hard_available, max(3, int(source.soldiers.count * self.probe_ratio)))
        return 0


class AggressiveStrategy(BotStrategy):
    name = "Aggressive"
    worker_target_ratio = 0.10
    max_workers = 4
    attack_margin = 0.55
    attack_ratio = 0.90
    reserve_ratio = 0.08
    early_probe_after = 6.0
    probe_ratio = 0.56
    late_min_margin = 0.45
    late_attack_ratio = 0.9


class EconomicStrategy(BotStrategy):
    name = "Economic"
    worker_target_ratio = 0.12
    max_workers = 5
    attack_margin = 0.85
    attack_ratio = 0.76
    reserve_ratio = 0.20
    early_probe_after = 20.0
    probe_ratio = 0.34
    late_min_margin = 0.55
    late_attack_ratio = 0.74


class BalancedStrategy(BotStrategy):
    name = "Balanced"
    worker_target_ratio = 0.12
    max_workers = 5
    attack_margin = 0.65
    attack_ratio = 0.85
    reserve_ratio = 0.12
    early_probe_after = 10.0
    probe_ratio = 0.48
    late_min_margin = 0.50
    late_attack_ratio = 0.80


STRATEGIES = [AggressiveStrategy, BalancedStrategy, EconomicStrategy]


class BotPlayer(Player):
    def __init__(
        self,
        player_id: int,
        name: str,
        color: tuple[int, int, int],
        strategy: BotStrategy | None = None,
    ) -> None:
        super().__init__(player_id, name, color)
        self._strategy = strategy or BalancedStrategy()
        self._decision_timer = random.random() * cfg.BOT_DECISION_INTERVAL
        self._attack_cooldown = cfg.BOT_MIN_ATTACK_INTERVAL

    @property
    def strategy(self) -> BotStrategy:
        return self._strategy

    def update(self, match: object, dt: float) -> None:
        if not self.is_alive:
            return
        if self._supply_buff > 0:
            self._supply_buff -= dt
        self._decision_timer -= dt
        self._attack_cooldown = max(0.0, self._attack_cooldown - dt)
        if self._decision_timer > 0:
            return
        self._decision_timer = cfg.BOT_DECISION_INTERVAL

        # Manage ALL owned territories
        owned = [t for t in match.territories if t.owner is self and t.queen.is_alive]
        if not owned:
            return

        for home in owned:
            if self._strategy.should_buy_worker(home):
                home.buy_worker()
            elif home.food >= cfg.SOLDIER_COST:
                home.buy_soldier()

        if self._attack_cooldown > 0:
            return
        sources = [t for t in match.territories if t.owner is self and t.soldiers.count > 2 and t.queen.is_alive]
        for source in sorted(sources, key=lambda t: t.soldiers.count, reverse=True):
            target = None
            if target is None:
                target = self._strategy.choose_target(match, self, source)
                
            if target is None:
                continue
            amount = self._strategy.attack_amount(source, target)
            if amount == 0 and getattr(match, "elapsed", 0.0) > self._strategy.early_probe_after:
                amount = self._strategy.probe_amount(source, target)
            if amount == 0 and getattr(match, "elapsed", 0.0) > 150.0:
                hard_available = max(0, source.soldiers.count - 1)
                def_val = getattr(target, "defense_value_legacy", 0)
                if hard_available > def_val * self._strategy.late_min_margin:
                    amount = min(
                        hard_available,
                        max(
                            int(source.soldiers.count * self._strategy.late_attack_ratio),
                            int(def_val * self._strategy.late_min_margin),
                        ),
                    )
            if amount > 0:
                if match.issue_attack(source, target, amount):
                    self._attack_cooldown = cfg.BOT_MIN_ATTACK_INTERVAL
                    return
