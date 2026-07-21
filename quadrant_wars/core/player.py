
import math
import random
from abc import ABC, abstractmethod

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.objective import WorldObjectiveType
from quadrant_wars.core.territory import TerritorySpecialization


class Player(ABC):
    def __init__(self, player_id, name, color):
        self._id = player_id
        self._name = name
        self._color = color
        self._is_alive = True
        self._war_banner_time = 0.0

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @property
    def color(self):
        return self._color

    @property
    def is_alive(self):
        return self._is_alive

    @property
    def attack_multiplier(self):
        if self._war_banner_time > 0.0:
            return cfg.WAR_BANNER_ATTACK_MULTIPLIER
        return 1.0

    @property
    def march_speed_multiplier(self):
        if self._war_banner_time > 0.0:
            return cfg.WAR_BANNER_MARCH_MULTIPLIER
        return 1.0

    @property
    def war_banner_time(self):
        return self._war_banner_time

    def apply_war_banner(self, duration = cfg.WAR_BANNER_DURATION):
        self._war_banner_time = max(self._war_banner_time, duration)

    def _update_buffs(self, dt):
        self._war_banner_time = max(0.0, self._war_banner_time - dt)

    def eliminate(self):
        self._is_alive = False

    @abstractmethod
    def update(self, match, dt):
        """Per-player decision hook."""


class HumanPlayer(Player):
    def update(self, match, dt):
        self._update_buffs(dt)
        return None


class BotStrategy(ABC):
    name = "Bot"
    worker_target_ratio = 0.20
    max_workers = 5
    attack_margin = 0.72
    attack_ratio = 0.82
    reserve_ratio = cfg.BOT_DEFENSE_RESERVE_RATIO
    early_probe_after = 14.0
    probe_ratio = 0.45
    probe_target_soldiers = 2
    probe_min_soldiers = 3
    probe_reserve_min = 2
    late_min_margin = 0.52
    late_attack_ratio = 0.78
    objective_min_soldiers = 6
    objective_commit_ratio = 0.50
    objective_reserve_min = 2
    threat_awareness = 1.0
    avoid_two_fronts = False
    upgrade_force = 10

    def should_buy_worker(self, home):
        if home.workers.count >= min(cfg.MAX_WORKERS_PER_TERRITORY, self.max_workers):
            return False
        total = max(1, home.workers.count + home.soldiers.count)
        return home.workers.count / total < self.worker_target_ratio

    def defense_reserve(self, soldier_count):
        if soldier_count <= 0:
            return 0
        return min(
            soldier_count,
            max(1, math.ceil(soldier_count * self.reserve_ratio)),
        )

    def choose_target(self, match, bot, source):
        enemies = [
            t for t in match.territories
            if t.owner is not bot and getattr(t.owner, "is_alive", False) and t.queen.is_alive
        ]
        if not enemies:
            return None
        sx, sy = source.centroid

        third_party_commitments = {}
        for territory in enemies:
            commitment = sum(
                army.soldiers
                for army in match.armies
                if getattr(army, "targets_territory", False)
                and army.target_id == territory.id
                and army.attacker is not bot
                and army.attacker is not territory.owner
            )
            commitment += sum(
                1
                for arena in getattr(match, "battles", ())
                if getattr(arena, "target", None) is territory
                for agent in arena.agents
                if agent.owner is not bot
                and agent.owner is not territory.owner
                and not agent.neutral
            )
            commitment += sum(
                1
                for player_id in getattr(
                    match,
                    "recent_territory_attackers",
                    lambda _territory_id: set(),
                )(territory.id)
                if player_id not in (bot.id, territory.owner.id)
            )
            third_party_commitments[territory.id] = commitment

        uncontested = [
            territory
            for territory in enemies
            if third_party_commitments[territory.id] == 0
        ]
        if uncontested:
            enemies = uncontested

        def target_score(territory):
            owner_regions = sum(1 for item in match.territories if item.owner is territory.owner)
            economy_level = (
                territory.specialization_level
                if territory.specialization is TerritorySpecialization.ECONOMY
                else 0
            )
            strategic_threat = (
                territory.workers.count * 0.75
                + territory.food / 30.0
                + economy_level * 1.8
                + max(0, owner_regions - 1) * 6.0
            )
            third_party_commitment = third_party_commitments[territory.id]
            distance = math.hypot(territory.centroid[0] - sx, territory.centroid[1] - sy)
            strategic_score = (
                territory.defense_value_legacy
                - strategic_threat * self.threat_awareness
                + min(18, third_party_commitment) * 1.35
            )
            # Expansion follows the nearest front first. The strategic score
            # only breaks ties between equally close border territories.
            return distance, strategic_score, territory.defense_value_legacy

        return min(
            enemies,
            key=target_score,
        )

    def attack_amount(self, source, target):
        reserve = self.defense_reserve(source.soldiers.count)
        available = max(0, source.soldiers.count - reserve)
        required = math.ceil(target.defense_value_legacy * self.attack_margin)
        if available < required:
            return 0
        wanted = max(required, int(source.soldiers.count * self.attack_ratio))
        return max(0, min(available, wanted))

    def probe_amount(self, source, target):
        available = max(
            0,
            source.soldiers.count
            - max(
                self.probe_reserve_min,
                self.defense_reserve(source.soldiers.count),
            ),
        )
        if available < self.probe_min_soldiers:
            return 0
        weak_target = target.soldiers.count <= self.probe_target_soldiers
        if weak_target:
            return min(
                available,
                max(
                    self.probe_min_soldiers,
                    int(source.soldiers.count * self.probe_ratio),
                ),
            )
        return 0

    def choose_specialization(
        self,
        match,
        bot,
        territory,
    ):
        enemies = [
            t for t in match.territories
            if t.owner is not bot and getattr(t.owner, "is_alive", False)
        ]
        incoming = any(
            army.target_id == territory.id and army.attacker is not bot
            for army in match.armies
            if getattr(army, "targets_territory", False)
        )
        incoming = incoming or bool(
            getattr(match, "hostile_territory_commitment_count", lambda *_: 0)(
                bot, territory.id
            )
        )
        if incoming:
            return TerritorySpecialization.FORTRESS
        owned = match.territories_of(bot)
        if len(owned) <= 1 or not enemies:
            return TerritorySpecialization.ECONOMY

        # A balanced kingdom keeps its capital and rear regions productive.
        # Only the non-capital region closest to an enemy becomes the front line.
        candidates = [item for item in owned if not item.is_capital] or owned
        frontline = min(
            candidates,
            key=lambda item: min(
                math.dist(item.centroid, enemy.centroid)
                for enemy in enemies
            ),
        )
        if territory is frontline:
            return TerritorySpecialization.FORTRESS
        return TerritorySpecialization.ECONOMY

    def objective_threshold(self, objective_type):
        return self.objective_min_soldiers


