from __future__ import annotations

import unittest

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.objective import WorldObjective, WorldObjectiveState, WorldObjectiveType
from quadrant_wars.game.game_manager import ArmyTargetType, Match


class WorldObjectiveTest(unittest.TestCase):
    def _active_match(self, objective_type: WorldObjectiveType) -> tuple[Match, WorldObjective]:
        match = Match(["human", "human"], seed=19, headless=True)
        objective = WorldObjective(77, objective_type, (640.0, 360.0))
        objective.activate()
        match._world_objective = objective
        return match, objective

    def test_objective_is_telegraphed_then_activates(self) -> None:
        match = Match(["human", "human"], seed=9, headless=True)

        match.update(cfg.OBJECTIVE_FIRST_ACTIVE_AT - cfg.OBJECTIVE_TELEGRAPH_DURATION)
        first = match.world_objective
        self.assertIsNotNone(first)
        self.assertEqual(first.state, WorldObjectiveState.TELEGRAPHING)

        match.update(cfg.OBJECTIVE_TELEGRAPH_DURATION)
        self.assertTrue(first.active)
        self.assertEqual(first.state, WorldObjectiveState.ACTIVE)

    def test_caravan_reward_and_survivors_return_home(self) -> None:
        match, objective = self._active_match(WorldObjectiveType.CARAVAN)
        source = match.territories[0]
        source.add_soldiers(6)
        before_gold = source.food

        self.assertTrue(match.issue_objective_attack(source, 6))
        match.update(8.0)

        self.assertEqual(objective.state, WorldObjectiveState.RESOLVED)
        self.assertGreaterEqual(source.food, before_gold + cfg.OBJECTIVE_CARAVAN_GOLD)
        self.assertTrue(any(army.target_type is ArmyTargetType.RETURN for army in match.armies))

    def test_war_banner_applies_temporary_combat_and_march_buff(self) -> None:
        match, _ = self._active_match(WorldObjectiveType.WAR_BANNER)
        source = match.territories[0]
        source.add_soldiers(6)

        match.issue_objective_attack(source, 6)
        match.update(8.0)

        player = match.players[0]
        self.assertGreater(player.war_banner_time, 0.0)
        self.assertEqual(player.attack_multiplier, cfg.WAR_BANNER_ATTACK_MULTIPLIER)
        self.assertEqual(player.march_speed_multiplier, cfg.WAR_BANNER_MARCH_MULTIPLIER)

    def test_shrine_heals_living_queens_without_overhealing(self) -> None:
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

    def test_expired_objective_returns_inbound_armies_and_schedules_next_cycle(self) -> None:
        match, objective = self._active_match(WorldObjectiveType.CARAVAN)
        source = match.territories[0]
        source.add_soldiers(4)
        match.issue_objective_attack(source, 4)

        match.update(cfg.OBJECTIVE_ACTIVE_DURATION + 0.1)

        self.assertEqual(objective.state, WorldObjectiveState.EXPIRED)
        self.assertTrue(
            any(army.target_type is ArmyTargetType.RETURN for army in match.armies)
            or source.soldiers.count >= 4
        )
        self.assertAlmostEqual(match.objective_countdown, cfg.OBJECTIVE_RESPAWN_DELAY, delta=0.2)


if __name__ == "__main__":
    unittest.main()
