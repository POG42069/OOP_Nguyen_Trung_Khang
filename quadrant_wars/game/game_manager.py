from __future__ import annotations

import math
import random
from dataclasses import dataclass, field, replace
from enum import Enum, auto
from typing import Iterable

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.battle_arena import (
    BattleArena,
    BattleArenaType,
    BattleOutcome,
    BattleUnitType,
)
from quadrant_wars.core.map_generator import MapGenerator
from quadrant_wars.core.navigation import BattlefieldNavigator
from quadrant_wars.core.objective import WorldObjective, WorldObjectiveState, WorldObjectiveType
from quadrant_wars.core.player import BotPlayer, HumanPlayer, Player, STRATEGIES
from quadrant_wars.core.territory import DevelopmentResult, Territory, TerritorySpecialization
from quadrant_wars.core.unit import DefenderState, SoldierState


class ArmyTargetType(Enum):
    TERRITORY = auto()
    OBJECTIVE = auto()
    RETURN = auto()


@dataclass(frozen=True)
class MatchSetup:
    player_types: tuple[str, ...]
    bot_strategy_names: tuple[str | None, ...]
    seed: int


@dataclass(frozen=True)
class PlayerResult:
    player_id: int
    name: str
    color: tuple[int, int, int]
    territories: int
    soldiers: int
    workers: int
    defenders: int
    objectives_claimed: int


@dataclass(frozen=True)
class MatchResult:
    setup: MatchSetup
    winner_id: int | None
    duration: float
    players: tuple[PlayerResult, ...]

    @property
    def winner(self) -> PlayerResult | None:
        return next(
            (
                player
                for player in self.players
                if player.player_id == self.winner_id
            ),
            None,
        )


@dataclass
class MovingArmy:
    attacker: Player
    source_id: int
    target_type: ArmyTargetType
    target_id: int
    units: list[SoldierState]
    start: tuple[float, float]
    end: tuple[float, float]
    path: tuple[tuple[float, float], ...] = ()
    elapsed: float = 0.0
    duration: float = 1.0
    _segment_lengths: tuple[float, ...] = field(init=False, repr=False)
    _path_length: float = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if len(self.path) < 2:
            self.path = (self.start, self.end)
        self._segment_lengths = tuple(
            math.dist(start, end)
            for start, end in zip(self.path, self.path[1:])
        )
        self._path_length = max(0.01, sum(self._segment_lengths))

    @property
    def targets_territory(self) -> bool:
        return self.target_type is ArmyTargetType.TERRITORY

    @property
    def soldiers(self) -> int:
        return len(self.units)

    @property
    def progress(self) -> float:
        return min(1.0, self.elapsed / max(0.01, self.duration))

    @property
    def position(self) -> tuple[float, float]:
        return self._point_at(self.progress)

    @property
    def heading(self) -> tuple[float, float]:
        before = self._point_at(max(0.0, self.progress - 0.01))
        after = self._point_at(min(1.0, self.progress + 0.01))
        dx = after[0] - before[0]
        dy = after[1] - before[1]
        length = max(0.01, math.hypot(dx, dy))
        return dx / length, dy / length

    @property
    def path_length(self) -> float:
        return self._path_length

    def unit_position(self, index: int) -> tuple[float, float]:
        """Stable formation position for one Soldier along the shared A* path."""
        if not self.units:
            return self.position
        index = max(0, min(index, len(self.units) - 1))
        columns = max(1, min(16, math.ceil(math.sqrt(len(self.units) * 1.7))))
        row = index // columns
        column = index % columns
        row_count = min(columns, len(self.units) - row * columns)
        scale = (
            0.84 if len(self.units) <= 8
            else 0.72 if len(self.units) <= 20
            else 0.61 if len(self.units) <= 40
            else 0.52 if len(self.units) <= 80
            else 0.44
        )
        lateral = (column - (row_count - 1) / 2.0) * max(14.0, 25.0 * scale)
        trailing = row * max(12.0, 22.0 * scale)
        heading_x, heading_y = self.heading
        side_x, side_y = -heading_y, heading_x
        base_x, base_y = self.position
        return (
            base_x + side_x * lateral - heading_x * trailing,
            base_y + side_y * lateral - heading_y * trailing,
        )

    @property
    def unit_positions(self) -> tuple[tuple[float, float], ...]:
        return tuple(self.unit_position(index) for index in range(len(self.units)))

    def _point_at(self, progress: float) -> tuple[float, float]:
        remaining = max(0.0, min(1.0, progress)) * self._path_length
        for index, segment_length in enumerate(self._segment_lengths):
            if remaining <= segment_length or index == len(self._segment_lengths) - 1:
                ratio = remaining / max(0.01, segment_length)
                start = self.path[index]
                end = self.path[index + 1]
                return (
                    start[0] + (end[0] - start[0]) * ratio,
                    start[1] + (end[1] - start[1]) * ratio,
                )
            remaining -= segment_length
        return self.path[-1]

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


