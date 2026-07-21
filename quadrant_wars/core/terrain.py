import math
import random

from quadrant_wars.core.battlefield import (
    RIVER_NAVIGATION_CLEARANCE,
    nearest_river_distance,
    point_to_segment_distance,
    river_flow_paths,
)


WALL_HALF_WIDTH = 7.0
GATE_HALF_WIDTH = 38.0


class TerrainObstacle:
    """A circular piece of impassable terrain."""

    def __init__(self, center, radius, kind="mountain"):
        self.center = center
        self.radius = radius
        self.kind = kind


class BorderGate:
    def __init__(self, center, territory_ids):
        self.center = center
        self.territory_ids = tuple(territory_ids)


class BorderWall:
    def __init__(self, start, end, territory_ids, gate=None):
        self.start = start
        self.end = end
        self.territory_ids = tuple(territory_ids)
        self.gate = gate

    def drawing_pieces(self):
        if self.gate is None:
            return [(self.start, self.end)]

        dx = self.end[0] - self.start[0]
        dy = self.end[1] - self.start[1]
        length = max(1.0, math.hypot(dx, dy))
        ux, uy = dx / length, dy / length
        gap = min(GATE_HALF_WIDTH, length * 0.32)
        left = (
            self.gate.center[0] - ux * gap,
            self.gate.center[1] - uy * gap,
        )
        right = (
            self.gate.center[0] + ux * gap,
            self.gate.center[1] + uy * gap,
        )
        return [(self.start, left), (right, self.end)]


class TerrainMap:
    """One source of truth for terrain drawing and army navigation."""

    def __init__(self, width, height, obstacles=None, walls=None, gates=None):
        self.width = width
        self.height = height
        self.rivers = river_flow_paths((width, height))
        self.obstacles = list(obstacles or [])
        self.walls = list(walls or [])
        self.gates = list(gates or [])

    @classmethod
    def generate(cls, width, height, territories, seed):
        """Build a small deterministic mountain field clear of every castle."""
        terrain = cls(width, height)
        terrain._build_border_walls(territories)
        rng = random.Random(seed ^ 0x71E44A1)
        castles = [territory.battle_position for territory in territories]
        candidates = []

        # A regular spread makes every map readable; jitter keeps seeds distinct.
        for x_ratio, y_ratio in (
            (0.18, 0.25), (0.38, 0.22), (0.60, 0.23), (0.82, 0.27),
            (0.22, 0.48), (0.42, 0.46), (0.62, 0.49), (0.80, 0.47),
            (0.18, 0.72), (0.38, 0.76), (0.60, 0.73), (0.82, 0.75),
        ):
            candidates.append((
                width * x_ratio + rng.uniform(-45, 45),
                height * y_ratio + rng.uniform(-35, 35),
            ))

        for center in candidates:
            radius = rng.uniform(43, 59)
            if any(math.dist(center, castle) < radius + 100 for castle in castles):
                continue
            if nearest_river_distance(center, terrain.rivers) < radius + 25:
                continue
            if any(math.dist(center, gate.center) < radius + 70 for gate in terrain.gates):
                continue
            if any(math.dist(center, item.center) < radius + item.radius + 35 for item in terrain.obstacles):
                continue
            terrain.obstacles.append(TerrainObstacle(center, radius))
            if len(terrain.obstacles) == 5:
                break
        return terrain

    def _build_border_walls(self, territories):
        edges = {}
        for territory in territories:
            points = territory.polygon
            for start, end in zip(points, points[1:] + points[:1]):
                if self._outer_edge(start, end):
                    continue
                key = self._edge_key(start, end)
                edges.setdefault(key, []).append((territory.id, start, end))

        shared_by_pair = {}
        for records in edges.values():
            owners = sorted({record[0] for record in records})
            if len(owners) != 2:
                continue
            start, end = records[0][1], records[0][2]
            shared_by_pair.setdefault(tuple(owners), []).append((start, end))

        for owners, segments in shared_by_pair.items():
            def gate_score(segment):
                midpoint = (
                    (segment[0][0] + segment[1][0]) / 2.0,
                    (segment[0][1] + segment[1][1]) / 2.0,
                )
                return (
                    nearest_river_distance(midpoint, self.rivers),
                    math.dist(segment[0], segment[1]),
                )

            gate_segment = max(segments, key=gate_score)
            gate_center = (
                (gate_segment[0][0] + gate_segment[1][0]) / 2.0,
                (gate_segment[0][1] + gate_segment[1][1]) / 2.0,
            )
            gate = BorderGate(gate_center, owners)
            self.gates.append(gate)
            for start, end in segments:
                segment_gate = gate if (start, end) == gate_segment else None
                self.walls.append(BorderWall(start, end, owners, segment_gate))

    def _outer_edge(self, start, end):
        return (
            (start[0] == end[0] and start[0] in (0, self.width))
            or (start[1] == end[1] and start[1] in (0, self.height))
        )

    @staticmethod
    def _edge_key(start, end):
        first = (round(start[0], 5), round(start[1], 5))
        second = (round(end[0], 5), round(end[1], 5))
        return tuple(sorted((first, second)))

    def is_blocked(self, point, clearance=0.0, open_points=()):
        if nearest_river_distance(point, self.rivers) < RIVER_NAVIGATION_CLEARANCE + clearance:
            return True
        if any(
            math.dist(point, obstacle.center) < obstacle.radius + clearance
            for obstacle in self.obstacles
        ):
            return True
        for wall in self.walls:
            if point_to_segment_distance(point, wall.start, wall.end) >= WALL_HALF_WIDTH + clearance:
                continue
            if any(math.dist(point, opening) < 62.0 for opening in open_points):
                continue
            if wall.gate is not None:
                open_radius = max(12.0, GATE_HALF_WIDTH - clearance)
                if math.dist(point, wall.gate.center) < open_radius:
                    continue
            return True
        return False

    def segment_is_clear(self, start, end, clearance=0.0, open_points=()):
        """Sample a line so path simplification cannot cut across terrain."""
        distance = max(1.0, math.dist(start, end))
        samples = max(2, math.ceil(distance / 12.0))
        for index in range(1, samples):
            ratio = index / samples
            point = (
                start[0] + (end[0] - start[0]) * ratio,
                start[1] + (end[1] - start[1]) * ratio,
            )
            if self.is_blocked(point, clearance, open_points):
                return False
        return True