class AggressiveStrategy(BotStrategy):
    name = "Aggressive"
    worker_target_ratio = 0.24
    max_workers = 3
    attack_margin = 0.40
    attack_ratio = 0.86
    reserve_ratio = 0.15
    early_probe_after = 10.0
    probe_ratio = 0.75
    probe_target_soldiers = 2
    probe_min_soldiers = 3
    probe_reserve_min = 1
    late_min_margin = 0.56
    late_attack_ratio = 0.86
    objective_min_soldiers = 5
    objective_commit_ratio = 0.45
    objective_reserve_min = 2
    threat_awareness = 0.95
    upgrade_force = 10

    def choose_specialization(
        self,
        match,
        bot,
        territory,
    ):
        return TerritorySpecialization.BARRACKS


class EconomicStrategy(BotStrategy):
    name = "Economic"
    worker_target_ratio = 0.25
    max_workers = 4
    attack_margin = 0.80
    attack_ratio = 0.74
    reserve_ratio = 0.30
    early_probe_after = 22.0
    probe_ratio = 0.34
    late_min_margin = 0.66
    late_attack_ratio = 0.74
    objective_min_soldiers = 7
    objective_commit_ratio = 0.33
    objective_reserve_min = 3
    threat_awareness = 0.65
    upgrade_force = 12

    def should_buy_worker(self, home):
        if home.workers.count >= min(cfg.MAX_WORKERS_PER_TERRITORY, self.max_workers):
            return False
        marginal_income = (
            cfg.FOOD_PER_WORKER_PER_SECOND
            * float(getattr(home, "worker_income_multiplier", 1.0))
        )
        payback_seconds = home.worker_cost() / max(0.01, marginal_income)
        return payback_seconds <= 90.0

    def choose_specialization(
        self,
        match,
        bot,
        territory,
    ):
        return TerritorySpecialization.ECONOMY

    def objective_threshold(self, objective_type):
        if objective_type is WorldObjectiveType.CARAVAN:
            return 5
        return self.objective_min_soldiers


