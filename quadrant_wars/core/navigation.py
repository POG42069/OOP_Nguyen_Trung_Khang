from __future__ import annotations

import heapq
import math
from dataclasses import dataclass

from quadrant_wars.core.battlefield import (
    RIVER_NAVIGATION_CLEARANCE,
    nearest_river_distance,
    river_flow_paths,
    specialization_site_position,
)
from quadrant_wars.core.territory import TerritorySpecialization

Point = tuple[float, float]
GridCell = tuple[int, int]


@dataclass(frozen=True)
class NavigationObstacle:
    center: Point
    radius: float


class BattlefieldNavigator:
    """A* route planner for marching armies on the shared battlefield."""

    def __init__(self, width: int, height: int, cell_size: int = 40) -> None:
        self._width = width
        self._height = height
        self._cell_size = cell_size
        self._columns = math.ceil(width / cell_size)
        self._rows = math.ceil(height / cell_size)
        self._river_paths = river_flow_paths((width, height))

    def find_path(
        self,
        start: Point,
        end: Point,
        territories: list[object],
        *,
        source_id: int,
        target_territory_id: int | None,
    ) -> tuple[Point, ...]:
        obstacles = self._collect_obstacles(territories, source_id, target_territory_id)
        start_cell = self._to_cell(start)
        end_cell = self._to_cell(end)
        frontier: list[tuple[float, GridCell]] = [(0.0, start_cell)]
        came_from: dict[GridCell, GridCell | None] = {start_cell: None}
        cost_so_far: dict[GridCell, float] = {start_cell: 0.0}

        while frontier:
            _, current = heapq.heappop(frontier)
            if current == end_cell:
                break
            for neighbor, step_cost in self._neighbors(current):
                point = self._to_point(neighbor)
                if neighbor not in (start_cell, end_cell) and self._blocked(point, obstacles):
                    continue
                terrain_cost = self._terrain_cost(point)
                new_cost = cost_so_far[current] + step_cost * terrain_cost
                if new_cost >= cost_so_far.get(neighbor, math.inf):
                    continue
                cost_so_far[neighbor] = new_cost
                priority = new_cost + math.dist(neighbor, end_cell)
                heapq.heappush(frontier, (priority, neighbor))
                came_from[neighbor] = current

        if end_cell not in came_from:
            return (start, end)

        cells: list[GridCell] = []
        current: GridCell | None = end_cell
        while current is not None:
            cells.append(current)
            current = came_from[current]
        cells.reverse()
        raw = [start, *(self._to_point(cell) for cell in cells[1:-1]), end]
        return tuple(self._simplify(raw, obstacles))

    def _collect_obstacles(
        self,
        territories: list[object],
        source_id: int,
        target_territory_id: int | None,
    ) -> list[NavigationObstacle]:
        obstacles: list[NavigationObstacle] = []
        for territory in territories:
            if territory.id not in (source_id, target_territory_id):
                obstacles.append(NavigationObstacle(territory.battle_position, 105.0))
            if territory.specialization is not TerritorySpecialization.NONE:
                obstacles.append(NavigationObstacle(specialization_site_position(territory), 78.0))
        return obstacles

    def _neighbors(self, cell: GridCell) -> list[tuple[GridCell, float]]:
        x, y = cell
        neighbors: list[tuple[GridCell, float]] = []
        for dx, dy in ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)):
            candidate = (x + dx, y + dy)
            if 0 <= candidate[0] <= self._columns and 0 <= candidate[1] <= self._rows:
                neighbors.append((candidate, math.sqrt(2.0) if dx and dy else 1.0))
        return neighbors

    def _terrain_cost(self, point: Point) -> float:
        river_distance = nearest_river_distance(point, self._river_paths)
        if river_distance < RIVER_NAVIGATION_CLEARANCE:
            return 8.0
        if river_distance < RIVER_NAVIGATION_CLEARANCE + 28.0:
            return 2.4
        return 1.0

    def _blocked(self, point: Point, obstacles: list[NavigationObstacle]) -> bool:
        margin = 20.0
        if not margin <= point[0] <= self._width - margin:
            return True
        if not margin <= point[1] <= self._height - margin:
            return True
        return any(math.dist(point, obstacle.center) < obstacle.radius for obstacle in obstacles)

    def _simplify(self, path: list[Point], obstacles: list[NavigationObstacle]) -> list[Point]:
        if len(path) <= 2:
            return path
        result = [path[0]]
        anchor = 0
        while anchor < len(path) - 1:
            candidate = len(path) - 1
            while candidate > anchor + 1:
                if self._segment_clear(path[anchor], path[candidate], obstacles):
                    break
                candidate -= 1
            result.append(path[candidate])
            anchor = candidate
        return result

    @staticmethod
    def _segment_clear(start: Point, end: Point, obstacles: list[NavigationObstacle]) -> bool:
        distance = max(1.0, math.dist(start, end))
        samples = max(2, math.ceil(distance / 18.0))
        for index in range(1, samples):
            ratio = index / samples
            point = (
                start[0] + (end[0] - start[0]) * ratio,
                start[1] + (end[1] - start[1]) * ratio,
            )
            if any(math.dist(point, obstacle.center) < obstacle.radius for obstacle in obstacles):
                return False
        return True

    def _to_cell(self, point: Point) -> GridCell:
        return (
            max(0, min(self._columns, round(point[0] / self._cell_size))),
            max(0, min(self._rows, round(point[1] / self._cell_size))),
        )

    def _to_point(self, cell: GridCell) -> Point:
        return (
            min(float(self._width), cell[0] * self._cell_size),
            min(float(self._height), cell[1] * self._cell_size),
        )
