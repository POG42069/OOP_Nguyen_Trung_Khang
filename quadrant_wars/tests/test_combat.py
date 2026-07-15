from __future__ import annotations

import unittest

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.battle_arena import (
    MAX_MELEE_SLOTS,
    SIMULATION_STEP,
    BattleArena,
    BattleArenaType,
)
from quadrant_wars.core.combat import CombatResolver
from quadrant_wars.core.objective import WorldObjective, WorldObjectiveType
from quadrant_wars.core.player import HumanPlayer
from quadrant_wars.core.territory import Territory, TerritorySpecialization
from quadrant_wars.core.unit import DefenderState, SoldierState


def make_territory(soldiers: int, workers: int = 1) -> Territory:
    owner = HumanPlayer(0, "Defender", (255, 0, 0))
    territory = Territory(0, owner, [(0, 0), (100, 0), (100, 100), (0, 100)])
    territory.soldiers.remove(territory.soldiers.count)
    territory.soldiers.add(soldiers)
    territory.workers.remove(territory.workers.count)
    territory.workers.add(workers)
    return territory


def states(first_id: int, amount: int, source_id: int = 0, hp: float = cfg.SOLDIER_HP) -> list[SoldierState]:
    return [
        SoldierState(first_id + index, float(hp), source_id)
        for index in range(amount)
    ]


def run_arena(arena: BattleArena, seconds: float = 120.0):
    result = None
    for _ in range(int(seconds / SIMULATION_STEP)):
        result = arena.update(SIMULATION_STEP)
        if result is not None:
            return result
    return result


