import heapq
import math

from quadrant_wars.core.battlefield import specialization_site_position
from quadrant_wars.core.terrain import TerrainMap
from quadrant_wars.core.territory import TerritorySpecialization


class NavigationObstacle:
    def __init__(self, center, radius):
        self.center = center
        self.radius = radius


class BattlefieldNavigator:
    """Tìm đường A* ngắn nhất trên lưới và rút gọn thành các waypoint."""

    def __init__(self, width, height, cell_size=28, terrain=None):
        self._width = width
        self._height = height
        self._cell_size = cell_size
        self._columns = math.ceil(width / cell_size)
        self._rows = math.ceil(height / cell_size)
        self._terrain = terrain or TerrainMap(width, height)

    def find_path(self, start, end, territories, source_id, target_territory_id):
        self._open_points = (start, end)
        obstacles = self._collect_obstacles(
            territories,
            source_id,
            target_territory_id,
        )
        start_cell = self._to_cell(start)
        end_cell = self._to_cell(end)
        frontier = [(0.0, start_cell)]
        came_from = {start_cell: None}
        cost_so_far = {start_cell: 0.0}

        while frontier:
            _, current = heapq.heappop(frontier)
            if current == end_cell:
                break

            for neighbor, step_cost in self._neighbors(current):
                current_point = start if current == start_cell else self._to_point(current)
                next_point = end if neighbor == end_cell else self._to_point(neighbor)
                if neighbor != start_cell and self._blocked(next_point, obstacles):
                    continue
                if not self._segment_clear(current_point, next_point, obstacles):
                    continue

                new_cost = cost_so_far[current] + step_cost
                if new_cost >= cost_so_far.get(neighbor, math.inf):
                    continue
                cost_so_far[neighbor] = new_cost
                heuristic = math.dist(neighbor, end_cell)
                heapq.heappush(frontier, (new_cost + heuristic, neighbor))
                came_from[neighbor] = current

        if end_cell not in came_from:
            return ()

        cells = []
        current = end_cell
        while current is not None:
            cells.append(current)
            current = came_from[current]
        cells.reverse()

        raw_path = [
            start,
            *(self._to_point(cell) for cell in cells[1:-1]),
            end,
        ]
        return tuple(self._simplify(raw_path, obstacles))

    def _collect_obstacles(self, territories, source_id, target_territory_id):
        obstacles = []
        for territory in territories:
            if territory.id not in (source_id, target_territory_id):
                obstacles.append(NavigationObstacle(territory.battle_position, 105.0))
            if territory.specialization in (
                TerritorySpecialization.ECONOMY,
                TerritorySpecialization.BARRACKS,
            ):
                obstacles.append(
                    NavigationObstacle(specialization_site_position(territory), 78.0)
                )
        return obstacles

    def _neighbors(self, cell):
        x, y = cell
        result = []
        for dx, dy in (
            (-1, -1), (0, -1), (1, -1),
            (-1, 0), (1, 0),
            (-1, 1), (0, 1), (1, 1),
        ):
            candidate = (x + dx, y + dy)
            if 0 <= candidate[0] <= self._columns and 0 <= candidate[1] <= self._rows:
                cost = math.sqrt(2.0) if dx and dy else 1.0
                result.append((candidate, cost))
        return result

    def _blocked(self, point, obstacles):
        margin = 20.0
        if not margin <= point[0] <= self._width - margin:
            return True
        if not margin <= point[1] <= self._height - margin:
            return True
        if self._terrain.is_blocked(
            point,
            clearance=12.0,
            open_points=self._open_points,
        ):
            return True
        return any(
            math.dist(point, obstacle.center) < obstacle.radius
            for obstacle in obstacles
        )

    def _simplify(self, path, obstacles):
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

    def _segment_clear(self, start, end, obstacles):
        if not self._terrain.segment_is_clear(
            start,
            end,
            clearance=12.0,
            open_points=self._open_points,
        ):
            return False
        distance = max(1.0, math.dist(start, end))
        samples = max(2, math.ceil(distance / 16.0))
        for index in range(1, samples):
            ratio = index / samples
            point = (
                start[0] + (end[0] - start[0]) * ratio,
                start[1] + (end[1] - start[1]) * ratio,
            )
            if any(
                math.dist(point, obstacle.center) < obstacle.radius
                for obstacle in obstacles
            ):
                return False
        return True

    def _to_cell(self, point):
        return (
            max(0, min(self._columns, round(point[0] / self._cell_size))),
            max(0, min(self._rows, round(point[1] / self._cell_size))),
        )

    def _to_point(self, cell):
        return (
            min(float(self._width), cell[0] * self._cell_size),
            min(float(self._height), cell[1] * self._cell_size),
        )
