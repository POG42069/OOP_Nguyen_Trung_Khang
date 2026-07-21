import math
import random

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.battle_arena import (
    BattleArena,
    BattleArenaType,
    BattleOutcome,
    BattleUnitType,
)
from quadrant_wars.core.map_generator import MapGenerator
from quadrant_wars.core.marching import ArmyTargetType, MovingArmy
from quadrant_wars.core.navigation import BattlefieldNavigator
from quadrant_wars.core.objective import WorldObjective, WorldObjectiveState, WorldObjectiveType
from quadrant_wars.core.player import BotPlayer, HumanPlayer, Player, STRATEGIES
from quadrant_wars.core.territory import DevelopmentResult, Territory, TerritorySpecialization
from quadrant_wars.core.terrain import TerrainMap
from quadrant_wars.core.unit import DefenderState, SoldierState


class MatchSetup:
    def __init__(self, player_types, bot_strategy_names, seed):
        self.player_types = player_types
        self.bot_strategy_names = bot_strategy_names
        self.seed = seed

    def __eq__(self, other):
        return isinstance(other, MatchSetup) and vars(self) == vars(other)


class PlayerResult:
    def __init__(
        self,
        player_id,
        name,
        color,
        territories,
        soldiers,
        workers,
        defenders,
        objectives_claimed,
    ):
        self.player_id = player_id
        self.name = name
        self.color = color
        self.territories = territories
        self.soldiers = soldiers
        self.workers = workers
        self.defenders = defenders
        self.objectives_claimed = objectives_claimed

    def __eq__(self, other):
        return isinstance(other, PlayerResult) and vars(self) == vars(other)


class MatchResult:
    def __init__(self, setup, winner_id, duration, players):
        self.setup = setup
        self.winner_id = winner_id
        self.duration = duration
        self.players = players

    def __eq__(self, other):
        return isinstance(other, MatchResult) and vars(self) == vars(other)

    @property
    def winner(self):
        return next(
            (
                player
                for player in self.players
                if player.player_id == self.winner_id
            ),
            None,
        )




class CombatVisualEffect:
    def __init__(
        self,
        position,
        attacker_color,
        defender_color,
        attacker_won,
        soldiers,
        elapsed=0.0,
        duration=1.45,
    ):
        self.position = position
        self.attacker_color = attacker_color
        self.defender_color = defender_color
        self.attacker_won = attacker_won
        self.soldiers = soldiers
        self.elapsed = elapsed
        self.duration = duration

    def __eq__(self, other):
        return isinstance(other, CombatVisualEffect) and vars(self) == vars(other)

    @property
    def progress(self):
        return min(1.0, self.elapsed / max(0.01, self.duration))


