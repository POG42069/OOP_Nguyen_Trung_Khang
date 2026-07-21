
import math
import unittest

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.battlefield import point_to_segment_distance
from quadrant_wars.core.navigation import BattlefieldNavigator
from quadrant_wars.core.terrain import (
    BorderGate,
    BorderWall,
    TerrainMap,
    TerrainObstacle,
)
from quadrant_wars.core.territory import TerritorySpecialization
from quadrant_wars.core.unit import SoldierState
from quadrant_wars.game.game_manager import ArmyTargetType, MovingArmy


class _TerritoryStub:
    def __init__(self, territory_id, position):
        self.id = territory_id
        self.battle_position = position
        self.specialization = TerritorySpecialization.NONE


class _PlayerStub:
    march_speed_multiplier = 1.0


class NavigationTest(unittest.TestCase):
    def test_astar_routes_around_an_intervening_castle(self):
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

    def test_moving_army_uses_polyline_distance(self):
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

    def test_route_never_simplifies_through_a_mountain(self):
        terrain = TerrainMap(800, 500, [TerrainObstacle((400.0, 250.0), 85.0)])
        terrain.rivers = []
        navigator = BattlefieldNavigator(800, 500, cell_size=25, terrain=terrain)
        start = (100.0, 250.0)
        end = (700.0, 250.0)

        path = navigator.find_path(
            start,
            end,
            [],
            source_id=0,
            target_territory_id=None,
        )

        self.assertGreater(len(path), 2)
        self.assertTrue(all(
            point_to_segment_distance((400.0, 250.0), first, second) >= 96.0
            for first, second in zip(path, path[1:])
        ))

    def test_route_goes_around_an_impassable_river(self):
        terrain = TerrainMap(800, 500)
        terrain.rivers = [[(400.0, 0.0), (400.0, 320.0)]]
        navigator = BattlefieldNavigator(800, 500, cell_size=25, terrain=terrain)
        path = navigator.find_path(
            (100.0, 180.0),
            (700.0, 180.0),
            [],
            source_id=0,
            target_territory_id=None,
        )

        self.assertGreater(len(path), 2)
        self.assertTrue(all(
            terrain.segment_is_clear(first, second, clearance=12.0)
            for first, second in zip(path, path[1:])
        ))
    def test_shortest_route_crosses_a_border_at_its_gate(self):
        gate = BorderGate((400.0, 105.0), (0, 1))
        wall = BorderWall((400.0, 20.0), (400.0, 480.0), (0, 1), gate)
        terrain = TerrainMap(800, 500, walls=[wall], gates=[gate])
        terrain.rivers = []
        navigator = BattlefieldNavigator(800, 500, cell_size=20, terrain=terrain)

        path = navigator.find_path(
            (100.0, 250.0),
            (700.0, 250.0),
            [],
            source_id=0,
            target_territory_id=1,
        )

        crossings = []
        for start, end in zip(path, path[1:]):
            if (start[0] - 400.0) * (end[0] - 400.0) > 0:
                continue
            if start[0] == end[0]:
                continue
            ratio = (400.0 - start[0]) / (end[0] - start[0])
            if 0.0 <= ratio <= 1.0:
                crossings.append(start[1] + (end[1] - start[1]) * ratio)

        self.assertTrue(crossings)
        self.assertTrue(all(abs(y - gate.center[1]) < 30.0 for y in crossings))
        self.assertTrue(all(
            terrain.segment_is_clear(first, second, clearance=12.0)
            for first, second in zip(path, path[1:])
        ))
        actual_length = sum(math.dist(first, second) for first, second in zip(path, path[1:]))
        shortest_through_gate = (
            math.dist((100.0, 250.0), gate.center)
            + math.dist(gate.center, (700.0, 250.0))
        )
        self.assertLessEqual(actual_length, shortest_through_gate + 45.0)


if __name__ == "__main__":
    unittest.main()
