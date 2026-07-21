
import math
import unittest

from quadrant_wars.core.objective import WorldObjective, WorldObjectiveType
from quadrant_wars.core.player import (
    AggressiveStrategy,
    BalancedStrategy,
    EconomicStrategy,
)
from quadrant_wars.core.territory import TerritorySpecialization
from quadrant_wars.game.game_manager import Match
from quadrant_wars.simulation.balance_sim import run_match


class BalanceSimulationTest(unittest.TestCase):
    def test_headless_simulation_uses_the_real_strategy_distribution(self):
        two_player = run_match(2, seed=91, max_seconds=0.0)
        three_player = run_match(3, seed=92, max_seconds=0.0)
        four_player = run_match(4, seed=93, max_seconds=0.0)

        self.assertEqual(len(set(two_player["strategies"])), 2)
        self.assertEqual(len(set(three_player["strategies"])), 3)
        self.assertEqual(len(set(four_player["strategies"])), 3)

    def test_bot_strategies_enforce_their_defense_reserve(self):
        expected = (
            (AggressiveStrategy(), 2),
            (BalancedStrategy(), 2),
            (EconomicStrategy(), 3),
        )

        for strategy, reserve in expected:
            self.assertEqual(strategy.defense_reserve(10), reserve)

    def test_balanced_bot_waits_for_enough_objective_troops_after_reserve(self):
        match = Match(
            ["bot", "human"],
            seed=31,
            bot_strategy_classes=[BalancedStrategy],
            headless=True,
        )
        bot = match.players[0]
        source = match.territories[0]
        source.soldiers.remove(source.soldiers.count)
        source.soldiers.add(6)
        objective = WorldObjective(9, WorldObjectiveType.CARAVAN, (640.0, 360.0))
        objective.activate()
        match._world_objective = objective

        self.assertFalse(bot._try_objective_attack(match, [source]))
        self.assertEqual(source.soldiers.count, 6)

        source.soldiers.add(1)
        self.assertTrue(bot._try_objective_attack(match, [source]))
        self.assertEqual(source.soldiers.count, 2)

    def test_strategy_upgrade_saving_matches_each_role(self):
        self.assertEqual(AggressiveStrategy.upgrade_force, 10)
        self.assertEqual(BalancedStrategy.upgrade_force, 8)
        self.assertEqual(EconomicStrategy.upgrade_force, 12)
        self.assertLessEqual(AggressiveStrategy.max_workers, BalancedStrategy.max_workers)
        self.assertLess(BalancedStrategy.max_workers, EconomicStrategy.max_workers)

    def test_aggressive_probe_only_raids_an_exposed_economy(self):
        match = Match(
            ["bot", "human"],
            seed=47,
            bot_strategy_classes=[AggressiveStrategy],
            headless=True,
        )
        source, target = match.territories
        source.soldiers.add(3)
        target.soldiers.add(1)

        self.assertEqual(match.players[0].strategy.probe_amount(source, target), 3)

        target.soldiers.add(1)
        self.assertEqual(match.players[0].strategy.probe_amount(source, target), 0)

    def test_recent_attack_memory_blocks_only_third_party_cleanup(self):
        match = Match(["bot", "human", "human"], seed=48, headless=True)
        attacker = match.players[0]
        source, target = match.territories[:2]

        self.assertTrue(match.issue_attack(source, target, 1))
        self.assertEqual(match.recent_territory_attackers(target.id), {attacker.id})

        match._elapsed += 21.0
        self.assertEqual(match.recent_territory_attackers(target.id), set())

    def test_economic_bot_prioritizes_worker_roi(self):
        match = Match(
            ["bot", "human"],
            seed=46,
            bot_strategy_classes=[EconomicStrategy],
            headless=True,
        )
        territory = match.territories[0]
        strategy = match.players[0].strategy

        self.assertTrue(strategy.should_buy_worker(territory))

        territory.workers.add(strategy.max_workers - territory.workers.count)
        self.assertFalse(strategy.should_buy_worker(territory))

    def test_balanced_strategy_fortifies_only_the_frontline_region(self):
        match = Match(
            ["bot", "human", "human", "human"],
            seed=44,
            bot_strategy_classes=[BalancedStrategy],
            headless=True,
        )
        bot = match.players[0]
        capital, first_region, second_region, enemy_region = match.territories
        first_region._owner = bot
        second_region._owner = bot
        first_region.is_capital = False
        second_region.is_capital = False

        strategy = bot.strategy
        candidates = (first_region, second_region)
        frontline = min(
            candidates,
            key=lambda region: math.dist(region.centroid, enemy_region.centroid),
        )
        rear_region = next(region for region in candidates if region is not frontline)

        self.assertEqual(
            strategy.choose_specialization(match, bot, capital),
            TerritorySpecialization.BARRACKS,
        )
        self.assertEqual(
            strategy.choose_specialization(match, bot, frontline),
            TerritorySpecialization.FORTRESS,
        )
        self.assertEqual(
            strategy.choose_specialization(match, bot, rear_region),
            TerritorySpecialization.ECONOMY,
        )

    def test_balanced_bot_treats_its_only_region_as_frontline(self):
        match = Match(
            ["bot", "human"],
            seed=45,
            bot_strategy_classes=[BalancedStrategy],
            headless=True,
        )
        bot = match.players[0]

        self.assertEqual(
            bot.strategy.choose_specialization(match, bot, match.territories[0]),
            TerritorySpecialization.FORTRESS,
        )

    def test_seed_reproduces_bot_decisions_and_match_state(self):
        first = Match(["bot"] * 4, seed=20260715, headless=True)
        second = Match(["bot"] * 4, seed=20260715, headless=True)

        for _ in range(720):
            first.update(0.25)
            second.update(0.25)

        first_state = [
            (territory.owner.name, territory.snapshot())
            for territory in first.territories
        ]
        second_state = [
            (territory.owner.name, territory.snapshot())
            for territory in second.territories
        ]
        self.assertEqual(first_state, second_state)
        self.assertEqual(first.event_log, second.event_log)


if __name__ == "__main__":
    unittest.main()
