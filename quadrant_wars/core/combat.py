from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.battle_arena import (
    SIMULATION_STEP,
    BattleArena,
    BattleArenaType,
    BattleOutcome,
    BattleUnitType,
)
from quadrant_wars.core.unit import DefenderState, SoldierState


@dataclass(frozen=True)
class CombatResult:
    attacker_won: bool
    surviving_states: tuple[SoldierState, ...] = ()
    territory_id: int = -1

    @property
    def surviving_attackers(self) -> int:
        return len(self.surviving_states)


class _AnonymousAttacker:
    name = "Attacker"
    color = (210, 210, 210)
    is_alive = True
    attack_multiplier = 1.0


class CombatResolver:
    """Synchronous facade over the same fixed-step engine used by the game."""

    @staticmethod
    def resolve_instant(
        attacking_soldiers: int | Iterable[SoldierState],
        territory: object,
        attacker: object | None = None,
    ) -> CombatResult:
        attacker = attacker or _AnonymousAttacker()
        arena_type = (
            BattleArenaType.OBJECTIVE
            if hasattr(territory, "objective_type")
            else BattleArenaType.TERRITORY
        )
        arena = BattleArena(arena_type, territory)

        next_id = 1
        if isinstance(attacking_soldiers, int):
            incoming = [
                SoldierState(next_id + index, float(cfg.SOLDIER_HP), -1)
                for index in range(max(0, attacking_soldiers))
            ]
            next_id += len(incoming)
        else:
            incoming, next_id = CombatResolver._normalize_ids(
                list(attacking_soldiers), next_id
            )

        defenders = territory.detach_soldiers(territory.soldiers.count)
        defenders, next_id = CombatResolver._normalize_ids(defenders, next_id)
        fortress_defenders = territory.detach_defenders()
        fortress_defenders, _ = CombatResolver._normalize_ids(
            fortress_defenders,
            next_id,
        )
        arena.add_army(attacker, attacker.color, incoming)
        if defenders:
            arena.add_army(
                territory.owner,
                territory.owner.color,
                defenders,
                neutral=arena_type is BattleArenaType.OBJECTIVE,
                defending=True,
            )
        if fortress_defenders:
            arena.add_defenders(
                territory.owner,
                territory.owner.color,
                fortress_defenders,
            )

        outcome: BattleOutcome | None = None
        for _ in range(30 * 600):
            outcome = arena.update(SIMULATION_STEP)
            if outcome is not None:
                break

        if outcome is None:
            survivors = tuple(
                agent.export_state()
                for agent in arena.living_agents
                if agent.owner is attacker
            )
            CombatResolver._restore_defenders(arena, territory)
            return CombatResult(False, survivors, int(getattr(territory, "id", -1)))

        if not outcome.captured:
            defender_states = outcome.survivors_for(territory.owner)
            territory.receive_soldiers(defender_states)
            territory.finish_defense(
                outcome.defender_survivors_for(territory.owner),
                len(fortress_defenders),
            )

        attacker_won = outcome.captured and outcome.winner is attacker
        survivors = outcome.survivors_for(attacker) if attacker_won else ()
        return CombatResult(
            attacker_won=attacker_won,
            surviving_states=survivors,
            territory_id=int(getattr(territory, "id", -1)),
        )

    @staticmethod
    def apply_result(result: CombatResult, territory: object, attacker: object) -> None:
        if result.attacker_won:
            territory.reset_after_capture(attacker, result.surviving_states)

    @staticmethod
    def _normalize_ids(
        states: list[SoldierState | DefenderState],
        next_id: int,
    ) -> tuple[list[SoldierState | DefenderState], int]:
        normalized: list[SoldierState | DefenderState] = []
        for state in states:
            normalized.append(replace(state, unit_id=next_id))
            next_id += 1
        return normalized, next_id

    @staticmethod
    def _restore_defenders(arena: BattleArena, territory: object) -> None:
        territory.receive_soldiers(
            agent.export_state()
            for agent in arena.living_agents
            if agent.owner is territory.owner
            and agent.unit_type is BattleUnitType.SOLDIER
        )
        deployed = sum(
            1
            for agent in arena.agents
            if agent.owner is territory.owner
            and agent.unit_type is BattleUnitType.DEFENDER
        )
        territory.finish_defense(
            (
                agent.export_state()
                for agent in arena.living_agents
                if agent.owner is territory.owner
                and agent.unit_type is BattleUnitType.DEFENDER
            ),
            deployed,
        )
