from __future__ import annotations

from dataclasses import dataclass

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.territory import Territory


@dataclass(frozen=True)
class CombatResult:
    attacker_won: bool
    surviving_attackers: int
    killed_defending_soldiers: int
    killed_workers: int
    queen_killed: bool


class CombatResolver:
    """Pure combat rules, separated from rendering and game state orchestration."""

    @staticmethod
    def resolve(attacking_soldiers: int, territory: Territory) -> CombatResult:
        if attacking_soldiers <= 0:
            return CombatResult(False, 0, 0, 0, False)

        remaining = attacking_soldiers

        soldier_duels = min(remaining, territory.soldiers.count)
        remaining -= soldier_duels
        killed_defending_soldiers = soldier_duels

        if remaining <= 0:
            return CombatResult(False, 0, killed_defending_soldiers, 0, False)

        killed_workers = min(territory.workers.count, remaining // cfg.WORKER_COMBAT_VALUE)
        remaining -= killed_workers * cfg.WORKER_COMBAT_VALUE

        if territory.workers.count > killed_workers:
            return CombatResult(False, 0, killed_defending_soldiers, killed_workers, False)

        queen_killed = territory.queen.is_alive and remaining >= cfg.QUEEN_COMBAT_VALUE
        if queen_killed:
            remaining -= cfg.QUEEN_COMBAT_VALUE
            return CombatResult(True, remaining, killed_defending_soldiers, killed_workers, True)

        return CombatResult(False, 0, killed_defending_soldiers, killed_workers, False)

    @staticmethod
    def apply(result: CombatResult, territory: Territory, attacker: object) -> None:
        territory.soldiers.remove(result.killed_defending_soldiers)
        territory.workers.remove(result.killed_workers)
        if result.attacker_won:
            old_owner = territory.owner
            if hasattr(old_owner, "eliminate"):
                old_owner.eliminate()
            territory.reset_after_capture(attacker, result.surviving_attackers)