class BalancedStrategy(BotStrategy):
    name = "Balanced"
    worker_target_ratio = 0.25
    max_workers = 3
    attack_margin = 0.70
    attack_ratio = 0.84
    reserve_ratio = 0.20
    early_probe_after = 12.0
    probe_ratio = 0.48
    late_min_margin = 0.56
    late_attack_ratio = 0.86
    objective_min_soldiers = 5
    objective_commit_ratio = 0.45
    objective_reserve_min = 2
    threat_awareness = 0.80
    avoid_two_fronts = True
    upgrade_force = 8

    def choose_specialization(
        self,
        match,
        bot,
        territory,
    ):
        owned = match.territories_of(bot)
        enemies = [
            item
            for item in match.territories
            if item.owner is not bot and getattr(item.owner, "is_alive", False)
        ]
        incoming = bool(
            getattr(match, "hostile_territory_commitment_count", lambda *_: 0)(
                bot, territory.id
            )
        )
        if incoming:
            return TerritorySpecialization.FORTRESS
        if not enemies:
            return TerritorySpecialization.BARRACKS
        if len(owned) <= 1:
            return TerritorySpecialization.FORTRESS

        candidates = [item for item in owned if not item.is_capital] or owned
        frontline = min(
            candidates,
            key=lambda item: min(
                math.dist(item.centroid, enemy.centroid)
                for enemy in enemies
            ),
        )
        if territory is frontline:
            return TerritorySpecialization.FORTRESS
        if territory.is_capital:
            return TerritorySpecialization.BARRACKS
        return TerritorySpecialization.ECONOMY


STRATEGIES = [AggressiveStrategy, BalancedStrategy, EconomicStrategy]


