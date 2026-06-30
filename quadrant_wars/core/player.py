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

    def eliminate(self) -> None:
        self._is_alive = False

    @abstractmethod
    def update(self, match: object, dt: float) -> None:
        """Per-player decision hook."""


class HumanPlayer(Player):
    def update(self, match: object, dt: float) -> None:
        return None


class BotStrategy(ABC):
    name = "Bot"
    worker_target_ratio = 0.18
    max_workers = 8
    attack_margin = 1.35
    attack_ratio = 0.6
    reserve_ratio = cfg.BOT_DEFENSE_RESERVE_RATIO
    late_min_margin = 0.85
    late_attack_ratio = 0.72

    def should_buy_worker(self, home: object) -> bool:
        if home.workers.count >= self.max_workers:
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
        return min(enemies, key=lambda t: t.defense_value)

    def attack_amount(self, source: object, target: object) -> int:
        reserve = max(2, int(source.soldiers.count * self.reserve_ratio))
        hard_available = max(0, source.soldiers.count - 2)
        soft_available = max(0, source.soldiers.count - reserve)
        required = math.ceil(target.defense_value * self.attack_margin)
        if hard_available < required:
            return 0
        wanted = max(required, int(source.soldiers.count * self.attack_ratio), soft_available)
        return max(0, min(hard_available, wanted))


class AggressiveStrategy(BotStrategy):
    name = "Aggressive"
    worker_target_ratio = 0.10
    max_workers = 5
    attack_margin = 1.00
    attack_ratio = 0.88
    reserve_ratio = 0.08
    late_min_margin = 0.72
    late_attack_ratio = 0.88


class EconomicStrategy(BotStrategy):
    name = "Economic"
    worker_target_ratio = 0.18
    max_workers = 7
    attack_margin = 1.30
    attack_ratio = 0.58
    reserve_ratio = 0.34
    late_min_margin = 0.82
    late_attack_ratio = 0.76


class BalancedStrategy(BotStrategy):
    name = "Balanced"
    worker_target_ratio = 0.12
    max_workers = 5
    attack_margin = 1.62
    attack_ratio = 0.52
    reserve_ratio = 0.48
    late_min_margin = 0.96
    late_attack_ratio = 0.58


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
        self._decision_timer -= dt
        self._attack_cooldown = max(0.0, self._attack_cooldown - dt)
        if self._decision_timer > 0:
            return
        self._decision_timer = cfg.BOT_DECISION_INTERVAL

        home = match.home_territory(self)
        if home is None:
            return

        if self._strategy.should_buy_worker(home):
            home.buy_worker()
            return
        while home.food >= cfg.SOLDIER_COST:
            if not home.buy_soldier():
                break
            if home.food < cfg.SOLDIER_COST:
                break

        if self._attack_cooldown > 0:
            return
        sources = [t for t in match.territories if t.owner is self and t.soldiers.count > 3]
        for source in sorted(sources, key=lambda t: t.soldiers.count, reverse=True):
            target = self._strategy.choose_target(match, self, source)
            if target is None:
                continue
            amount = self._strategy.attack_amount(source, target)
            if amount == 0 and getattr(match, "elapsed", 0.0) > 360.0:
                hard_available = max(0, source.soldiers.count - 2)
                if hard_available > target.defense_value * self._strategy.late_min_margin:
                    amount = min(
                        hard_available,
                        max(
                            int(source.soldiers.count * self._strategy.late_attack_ratio),
                            int(target.defense_value * self._strategy.late_min_margin),
                        ),
                    )
            if amount > 0:
                if match.issue_attack(source, target, amount):
                    self._attack_cooldown = cfg.BOT_MIN_ATTACK_INTERVAL
                    return
