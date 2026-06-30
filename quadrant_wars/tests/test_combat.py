from __future__ import annotations

import unittest

from quadrant_wars.core.combat import CombatResolver
from quadrant_wars.core.player import HumanPlayer
from quadrant_wars.core.territory import Territory


def make_territory(soldiers: int, workers: int = 1) -> Territory:
    owner = HumanPlayer(0, "Defender", (255, 0, 0))
    territory = Territory(0, owner, [(0, 0), (100, 0), (100, 100), (0, 100)])
    territory.soldiers.remove(territory.soldiers.count)
    territory.soldiers.add(soldiers)
    territory.workers.remove(territory.workers.count)
    territory.workers.add(workers)
    return territory


class CombatResolverTest(unittest.TestCase):
    def test_example_10_attackers_fails_after_damaging_queen_layer(self) -> None:
        territory = make_territory(soldiers=6, workers=1)
        result = CombatResolver.resolve(10, territory)
        self.assertFalse(result.attacker_won)
        self.assertEqual(result.killed_defending_soldiers, 6)
        self.assertEqual(result.killed_workers, 1)
        self.assertFalse(result.queen_killed)
        self.assertEqual(result.surviving_attackers, 0)

    def test_14_attackers_win_exactly_against_6_soldiers_worker_queen(self) -> None:
        territory = make_territory(soldiers=6, workers=1)
        result = CombatResolver.resolve(14, territory)
        self.assertTrue(result.attacker_won)
        self.assertEqual(result.killed_defending_soldiers, 6)
        self.assertEqual(result.killed_workers, 1)
        self.assertTrue(result.queen_killed)
        self.assertEqual(result.surviving_attackers, 2)

    def test_soldiers_trade_one_to_one(self) -> None:
        territory = make_territory(soldiers=8, workers=0)
        result = CombatResolver.resolve(5, territory)
        self.assertFalse(result.attacker_won)
        self.assertEqual(result.killed_defending_soldiers, 5)
        self.assertEqual(result.surviving_attackers, 0)


if __name__ == "__main__":
    unittest.main()

