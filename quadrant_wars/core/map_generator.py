from __future__ import annotations

import random
from dataclasses import dataclass

from quadrant_wars import balance_config as cfg

Point = tuple[float, float]


@dataclass(frozen=True)
class MapData:
    polygons: list[list[Point]]


class MapGenerator:
    """Generates balanced contiguous regions without external geometry packages."""

    def __init__(self, width: int = cfg.WINDOW_WIDTH, height: int = cfg.WINDOW_HEIGHT) -> None:
        self._width = width
        self._height = height

    def generate(self, player_count: int, seed: int | None = None) -> MapData:
        if not cfg.MIN_PLAYERS <= player_count <= cfg.MAX_PLAYERS:
            raise ValueError("player_count must be between 2 and 4")
        rng = random.Random(seed)
        left, top = 70, 70
        right, bottom = self._width - 310, self._height - 70
        cx = (left + right) / 2 + rng.uniform(-18, 18)
        cy = (top + bottom) / 2 + rng.uniform(-18, 18)

        if player_count == 2:
            split = [
                (cx + rng.uniform(-45, 45), top),
                (cx + rng.uniform(-70, 70), top + (bottom - top) * 0.23),
                (cx + rng.uniform(-55, 55), top + (bottom - top) * 0.47),
                (cx + rng.uniform(-75, 75), top + (bottom - top) * 0.72),
                (cx + rng.uniform(-45, 45), bottom),
            ]
            polygons = [
                [(left, top), split[0], split[1], split[2], split[3], split[4], (left, bottom)],
                [split[0], (right, top), (right, bottom), split[4], split[3], split[2], split[1]],
            ]
        elif player_count == 3:
            a = (cx + rng.uniform(-28, 28), cy + rng.uniform(-22, 22))
            p_top = (cx + rng.uniform(-110, 110), top)
            p_right = (right, cy + rng.uniform(-110, 110))
            p_left = (left, cy + rng.uniform(-110, 110))
            p_bottom = (cx + rng.uniform(-90, 90), bottom)
            polygons = [
                [(left, top), p_top, (right, top), p_right, a],
                [p_right, (right, bottom), p_bottom, a],
                [p_bottom, (left, bottom), p_left, (left, top), a],
            ]
        else:
            a = (cx + rng.uniform(-20, 20), cy + rng.uniform(-20, 20))
            p_top = (cx + rng.uniform(-80, 80), top)
            p_right = (right, cy + rng.uniform(-80, 80))
            p_bottom = (cx + rng.uniform(-80, 80), bottom)
            p_left = (left, cy + rng.uniform(-80, 80))
            b1a = (cx + rng.uniform(-90, 70), top + (cy - top) * 0.35)
            b1b = (cx + rng.uniform(-65, 95), top + (cy - top) * 0.68)
            b2a = (cx + (right - cx) * 0.34, cy + rng.uniform(-85, 45))
            b2b = (cx + (right - cx) * 0.68, cy + rng.uniform(-45, 85))
            b3a = (cx + rng.uniform(-95, 65), cy + (bottom - cy) * 0.34)
            b3b = (cx + rng.uniform(-55, 95), cy + (bottom - cy) * 0.68)
            b4a = (left + (cx - left) * 0.34, cy + rng.uniform(-75, 55))
            b4b = (left + (cx - left) * 0.68, cy + rng.uniform(-45, 85))
            polygons = [
                [(left, top), p_top, b1a, b1b, a, b4b, b4a, p_left],
                [p_top, (right, top), p_right, b2b, b2a, a, b1b, b1a],
                [a, b2a, b2b, p_right, (right, bottom), p_bottom, b3b, b3a],
                [p_left, b4a, b4b, a, b3a, b3b, p_bottom, (left, bottom)],
            ]
        return MapData(polygons=polygons)
