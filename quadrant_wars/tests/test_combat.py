from __future__ import annotations

import unittest

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.combat import CombatResolver, CombatZone
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
    def test_resolve_instant_uses_current_hp_model(self) -> None:
        territory = make_territory(soldiers=6, workers=1)

        result = CombatResolver.resolve_instant(4, territory)

        self.assertFalse(result.attacker_won)
        self.assertEqual(result.surviving_attackers, 0)
        self.assertLess(territory.soldiers.count, 6)
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
        self.assertTrue(territory.queen.is_alive)
        self.assertEqual(territory.soldiers.count, second.surviving_attackers)

    def test_realtime_combat_matches_instant_resolution(self) -> None:
        instant_target = make_territory(soldiers=6, workers=1)
        realtime_target = make_territory(soldiers=6, workers=1)
        attacker = HumanPlayer(1, "Attacker", (0, 0, 255))

        instant = CombatResolver.resolve_instant(6, instant_target, attacker)
        zone = CombatZone(attacker, attacker.color, realtime_target, 6)
        realtime = None
        for _ in range(100):
            realtime = zone.update(cfg.COMBAT_TICK_INTERVAL)
            if realtime is not None:
                break

        self.assertIsNotNone(realtime)
        self.assertEqual(realtime.attacker_won, instant.attacker_won)
        self.assertEqual(realtime.surviving_attackers, instant.surviving_attackers)
        self.assertEqual(realtime_target.soldiers.count, instant_target.soldiers.count)
        self.assertEqual(realtime_target.workers.count, instant_target.workers.count)
        self.assertEqual(realtime_target.queen.front_hp, instant_target.queen.front_hp)

    def test_apply_result_is_noop_after_failed_assault(self) -> None:
        territory = make_territory(soldiers=6, workers=1)
        attacker = HumanPlayer(1, "Attacker", (0, 0, 255))

        result = CombatResolver.resolve_instant(4, territory, attacker)
        CombatResolver.apply_result(result, territory, attacker)

        self.assertFalse(result.attacker_won)
        self.assertIsNot(territory.owner, attacker)


if __name__ == "__main__":
    unittest.main()