class Match:
    def __init__(
        self,
        player_types,
        seed = None,
        bot_strategy_classes = None,
        headless = False,
    ):
        normalized_player_types = tuple(
            "human" if player_type.lower() == "human" else "bot"
            for player_type in player_types
        )
        self._players = []
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
        self._terrain = TerrainMap.generate(
            cfg.WINDOW_WIDTH,
            cfg.WINDOW_HEIGHT,
            self._territories,
            self._seed,
        )
        self._navigator = BattlefieldNavigator(
            cfg.WINDOW_WIDTH,
            cfg.WINDOW_HEIGHT,
            terrain=self._terrain,
        )
        self._armies = []
        self._battles = {}
        self._next_unit_id = 1
        self._effects = []
        self._sound_events = []
        self._winner = None
        self._elapsed = 0.0
        self._event_log = []
        self._headless = headless
        self._march_sound_timer = 0.0
        self._recent_territory_attackers = {}

        self._objective_rng = random.Random(self._seed ^ 0x0B1EC71)
        self._world_objective = None
        self._objective_id = 0
        self._next_objective_at = cfg.OBJECTIVE_FIRST_ACTIVE_AT
        self._last_objective_type = None
        self._objective_cleanup_at = None
        self._claimed_objective_ids = set()
        self._objective_claims_by_player = {
            player.id: 0 for player in self._players
        }

    @classmethod
    def from_setup(
        cls,
        setup,
        *,
        new_seed = False,
        headless = False,
    ):
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
    def players(self):
        return list(self._players)

    @property
    def setup(self):
        return self._setup

    @property
    def territories(self):
        return list(self._territories)

    @property
    def armies(self):
        return list(self._armies)

    @property
    def terrain(self):
        return self._terrain

    @property
    def battles(self):
        return list(self._battles.values())

    @property
    def effects(self):
        return list(self._effects)

    @property
    def world_objective(self):
        return self._world_objective

    @property
    def objective_countdown(self):
        objective = self._world_objective
        if objective is None:
            return max(0.0, self._next_objective_at - self._elapsed)
        if objective.state is WorldObjectiveState.TELEGRAPHING:
            return max(0.0, self._next_objective_at - self._elapsed)
        if objective.active:
            return 0.0
        return max(0.0, self._next_objective_at - self._elapsed)

    @property
    def winner(self):
        return self._winner

    @property
    def elapsed(self):
        return self._elapsed

    @property
    def event_log(self):
        return self._event_log[-6:]

    def pop_sound_events(self):
        events = self._sound_events[:]
        self._sound_events.clear()
        return events

    def result_snapshot(self):
        player_results = []
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

    def territories_of(self, player):
        return [t for t in self._territories if t.owner is player and t.queen.is_alive]

    def home_territory(self, player):
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

    def best_attack_source(self, player, target):
        owned = [t for t in self.territories_of(player) if t.soldiers.count > 1]
        if not owned:
            return None
        tx, ty = target.centroid
        return min(owned, key=lambda t: math.hypot(t.centroid[0] - tx, t.centroid[1] - ty))

    def living_players(self):
        alive = []
        for player in self._players:
            if not player.is_alive:
                continue
            if any(t.owner is player and t.queen.is_alive for t in self._territories):
                alive.append(player)
            else:
                self._check_elimination(player)
        return alive

    def territory_at(self, position):
        for territory in self._territories:
            if _point_in_polygon(position, territory.polygon):
                return territory
        return None

    def territory_in_battle(self, territory_id):
        return (BattleArenaType.TERRITORY, territory_id) in self._battles

    def develop_territory(
        self,
        player,
        territory_id,
        specialization,
    ):
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

    def issue_attack(self, source, target, soldiers):
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
        dispatched = self._dispatch_army(
            source.owner,
            source.id,
            ArmyTargetType.TERRITORY,
            target.id,
            units,
            source.battle_position,
            target.battle_position,
        )
        if not dispatched:
            source.receive_soldiers(units)
            return False
        target_name = target.owner.name if getattr(target, "owner", None) else "Neutral land"
        self._event_log.append(f"{source.owner.name} sent {len(units)} soldiers to {target_name}")
        self._sound_events.append("attack")
        return True

    def issue_objective_attack(self, source, soldiers):
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
        dispatched = self._dispatch_army(
            source.owner,
            source.id,
            ArmyTargetType.OBJECTIVE,
            objective.id,
            units,
            source.battle_position,
            objective.centroid,
        )
        if not dispatched:
            source.receive_soldiers(units)
            return False
        self._event_log.append(f"{source.owner.name} sent {len(units)} soldiers to {objective.display_name}")
        self._sound_events.append("attack")
        return True

    def cancellable_armies(self, player):
        """Armies may be recalled only while they are still marching."""
        return [
            army for army in self._armies
            if army.attacker is player and army.can_be_recalled
        ]

    def cancel_attack(self, player, army):
        """Turn an outbound march into a return march from its current position."""
        if army not in self._armies:
            return False
        if army.attacker is not player or not army.can_be_recalled:
            return False

        self._armies.remove(army)
        self._return_units(player, army.units, army.position)
        self._event_log.append(
            f"{player.name} recalled {army.soldiers} soldiers before battle"
        )
        self._sound_events.append("click")
        return True

    def objective_commitment_count(self, player):
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

    def territory_commitment_count(self, player, territory_id):
        moving = sum(
            army.soldiers
            for army in self._armies
            if army.attacker is player
            and army.targets_territory
            and army.target_id == territory_id
        )
        arena = self._battles.get((BattleArenaType.TERRITORY, territory_id))
        return moving + (arena.commitment_count(player) if arena is not None else 0)

    def recent_territory_attackers(self, territory_id):
        attackers = self._recent_territory_attackers.get(territory_id, {})
        return {
            player_id
            for player_id, expires_at in attackers.items()
            if expires_at > self._elapsed
        }

    def hostile_territory_commitment_count(
        self,
        defender,
        territory_id,
    ):
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

    def offensive_territory_commitment_count(self, player):
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

    def update(self, dt):
        if self._winner is not None:
            return
        self._elapsed += dt
        self._update_world_objective(dt)

        for territory in self._territories:
            in_combat = (BattleArenaType.TERRITORY, territory.id) in self._battles
            territory.update(dt, in_combat=in_combat)
        for player in self._players:
            player.update(self, dt)

        arrived = []
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

        finished_battles = []
        for arena in list(self._battles.values()):
            result = arena.update(dt)
            arena_sounds = arena.pop_sound_events()
            if not self._headless:
                self._sound_events.extend(arena_sounds)
            if result is not None:
                finished_battles.append((arena, result))
        for arena, outcome in finished_battles:
            self._resolve_battle_end(arena, outcome)

        expired = []
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
        attacker,
        source_id,
        target_type,
        target_id,
        units,
        start,
        end,
    ):
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
        if len(path) < 2:
            return False
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
        return True

    def _assign_unit_ids(
        self,
        states,
    ):
        assigned = []
        for state in states:
            if state.unit_id > 0:
                assigned.append(state)
                self._next_unit_id = max(self._next_unit_id, state.unit_id + 1)
                continue
            assigned.append(
                type(state)(self._next_unit_id, state.hp, state.source_id)
            )
            self._next_unit_id += 1
        return assigned

    def _resolve_arrival(self, army):
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

    def _join_territory_battle(self, army, target):
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

    def _resolve_battle_end(self, arena, outcome):
        key = (arena.arena_type, arena.target_id)
        if self._battles.get(key) is arena:
            del self._battles[key]
        if arena.arena_type is BattleArenaType.OBJECTIVE:
            self._resolve_objective_battle_end(arena, outcome)
            return

        target = arena.target
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

    def _update_world_objective(self, dt):
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

    def _spawn_world_objective(self):
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

    def _activate_world_objective(self):
        objective = self._world_objective
        if objective is None or objective.state is not WorldObjectiveState.TELEGRAPHING:
            return
        objective.activate()
        self._event_log.append(f"{objective.display_name} is ready to claim!")
        self._sound_events.append("objective_ready")

    def _choose_objective_position(self):
        cx, cy = cfg.WINDOW_WIDTH / 2, cfg.WINDOW_HEIGHT / 2 + 24
        candidates = [gate.center for gate in self._terrain.gates]
        candidates.extend([
            (cx, cy),
            (cx - 92, cy - 48),
            (cx + 92, cy - 48),
            (cx - 112, cy + 56),
            (cx + 112, cy + 56),
        ])
        self._objective_rng.shuffle(candidates)
        clear_candidates = [
            point for point in candidates
            if not self._terrain.is_blocked(point, clearance=20.0, open_points=(point,))
        ]
        return max(
            clear_candidates or candidates,
            key=lambda point: min(
                math.hypot(point[0] - territory.centroid[0], point[1] - territory.centroid[1])
                for territory in self._territories
            ),
        )

    def _resolve_objective_arrival(self, army):
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
        arena,
        outcome,
    ):
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

    def _grant_objective_reward(self, player, objective):
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

    def _finish_objective_cycle(self):
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
        player,
        units,
        start,
    ):
        if not player.is_alive:
            return
        by_source = {}
        for state in units:
            if state.hp > 0.0:
                by_source.setdefault(state.source_id, []).append(state)
        for source_id, source_units in by_source.items():
            destination = self._return_destination(player, source_id, start)
            if destination is None:
                continue
            dispatched = self._dispatch_army(
                player,
                source_id,
                ArmyTargetType.RETURN,
                destination.id,
                source_units,
                start,
                destination.battle_position,
            )
            if not dispatched:
                destination.receive_soldiers(source_units)

    def _return_destination(
        self,
        player,
        source_id,
        start,
    ):
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

    def _resolve_return_arrival(self, army):
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
            dispatched = self._dispatch_army(
                army.attacker,
                army.source_id,
                ArmyTargetType.RETURN,
                fallback.id,
                army.units,
                army.position,
                fallback.battle_position,
            )
            if not dispatched:
                fallback.receive_soldiers(army.units)

    def _check_elimination(self, player):
        if not hasattr(player, "is_alive") or not player.is_alive:
            return
        has_territory = any(t.owner is player and t.queen.is_alive for t in self._territories)
        if not has_territory:
            player.eliminate()
            self._armies = [army for army in self._armies if army.attacker is not player]
            for arena in self._battles.values():
                arena.eliminate_owner(player)
            self._event_log.append(f"{player.name} has been eliminated!")


def _point_in_polygon(point, polygon):
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
