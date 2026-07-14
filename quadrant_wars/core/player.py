from __future__ import annotations

import math
import random
from abc import ABC, abstractmethod

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.objective import WorldObjectiveType
from quadrant_wars.core.territory import TerritorySpecialization


class Player(ABC):
    def __init__(self, player_id: int, name: str, color: tuple[int, int, int]) -> None:
        self._id = player_id
        self._name = name
        self._color = color
        self._is_alive = True
        self._war_banner_time = 0.0

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
    def attack_multiplier(self) -> float:
        if self._war_banner_time > 0.0:
            return cfg.WAR_BANNER_ATTACK_MULTIPLIER
        return 1.0

    @property
    def march_speed_multiplier(self) -> float:
        if self._war_banner_time > 0.0:
            return cfg.WAR_BANNER_MARCH_MULTIPLIER
        return 1.0

    @property
    def war_banner_time(self) -> float:
        return self._war_banner_time

    def apply_war_banner(self, duration: float = cfg.WAR_BANNER_DURATION) -> None:
        self._war_banner_time = max(self._war_banner_time, duration)

    def _update_buffs(self, dt: float) -> None:
        self._war_banner_time = max(0.0, self._war_banner_time - dt)

    def eliminate(self) -> None:
        self._is_alive = False

    @abstractmethod
    def update(self, match: object, dt: float) -> None:
        """Per-player decision hook."""


class HumanPlayer(Player):
    def update(self, match: object, dt: float) -> None:
        self._update_buffs(dt)
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
    objective_min_soldiers = 5
    objective_commit_ratio = 0.50

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

    def choose_specialization(
        self,
        match: object,
        bot: "BotPlayer",
        territory: object,
    ) -> TerritorySpecialization:
        enemies = [
            t for t in match.territories
            if t.owner is not bot and getattr(t.owner, "is_alive", False)
        ]
        incoming = any(
            army.target_id == territory.id and army.attacker is not bot
            for army in match.armies
            if getattr(army, "targets_territory", False)
        )
        nearest = min(
            (
                math.hypot(
                    territory.centroid[0] - enemy.centroid[0],
                    territory.centroid[1] - enemy.centroid[1],
                )
                for enemy in enemies
            ),
            default=9999.0,
        )
        if incoming or nearest < 380.0:
            return TerritorySpecialization.FORTRESS
        if territory.workers.count >= 3:
            return TerritorySpecialization.ECONOMY
        return TerritorySpecialization.BARRACKS

    def objective_threshold(self, objective_type: WorldObjectiveType) -> int:
        return self.objective_min_soldiers


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
    objective_min_soldiers = 4
    objective_commit_ratio = 0.66

    def choose_specialization(
        self,
        match: object,
        bot: "BotPlayer",
        territory: object,
    ) -> TerritorySpecialization:
        return TerritorySpecialization.BARRACKS


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
    objective_min_soldiers = 6
    objective_commit_ratio = 0.33

    def choose_specialization(
        self,
        match: object,
        bot: "BotPlayer",
        territory: object,
    ) -> TerritorySpecialization:
        return TerritorySpecialization.ECONOMY

    def objective_threshold(self, objective_type: WorldObjectiveType) -> int:
        if objective_type is WorldObjectiveType.CARAVAN:
            return 4
        return self.objective_min_soldiers


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
    objective_min_soldiers = 5
    objective_commit_ratio = 0.50


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
        self._update_buffs(dt)
        if not self.is_alive:
            return
        self._decision_timer -= dt
        self._attack_cooldown = max(0.0, self._attack_cooldown - dt)
        if self._decision_timer > 0:
            return
        self._decision_timer = cfg.BOT_DECISION_INTERVAL

        # Manage ALL owned territories
        owned = [t for t in match.territories if t.owner is self and t.queen.is_alive]
        if not owned:
            return

        # Develop at most one region per decision before spending the local treasury.
        for home in sorted(owned, key=lambda t: (t.specialization_level, -t.food, t.id)):
            desired = self._strategy.choose_specialization(match, self, home)
            quote = home.development_quote(desired)
            army_ready_for_upgrade = home.soldiers.count >= max(4, self._strategy.objective_min_soldiers)
            if quote.allowed and (quote.action != "upgrade" or army_ready_for_upgrade):
                result = match.develop_territory(self, home.id, desired)
                if result.success:
                    break

        for home in owned:
            desired = self._strategy.choose_specialization(match, self, home)
            development = home.development_quote(desired)
            # A bot must stop buying short-term units long enough to afford its plan.
            army_ready_for_upgrade = home.soldiers.count >= max(4, self._strategy.objective_min_soldiers)
            should_save = development.action in ("build", "repair", "convert") or (
                development.action == "upgrade" and army_ready_for_upgrade
            )
            if development.cost > 0 and not development.allowed and should_save:
                continue
            if self._strategy.should_buy_worker(home):
                home.buy_worker()
            elif home.food >= home.soldier_cost:
                home.buy_soldier()

        if self._attack_cooldown > 0:
            return
        if self._try_objective_attack(match, owned):
            self._attack_cooldown = cfg.BOT_MIN_ATTACK_INTERVAL
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

    def _try_objective_attack(self, match: object, owned: list[object]) -> bool:
        objective = getattr(match, "world_objective", None)
        if objective is None or not objective.active:
            return False
        if match.has_objective_commitment(self):
            return False

        sources = []
        for territory in owned:
            available = max(0, territory.soldiers.count - 1)
            if available:
                distance = math.hypot(
                    territory.centroid[0] - objective.centroid[0],
                    territory.centroid[1] - objective.centroid[1],
                )
                sources.append((distance, territory, available))
        total_available = sum(item[2] for item in sources)
        threshold = self._strategy.objective_threshold(objective.objective_type)
        if total_available < threshold:
            return False

        commitment = max(threshold, math.ceil(total_available * self._strategy.objective_commit_ratio))
        remaining = min(total_available, commitment)
        issued = False
        for _, source, available in sorted(sources, key=lambda item: item[0]):
            amount = min(available, remaining)
            if amount > 0 and match.issue_objective_attack(source, amount):
                remaining -= amount
                issued = True
            if remaining <= 0:
                break
        return issued
