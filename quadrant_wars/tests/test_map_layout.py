import unittest

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.map_generator import MapGenerator
from quadrant_wars.game.game_manager import Match
from quadrant_wars.ui.renderer import (
    RIVER_BUILDING_CLEARANCE,
    Renderer,
    _nearest_river_distance,
    _river_flow_paths,
)


class _RiverLayoutRenderer:
    """Minimal renderer shape used to exercise specialization placement."""

    def __init__(self):
        self._river_paths = _river_flow_paths((cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT))


class MapLayoutTest(unittest.TestCase):
    def test_territories_fill_the_playable_map(self):
        generator = MapGenerator()
        for player_count in range(cfg.MIN_PLAYERS, cfg.MAX_PLAYERS + 1):
            map_data = generator.generate(player_count, seed=17)
            points = [point for polygon in map_data.polygons for point in polygon]
            self.assertEqual(0, min(x for x, _ in points))
            self.assertEqual(cfg.WINDOW_WIDTH, max(x for x, _ in points))
            self.assertEqual(0, min(y for _, y in points))
            self.assertEqual(cfg.WINDOW_HEIGHT, max(y for _, y in points))

    def test_specialization_sites_keep_a_full_building_clear_of_rivers(self):
        renderer = _RiverLayoutRenderer()
        for player_count in range(cfg.MIN_PLAYERS, cfg.MAX_PLAYERS + 1):
            for seed in range(12):
                match = Match(["human"] * player_count, seed=seed, headless=True)
                for territory in match.territories:
                    position = Renderer._specialization_site_position(renderer, territory)
                    distance = _nearest_river_distance(position, renderer._river_paths)
                    self.assertGreaterEqual(distance, RIVER_BUILDING_CLEARANCE)

    def test_each_shared_border_has_one_gate(self):
        expected_gates = {2: 1, 3: 3, 4: 4}
        for player_count, expected in expected_gates.items():
            match = Match(["human"] * player_count, seed=17, headless=True)
            pairs = {gate.territory_ids for gate in match.terrain.gates}

            self.assertEqual(len(match.terrain.gates), expected)
            self.assertEqual(len(pairs), expected)
            self.assertTrue(all(wall.territory_ids in pairs for wall in match.terrain.walls))


if __name__ == "__main__":
    unittest.main()
