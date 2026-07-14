from __future__ import annotations

import math
import random
from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterable

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.combat import CombatResolver, CombatZone, CombatResult
from quadrant_wars.core.map_generator import MapGenerator
from quadrant_wars.core.objective import WorldObjective, WorldObjectiveState, WorldObjectiveType
from quadrant_wars.core.player import BotPlayer, HumanPlayer, Player, STRATEGIES
from quadrant_wars.core.territory import DevelopmentResult, Territory, TerritorySpecialization


class ArmyTargetType(Enum):
    TERRITORY = auto()
    OBJECTIVE = auto()
    RETURN = auto()


@dataclass
class MovingArmy:
    attacker: Player
    source_id: int
    target_type: ArmyTargetType
    target_id: int
    soldiers: int
    start: tuple[float, float]
    end: tuple[float, float]
    elapsed: float = 0.0
    duration: float = 1.0

    @property
    def targets_territory(self) -> bool:
        return self.target_type is ArmyTargetType.TERRITORY

    @property
    def progress(self) -> float:
        return min(1.0, self.elapsed / max(0.01, self.duration))

    @property
    def position(self) -> tuple[float, float]:
        p = self.progress
        t = p * p * (3.0 - 2.0 * p)
        return (
            self.start[0] + (self.end[0] - self.start[0]) * t,
            self.start[1] + (self.end[1] - self.start[1]) * t,
        )

    def advance(self, dt: float) -> None:
        self.elapsed += dt * max(0.1, self.attacker.march_speed_multiplier)


@dataclass
class CombatVisualEffect:
    position: tuple[float, float]
    attacker_color: tuple[int, int, int]
    defender_color: tuple[int, int, int]
    attacker_won: bool
    soldiers: int
    elapsed: float = 0.0
    duration: float = 1.45

    @property
    def progress(self) -> float:
        return min(1.0, self.elapsed / max(0.01, self.duration))


@dataclass
class ObjectiveEngagement:
    zone: CombatZone
    army: MovingArmy


