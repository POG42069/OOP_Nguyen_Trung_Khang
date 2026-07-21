
import unittest

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.objective import WorldObjective, WorldObjectiveState, WorldObjectiveType
from quadrant_wars.core.battle_arena import BattleArenaType, BattlePhase
from quadrant_wars.game.game_manager import ArmyTargetType, Match


class WorldObjectiveTest(unittest.TestCase):
    def _active_match(self, objective_type):
        match = Match(["human", "human"], seed=19, headless=True)
        objective = WorldObjective(77, objective_type, (640.0, 360.0))
        objective.activate()
        match._world_objective = objective
        return match, objective

    def test_objective_is_telegraphed_then_activates(self):
        match = Match(["human", "human"], seed=9, headless=True)

        match.update(cfg.OBJECTIVE_FIRST_ACTIVE_AT - cfg.OBJECTIVE_TELEGRAPH_DURATION)
        first = match.world_objective
        self.assertIsNotNone(first)
        self.assertEqual(first.state, WorldObjectiveState.TELEGRAPHING)

        match.update(cfg.OBJECTIVE_TELEGRAPH_DURATION)
        self.assertTrue(first.active)
        self.assertEqual(first.state, WorldObjectiveState.ACTIVE)

    def test_caravan_reward_and_survivors_return_home(self):
        match, objective = self._active_match(WorldObjectiveType.CARAVAN)
        source = match.territories[0]
        source.add_soldiers(6)
        before_gold = source.food

        self.assertTrue(match.issue_objective_attack(source, 6))
        match.update(8.0)

        self.assertEqual(objective.state, WorldObjectiveState.RESOLVED)
        self.assertGreaterEqual(source.food, before_gold + cfg.OBJECTIVE_CARAVAN_GOLD)
        self.assertTrue(any(army.target_type is ArmyTargetType.RETURN for army in match.armies))

    def test_war_banner_applies_temporary_combat_and_march_buff(self):
        match, _ = self._active_match(WorldObjectiveType.WAR_BANNER)
        source = match.territories[0]
        source.add_soldiers(6)

        match.issue_objective_attack(source, 6)
        match.update(8.0)

        player = match.players[0]
        self.assertGreater(player.war_banner_time, 0.0)
        self.assertEqual(player.attack_multiplier, cfg.WAR_BANNER_ATTACK_MULTIPLIER)
        self.assertEqual(player.march_speed_multiplier, cfg.WAR_BANNER_MARCH_MULTIPLIER)

    def test_shrine_heals_living_queens_without_overhealing(self):
        match, _ = self._active_match(WorldObjectiveType.ANCIENT_SHRINE)
        source = match.territories[0]
        source.queen.take_damage(50)
        source.add_soldiers(6)
        before = source.queen.front_hp

        match.issue_objective_attack(source, 6)
        match.update(8.0)

        self.assertGreaterEqual(
            source.queen.front_hp,
            min(cfg.QUEEN_HP, before + cfg.OBJECTIVE_SHRINE_HEAL),
        )
        self.assertLessEqual(source.queen.front_hp, cfg.QUEEN_HP)

    def test_active_objective_persists_until_captured(self):
        match, objective = self._active_match(WorldObjectiveType.CARAVAN)

        match.update(600.0)

        self.assertIs(match.world_objective, objective)
        self.assertEqual(objective.state, WorldObjectiveState.ACTIVE)
        self.assertTrue(objective.active)
        self.assertEqual(match.objective_countdown, 0.0)

    def test_failed_assault_leaves_damage_and_objective_available(self):
        match, objective = self._active_match(WorldObjectiveType.CARAVAN)
        source = match.territories[0]
        source.add_soldiers(1)
        guard_hp_before = objective.soldiers.total_hp

        self.assertTrue(match.issue_objective_attack(source, 1))
        match.update(8.0)

        self.assertEqual(objective.state, WorldObjectiveState.ACTIVE)
        self.assertLess(objective.soldiers.total_hp, guard_hp_before)
        self.assertEqual(match.objective_countdown, 0.0)

    def test_capture_schedules_the_next_objective_after_a_full_delay(self):
        match, objective = self._active_match(WorldObjectiveType.CARAVAN)
        source = match.territories[0]
        source.add_soldiers(6)

        self.assertTrue(match.issue_objective_attack(source, 6))
        match.update(8.0)

        self.assertEqual(objective.state, WorldObjectiveState.RESOLVED)
        self.assertAlmostEqual(match.objective_countdown, cfg.OBJECTIVE_RESPAWN_DELAY, delta=0.2)

    def test_rival_interrupts_neutral_fight_without_healing_or_hurting_guards(self):
        match, objective = self._active_match(WorldObjectiveType.CARAVAN)
        first_source, second_source = match.territories
        first_source.add_soldiers(8)
        second_source.add_soldiers(3)

        self.assertTrue(match.issue_objective_attack(first_source, 7))
        match.armies[0].elapsed = match.armies[0].duration
        match.update(0.05)
        arena = match.battles[0]
        for _ in range(40):
            match.update(0.05)

        first_hp_before = {
            agent.unit_id: agent.hp
            for agent in arena.living_agents
            if agent.owner is match.players[0]
        }
        guardian_hp_before = sum(
            agent.hp for agent in arena.living_agents if agent.neutral
        )
        self.assertLess(guardian_hp_before, cfg.OBJECTIVE_GUARDS * cfg.SOLDIER_HP)

        self.assertTrue(match.issue_objective_attack(second_source, 2))
        rival_army = next(
            army for army in match.armies if army.attacker is match.players[1]
        )
        rival_army.elapsed = rival_army.duration
        match.update(0.05)

        self.assertEqual(arena.phase, BattlePhase.PLAYER_COMBAT)
        match.update(0.8)
        self.assertEqual(
            sum(agent.hp for agent in arena.living_agents if agent.neutral),
            guardian_hp_before,
        )
        for agent in arena.living_agents:
            if agent.owner is match.players[0] and agent.unit_id in first_hp_before:
                self.assertLessEqual(agent.hp, first_hp_before[agent.unit_id])

    def test_capture_turns_every_late_objective_army_into_a_return(self):
        match, objective = self._active_match(WorldObjectiveType.WAR_BANNER)
        first_source, second_source = match.territories
        first_source.add_soldiers(10)
        second_source.add_soldiers(4)

        match.issue_objective_attack(first_source, 8)
        match.armies[0].elapsed = match.armies[0].duration
        match.update(0.05)
        match.issue_objective_attack(second_source, 3)
        late_army = next(
            army for army in match.armies if army.attacker is match.players[1]
        )
        late_ids = {state.unit_id for state in late_army.units}
        late_army.duration = 1000.0

        for _ in range(300):
            match.update(0.05)
            if objective.state is WorldObjectiveState.RESOLVED:
                break

        self.assertEqual(objective.state, WorldObjectiveState.RESOLVED)
        self.assertEqual(
            sum("claimed" in event for event in match.event_log),
            1,
        )
        self.assertFalse(
            any(
                army.target_type is ArmyTargetType.OBJECTIVE
                and army.target_id == objective.id
                for army in match.armies
            )
        )
        returned_ids = {
            state.unit_id
            for army in match.armies
            if army.target_type is ArmyTargetType.RETURN
            for state in army.units
        }
        self.assertTrue(late_ids.issubset(returned_ids))

    def test_objective_reward_is_idempotent(self):
        match, objective = self._active_match(WorldObjectiveType.CARAVAN)
        source = match.territories[0]
        source.add_soldiers(7)
        match.issue_objective_attack(source, 7)
        match.update(8.0)
        gold_after_claim = source.food

        self.assertEqual(objective.state, WorldObjectiveState.RESOLVED)
        self.assertEqual(
            sum("claimed" in event for event in match.event_log),
            1,
        )
        self.assertIn(objective.id, match._claimed_objective_ids)
        match._grant_objective_reward(match.players[0], objective)

        self.assertEqual(source.food, gold_after_claim)


if __name__ == "__main__":
    unittest.main()
