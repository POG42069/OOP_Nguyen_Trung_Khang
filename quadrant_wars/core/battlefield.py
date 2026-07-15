from __future__ import annotations

import math
from collections.abc import Iterable

from quadrant_wars import balance_config as cfg

Point = tuple[float, float]

RIVER_BUILDING_CLEARANCE = 120.0
RIVER_NAVIGATION_CLEARANCE = 54.0


def river_flow_paths(viewport: tuple[int, int]) -> list[list[Point]]:
    """Return the shared visual/gameplay centre lines of the map rivers."""
    width, height = viewport
    normalized = (
        ((0.24, -0.04), (0.22, 0.06), (0.17, 0.15), (0.08, 0.24), (-0.03, 0.37)),
        ((-0.03, 0.53), (0.01, 0.64), (0.07, 0.71), (0.11, 0.78), (0.14, 0.88), (0.16, 1.04)),
        ((0.80, -0.04), (0.82, 0.06), (0.87, 0.12), (0.94, 0.19), (1.02, 0.28), (1.03, 0.47)),
        ((1.04, 0.60), (0.99, 0.68), (0.93, 0.75), (0.86, 0.82), (0.82, 0.90), (0.79, 1.04)),
    )
    return [[(x * width, y * height) for x, y in path] for path in normalized]


def territory_landmark_position(
    territory_id: int,
    polygon: Iterable[Point],
    seed: int = 7,
    spread_ratio: float = 0.28,
) -> Point:
    """Choose the deterministic interior position shared by a castle and combat."""
    points = list(polygon)
    cx = sum(point[0] for point in points) / len(points)
    cy = sum(point[1] for point in points) / len(points)
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    spread = max(30.0, min(max(xs) - min(xs), max(ys) - min(ys)) * spread_ratio * 0.44)
    angle = ((territory_id + 1) * 59 + seed * 37) * 2.399963
    radius = spread * (0.24 + ((seed * 73) % 100) / 140)
    x = cx + math.cos(angle) * radius + math.sin(seed * 1.7) * 26
    y = cy + math.sin(angle) * radius + math.cos(seed * 1.3) * 22
    for factor in (1.0, 0.82, 0.64, 0.46, 0.28, 0.1):
        candidate = (cx + (x - cx) * factor, cy + (y - cy) * factor)
        if point_in_polygon(candidate, points):
            return candidate
    return cx, cy


def specialization_site_position(territory: object) -> Point:
    """Choose a stable construction site clear of both castle and rivers."""
    capital = territory_landmark_position(territory.id, territory.polygon)
    candidates = specialization_site_candidates(territory)
    if not candidates:
        return territory_landmark_position(territory.id, territory.polygon, 328, 0.62)

    paths = river_flow_paths((cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT))

    def capital_distance(point: Point) -> float:
        return math.dist(point, capital)

    def river_distance(point: Point) -> float:
        return nearest_river_distance(point, paths)

    dry = [
        point
        for point in candidates
        if river_distance(point) >= RIVER_BUILDING_CLEARANCE + 2.0
    ]
    if dry:
        return max(dry, key=capital_distance)
    return max(candidates, key=lambda point: (river_distance(point), capital_distance(point)))


def specialization_site_candidates(territory: object) -> list[Point]:
    cx, cy = territory.centroid
    candidates: list[Point] = []
    for vx, vy in territory.polygon:
        for factor in (0.34, 0.48):
            point = (cx + (vx - cx) * factor, cy + (vy - cy) * factor)
            if (
                48 <= point[0] <= cfg.WINDOW_WIDTH - 48
                and 42 <= point[1] <= cfg.WINDOW_HEIGHT - 42
                and point_in_polygon(point, territory.polygon)
            ):
                candidates.append(point)
    return candidates


def nearest_river_distance(point: Point, river_paths: Iterable[Iterable[Point]]) -> float:
    distances: list[float] = []
    for path_iterable in river_paths:
        path = list(path_iterable)
        distances.extend(
            point_to_segment_distance(point, start, end)
            for start, end in zip(path, path[1:])
        )
    return min(distances, default=math.inf)


def point_to_segment_distance(point: Point, start: Point, end: Point) -> float:
    px, py = point
    sx, sy = start
    ex, ey = end
    dx = ex - sx
    dy = ey - sy
    length_squared = dx * dx + dy * dy
    if length_squared <= 0.0:
        return math.dist(point, start)
    ratio = max(0.0, min(1.0, ((px - sx) * dx + (py - sy) * dy) / length_squared))
    return math.hypot(px - (sx + dx * ratio), py - (sy + dy * ratio))


def point_in_polygon(point: Point, polygon: Iterable[Point]) -> bool:
    points = list(polygon)
    x, y = point
    inside = False
    previous = len(points) - 1
    for current in range(len(points)):
        xi, yi = points[current]
        xj, yj = points[previous]
        intersects = (yi > y) != (yj > y) and x < (
            (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi
        )
        if intersects:
            inside = not inside
        previous = current
    return inside
