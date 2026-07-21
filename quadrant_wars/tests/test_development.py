
import unittest

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.battle_arena import BattleArena, BattleArenaType
from quadrant_wars.core.player import HumanPlayer
from quadrant_wars.core.territory import Territory, TerritorySpecialization
from quadrant_wars.core.unit import DefenderState, SoldierState
from quadrant_wars.game.game_manager import Match


def make_territory():
    owner = HumanPlayer(0, "Builder", (214, 84, 76))
    territory = Territory(0, owner, [(0, 0), (120, 0), (120, 120), (0, 120)])
    territory.add_food(200)
    return territory


class TerritoryDevelopmentTest(unittest.TestCase):
    def test_economy_only_multiplies_worker_income_and_discounts_workers(self):
        territory = make_territory()
        normal_worker_cost = territory.worker_cost()

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
        self.assertAlmostEqual(territory.base_income_per_second, 0.30)
        self.assertEqual(
            territory.worker_cost(),
            round(normal_worker_cost * (1.0 - cfg.ECONOMY_WORKER_DISCOUNT_PER_LEVEL * 2)),
        )

        before = territory.food
        territory.update(1.0)
        self.assertAlmostEqual(
            territory.food - before,
            cfg.BASE_TERRITORY_INCOME_PER_SECOND
            + cfg.FOOD_PER_WORKER_PER_SECOND
            * territory.workers.count
            * territory.worker_income_multiplier,
        )

        while territory.workers.count < cfg.MAX_WORKERS_PER_TERRITORY:
            territory.workers.add(1)
        self.assertAlmostEqual(territory.income_per_second, 2.90)

    def test_territory_generates_base_income_without_workers(self):
        territory = make_territory()
        territory.workers.remove(territory.workers.count)
        before = territory.food

        territory.update(10.0)

        self.assertAlmostEqual(
            territory.food - before,
            cfg.BASE_TERRITORY_INCOME_PER_SECOND * 10.0,
        )
        self.assertEqual(
            territory.income_per_second,
            cfg.BASE_TERRITORY_INCOME_PER_SECOND,
        )

    def test_each_worker_adds_income_and_worker_costs_scale(self):
        territory = make_territory()
        expected_costs = []
        actual_costs = []

        for worker_count in range(1, cfg.MAX_WORKERS_PER_TERRITORY):
            actual_costs.append(territory.worker_cost())
            expected_costs.append(
                round(cfg.WORKER_BASE_COST * cfg.WORKER_COST_GROWTH ** worker_count)
            )
            territory.workers.add(1)

        self.assertEqual(actual_costs, expected_costs)
        self.assertAlmostEqual(
            territory.income_per_second,
            cfg.BASE_TERRITORY_INCOME_PER_SECOND
            + cfg.MAX_WORKERS_PER_TERRITORY * cfg.FOOD_PER_WORKER_PER_SECOND,
        )
        self.assertAlmostEqual(
            territory.snapshot().income_per_second,
            territory.income_per_second,
        )

        territory.workers.remove(territory.workers.count)
        self.assertEqual(territory.worker_cost(), cfg.WORKER_BASE_COST)
        self.assertGreaterEqual(territory.food, territory.worker_cost())
        self.assertTrue(territory.buy_worker())

    def test_barracks_discount_and_spawn_delay(self):
        territory = make_territory()
        territory.develop(TerritorySpecialization.BARRACKS)

        self.assertEqual(
            territory.soldier_cost,
            cfg.SOLDIER_COST - cfg.BARRACKS_SOLDIER_DISCOUNT_PER_LEVEL,
        )
        self.assertLess(territory.soldier_spawn_delay, cfg.SPAWN_DELAY)
        self.assertTrue(territory.buy_soldier())
        territory.update(territory.soldier_spawn_delay - 0.01)
        self.assertEqual(territory.soldiers.count, cfg.STARTING_SOLDIERS)
        territory.update(0.02)
        self.assertEqual(territory.soldiers.count, cfg.STARTING_SOLDIERS + 1)

        territory.develop(TerritorySpecialization.BARRACKS)
        self.assertEqual(territory.soldier_cost, 10)
        self.assertAlmostEqual(territory.soldier_spawn_delay, 0.78)

    def test_fortress_adds_defenders_and_small_damage_reduction(self):
        territory = make_territory()
        territory.develop(TerritorySpecialization.FORTRESS)
        self.assertEqual(territory.defenders.count, 2)
        self.assertEqual(territory.defender_capacity, 2)
        territory.develop(TerritorySpecialization.FORTRESS)

        self.assertEqual(territory.defenders.count, 4)
        self.assertEqual(territory.defender_capacity, 4)
        self.assertEqual(
            territory.damage_taken_multiplier,
            1.0 - cfg.FORTRESS_DAMAGE_REDUCTION_PER_LEVEL * 2,
        )
        self.assertGreater(territory.defense_value, territory.soldiers.total_hp + territory.workers.total_hp)

    def test_defender_casualties_heal_and_respawn_only_outside_combat(self):
        territory = make_territory()
        territory.develop(TerritorySpecialization.FORTRESS)
        territory.develop(TerritorySpecialization.FORTRESS)
        deployed = territory.detach_defenders()

        territory.finish_defense(
            [DefenderState(1, 9.0, territory.id)],
            deployed_count=len(deployed),
        )

        self.assertEqual(territory.defenders.count, 1)
        self.assertEqual(territory.defender_respawn_count, 3)
        territory.update(50.0, in_combat=True)
        self.assertEqual(territory.defenders.front_hp, 9.0)
        self.assertAlmostEqual(territory.next_defender_respawn, 45.0)

        territory.update(44.0)
        self.assertEqual(territory.defenders.count, 1)
        self.assertEqual(territory.defenders.front_hp, cfg.DEFENDER_HP)
        territory.update(1.0)
        self.assertEqual(territory.defenders.count, 4)
        self.assertEqual(territory.defender_respawn_count, 0)

    def test_conversion_uses_local_gold_and_resets_to_level_one(self):
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

    def test_conversion_away_from_fortress_clears_garrison_and_timers(self):
        territory = make_territory()
        territory.develop(TerritorySpecialization.FORTRESS)
        deployed = territory.detach_defenders()
        territory.finish_defense([], len(deployed))

        result = territory.develop(TerritorySpecialization.ECONOMY)

        self.assertTrue(result.success)
        self.assertEqual(territory.defenders.count, 0)
        self.assertEqual(territory.defender_capacity, 0)
        self.assertEqual(territory.defender_respawn_count, 0)

    def test_capture_reduces_level_but_retains_branch(self):
        territory = make_territory()
        territory.develop(TerritorySpecialization.FORTRESS)
        territory.develop(TerritorySpecialization.FORTRESS)
        conqueror = HumanPlayer(1, "Conqueror", (70, 137, 214))

        territory.reset_after_capture(conqueror, 3)
        self.assertEqual(territory.specialization, TerritorySpecialization.FORTRESS)
        self.assertEqual(territory.specialization_level, 1)
        self.assertEqual(territory.defenders.count, 0)
        self.assertEqual(territory.defender_respawn_count, 2)
        territory.reset_after_capture(make_territory().owner, 2)
        self.assertEqual(territory.specialization, TerritorySpecialization.FORTRESS)
        self.assertEqual(territory.specialization_level, 0)
        self.assertEqual(territory.defender_respawn_count, 0)

    def test_match_blocks_development_during_active_territory_battle(self):
        match = Match(["human", "human"], seed=17, headless=True)
        territory = match.territories[0]
        player = match.players[0]
        territory.add_food(100)
        arena = BattleArena(BattleArenaType.TERRITORY, territory)
        match._battles[(BattleArenaType.TERRITORY, territory.id)] = arena
        arena.add_army(
            match.players[1],
            match.players[1].color,
            [SoldierState(1, cfg.SOLDIER_HP, 1)],
        )
        before = territory.food

        result = match.develop_territory(
            player,
            territory.id,
            TerritorySpecialization.ECONOMY,
        )

        self.assertFalse(result.success)
        self.assertEqual(territory.food, before)

    def test_insufficient_local_gold_does_not_mutate_territory(self):
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