class Match:
    def __init__(
        self,
        player_types: Iterable[str],
        seed: int | None = None,
        bot_strategy_classes: list[type] | None = None,
        headless: bool = False,
    ) -> None:
        self._players: list[Player] = []
        strategy_rng = random.Random(seed)
        strategy_classes = bot_strategy_classes[:] if bot_strategy_classes else STRATEGIES[:]
        if not bot_strategy_classes:
            strategy_rng.shuffle(strategy_classes)
        for i, player_type in enumerate(player_types):
            color = cfg.PLAYER_COLORS[i]
            if player_type.lower() == "human":
                self._players.append(HumanPlayer(i, f"Player {i + 1}", color))
            else:
                strategy = strategy_classes[i % len(strategy_classes)]()
                self._players.append(BotPlayer(i, f"{strategy.name} Bot {i + 1}", color, strategy))

        map_data = MapGenerator().generate(len(self._players), seed=seed)
        self._territories = [
            Territory(i, self._players[i], polygon)
            for i, polygon in enumerate(map_data.polygons)
        ]
        self._armies: list[MovingArmy] = []
        self._combat_zones: list[CombatZone] = []
        self._effects: list[CombatVisualEffect] = []
        self._sound_events: list[str] = []
        self._winner: Player | None = None
        self._elapsed = 0.0
        self._event_log: list[str] = []
        self._headless = headless

        self._objective_rng = random.Random((seed or 0) ^ 0x0B1EC71)
        self._world_objective: WorldObjective | None = None
        self._objective_id = 0
        self._next_objective_at = cfg.OBJECTIVE_FIRST_ACTIVE_AT
        self._last_objective_type: WorldObjectiveType | None = None
        self._objective_queue: list[MovingArmy] = []
        self._objective_engagement: ObjectiveEngagement | None = None
        self._objective_cleanup_at: float | None = None

    @property
    def players(self) -> list[Player]:
        return list(self._players)

    @property
    def territories(self) -> list[Territory]:
        return list(self._territories)

    @property
    def armies(self) -> list[MovingArmy]:
        return list(self._armies)

    @property
    def combat_zones(self) -> list[CombatZone]:
        return list(self._combat_zones)

    @property
    def effects(self) -> list[CombatVisualEffect]:
        return list(self._effects)

    @property
    def world_objective(self) -> WorldObjective | None:
        return self._world_objective

    @property
    def objective_countdown(self) -> float:
        objective = self._world_objective
        if objective is None:
            return max(0.0, self._next_objective_at - self._elapsed)
        if objective.state is WorldObjectiveState.TELEGRAPHING:
            return max(0.0, self._next_objective_at - self._elapsed)
        if objective.active:
            return max(0.0, cfg.OBJECTIVE_ACTIVE_DURATION - objective.active_elapsed)
        return max(0.0, self._next_objective_at - self._elapsed)

    @property
    def winner(self) -> Player | None:
        return self._winner

    @property
    def elapsed(self) -> float:
        return self._elapsed

    @property
    def event_log(self) -> list[str]:
        return self._event_log[-6:]

    def pop_sound_events(self) -> list[str]:
        events = self._sound_events[:]
        self._sound_events.clear()
        return events

    def territories_of(self, player: Player) -> list[Territory]:
        return [t for t in self._territories if t.owner is player and t.queen.is_alive]

    def home_territory(self, player: Player) -> Territory | None:
        if not player.is_alive:
            return None
        owned = self.territories_of(player)
        if not owned:
            return None
        capitals = [t for t in owned if t.is_capital]
        if capitals:
            return capitals[0]
        new_capital = max(owned, key=lambda t: t.food)
        new_capital.is_capital = True
        return new_capital

    def best_attack_source(self, player: Player, target: object) -> Territory | None:
        owned = [t for t in self.territories_of(player) if t.soldiers.count > 1]
        if not owned:
            return None
        tx, ty = target.centroid
        return min(owned, key=lambda t: math.hypot(t.centroid[0] - tx, t.centroid[1] - ty))

    def living_players(self) -> list[Player]:
        alive = []
        for player in self._players:
            if not player.is_alive:
                continue
            if any(t.owner is player and t.queen.is_alive for t in self._territories):
                alive.append(player)
            else:
                player.eliminate()
        return alive

    def territory_at(self, position: tuple[int, int]) -> Territory | None:
        for territory in self._territories:
            if _point_in_polygon(position, territory.polygon):
                return territory
        return None

    def develop_territory(
        self,
        player: Player,
        territory_id: int,
        specialization: TerritorySpecialization,
    ) -> DevelopmentResult:
        if not player.is_alive or not 0 <= territory_id < len(self._territories):
            return DevelopmentResult(False, None, "Invalid territory")
        territory = self._territories[territory_id]
        if territory.owner is not player:
            return DevelopmentResult(False, None, "You do not control this territory")
        result = territory.develop(specialization)
        if result.success:
            self._event_log.append(f"{player.name} developed T{territory.id + 1}: {result.message}")
            self._sound_events.append("develop")
        return result

    def issue_attack(self, source: Territory, target: Territory, soldiers: int) -> bool:
        if soldiers <= 0 or source is target:
            return False
        if not getattr(source.owner, "is_alive", False):
            return False
        removed = source.remove_soldiers(min(soldiers, source.soldiers.count))
        if removed <= 0:
            return False
        self._dispatch_army(
            source.owner,
            source.id,
            ArmyTargetType.TERRITORY,
            target.id,
            removed,
            source.centroid,
            target.centroid,
        )
        target_name = target.owner.name if getattr(target, "owner", None) else "Neutral land"
        self._event_log.append(f"{source.owner.name} sent {removed} soldiers to {target_name}")
        self._sound_events.append("attack")
        return True

    def issue_objective_attack(self, source: Territory, soldiers: int) -> bool:
        objective = self._world_objective
        if objective is None or not objective.active or soldiers <= 0:
            return False
        if not getattr(source.owner, "is_alive", False):
            return False
        removed = source.remove_soldiers(min(soldiers, source.soldiers.count))
        if removed <= 0:
            return False
        self._dispatch_army(
            source.owner,
            source.id,
            ArmyTargetType.OBJECTIVE,
            objective.id,
            removed,
            source.centroid,
            objective.centroid,
        )
        self._event_log.append(f"{source.owner.name} sent {removed} soldiers to {objective.display_name}")
        self._sound_events.append("attack")
        return True

    def has_objective_commitment(self, player: Player) -> bool:
        if any(
            army.attacker is player and army.target_type is ArmyTargetType.OBJECTIVE
            for army in self._armies
        ):
            return True
        if any(army.attacker is player for army in self._objective_queue):
            return True
        engagement = self._objective_engagement
        return engagement is not None and engagement.army.attacker is player

    def update(self, dt: float) -> None:
        if self._winner is not None:
            return
        self._elapsed += dt
        self._update_world_objective(dt)

        for territory in self._territories:
            territory.update(dt)
        for player in self._players:
            player.update(self, dt)

        arrived: list[MovingArmy] = []
        for army in self._armies:
            army.advance(dt)
            if army.progress >= 1.0:
                arrived.append(army)
        for army in arrived:
            if army in self._armies:
                self._armies.remove(army)
            self._resolve_arrival(army)

        finished_zones: list[CombatZone] = []
        for zone in self._combat_zones:
            result = zone.update(dt)
            if result is not None:
                finished_zones.append(zone)
        for zone in finished_zones:
            if zone in self._combat_zones:
                self._combat_zones.remove(zone)
            self._resolve_combat_end(zone)

        expired: list[CombatVisualEffect] = []
        for effect in self._effects:
            effect.elapsed += dt
            if effect.progress >= 1.0:
                expired.append(effect)
        for effect in expired:
            self._effects.remove(effect)

        living = self.living_players()
        if len(living) == 1:
            self._winner = living[0]
        elif len(living) == 0:
            self._winner = self._players[0]

    def _dispatch_army(
        self,
        attacker: Player,
        source_id: int,
        target_type: ArmyTargetType,
        target_id: int,
        soldiers: int,
        start: tuple[float, float],
        end: tuple[float, float],
    ) -> None:
        distance = math.hypot(end[0] - start[0], end[1] - start[1])
        duration = max(0.6, distance / cfg.SOLDIER_TRAVEL_SPEED)
        self._armies.append(
            MovingArmy(
                attacker=attacker,
                source_id=source_id,
                target_type=target_type,
                target_id=target_id,
                soldiers=soldiers,
                start=start,
                end=end,
                duration=duration,
            )
        )

    def _resolve_arrival(self, army: MovingArmy) -> None:
        if army.target_type is ArmyTargetType.RETURN:
            self._resolve_return_arrival(army)
            return
        if not army.attacker.is_alive:
            return
        if army.target_type is ArmyTargetType.OBJECTIVE:
            self._resolve_objective_arrival(army)
            return
        if not 0 <= army.target_id < len(self._territories):
            return

        target = self._territories[army.target_id]
        if target.owner is army.attacker:
            target.add_soldiers(army.soldiers)
            return

        if self._headless:
            defender_color = target.owner.color
            defender_name = target.owner.name
            result = CombatResolver.resolve_instant(army.soldiers, target, army.attacker)
            self._effects.append(
                CombatVisualEffect(
                    position=target.centroid,
                    attacker_color=army.attacker.color,
                    defender_color=defender_color,
                    attacker_won=result.attacker_won,
                    soldiers=army.soldiers,
                )
            )
            if result.attacker_won:
                old_owner = target.owner
                CombatResolver.apply_result(result, target, army.attacker)
                self._check_elimination(old_owner)
                self._event_log.append(
                    f"{army.attacker.name} conquered {defender_name}; {result.surviving_attackers} survived"
                )
                self._sound_events.append("combat_win")
            else:
                self._event_log.append(f"{defender_name} defended against {army.attacker.name}")
                self._sound_events.append("combat_defend")
            return

        zone = CombatZone(
            attacker=army.attacker,
            attacker_color=army.attacker.color,
            territory=target,
            soldier_count=army.soldiers,
        )
        self._combat_zones.append(zone)
        self._event_log.append(f"Battle! {army.attacker.name} ({army.soldiers}) vs {target.owner.name}")
        self._sound_events.append("combat_defend")

    def _resolve_combat_end(self, zone: CombatZone) -> None:
        if isinstance(zone.territory, WorldObjective):
            self._resolve_objective_combat_end(zone)
            return
        result = zone.result
        if result is None:
            return
        target = zone.territory
        defender_color = getattr(target.owner, "color", (128, 128, 128))
        self._effects.append(
            CombatVisualEffect(
                position=target.centroid,
                attacker_color=zone.attacker_color,
                defender_color=defender_color,
                attacker_won=result.attacker_won,
                soldiers=result.surviving_attackers,
            )
        )
        if result.attacker_won:
            old_owner = target.owner
            defender_name = getattr(old_owner, "name", "Unknown")
            CombatResolver.apply_result(result, target, zone.attacker)
            self._check_elimination(old_owner)
            self._event_log.append(
                f"{zone.attacker.name} conquered {defender_name}! {result.surviving_attackers} survived"
            )
            self._sound_events.append("combat_win")
        else:
            self._event_log.append(f"{target.owner.name} repelled {zone.attacker.name}!")
            self._sound_events.append("combat_defend")

    def _update_world_objective(self, dt: float) -> None:
        objective = self._world_objective
        if objective is None:
            if self._elapsed >= self._next_objective_at - cfg.OBJECTIVE_TELEGRAPH_DURATION:
                self._spawn_world_objective()
                if self._elapsed >= self._next_objective_at:
                    self._activate_world_objective()
            return

        objective.update(dt)
        if objective.state is WorldObjectiveState.TELEGRAPHING:
            if self._elapsed >= self._next_objective_at:
                self._activate_world_objective()
            return

        if objective.active and objective.active_elapsed >= cfg.OBJECTIVE_ACTIVE_DURATION:
            objective.expire()
            self._event_log.append(f"{objective.display_name} faded without a winner")
            self._sound_events.append("objective_expire")
            self._finish_objective_cycle()
            return

        if objective.state in (WorldObjectiveState.RESOLVED, WorldObjectiveState.EXPIRED):
            if self._objective_cleanup_at is not None and self._elapsed >= self._objective_cleanup_at:
                self._world_objective = None
                self._objective_cleanup_at = None

    def _spawn_world_objective(self) -> None:
        choices = list(WorldObjectiveType)
        if self._last_objective_type is not None and len(choices) > 1:
            choices.remove(self._last_objective_type)
        objective_type = self._objective_rng.choice(choices)
        self._last_objective_type = objective_type
        self._objective_id += 1
        self._world_objective = WorldObjective(
            self._objective_id,
            objective_type,
            self._choose_objective_position(),
        )
        self._event_log.append(f"{self._world_objective.display_name} is approaching")
        self._sound_events.append("objective_warning")

    def _activate_world_objective(self) -> None:
        objective = self._world_objective
        if objective is None or objective.state is not WorldObjectiveState.TELEGRAPHING:
            return
        objective.activate()
        self._event_log.append(f"{objective.display_name} is ready to claim!")
        self._sound_events.append("objective_ready")

    def _choose_objective_position(self) -> tuple[float, float]:
        cx, cy = cfg.WINDOW_WIDTH / 2, cfg.WINDOW_HEIGHT / 2 + 24
        candidates = [
            (cx, cy),
            (cx - 92, cy - 48),
            (cx + 92, cy - 48),
            (cx - 112, cy + 56),
            (cx + 112, cy + 56),
        ]
        self._objective_rng.shuffle(candidates)
        return max(
            candidates,
            key=lambda point: min(
                math.hypot(point[0] - territory.centroid[0], point[1] - territory.centroid[1])
                for territory in self._territories
            ),
        )

    def _resolve_objective_arrival(self, army: MovingArmy) -> None:
        objective = self._world_objective
        if objective is None or objective.id != army.target_id or not objective.active:
            self._return_soldiers(army.attacker, army.source_id, army.soldiers, army.position)
            return
        if self._objective_engagement is not None:
            self._objective_queue.append(army)
            return
        self._start_objective_engagement(army)

    def _start_objective_engagement(self, army: MovingArmy) -> None:
        objective = self._world_objective
        if objective is None or not objective.active:
            self._return_soldiers(army.attacker, army.source_id, army.soldiers, army.position)
            return
        objective.start_contest()
        self._event_log.append(f"{army.attacker.name} contests {objective.display_name}")
        self._sound_events.append("objective_contest")
        if self._headless:
            result = CombatResolver.resolve_instant(army.soldiers, objective, army.attacker)
            self._finish_objective_assault(army, result)
            return

        zone = CombatZone(
            attacker=army.attacker,
            attacker_color=army.attacker.color,
            territory=objective,
            soldier_count=army.soldiers,
        )
        self._objective_engagement = ObjectiveEngagement(zone, army)
        self._combat_zones.append(zone)

    def _resolve_objective_combat_end(self, zone: CombatZone) -> None:
        engagement = self._objective_engagement
        if engagement is None or engagement.zone is not zone or zone.result is None:
            return
        self._objective_engagement = None
        self._finish_objective_assault(engagement.army, zone.result)

    def _finish_objective_assault(self, army: MovingArmy, result: CombatResult) -> None:
        objective = self._world_objective
        if objective is None:
            return
        self._effects.append(
            CombatVisualEffect(
                position=objective.centroid,
                attacker_color=army.attacker.color,
                defender_color=objective.owner.color,
                attacker_won=result.attacker_won,
                soldiers=result.surviving_attackers,
            )
        )
        if result.attacker_won:
            CombatResolver.apply_result(result, objective, army.attacker)
            self._grant_objective_reward(army.attacker, objective)
            self._return_soldiers(
                army.attacker,
                army.source_id,
                result.surviving_attackers,
                objective.centroid,
            )
            self._event_log.append(f"{army.attacker.name} claimed {objective.display_name}!")
            self._sound_events.append("objective_claim")
            self._finish_objective_cycle()
            return

        objective.end_contest()
        self._event_log.append(f"{army.attacker.name} failed to claim {objective.display_name}")
        self._sound_events.append("combat_defend")
        self._start_next_objective_assault()

    def _start_next_objective_assault(self) -> None:
        objective = self._world_objective
        if objective is None or not objective.active or self._objective_engagement is not None:
            return
        if not self._objective_queue:
            return
        army = self._objective_queue.pop(0)
        self._start_objective_engagement(army)

    def _grant_objective_reward(self, player: Player, objective: WorldObjective) -> None:
        if objective.objective_type is WorldObjectiveType.CARAVAN:
            home = self.home_territory(player)
            if home is not None:
                home.add_food(cfg.OBJECTIVE_CARAVAN_GOLD)
        elif objective.objective_type is WorldObjectiveType.WAR_BANNER:
            player.apply_war_banner()
        elif objective.objective_type is WorldObjectiveType.ANCIENT_SHRINE:
            for territory in self.territories_of(player):
                territory.queen.heal(cfg.OBJECTIVE_SHRINE_HEAL)

    def _finish_objective_cycle(self) -> None:
        objective = self._world_objective
        if objective is None:
            return
        engagement = self._objective_engagement
        if engagement is not None:
            if engagement.zone in self._combat_zones:
                self._combat_zones.remove(engagement.zone)
            self._return_soldiers(
                engagement.army.attacker,
                engagement.army.source_id,
                engagement.zone.attacking_soldiers.count,
                objective.centroid,
            )
            self._objective_engagement = None

        for queued_army in self._objective_queue:
            self._return_soldiers(
                queued_army.attacker,
                queued_army.source_id,
                queued_army.soldiers,
                objective.centroid,
            )
        self._objective_queue.clear()

        in_flight = [
            army for army in self._armies
            if army.target_type is ArmyTargetType.OBJECTIVE and army.target_id == objective.id
        ]
        for army in in_flight:
            self._armies.remove(army)
            self._return_soldiers(army.attacker, army.source_id, army.soldiers, army.position)

        self._next_objective_at = self._elapsed + cfg.OBJECTIVE_RESPAWN_DELAY
        self._objective_cleanup_at = self._elapsed + cfg.OBJECTIVE_RESULT_DISPLAY_DURATION

    def _return_soldiers(
        self,
        player: Player,
        source_id: int,
        soldiers: int,
        start: tuple[float, float],
    ) -> None:
        if soldiers <= 0 or not player.is_alive:
            return
        destination = self._return_destination(player, source_id, start)
        if destination is None:
            return
        self._dispatch_army(
            player,
            source_id,
            ArmyTargetType.RETURN,
            destination.id,
            soldiers,
            start,
            destination.centroid,
        )

    def _return_destination(
        self,
        player: Player,
        source_id: int,
        start: tuple[float, float],
    ) -> Territory | None:
        if 0 <= source_id < len(self._territories):
            source = self._territories[source_id]
            if source.owner is player and source.queen.is_alive:
                return source
        owned = self.territories_of(player)
        if not owned:
            return None
        return min(
            owned,
            key=lambda territory: math.hypot(
                territory.centroid[0] - start[0], territory.centroid[1] - start[1]
            ),
        )

    def _resolve_return_arrival(self, army: MovingArmy) -> None:
        if not army.attacker.is_alive:
            return
        if 0 <= army.target_id < len(self._territories):
            target = self._territories[army.target_id]
            if target.owner is army.attacker and target.queen.is_alive:
                target.add_soldiers(army.soldiers)
                return
        fallback = self._return_destination(army.attacker, army.source_id, army.position)
        if fallback is not None and fallback.id != army.target_id:
            self._dispatch_army(
                army.attacker,
                army.source_id,
                ArmyTargetType.RETURN,
                fallback.id,
                army.soldiers,
                army.position,
                fallback.centroid,
            )

    def _check_elimination(self, player: object) -> None:
        if not hasattr(player, "is_alive") or not player.is_alive:
            return
        has_territory = any(t.owner is player and t.queen.is_alive for t in self._territories)
        if not has_territory:
            player.eliminate()
            self._event_log.append(f"{player.name} has been eliminated!")


def _point_in_polygon(point: tuple[int, int], polygon: list[tuple[float, float]]) -> bool:
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        intersects = (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi
        if intersects:
            inside = not inside
        j = i
    return inside
