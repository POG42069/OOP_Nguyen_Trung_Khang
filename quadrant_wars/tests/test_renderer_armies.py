from __future__ import annotations

import math
import unittest

import pygame

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.battle_arena import BattleArena, BattleArenaType
from quadrant_wars.core.player import HumanPlayer
from quadrant_wars.core.territory import Territory
from quadrant_wars.core.unit import SoldierState
from quadrant_wars.game.game_manager import ArmyTargetType, MovingArmy
from quadrant_wars.ui.renderer import Renderer


class RendererArmyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()

    @classmethod
    def tearDownClass(cls) -> None:
        pygame.quit()

    def _renderer_spy(self) -> tuple[Renderer, list[tuple]]:
        renderer = Renderer.__new__(Renderer)
        renderer._screen = pygame.Surface((640, 480), pygame.SRCALPHA)
        renderer._unit_positions = {}
        renderer._unit_targets = {}
        renderer._unit_facing = {}
        renderer._frame_dt = 1.0 / 60.0
        calls: list[tuple] = []
        renderer._draw_unit_sprite = lambda *args, **kwargs: calls.append((args, kwargs))
        return renderer, calls

    def test_marching_army_draws_every_dispatched_soldier(self) -> None:
        renderer, calls = self._renderer_spy()
        player = HumanPlayer(0, "Player", (214, 84, 76))
        army = MovingArmy(
            attacker=player,
            source_id=0,
            target_type=ArmyTargetType.TERRITORY,
            target_id=1,
            units=[SoldierState(index + 1, cfg.SOLDIER_HP, 0) for index in range(37)],
            start=(80.0, 200.0),
            end=(560.0, 200.0),
            duration=5.0,
        )

        renderer._draw_army(army)

        self.assertEqual(len(calls), 37)

    def test_combat_draws_all_living_attackers_and_defenders(self) -> None:
        renderer, calls = self._renderer_spy()
        attacker = HumanPlayer(0, "Attacker", (214, 84, 76))
        defender = HumanPlayer(1, "Defender", (70, 137, 214))
        territory = Territory(1, defender, [(220, 120), (420, 120), (420, 340), (220, 340)])
        territory.soldiers.remove(territory.soldiers.count)
        territory.soldiers.add(11)
        arena = BattleArena(BattleArenaType.TERRITORY, territory)
        arena.add_army(
            attacker,
            attacker.color,
            [SoldierState(index + 1, cfg.SOLDIER_HP, 0) for index in range(23)],
            (1.0, 0.2),
        )
        defenders = territory.detach_soldiers(territory.soldiers.count)
        defenders = [
            SoldierState(index + 100, state.hp, territory.id)
            for index, state in enumerate(defenders)
        ]
        arena.add_army(defender, defender.color, defenders, defending=True)

        renderer._draw_battle_arena(arena)

        self.assertEqual(len(calls), 34)
        attacker_calls = [call for call in calls if call[0][1] == attacker.color]
        self.assertEqual(len(attacker_calls), 23)
        self.assertTrue(all(call[1]["animation"] == "walk" for call in attacker_calls))

    def test_unit_smoothing_never_exceeds_the_role_speed_limit(self) -> None:
        renderer, _ = self._renderer_spy()
        renderer._unit_positions["player-1-worker"] = (0.0, 0.0)

        position, speed, _ = renderer._smooth_unit_position(
            "player-1-worker",
            (1000.0, 0.0),
            3.2,
            max_speed=44.0,
        )

        self.assertLessEqual(math.dist((0.0, 0.0), position), 44.0 / 60.0 + 1e-6)
        self.assertLessEqual(speed, 44.0 + 1e-6)

    def test_player_one_worker_stops_moving_during_work_animation(self) -> None:
        renderer, _ = self._renderer_spy()
        player = HumanPlayer(0, "Player 1", (214, 84, 76))
        territory = Territory(0, player, [(80, 80), (560, 80), (560, 400), (80, 400)])
        renderer._unit_positions["0:worker:0"] = (210.0, 220.0)
        match = type("MatchStub", (), {"battles": []})()

        renderer._draw_wandering_units(match, territory, 0.0)

        self.assertEqual(renderer._unit_positions["0:worker:0"], (210.0, 220.0))

    def test_new_worker_spawn_keeps_a_stable_speed_limited_route(self) -> None:
        renderer, _ = self._renderer_spy()
        player = HumanPlayer(0, "Player 1", (214, 84, 76))
        territory = Territory(0, player, [(80, 80), (560, 80), (560, 400), (80, 400)])
        territory.workers.add(1)
        territory.visual_spawns.append({"role": "worker", "progress": 0.1, "index": 1})
        match = type("MatchStub", (), {"battles": []})()

        renderer._draw_wandering_units(match, territory, 0.0)
        first = renderer._unit_positions["0:worker:1"]
        renderer._draw_wandering_units(match, territory, 500.0)
        second = renderer._unit_positions["0:worker:1"]

        self.assertLessEqual(math.dist(first, second), 44.0 / 60.0 + 1e-6)


if __name__ == "__main__":
    unittest.main()