class BotPlayer(Player):
    def __init__(
        self,
        player_id,
        name,
        color,
        strategy = None,
        decision_phase = None,
    ):
        super().__init__(player_id, name, color)
        self._strategy = strategy or BalancedStrategy()
        phase = random.random() if decision_phase is None else decision_phase
        self._decision_timer = phase * cfg.BOT_DECISION_INTERVAL
        self._attack_cooldown = cfg.BOT_MIN_ATTACK_INTERVAL

    @property
    def strategy(self):
        return self._strategy

    def update(self, match, dt):
        self._update_buffs(dt)
        if not self.is_alive:
            return
        self._decision_timer -= dt
        self._attack_cooldown = max(0.0, self._attack_cooldown - dt)
        if self._decision_timer > 0:
            return
        self._decision_timer = cfg.BOT_DECISION_INTERVAL

        # Manage every owned territory.
        owned = [t for t in match.territories if t.owner is self and t.queen.is_alive]
        if not owned:
            return
        threatened_ids = {
            territory.id
            for territory in owned
            if self._incoming_strength(match, territory) > 0
        }

        # Develop at most one region per decision before spending the local treasury.
        for home in sorted(owned, key=lambda t: (t.specialization_level, -t.food, t.id)):
            if home.id in threatened_ids:
                continue
            if getattr(match, "territory_in_battle", lambda _id: False)(home.id):
                continue
            desired = self._strategy.choose_specialization(match, self, home)
            quote = home.development_quote(desired)
            army_ready_for_upgrade = home.soldiers.count >= self._strategy.upgrade_force
            if quote.allowed and (quote.action != "upgrade" or army_ready_for_upgrade):
                result = match.develop_territory(self, home.id, desired)
                if result.success:
                    break

        for home in owned:
            if home.id in threatened_ids:
                if home.food >= home.soldier_cost:
                    home.buy_soldier()
                continue
            desired = self._strategy.choose_specialization(match, self, home)
            development = home.development_quote(desired)
            # A missing branch is funded early. Tier II saving starts only
            # behind an army large enough to survive the spending pause.
            should_save = development.action in ("build", "repair", "convert") or (
                development.action == "upgrade"
                and home.soldiers.count >= self._strategy.upgrade_force
            )
            if development.cost > 0 and not development.allowed and should_save:
                continue
            if self._strategy.should_buy_worker(home):
                home.buy_worker()
            elif home.food >= home.soldier_cost:
                home.buy_soldier()

        if self._attack_cooldown > 0:
            return
        if self._try_reinforce_incoming(match, owned):
            self._attack_cooldown = cfg.BOT_MIN_ATTACK_INTERVAL * 0.55
            return
        if self._try_objective_attack(match, owned):
            self._attack_cooldown = cfg.BOT_MIN_ATTACK_INTERVAL
            return
        sources = [
            territory
            for territory in match.territories
            if territory.owner is self
            and territory.soldiers.count > 2
            and territory.queen.is_alive
            and self._incoming_strength(match, territory) <= 0
        ]
        for source in sorted(sources, key=lambda t: t.soldiers.count, reverse=True):
            target = self._strategy.choose_target(match, self, source)
            if target is None:
                continue
            amount = self._strategy.attack_amount(source, target)
            if (
                amount == 0
                and getattr(match, "elapsed", 0.0) > self._strategy.early_probe_after
            ):
                amount = self._strategy.probe_amount(source, target)
            living_count = len(getattr(match, "living_players", lambda: ())())
            final_assault_at = max(
                360.0,
                cfg.BOT_FINAL_ASSAULT_AT - max(0, living_count - 2) * 45.0,
            )
            if amount == 0 and getattr(match, "elapsed", 0.0) > final_assault_at:
                final_available = max(0, source.soldiers.count - 1)
                final_threshold = max(
                    3,
                    math.ceil(getattr(target, "defense_value_legacy", 0) * 0.50),
                )
                if final_available >= final_threshold:
                    amount = final_available
            if amount == 0 and getattr(match, "elapsed", 0.0) > 120.0:
                hard_available = max(
                    0,
                    source.soldiers.count
                    - self._strategy.defense_reserve(source.soldiers.count),
                )
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

    def _incoming_strength(self, match, territory):
        counter = getattr(match, "hostile_territory_commitment_count", None)
        if counter is not None:
            return int(counter(self, territory.id))
        return sum(
            army.soldiers
            for army in match.armies
            if getattr(army, "targets_territory", False)
            and army.target_id == territory.id
            and army.attacker is not self
        )

    def _try_reinforce_incoming(self, match, owned):
        threatened = [
            (self._incoming_strength(match, territory), territory)
            for territory in owned
        ]
        threatened = [item for item in threatened if item[0] > 0]
        if not threatened:
            return False
        incoming, target = max(threatened, key=lambda item: item[0])
        needed = max(0, incoming - target.soldiers.count + 1)
        if needed <= 0:
            return False
        sources = [
            territory
            for territory in owned
            if territory is not target
            and territory.soldiers.count
            > self._strategy.defense_reserve(territory.soldiers.count)
            and self._incoming_strength(match, territory) <= 0
        ]
        for source in sorted(
            sources,
            key=lambda territory: math.dist(territory.centroid, target.centroid),
        ):
            amount = min(
                needed,
                source.soldiers.count
                - self._strategy.defense_reserve(source.soldiers.count),
            )
            if amount > 0 and match.issue_attack(source, target, amount):
                return True
        return False

    def _try_objective_attack(self, match, owned):
        objective = getattr(match, "world_objective", None)
        if objective is None or not objective.active:
            return False
        if (
            self._strategy.avoid_two_fronts
            and getattr(match, "elapsed", 0.0) < 360.0
            and match.offensive_territory_commitment_count(self) > 0
        ):
            return False

        current_commitment = match.objective_commitment_count(self)

        sources = []
        for territory in owned:
            if self._incoming_strength(match, territory) > 0:
                continue
            reserve = max(
                self._strategy.defense_reserve(territory.soldiers.count),
                self._strategy.objective_reserve_min,
            )
            available = max(
                0,
                territory.soldiers.count
                - reserve,
            )
            if available:
                distance = math.hypot(
                    territory.centroid[0] - objective.centroid[0],
                    territory.centroid[1] - objective.centroid[1],
                )
                sources.append((distance, territory, available))
        total_available = sum(item[2] for item in sources)
        threshold = self._strategy.objective_threshold(objective.objective_type)
        if total_available + current_commitment < threshold:
            return False

        commitment = max(
            threshold,
            math.ceil(
                (total_available + current_commitment)
                * self._strategy.objective_commit_ratio
            ),
        )
        remaining = min(total_available, max(0, commitment - current_commitment))
        if remaining <= 0:
            return False
        issued = False
        for _, source, available in sorted(sources, key=lambda item: item[0]):
            amount = min(available, remaining)
            if amount > 0 and match.issue_objective_attack(source, amount):
                remaining -= amount
                issued = True
            if remaining <= 0:
                break
        return issued
