from __future__ import annotations

from dataclasses import dataclass

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.unit import Soldier


@dataclass(frozen=True)
class CombatResult:
    attacker_won: bool
    surviving_attackers: int
    territory_id: int = -1


class CombatZone:
    """Real-time combat happening at a territory.

    Each tick, attackers and defenders exchange damage.
    Combat ends when one side is eliminated.
    """

    def __init__(
        self,
        attacker: object,
        attacker_color: tuple[int, int, int],
        territory: object,
        soldier_count: int,
    ) -> None:
        self._attacker = attacker
        self._attacker_color = attacker_color
        self._territory = territory
        self._attacking_soldiers = Soldier(soldier_count)
        self._tick_timer = 0.0
        self._finished = False
        self._result: CombatResult | None = None
        self._elapsed = 0.0
        self._damage_flash = 0.0
        self._initial_attackers = soldier_count

    @property
    def attacker(self) -> object:
        return self._attacker

    @property
    def attacker_color(self) -> tuple[int, int, int]:
        return self._attacker_color

    @property
    def territory(self) -> object:
        return self._territory

    @property
    def attacking_soldiers(self) -> Soldier:
        return self._attacking_soldiers

    @property
    def initial_attackers(self) -> int:
        return self._initial_attackers

    @property
    def finished(self) -> bool:
        return self._finished

    @property
    def result(self) -> CombatResult | None:
        return self._result

    @property
    def elapsed(self) -> float:
        return self._elapsed

    @property
    def damage_flash(self) -> float:
        return self._damage_flash

    @property
    def position(self) -> tuple[float, float]:
        return self._territory.centroid

    def update(self, dt: float) -> CombatResult | None:
        """Advance combat by dt seconds. Returns result when finished."""
        if self._finished:
            return self._result
        self._elapsed += dt
        self._damage_flash = max(0.0, self._damage_flash - dt * 3.0)
        self._tick_timer += dt

        while self._tick_timer >= cfg.COMBAT_TICK_INTERVAL and not self._finished:
            self._tick_timer -= cfg.COMBAT_TICK_INTERVAL
            self._resolve_tick()

        return self._result if self._finished else None

    def _resolve_tick(self) -> None:
        """One combat tick: both sides deal damage."""
        territory = self._territory
        attackers = self._attacking_soldiers

        if not attackers.is_alive:
            self._finish(False, 0)
            return

        # --- Attackers deal damage to defenders ---
        atk_damage = attackers.dps * cfg.COMBAT_TICK_INTERVAL
        atk_damage *= float(getattr(self._attacker, "attack_multiplier", 1.0))
        atk_damage *= float(getattr(territory, "damage_taken_multiplier", 1.0))

        if atk_damage > 0:
            self._damage_flash = 1.0
            remaining_dmg = atk_damage
            if territory.soldiers.is_alive and remaining_dmg > 0:
                dealt = territory.soldiers.take_damage(remaining_dmg)
                remaining_dmg -= dealt
            if territory.workers.is_alive and remaining_dmg > 0:
                dealt = territory.workers.take_damage(remaining_dmg)
                remaining_dmg -= dealt
            if territory.queen.is_alive and remaining_dmg > 0:
                territory.queen.take_damage(remaining_dmg)

        # --- Check if queen is dead (attacker wins) ---
        if not territory.queen.is_alive:
            self._finish(True, attackers.count)
            return

        # --- Defenders deal damage back to attackers ---
        def_damage = 0.0
        if territory.soldiers.is_alive:
            def_damage += territory.soldiers.dps * cfg.COMBAT_TICK_INTERVAL
        if territory.queen.is_alive:
            def_damage += territory.queen.dps * cfg.COMBAT_TICK_INTERVAL

        if hasattr(territory, "owner"):
            def_damage *= float(getattr(territory.owner, "attack_multiplier", 1.0))

        if def_damage > 0:
            attackers.take_damage(def_damage)
            self._damage_flash = 1.0

        if not attackers.is_alive:
            self._finish(False, 0)

    def _finish(self, attacker_won: bool, survivors: int) -> None:
        self._finished = True
        self._result = CombatResult(
            attacker_won=attacker_won,
            surviving_attackers=survivors,
            territory_id=self._territory.id,
        )


class CombatResolver:
    """Instant combat resolution for headless simulation and bot evaluation."""

    @staticmethod
    def resolve_instant(
        attacking_soldiers: int,
        territory: object,
        attacker: object | None = None,
    ) -> CombatResult:
        """Simulate combat to completion instantly (for headless sim)."""
        zone = CombatZone(
            attacker=attacker,
            attacker_color=(0, 0, 0),
            territory=territory,
            soldier_count=attacking_soldiers,
        )
        for _ in range(500):
            result = zone.update(cfg.COMBAT_TICK_INTERVAL)
            if result is not None:
                return result
        return CombatResult(attacker_won=False, surviving_attackers=0)

    @staticmethod
    def apply_result(result: CombatResult, territory: object, attacker: object) -> None:
        """Apply combat result to game state. Does NOT eliminate player — caller must check."""
        if result.attacker_won:
            territory.reset_after_capture(attacker, result.surviving_attackers)