class CombatResolverTest(unittest.TestCase):
    def test_opening_territory_requires_three_attackers(self) -> None:
        attacker = HumanPlayer(1, "Attacker", (0, 0, 255))

        failed = CombatResolver.resolve_instant(2, make_territory(1, 1), attacker)
        captured = CombatResolver.resolve_instant(3, make_territory(1, 1), attacker)

        self.assertFalse(failed.attacker_won)
        self.assertTrue(captured.attacker_won)

    def test_failed_attack_preserves_individual_defender_damage(self) -> None:
        territory = make_territory(soldiers=6, workers=1)

        result = CombatResolver.resolve_instant(4, territory)

        self.assertFalse(result.attacker_won)
        self.assertEqual(result.surviving_attackers, 0)
        self.assertLess(territory.soldiers.total_hp, 6 * cfg.SOLDIER_HP)
        self.assertTrue(territory.queen.is_alive)

    def test_damage_to_queen_persists_between_assaults(self) -> None:
        territory = make_territory(soldiers=0, workers=0)
        attacker = HumanPlayer(1, "Attacker", (0, 0, 255))

        first = CombatResolver.resolve_instant(1, territory, attacker)

        self.assertFalse(first.attacker_won)
        self.assertLess(territory.queen.front_hp, cfg.QUEEN_HP)
        hp_after_first = territory.queen.front_hp

        second = CombatResolver.resolve_instant(5, territory, attacker)

        self.assertTrue(second.attacker_won)
        self.assertLess(territory.queen.front_hp, hp_after_first)
        CombatResolver.apply_result(second, territory, attacker)
        self.assertIs(territory.owner, attacker)
        self.assertEqual(territory.soldiers.count, second.surviving_attackers)
        self.assertEqual(
            territory.soldiers.total_hp,
            sum(state.hp for state in second.surviving_states),
        )

    def test_realtime_arena_matches_instant_resolution(self) -> None:
        instant_target = make_territory(soldiers=6, workers=1)
        realtime_target = make_territory(soldiers=6, workers=1)
        attacker = HumanPlayer(1, "Attacker", (0, 0, 255))
        incoming = states(1, 6)

        instant = CombatResolver.resolve_instant(incoming, instant_target, attacker)
        arena = BattleArena(BattleArenaType.TERRITORY, realtime_target)
        arena.add_army(attacker, attacker.color, incoming)
        defenders = realtime_target.detach_soldiers(realtime_target.soldiers.count)
        defenders = [
            SoldierState(7 + index, state.hp, realtime_target.id)
            for index, state in enumerate(defenders)
        ]
        arena.add_army(
            realtime_target.owner,
            realtime_target.owner.color,
            defenders,
            defending=True,
        )
        realtime = run_arena(arena)

        self.assertIsNotNone(realtime)
        if not realtime.captured:
            realtime_target.receive_soldiers(realtime.survivors_for(realtime_target.owner))
        self.assertEqual(realtime.captured, instant.attacker_won)
        self.assertEqual(
            len(realtime.survivors_for(attacker)),
            instant.surviving_attackers,
        )
        self.assertAlmostEqual(
            realtime_target.soldiers.total_hp,
            instant_target.soldiers.total_hp,
        )
        self.assertAlmostEqual(
            realtime_target.queen.front_hp,
            instant_target.queen.front_hp,
        )

    def test_fortress_defenders_match_instant_and_realtime_resolution(self) -> None:
        instant_target = make_territory(soldiers=1, workers=1)
        realtime_target = make_territory(soldiers=1, workers=1)
        for territory in (instant_target, realtime_target):
            territory.add_food(100)
            self.assertTrue(territory.develop(TerritorySpecialization.FORTRESS).success)
        attacker = HumanPlayer(1, "Attacker", (0, 0, 255))

        instant = CombatResolver.resolve_instant(states(1, 5), instant_target, attacker)

        arena = BattleArena(BattleArenaType.TERRITORY, realtime_target)
        arena.add_army(attacker, attacker.color, states(1, 5))
        defending_soldiers = [
            SoldierState(6 + index, state.hp, realtime_target.id)
            for index, state in enumerate(
                realtime_target.detach_soldiers(realtime_target.soldiers.count)
            )
        ]
        arena.add_army(
            realtime_target.owner,
            realtime_target.owner.color,
            defending_soldiers,
            defending=True,
        )
        defending_guards = [
            DefenderState(7 + index, state.hp, realtime_target.id)
            for index, state in enumerate(realtime_target.detach_defenders())
        ]
        arena.add_defenders(
            realtime_target.owner,
            realtime_target.owner.color,
            defending_guards,
        )
        realtime = run_arena(arena)

        self.assertIsNotNone(realtime)
        if not realtime.captured:
            realtime_target.receive_soldiers(
                realtime.survivors_for(realtime_target.owner)
            )
            realtime_target.finish_defense(
                realtime.defender_survivors_for(realtime_target.owner),
                len(defending_guards),
            )
        self.assertEqual(realtime.captured, instant.attacker_won)
        self.assertEqual(
            realtime_target.soldiers.count,
            instant_target.soldiers.count,
        )
        self.assertAlmostEqual(
            realtime_target.soldiers.total_hp,
            instant_target.soldiers.total_hp,
        )
        self.assertEqual(
            realtime_target.defenders.count,
            instant_target.defenders.count,
        )
        self.assertAlmostEqual(
            realtime_target.defenders.total_hp,
            instant_target.defenders.total_hp,
        )
        self.assertEqual(
            realtime_target.defender_respawn_count,
            instant_target.defender_respawn_count,
        )
        self.assertAlmostEqual(
            realtime_target.queen.front_hp,
            instant_target.queen.front_hp,
        )

    def test_simultaneous_impacts_allow_a_true_double_knockout(self) -> None:
        objective = WorldObjective(1, WorldObjectiveType.CARAVAN, (100.0, 100.0))
        objective.soldiers.remove(objective.soldiers.count)
        first = HumanPlayer(0, "First", (220, 70, 60))
        second = HumanPlayer(1, "Second", (60, 120, 220))
        arena = BattleArena(BattleArenaType.OBJECTIVE, objective)
        arena.add_army(first, first.color, states(1, 1, hp=4), entry_positions=[(94.0, 100.0)])
        arena.add_army(second, second.color, states(2, 1, hp=4), entry_positions=[(106.0, 100.0)])

        arena.update(0.5)

        self.assertEqual(len(arena.living_agents), 0)
        self.assertEqual(len(arena.visible_agents), 2)

    def test_targeting_uses_nearest_enemy_and_caps_six_attackers(self) -> None:
        objective = WorldObjective(2, WorldObjectiveType.WAR_BANNER, (100.0, 100.0))
        objective.soldiers.remove(objective.soldiers.count)
        first = HumanPlayer(0, "First", (220, 70, 60))
        second = HumanPlayer(1, "Second", (60, 120, 220))
        arena = BattleArena(BattleArenaType.OBJECTIVE, objective)
        attacker_states = states(1, 12)
        arena.add_army(
            first,
            first.color,
            attacker_states,
            entry_positions=[(80.0 + index * 0.1, 100.0) for index in range(12)],
        )
        arena.add_army(
            second,
            second.color,
            states(100, 2),
            entry_positions=[(102.0, 100.0), (150.0, 100.0)],
        )

        arena.update(SIMULATION_STEP)

        first_agent = next(agent for agent in arena.agents if agent.unit_id == 1)
        self.assertEqual(first_agent.target_id, 100)
        targeting_near = [
            agent for agent in arena.agents
            if agent.owner is first and agent.target_id == 100
        ]
        self.assertEqual(len(targeting_near), MAX_MELEE_SLOTS)

    def test_two_to_four_faction_ffa_keeps_one_shared_arena(self) -> None:
        for faction_count in (2, 3, 4):
            with self.subTest(faction_count=faction_count):
                objective = WorldObjective(10 + faction_count, WorldObjectiveType.CARAVAN, (100.0, 100.0))
                objective.soldiers.remove(objective.soldiers.count)
                arena = BattleArena(BattleArenaType.OBJECTIVE, objective)
                players = [
                    HumanPlayer(index, f"P{index}", (60 + index * 40, 90, 210 - index * 30))
                    for index in range(faction_count)
                ]
                next_id = 1
                for index, player in enumerate(players):
                    amount = 14 if index == 0 else 2
                    arena.add_army(player, player.color, states(next_id, amount, index))
                    next_id += amount

                self.assertEqual(len(arena.player_factions), faction_count)
                result = run_arena(arena)
                self.assertIsNotNone(result)
                self.assertTrue(result.captured)
                self.assertIs(result.winner, players[0])

    def test_same_faction_reinforcement_joins_without_new_faction(self) -> None:
        objective = WorldObjective(30, WorldObjectiveType.ANCIENT_SHRINE, (100.0, 100.0))
        objective.soldiers.remove(objective.soldiers.count)
        player = HumanPlayer(0, "Player", (220, 70, 60))
        rival = HumanPlayer(1, "Rival", (60, 120, 220))
        arena = BattleArena(BattleArenaType.OBJECTIVE, objective)
        arena.add_army(player, player.color, states(1, 3, 4))
        arena.add_army(rival, rival.color, states(10, 2, 5))
        arena.add_army(player, player.color, states(20, 4, 6))

        self.assertEqual(len(arena.player_factions), 2)
        self.assertEqual(arena.commitment_count(player), 7)
        self.assertEqual(
            {agent.source_id for agent in arena.living_agents if agent.owner is player},
            {4, 6},
        )

    def test_ffa_result_does_not_depend_on_faction_registration_order(self) -> None:
        players = [
            HumanPlayer(index, f"P{index}", (70 + index * 55, 90, 210 - index * 35))
            for index in range(3)
        ]
        deployments = (
            (states(1, 7, 0), [(68.0 + index * 2.0, 96.0 + index * 7.0) for index in range(7)]),
            (states(20, 4, 1), [(132.0 - index * 2.0, 96.0 + index * 8.0) for index in range(4)]),
            (states(40, 3, 2), [(94.0 + index * 7.0, 62.0) for index in range(3)]),
        )

        def resolve(order: tuple[int, ...]):
            objective = WorldObjective(44, WorldObjectiveType.CARAVAN, (100.0, 100.0))
            objective.soldiers.remove(objective.soldiers.count)
            arena = BattleArena(BattleArenaType.OBJECTIVE, objective)
            for index in order:
                units, positions = deployments[index]
                arena.add_army(
                    players[index],
                    players[index].color,
                    units,
                    entry_positions=positions,
                )
            outcome = run_arena(arena)
            return (
                outcome.winner,
                outcome.captured,
                tuple(
                    (survivor.owner, survivor.state.unit_id, round(survivor.state.hp, 5))
                    for survivor in outcome.survivors
                ),
            )

        self.assertEqual(resolve((0, 1, 2)), resolve((2, 1, 0)))

    def test_arena_never_replaces_or_drops_individual_soldier_agents(self) -> None:
        objective = WorldObjective(45, WorldObjectiveType.WAR_BANNER, (100.0, 100.0))
        objective.soldiers.remove(objective.soldiers.count)
        first = HumanPlayer(0, "First", (220, 70, 60))
        second = HumanPlayer(1, "Second", (60, 120, 220))
        arena = BattleArena(BattleArenaType.OBJECTIVE, objective)
        arena.add_army(first, first.color, states(1, 8, 3))
        arena.add_army(second, second.color, states(20, 8, 4))
        dispatched_ids = {agent.unit_id for agent in arena.agents}

        for _ in range(900):
            arena.update(SIMULATION_STEP)
            self.assertEqual({agent.unit_id for agent in arena.agents}, dispatched_ids)
            if arena.finished:
                break

        self.assertTrue(arena.finished)

    def test_apply_result_is_noop_after_failed_assault(self) -> None:
        territory = make_territory(soldiers=6, workers=1)
        attacker = HumanPlayer(1, "Attacker", (0, 0, 255))

        result = CombatResolver.resolve_instant(4, territory, attacker)
        CombatResolver.apply_result(result, territory, attacker)

        self.assertFalse(result.attacker_won)
        self.assertIsNot(territory.owner, attacker)


if __name__ == "__main__":
    unittest.main()
