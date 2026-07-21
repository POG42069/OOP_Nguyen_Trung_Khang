
import unittest

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.battle_arena import (
    SIMULATION_STEP,
    BattleArena,
    BattleArenaType,
    BattlePhase,
)
from quadrant_wars.core.player import HumanPlayer
from quadrant_wars.core.territory import Territory
from quadrant_wars.core.unit import SoldierState
from quadrant_wars.game.game_manager import ArmyTargetType, Match


class BattleIntegrationTest(unittest.TestCase):
    def test_three_factions_share_one_territory_arena_and_survivors_keep_hp(self):
        match = Match(["human"] * 3, seed=3, headless=True)
        target, strong_source, weak_source = match.territories
        strong_source.add_soldiers(13)
        weak_source.add_soldiers(4)

        self.assertTrue(match.issue_attack(strong_source, target, 12))
        self.assertTrue(match.issue_attack(weak_source, target, 3))
        dispatched_ids = {
            state.unit_id
            for army in match.armies
            for state in army.units
        }
        for army in match.armies:
            army.elapsed = army.duration
        match.update(0.05)

        self.assertEqual(len(match.battles), 1)
        arena = match.battles[0]
        self.assertEqual(arena.arena_type, BattleArenaType.TERRITORY)
        self.assertEqual(len(arena.player_factions), 3)
        self.assertEqual(
            sum(agent.unit_id in dispatched_ids for agent in arena.agents),
            len(dispatched_ids),
        )

        for _ in range(600):
            match.update(SIMULATION_STEP)
            if not match.battles:
                break

        self.assertIs(target.owner, match.players[1])
        self.assertGreater(target.soldiers.count, 0)
        self.assertLessEqual(target.soldiers.count, 12)
        self.assertLess(target.soldiers.total_hp, target.soldiers.count * cfg.SOLDIER_HP)

    def test_worker_hp_is_a_shelter_shield_before_the_queen_core(self):
        defender = HumanPlayer(0, "Defender", (220, 70, 60))
        attacker = HumanPlayer(1, "Attacker", (60, 120, 220))
        territory = Territory(0, defender, [(0, 0), (200, 0), (200, 200), (0, 200)])
        territory.soldiers.remove(territory.soldiers.count)
        arena = BattleArena(BattleArenaType.TERRITORY, territory)
        arena.add_army(
            attacker,
            attacker.color,
            [SoldierState(1, cfg.SOLDIER_HP, 1)],
        )

        for _ in range(180):
            arena.update(SIMULATION_STEP)
            if territory.workers.total_hp < cfg.WORKER_HP:
                break

        self.assertEqual(territory.workers.total_hp, cfg.WORKER_HP - cfg.SOLDIER_ATK)
        self.assertEqual(territory.queen.front_hp, cfg.QUEEN_HP)

    def test_new_rival_pauses_core_damage_and_reopens_ffa(self):
        defender = HumanPlayer(0, "Defender", (220, 70, 60))
        attacker = HumanPlayer(1, "Attacker", (60, 120, 220))
        rival = HumanPlayer(2, "Rival", (70, 190, 110))
        territory = Territory(0, defender, [(0, 0), (200, 0), (200, 200), (0, 200)])
        territory.soldiers.remove(territory.soldiers.count)
        territory.workers.remove(territory.workers.count)
        arena = BattleArena(BattleArenaType.TERRITORY, territory)
        arena.add_army(
            attacker,
            attacker.color,
            [SoldierState(index + 1, cfg.SOLDIER_HP, 1) for index in range(6)],
        )
        for _ in range(180):
            arena.update(SIMULATION_STEP)
            if territory.queen.front_hp < cfg.QUEEN_HP:
                break
        damaged_core_hp = territory.queen.front_hp

        arena.add_army(
            rival,
            rival.color,
            [SoldierState(100 + index, cfg.SOLDIER_HP, 2) for index in range(4)],
        )
        self.assertEqual(arena.phase, BattlePhase.PLAYER_COMBAT)
        arena.update(0.5)

        self.assertEqual(arena.phase, BattlePhase.PLAYER_COMBAT)
        self.assertEqual(territory.queen.front_hp, damaged_core_hp)

    def test_return_falls_back_to_nearest_owned_region_and_preserves_hp(self):
        match = Match(["human"] * 3, seed=11, headless=True)
        player = match.players[0]
        lost_source = match.territories[0]
        fallback = match.territories[1]
        fallback.owner = player
        lost_source.owner = match.players[2]
        survivors = [
            SoldierState(50, 3.5, lost_source.id),
            SoldierState(51, 11.0, lost_source.id),
        ]

        match._return_units(player, survivors, (640.0, 360.0))

        self.assertEqual(len(match.armies), 1)
        army = match.armies[0]
        self.assertEqual(army.target_type, ArmyTargetType.RETURN)
        self.assertEqual(army.target_id, fallback.id)
        self.assertEqual([state.hp for state in army.units], [3.5, 11.0])

    def test_attack_can_be_recalled_only_before_it_reaches_battle(self):
        match = Match(["human", "human"], seed=31, headless=True)
        player = match.players[0]
        source = match.territories[0]
        target = match.territories[1]
        source.add_soldiers(8)
        before = source.soldiers.count

        self.assertTrue(match.issue_attack(source, target, 5))
        outbound = match.cancellable_armies(player)[0]
        outbound.elapsed = outbound.duration * 0.45
        self.assertTrue(match.cancel_attack(player, outbound))

        self.assertNotIn(outbound, match.armies)
        self.assertEqual(len(match.cancellable_armies(player)), 0)
        returning = match.armies[0]
        self.assertEqual(returning.target_type, ArmyTargetType.RETURN)
        returning.elapsed = returning.duration
        match.update(0.01)
        self.assertEqual(source.soldiers.count, before)

    def test_attack_cannot_be_recalled_after_entering_battle(self):
        match = Match(["human", "human"], seed=32, headless=True)
        source = match.territories[0]
        target = match.territories[1]
        source.add_soldiers(8)
        match.issue_attack(source, target, 5)
        outbound = match.armies[0]
        outbound.elapsed = outbound.duration

        match.update(0.01)

        self.assertNotIn(outbound, match.armies)
        self.assertFalse(match.cancel_attack(source.owner, outbound))


if __name__ == "__main__":
    unittest.main()