class Match:
    def __init__(
        self,
        player_types: Iterable[str],
        seed: int | None = None,
        bot_strategy_classes: list[type] | None = None,
        headless: bool = False,
    ) -> None:
        normalized_player_types = tuple(
            "human" if player_type.lower() == "human" else "bot"
            for player_type in player_types
        )
        self._players: list[Player] = []
        self._seed = seed if seed is not None else random.SystemRandom().randrange(2**63)
        strategy_rng = random.Random(self._seed)
        strategy_classes = bot_strategy_classes[:] if bot_strategy_classes else STRATEGIES[:]
        if not bot_strategy_classes:
            strategy_rng.shuffle(strategy_classes)
        for i, player_type in enumerate(normalized_player_types):
            color = cfg.PLAYER_COLORS[i]
            if player_type.lower() == "human":
                self._players.append(HumanPlayer(i, f"Player {i + 1}", color))
            else:
                strategy = strategy_classes[i % len(strategy_classes)]()
                self._players.append(
                    BotPlayer(
                        i,
                        f"{strategy.name} Bot {i + 1}",
                        color,
                        strategy,
                        decision_phase=strategy_rng.random(),
                    )
                )

        self._setup = MatchSetup(
            player_types=normalized_player_types,
            bot_strategy_names=tuple(
                player.strategy.name if isinstance(player, BotPlayer) else None
                for player in self._players
            ),
            seed=self._seed,
        )

        map_data = MapGenerator().generate(len(self._players), seed=self._seed)
        self._territories = [
            Territory(i, self._players[i], polygon)
            for i, polygon in enumerate(map_data.polygons)
        ]
        self._navigator = BattlefieldNavigator(cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT)
        self._armies: list[MovingArmy] = []
        self._battles: dict[tuple[BattleArenaType, int], BattleArena] = {}
        self._next_unit_id = 1
        self._effects: list[CombatVisualEffect] = []
        self._sound_events: list[str] = []
        self._winner: Player | None = None
        self._elapsed = 0.0
        self._event_log: list[str] = []
        self._headless = headless
        self._march_sound_timer = 0.0
        self._recent_territory_attackers: dict[int, dict[int, float]] = {}

        self._objective_rng = random.Random(self._seed ^ 0x0B1EC71)
        self._world_objective: WorldObjective | None = None
        self._objective_id = 0
        self._next_objective_at = cfg.OBJECTIVE_FIRST_ACTIVE_AT
        self._last_objective_type: WorldObjectiveType | None = None
        self._objective_cleanup_at: float | None = None
        self._claimed_objective_ids: set[int] = set()
        self._objective_claims_by_player: dict[int, int] = {
            player.id: 0 for player in self._players
        }

    @classmethod
    def from_setup(
        cls,
        setup: MatchSetup,
        *,
        new_seed: bool = False,
        headless: bool = False,
    ) -> "Match":
        strategy_by_name = {strategy.name: strategy for strategy in STRATEGIES}
        strategy_classes = [
            strategy_by_name.get(name or "", STRATEGIES[0])
            for name in setup.bot_strategy_names
        ]
        return cls(
            setup.player_types,
            seed=None if new_seed else setup.seed,
            bot_strategy_classes=strategy_classes,
            headless=headless,
        )

    @property
    def players(self) -> list[Player]:
        return list(self._players)

    @property
    def setup(self) -> MatchSetup:
        return self._setup

    @property
    def territories(self) -> list[Territory]:
        return list(self._territories)

    @property
    def armies(self) -> list[MovingArmy]:
        return list(self._armies)

    @property
    def battles(self) -> list[BattleArena]:
        return list(self._battles.values())

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
            return 0.0
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

    def result_snapshot(self) -> MatchResult:
        player_results: list[PlayerResult] = []
        for player in self._players:
            owned = [territory for territory in self._territories if territory.owner is player]
            travelling_soldiers = sum(
                army.soldiers for army in self._armies if army.attacker is player
            )
            deployed_soldiers = sum(
                1
                for arena in self._battles.values()
                for agent in arena.living_agents
                if agent.owner is player
                and agent.unit_type is BattleUnitType.SOLDIER
            )
            deployed_defenders = sum(
                1
                for arena in self._battles.values()
                for agent in arena.living_agents
                if agent.owner is player
                and agent.unit_type is BattleUnitType.DEFENDER
            )
            player_results.append(
                PlayerResult(
                    player_id=player.id,
                    name=player.name,
                    color=player.color,
                    territories=len(owned),
                    soldiers=(
                        sum(territory.soldiers.count for territory in owned)
                        + travelling_soldiers
                        + deployed_soldiers
                    ),
                    workers=sum(territory.workers.count for territory in owned),
                    defenders=(
                        sum(territory.defenders.count for territory in owned)
                        + deployed_defenders
                    ),
                    objectives_claimed=self._objective_claims_by_player.get(player.id, 0),
                )
            )
        return MatchResult(
            setup=self._setup,
            winner_id=self._winner.id if self._winner is not None else None,
            duration=self._elapsed,
            players=tuple(player_results),
        )

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
                self._check_elimination(player)
        return alive

    def territory_at(self, position: tuple[int, int]) -> Territory | None:
        for territory in self._territories:
            if _point_in_polygon(position, territory.polygon):
                return territory
        return None

    def territory_in_battle(self, territory_id: int) -> bool:
        return (BattleArenaType.TERRITORY, territory_id) in self._battles

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
        if (BattleArenaType.TERRITORY, territory.id) in self._battles:
            return DevelopmentResult(False, None, "Territory is under attack")
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
        units = self._assign_unit_ids(
            source.detach_soldiers(min(soldiers, source.soldiers.count))
        )
        if not units:
            return False
        if target.owner is not source.owner:
            attackers = self._recent_territory_attackers.setdefault(target.id, {})
            attackers[source.owner.id] = self._elapsed + cfg.BOT_RECENT_ATTACK_AVOIDANCE
        self._dispatch_army(
            source.owner,
            source.id,
            ArmyTargetType.TERRITORY,
            target.id,
            units,
            source.battle_position,
            target.battle_position,
        )
        target_name = target.owner.name if getattr(target, "owner", None) else "Neutral land"
        self._event_log.append(f"{source.owner.name} sent {len(units)} soldiers to {target_name}")
        self._sound_events.append("attack")
        return True

    def issue_objective_attack(self, source: Territory, soldiers: int) -> bool:
        objective = self._world_objective
        if objective is None or not objective.active or soldiers <= 0:
            return False
        if not getattr(source.owner, "is_alive", False):
            return False
        units = self._assign_unit_ids(
            source.detach_soldiers(min(soldiers, source.soldiers.count))
        )
        if not units:
            return False
        self._dispatch_army(
            source.owner,
            source.id,
            ArmyTargetType.OBJECTIVE,
            objective.id,
            units,
            source.battle_position,
            objective.centroid,
        )
        self._event_log.append(f"{source.owner.name} sent {len(units)} soldiers to {objective.display_name}")
        self._sound_events.append("attack")
        return True

    def objective_commitment_count(self, player: Player) -> int:
        moving = sum(
            army.soldiers
            for army in self._armies
            if army.attacker is player and army.target_type is ArmyTargetType.OBJECTIVE
        )
        objective = self._world_objective
        if objective is None:
            return moving
        arena = self._battles.get((BattleArenaType.OBJECTIVE, objective.id))
        return moving + (arena.commitment_count(player) if arena is not None else 0)

    def territory_commitment_count(self, player: Player, territory_id: int) -> int:
        moving = sum(
            army.soldiers
            for army in self._armies
            if army.attacker is player
            and army.targets_territory
            and army.target_id == territory_id
        )
        arena = self._battles.get((BattleArenaType.TERRITORY, territory_id))
        return moving + (arena.commitment_count(player) if arena is not None else 0)

    def recent_territory_attackers(self, territory_id: int) -> set[int]:
        attackers = self._recent_territory_attackers.get(territory_id, {})
        return {
            player_id
            for player_id, expires_at in attackers.items()
            if expires_at > self._elapsed
        }

    def hostile_territory_commitment_count(
        self,
        defender: Player,
        territory_id: int,
    ) -> int:
        moving = sum(
            army.soldiers
            for army in self._armies
            if army.targets_territory
            and army.target_id == territory_id
            and army.attacker is not defender
        )
        arena = self._battles.get((BattleArenaType.TERRITORY, territory_id))
        if arena is None:
            return moving
        return moving + sum(
            1
            for agent in arena.living_agents
            if not agent.neutral and agent.owner is not defender
        )

    def offensive_territory_commitment_count(self, player: Player) -> int:
        moving = sum(
            army.soldiers
            for army in self._armies
            if army.targets_territory
            and 0 <= army.target_id < len(self._territories)
            and self._territories[army.target_id].owner is not player
            and army.attacker is player
        )
        battling = sum(
            arena.commitment_count(player)
            for arena in self._battles.values()
            if arena.arena_type is BattleArenaType.TERRITORY
            and arena.target.owner is not player
        )
        return moving + battling

    def update(self, dt: float) -> None:
        if self._winner is not None:
            return
        self._elapsed += dt
        self._update_world_objective(dt)

        for territory in self._territories:
            in_combat = (BattleArenaType.TERRITORY, territory.id) in self._battles
            territory.update(dt, in_combat=in_combat)
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

        self._march_sound_timer = max(0.0, self._march_sound_timer - dt)
        if self._armies and self._march_sound_timer <= 0.0 and not self._headless:
            self._sound_events.append("footstep")
            self._march_sound_timer = 0.24

        finished_battles: list[tuple[BattleArena, BattleOutcome]] = []
        for arena in list(self._battles.values()):
            result = arena.update(dt)
            arena_sounds = arena.pop_sound_events()
            if not self._headless:
                self._sound_events.extend(arena_sounds)
            if result is not None:
                finished_battles.append((arena, result))
        for arena, outcome in finished_battles:
            self._resolve_battle_end(arena, outcome)

        expired: list[CombatVisualEffect] = []
        for effect in self._effects:
            effect.elapsed += dt
            if effect.progress >= 1.0:
                expired.append(effect)
        for effect in expired:
            self._effects.remove(effect)

        living = self.living_players()
        if len(living) == 1 and not self._battles:
            self._winner = living[0]
        elif len(living) == 0 and not self._battles:
            self._winner = self._players[0]

    def _dispatch_army(
        self,
        attacker: Player,
        source_id: int,
        target_type: ArmyTargetType,
        target_id: int,
        units: list[SoldierState],
        start: tuple[float, float],
        end: tuple[float, float],
    ) -> None:
        target_territory_id = (
            target_id
            if target_type in (ArmyTargetType.TERRITORY, ArmyTargetType.RETURN)
            else None
        )
        path = self._navigator.find_path(
            start,
            end,
            self._territories,
            source_id=source_id,
            target_territory_id=target_territory_id,
        )
        distance = sum(math.dist(a, b) for a, b in zip(path, path[1:]))
        duration = max(0.6, distance / cfg.SOLDIER_TRAVEL_SPEED)
        self._armies.append(
            MovingArmy(
                attacker=attacker,
                source_id=source_id,
                target_type=target_type,
                target_id=target_id,
                units=list(units),
                start=start,
                end=end,
                path=path,
                duration=duration,
            )
        )

    def _assign_unit_ids(
        self,
        states: Iterable[SoldierState | DefenderState],
    ) -> list[SoldierState | DefenderState]:
        assigned: list[SoldierState | DefenderState] = []
        for state in states:
            if state.unit_id > 0:
                assigned.append(state)
                self._next_unit_id = max(self._next_unit_id, state.unit_id + 1)
                continue
            assigned.append(replace(state, unit_id=self._next_unit_id))
            self._next_unit_id += 1
        return assigned

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
        key = (BattleArenaType.TERRITORY, target.id)
        arena = self._battles.get(key)
        if arena is not None and arena.captured_pending:
            self._return_units(army.attacker, army.units, army.position)
            return
        if target.owner is army.attacker and key not in self._battles:
            target.receive_soldiers(army.units)
            return
        self._join_territory_battle(army, target)

    def _join_territory_battle(self, army: MovingArmy, target: Territory) -> None:
        key = (BattleArenaType.TERRITORY, target.id)
        arena = self._battles.get(key)
        created = arena is None
        if arena is None:
            arena = BattleArena(BattleArenaType.TERRITORY, target)
            self._battles[key] = arena
            arena.add_army(
                army.attacker,
                army.attacker.color,
                army.units,
                army.heading,
                entry_positions=army.unit_positions,
            )
            defenders = self._assign_unit_ids(
                target.detach_soldiers(target.soldiers.count)
            )
            arena.add_army(
                target.owner,
                target.owner.color,
                defenders,
                neutral=False,
                defending=True,
            )
            fortress_defenders = self._assign_unit_ids(target.detach_defenders())
            arena.add_defenders(
                target.owner,
                target.owner.color,
                fortress_defenders,
            )
        else:
            arena.add_army(
                army.attacker,
                army.attacker.color,
                army.units,
                army.heading,
                entry_positions=army.unit_positions,
            )

        if created:
            self._event_log.append(
                f"Battle! {army.attacker.name} ({army.soldiers}) vs {target.owner.name}"
            )
            self._sound_events.append("combat_defend")
            if any(
                agent.unit_type is BattleUnitType.DEFENDER
                for agent in arena.living_agents
            ):
                self._sound_events.append("fortress_alarm")
        else:
            self._event_log.append(
                f"{army.attacker.name} reinforced battle T{target.id + 1} (+{army.soldiers})"
            )
            self._sound_events.append("battle_reinforce")

    def _resolve_battle_end(self, arena: BattleArena, outcome: BattleOutcome) -> None:
        key = (arena.arena_type, arena.target_id)
        if self._battles.get(key) is arena:
            del self._battles[key]
        if arena.arena_type is BattleArenaType.OBJECTIVE:
            self._resolve_objective_battle_end(arena, outcome)
            return

        target: Territory = arena.target
        defender = target.owner
        if outcome.captured and isinstance(outcome.winner, Player):
            winner = outcome.winner
            survivors = outcome.survivors_for(winner)
            target.reset_after_capture(winner, survivors)
            self._effects.append(
                CombatVisualEffect(
                    position=target.battle_position,
                    attacker_color=winner.color,
                    defender_color=defender.color,
                    attacker_won=True,
                    soldiers=len(survivors),
                )
            )
            self._event_log.append(
                f"{winner.name} conquered {defender.name}; {len(survivors)} survived"
            )
            self._sound_events.append("combat_win")
            self._check_elimination(defender)
            return

        defenders = outcome.survivors_for(defender)
        target.receive_soldiers(defenders)
        deployed_defenders = sum(
            1
            for agent in arena.agents
            if agent.owner is defender
            and agent.unit_type is BattleUnitType.DEFENDER
        )
        target.finish_defense(
            outcome.defender_survivors_for(defender),
            deployed_defenders,
        )
        self._effects.append(
            CombatVisualEffect(
                position=target.battle_position,
                attacker_color=getattr(outcome.winner, "color", defender.color),
                defender_color=defender.color,
                attacker_won=False,
                soldiers=len(defenders),
            )
        )
        self._event_log.append(f"{defender.name} held territory T{target.id + 1}")
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

        if objective.state is WorldObjectiveState.RESOLVED:
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
            self._return_units(army.attacker, army.units, army.position)
            return
        key = (BattleArenaType.OBJECTIVE, objective.id)
        arena = self._battles.get(key)
        if arena is not None and arena.captured_pending:
            self._return_units(army.attacker, army.units, army.position)
            return

        rival_present = arena is not None and any(
            owner is not army.attacker for owner in arena.player_factions
        )
        if arena is None:
            arena = BattleArena(BattleArenaType.OBJECTIVE, objective)
            self._battles[key] = arena
            objective.start_contest()
            arena.add_army(
                army.attacker,
                army.attacker.color,
                army.units,
                army.heading,
                entry_positions=army.unit_positions,
            )
            guardians = self._assign_unit_ids(
                objective.detach_soldiers(objective.soldiers.count)
            )
            arena.add_army(
                objective.owner,
                objective.owner.color,
                guardians,
                neutral=True,
                defending=True,
            )
            self._event_log.append(
                f"{army.attacker.name} contests {objective.display_name}"
            )
            self._sound_events.append("objective_contest")
            return

        arena.add_army(
            army.attacker,
            army.attacker.color,
            army.units,
            army.heading,
            entry_positions=army.unit_positions,
        )
        self._event_log.append(
            f"{army.attacker.name} joined {objective.display_name} (+{army.soldiers})"
        )
        self._sound_events.append("objective_clash" if rival_present else "battle_reinforce")

    def _resolve_objective_battle_end(
        self,
        arena: BattleArena,
        outcome: BattleOutcome,
    ) -> None:
        objective = self._world_objective
        if objective is None or objective.id != arena.target_id:
            return
        if outcome.captured and isinstance(outcome.winner, Player):
            if objective.id in self._claimed_objective_ids:
                return
            winner = outcome.winner
            survivors = outcome.survivors_for(winner)
            objective.reset_after_capture(winner, survivors)
            self._grant_objective_reward(winner, objective)
            self._return_units(winner, survivors, objective.centroid)
            self._effects.append(
                CombatVisualEffect(
                    position=objective.centroid,
                    attacker_color=winner.color,
                    defender_color=objective.owner.color,
                    attacker_won=True,
                    soldiers=len(survivors),
                )
            )
            self._event_log.append(f"{winner.name} claimed {objective.display_name}!")
            self._sound_events.append("objective_claim")
            self._finish_objective_cycle()
            return

        guardians = outcome.survivors_for(objective.owner)
        objective.receive_soldiers(guardians)
        objective.end_contest()
        self._event_log.append(f"{objective.display_name} resisted every contender")
        self._sound_events.append("combat_defend")

    def _grant_objective_reward(self, player: Player, objective: WorldObjective) -> None:
        if objective.id in self._claimed_objective_ids:
            return
        self._claimed_objective_ids.add(objective.id)
        self._objective_claims_by_player[player.id] = (
            self._objective_claims_by_player.get(player.id, 0) + 1
        )
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
        in_flight = [
            army for army in self._armies
            if army.target_type is ArmyTargetType.OBJECTIVE and army.target_id == objective.id
        ]
        for army in in_flight:
            self._armies.remove(army)
            self._return_units(army.attacker, army.units, army.position)

        self._next_objective_at = self._elapsed + cfg.OBJECTIVE_RESPAWN_DELAY
        self._objective_cleanup_at = self._elapsed + cfg.OBJECTIVE_RESULT_DISPLAY_DURATION

    def _return_units(
        self,
        player: Player,
        units: Iterable[SoldierState],
        start: tuple[float, float],
    ) -> None:
        if not player.is_alive:
            return
        by_source: dict[int, list[SoldierState]] = {}
        for state in units:
            if state.hp > 0.0:
                by_source.setdefault(state.source_id, []).append(state)
        for source_id, source_units in by_source.items():
            destination = self._return_destination(player, source_id, start)
            if destination is None:
                continue
            self._dispatch_army(
                player,
                source_id,
                ArmyTargetType.RETURN,
                destination.id,
                source_units,
                start,
                destination.battle_position,
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
                key = (BattleArenaType.TERRITORY, target.id)
                if key in self._battles:
                    self._join_territory_battle(army, target)
                else:
                    target.receive_soldiers(army.units)
                return
        fallback = self._return_destination(army.attacker, army.source_id, army.position)
        if fallback is not None and fallback.id != army.target_id:
            self._dispatch_army(
                army.attacker,
                army.source_id,
                ArmyTargetType.RETURN,
                fallback.id,
                army.units,
                army.position,
                fallback.battle_position,
            )

    def _check_elimination(self, player: object) -> None:
        if not hasattr(player, "is_alive") or not player.is_alive:
            return
        has_territory = any(t.owner is player and t.queen.is_alive for t in self._territories)
        if not has_territory:
            player.eliminate()
            self._armies = [army for army in self._armies if army.attacker is not player]
            for arena in self._battles.values():
                arena.eliminate_owner(player)
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
