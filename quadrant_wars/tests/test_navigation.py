from __future__ import annotations

import unittest

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.battlefield import point_to_segment_distance
from quadrant_wars.core.navigation import BattlefieldNavigator
from quadrant_wars.core.territory import TerritorySpecialization
from quadrant_wars.core.unit import SoldierState
from quadrant_wars.game.game_manager import ArmyTargetType, MovingArmy


class _TerritoryStub:
    def __init__(self, territory_id: int, position: tuple[float, float]) -> None:
        self.id = territory_id
        self.battle_position = position
        self.specialization = TerritorySpecialization.NONE


class _PlayerStub:
    march_speed_multiplier = 1.0


class NavigationTest(unittest.TestCase):
    def test_astar_routes_around_an_intervening_castle(self) -> None:
        start = (100.0, cfg.WINDOW_HEIGHT / 2)
        blocker = (cfg.WINDOW_WIDTH / 2, cfg.WINDOW_HEIGHT / 2)
        end = (cfg.WINDOW_WIDTH - 100.0, cfg.WINDOW_HEIGHT / 2)
        territories = [
            _TerritoryStub(0, start),
            _TerritoryStub(1, blocker),
            _TerritoryStub(2, end),
        ]
        navigator = BattlefieldNavigator(cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT)

        path = navigator.find_path(
            start,
            end,
            territories,
            source_id=0,
            target_territory_id=2,
        )

        self.assertGreater(len(path), 2)
        self.assertEqual(path[0], start)
        self.assertEqual(path[-1], end)
        self.assertTrue(
            all(
                point_to_segment_distance(blocker, first, second) >= 104.0
                for first, second in zip(path, path[1:])
            )
        )

    def test_moving_army_uses_polyline_distance(self) -> None:
        army = MovingArmy(
            attacker=_PlayerStub(),
            source_id=0,
            target_type=ArmyTargetType.TERRITORY,
            target_id=1,
            units=[SoldierState(index + 1, cfg.SOLDIER_HP, 0) for index in range(4)],
            start=(0.0, 0.0),
            end=(100.0, 100.0),
            path=((0.0, 0.0), (0.0, 100.0), (100.0, 100.0)),
            duration=2.0,
        )

        army.advance(1.0)

        self.assertEqual(army.path_length, 200.0)
        self.assertAlmostEqual(army.position[0], 0.0)
        self.assertAlmostEqual(army.position[1], 100.0)


if __name__ == "__main__":
    unittest.main()
