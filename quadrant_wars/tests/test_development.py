from __future__ import annotations

import unittest

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.combat import CombatResolver
from quadrant_wars.core.player import HumanPlayer
from quadrant_wars.core.territory import Territory, TerritorySpecialization


def make_territory() -> Territory:
    owner = HumanPlayer(0, "Builder", (214, 84, 76))
    territory = Territory(0, owner, [(0, 0), (120, 0), (120, 120), (0, 120)])
    territory.add_food(200)
    return territory


class TerritoryDevelopmentTest(unittest.TestCase):
    def test_economy_build_and_upgrade_change_income_multiplier(self) -> None:
        territory = make_territory()

        first = territory.develop(TerritorySpecialization.ECONOMY)
        second = territory.develop(TerritorySpecialization.ECONOMY)

        self.assertTrue(first.success)
        self.assertTrue(second.success)
        self.assertEqual(territory.specialization, TerritorySpecialization.ECONOMY)
        self.assertEqual(territory.specialization_level, 2)
        self.assertEqual(
            territory.worker_income_multiplier,
            1.0 + cfg.ECONOMY_INCOME_BONUS_PER_LEVEL * 2,
        )

        before = territory.food
        territory.update(1.0)
        self.assertAlmostEqual(
            territory.food - before,
            cfg.FOOD_PER_WORKER_PER_SECOND * territory.worker_income_multiplier,
        )

    def test_barracks_discount_and_spawn_delay(self) -> None:
        territory = make_territory()
        territory.develop(TerritorySpecialization.BARRACKS)

        self.assertEqual(territory.soldier_cost, cfg.SOLDIER_COST - 1)
        self.assertLess(territory.soldier_spawn_delay, cfg.SPAWN_DELAY)
        self.assertTrue(territory.buy_soldier())
        territory.update(territory.soldier_spawn_delay - 0.01)
        self.assertEqual(territory.soldiers.count, cfg.STARTING_SOLDIERS)
        territory.update(0.02)
        self.assertEqual(territory.soldiers.count, cfg.STARTING_SOLDIERS + 1)

    def test_fortress_modifies_defense_and_regeneration(self) -> None:
        territory = make_territory()
        territory.develop(TerritorySpecialization.FORTRESS)
        territory.develop(TerritorySpecialization.FORTRESS)

        self.assertEqual(territory.damage_taken_multiplier, 0.8)
        self.assertEqual(territory.queen_regen_multiplier, 1.4)
        self.assertGreater(territory.defense_value, territory.soldiers.total_hp + territory.workers.total_hp)

        normal = make_territory()
        normal.soldiers.remove(normal.soldiers.count)
        normal.workers.remove(normal.workers.count)
        fortress_target = make_territory()
        fortress_target.soldiers.remove(fortress_target.soldiers.count)
        fortress_target.workers.remove(fortress_target.workers.count)
        fortress_target.develop(TerritorySpecialization.FORTRESS)
        attacker = HumanPlayer(2, "Attacker", (72, 170, 112))
        CombatResolver.resolve_instant(1, normal, attacker)
        CombatResolver.resolve_instant(1, fortress_target, attacker)
        self.assertGreater(fortress_target.queen.front_hp, normal.queen.front_hp)

    def test_conversion_uses_local_gold_and_resets_to_level_one(self) -> None:
        territory = make_territory()
        territory.develop(TerritorySpecialization.ECONOMY)
        territory.develop(TerritorySpecialization.ECONOMY)
        before = territory.food

        result = territory.develop(TerritorySpecialization.BARRACKS)

        self.assertTrue(result.success)
        self.assertEqual(result.quote.cost, cfg.DEVELOPMENT_CONVERSION_COST)
        self.assertEqual(territory.specialization, TerritorySpecialization.BARRACKS)
        self.assertEqual(territory.specialization_level, 1)
        self.assertEqual(territory.food, before - cfg.DEVELOPMENT_CONVERSION_COST)

    def test_capture_reduces_level_but_retains_branch(self) -> None:
        territory = make_territory()
        territory.develop(TerritorySpecialization.FORTRESS)
        territory.develop(TerritorySpecialization.FORTRESS)
        conqueror = HumanPlayer(1, "Conqueror", (70, 137, 214))

        territory.reset_after_capture(conqueror, 3)
        self.assertEqual(territory.specialization, TerritorySpecialization.FORTRESS)
        self.assertEqual(territory.specialization_level, 1)
        territory.reset_after_capture(make_territory().owner, 2)
        self.assertEqual(territory.specialization, TerritorySpecialization.FORTRESS)
        self.assertEqual(territory.specialization_level, 0)

    def test_insufficient_local_gold_does_not_mutate_territory(self) -> None:
        owner = HumanPlayer(0, "Poor", (214, 84, 76))
        territory = Territory(0, owner, [(0, 0), (120, 0), (120, 120), (0, 120)])
        before = territory.food

        result = territory.develop(TerritorySpecialization.ECONOMY)

        self.assertFalse(result.success)
        self.assertEqual(territory.specialization, TerritorySpecialization.NONE)
        self.assertEqual(territory.specialization_level, 0)
        self.assertEqual(territory.food, before)


if __name__ == "__main__":
    unittest.main()
