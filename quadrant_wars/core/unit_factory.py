
from quadrant_wars.core.unit import Queen, Soldier, Unit, Worker


class UnitFactory:
    """Factory Method helper used by Territory and tests."""

    @staticmethod
    def create(kind, count = 1):
        key = kind.strip().lower()
        if key == "queen":
            return Queen(count)
        if key == "worker":
            return Worker(count)
        if key == "soldier":
            return Soldier(count)
        raise ValueError(f"Unknown unit kind: {kind}")

