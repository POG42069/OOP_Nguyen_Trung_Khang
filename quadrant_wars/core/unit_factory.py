from __future__ import annotations

from quadrant_wars.core.unit import Queen, Soldier, Unit, Worker


class UnitFactory:
    """Factory Method helper used by Territory and tests."""

    @staticmethod
    def create(kind: str, count: int = 1) -> Unit:
        key = kind.strip().lower()
        if key == "queen":
            return Queen(count)
        if key == "worker":
            return Worker(count)
        if key == "soldier":
            return Soldier(count)
        raise ValueError(f"Unknown unit kind: {kind}")

