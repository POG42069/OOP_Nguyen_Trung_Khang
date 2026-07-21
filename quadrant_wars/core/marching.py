import math
from enum import Enum, auto


class ArmyTargetType(Enum):
    TERRITORY = auto()
    OBJECTIVE = auto()
    RETURN = auto()


class MovingArmy:
    """A group travelling along a waypoint path before it can enter combat."""

    def __init__(
        self,
        attacker,
        source_id,
        target_type,
        target_id,
        units,
        start,
        end,
        path=(),
        elapsed=0.0,
        duration=1.0,
    ):
        self.attacker = attacker
        self.source_id = source_id
        self.target_type = target_type
        self.target_id = target_id
        self.units = units
        self.start = start
        self.end = end
        self.path = path
        self.elapsed = elapsed
        self.duration = duration
        if len(self.path) < 2:
            self.path = (self.start, self.end)
        self._segment_lengths = tuple(
            math.dist(start, end)
            for start, end in zip(self.path, self.path[1:])
        )
        self._path_length = max(0.01, sum(self._segment_lengths))

    @property
    def targets_territory(self):
        return self.target_type is ArmyTargetType.TERRITORY

    @property
    def can_be_recalled(self):
        return self.target_type is not ArmyTargetType.RETURN

    @property
    def soldiers(self):
        return len(self.units)

    @property
    def progress(self):
        return min(1.0, self.elapsed / max(0.01, self.duration))

    @property
    def position(self):
        return self._point_at(self.progress)

    @property
    def heading(self):
        before = self._point_at(max(0.0, self.progress - 0.01))
        after = self._point_at(min(1.0, self.progress + 0.01))
        dx = after[0] - before[0]
        dy = after[1] - before[1]
        length = max(0.01, math.hypot(dx, dy))
        return dx / length, dy / length

    @property
    def path_length(self):
        return self._path_length

    def unit_position(self, index):
        if not self.units:
            return self.position
        index = max(0, min(index, len(self.units) - 1))
        columns = max(1, min(16, math.ceil(math.sqrt(len(self.units) * 1.7))))
        row = index // columns
        column = index % columns
        row_count = min(columns, len(self.units) - row * columns)
        scale = 0.84 if len(self.units) <= 8 else 0.72 if len(self.units) <= 20 else 0.61 if len(self.units) <= 40 else 0.52 if len(self.units) <= 80 else 0.44
        lateral = (column - (row_count - 1) / 2.0) * max(14.0, 25.0 * scale)
        trailing = row * max(12.0, 22.0 * scale)
        heading_x, heading_y = self.heading
        side_x, side_y = -heading_y, heading_x
        base_x, base_y = self.position
        return (
            base_x + side_x * lateral - heading_x * trailing,
            base_y + side_y * lateral - heading_y * trailing,
        )

    @property
    def unit_positions(self):
        return tuple(self.unit_position(index) for index in range(len(self.units)))

    def _point_at(self, progress):
        remaining = max(0.0, min(1.0, progress)) * self._path_length
        for index, segment_length in enumerate(self._segment_lengths):
            if remaining <= segment_length or index == len(self._segment_lengths) - 1:
                ratio = remaining / max(0.01, segment_length)
                start = self.path[index]
                end = self.path[index + 1]
                return (
                    start[0] + (end[0] - start[0]) * ratio,
                    start[1] + (end[1] - start[1]) * ratio,
                )
            remaining -= segment_length
        return self.path[-1]

    def advance(self, dt):
        self.elapsed += dt * max(0.1, self.attacker.march_speed_multiplier)
