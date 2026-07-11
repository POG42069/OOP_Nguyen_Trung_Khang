from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Iterable

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.combat import CombatResolver, CombatZone, CombatResult
from quadrant_wars.core.map_generator import MapGenerator
from quadrant_wars.core.player import BotPlayer, HumanPlayer, Player, STRATEGIES
from quadrant_wars.core.supply import SupplyDrop
from quadrant_wars.core.territory import Territory


@dataclass
class MovingArmy:
    attacker: Player
    source_id: int
    target_id: int
    soldiers: int
    start: tuple[float, float]
    end: tuple[float, float]
    elapsed: float = 0.0
    duration: float = 1.0

    @property
    def progress(self) -> float:
        return min(1.0, self.elapsed / max(0.01, self.duration))

    @property
    def position(self) -> tuple[float, float]:
        p = self.progress
        # Smooth ease-in-out
        t = p * p * (3.0 - 2.0 * p)
        return (
            self.start[0] + (self.end[0] - self.start[0]) * t,
            self.start[1] + (self.end[1] - self.start[1]) * t,
        )


@dataclass
class CombatVisualEffect:
    position: tuple[float, float]
    attacker_color: tuple[int, int, int]
    defender_color: tuple[int, int, int]
    attacker_won: bool
    soldiers: int
    elapsed: float = 0.0
    duration: float = 1.45

    @property
    def progress(self) -> float:
        return min(1.0, self.elapsed / max(0.01, self.duration))


class Match:
    def __init__(
        self,
        player_types: Iterable[str],
        seed: int | None = None,
        bot_strategy_classes: list[type] | None = None,
        headless: bool = False,
    ) -> None:
        self._players: list[Player] = []
        strategy_rng = random.Random(seed)
        strategy_classes = bot_strategy_classes[:] if bot_strategy_classes else STRATEGIES[:]
        if not bot_strategy_classes:
            strategy_rng.shuffle(strategy_classes)
        for i, player_type in enumerate(player_types):
            color = cfg.PLAYER_COLORS[i]
            if player_type.lower() == "human":
                self._players.append(HumanPlayer(i, f"Player {i + 1}", color))
            else:
                strategy = strategy_classes[i % len(strategy_classes)]()
                self._players.append(BotPlayer(i, f"{strategy.name} Bot {i + 1}", color, strategy))

        map_data = MapGenerator().generate(len(self._players), seed=seed)
        self._territories = [
            Territory(i, self._players[i], polygon)
            for i, polygon in enumerate(map_data.polygons)
        ]
        self._armies: list[MovingArmy] = []
        self._combat_zones: list[CombatZone] = []
        self._effects: list[CombatVisualEffect] = []
        self._sound_events: list[str] = []
        self._winner: Player | None = None
        self._elapsed = 0.0
        self._event_log: list[str] = []
        self._headless = headless
        
        self._time_since_last_combat = 0.0

    @property
    def players(self) -> list[Player]:
        return list(self._players)

    @property
    def territories(self) -> list[Territory]:
        return list(self._territories)

    @property
    def armies(self) -> list[MovingArmy]:
        return list(self._armies)

    @property
    def combat_zones(self) -> list[CombatZone]:
        return list(self._combat_zones)

    @property
    def effects(self) -> list[CombatVisualEffect]:
        return list(self._effects)

    @property
    def supply_drop(self) -> SupplyDrop | None:
        return self._supply_drop

    @property
    def winner(self) -> Player | None:
        return self._winner

    @property
    def elapsed(self) -> float:
        return self._elapsed

    @property
    def event_log(self) -> list[str]:
        return self._event_log[-6:]

    def pop_sound_events(self) -> list[str]:
        events = self._sound_events[:]
        self._sound_events.clear()
        return events

    def territories_of(self, player: Player) -> list[Territory]:
        """All territories owned by a player with a living queen."""
        return [t for t in self._territories if t.owner is player and t.queen.is_alive]

    def home_territory(self, player: Player) -> Territory | None:
        """Best territory for a player to summon from (prefer capital, else most food)."""
        if not player.is_alive:
            return None
        owned = self.territories_of(player)
        if not owned:
            return None
        capitals = [t for t in owned if t.is_capital]
        if capitals:
            return capitals[0]
            
        # Capital Transfer
        new_capital = max(owned, key=lambda t: t.food)
        new_capital.is_capital = True
        return new_capital

    def best_attack_source(self, player: Player, target: Territory) -> Territory | None:
        """Best territory to attack from: closest owned territory with soldiers."""
        owned = [t for t in self.territories_of(player) if t.soldiers.count > 1]
        if not owned:
            return None
        tx, ty = target.centroid
        return min(owned, key=lambda t: math.hypot(t.centroid[0] - tx, t.centroid[1] - ty))

    def living_players(self) -> list[Player]:
        """A player is alive if they own at least one territory with a living queen."""
        alive = []
        for p in self._players:
            if not p.is_alive:
                continue
            if any(t.owner is p and t.queen.is_alive for t in self._territories):
                alive.append(p)
            else:
                p.eliminate()
        return alive

    def territory_at(self, position: tuple[int, int]) -> Territory | None:
        for territory in self._territories:
            if _point_in_polygon(position, territory.polygon):
                return territory
        return None

    def issue_attack(self, source: Territory, target: Territory, soldiers: int) -> bool:
        if soldiers <= 0 or source.owner is target.owner:
            return False
        if not getattr(source.owner, "is_alive", False):
            return False
        # Target owner can be dead (territory still exists)
        removed = source.remove_soldiers(min(soldiers, source.soldiers.count))
        if removed <= 0:
            return False
        sx, sy = source.centroid
        tx, ty = target.centroid
        distance = math.hypot(tx - sx, ty - sy)
        duration = max(0.6, distance / cfg.SOLDIER_TRAVEL_SPEED)
        self._armies.append(
            MovingArmy(source.owner, source.id, getattr(target, 'id', -1), removed, (sx, sy), (tx, ty), duration=duration)
        )
        target_name = getattr(target.owner, "name", "Supply Drop") if getattr(target, "owner", None) else "Supply Drop"
        self._event_log.append(f"{source.owner.name} sent {removed} soldiers to {target_name}")
        self._sound_events.append("attack")
        return True

    def update(self, dt: float) -> None:
        if self._winner is not None:
            return
        self._elapsed += dt

        for territory in self._territories:
            territory.update(dt)
        for player in self._players:
            player.update(self, dt)

        # --- Update moving armies ---
        arrived: list[MovingArmy] = []
        for army in self._armies:
            army.elapsed += dt
            if army.progress >= 1.0:
                arrived.append(army)
        for army in arrived:
            self._armies.remove(army)
            self._resolve_arrival(army)

        # --- Update active combat zones ---
        finished_zones: list[CombatZone] = []
        for zone in self._combat_zones:
            result = zone.update(dt)
            if result is not None:
                finished_zones.append(zone)
        for zone in finished_zones:
            self._combat_zones.remove(zone)
            self._resolve_combat_end(zone)

        # --- Update visual effects ---
        expired: list[CombatVisualEffect] = []
        for effect in self._effects:
            effect.elapsed += dt
            if effect.progress >= 1.0:
                expired.append(effect)
        for effect in expired:
            self._effects.remove(effect)

        living = self.living_players()
        if len(living) == 1:
            self._winner = living[0]
        elif len(living) == 0:
            # Edge case: simultaneous elimination
            self._winner = self._players[0]

    def _resolve_arrival(self, army: MovingArmy) -> None:
        target = self._territories[army.target_id]
            
        if not army.attacker.is_alive:
            return
        if target.owner is army.attacker:
            target.add_soldiers(army.soldiers)
            return

        if self._headless:
            defender_color = target.owner.color
            defender_name = target.owner.name
            result = CombatResolver.resolve_instant(army.soldiers, target)
            self._effects.append(
                CombatVisualEffect(
                    position=target.centroid,
                    attacker_color=army.attacker.color,
                    defender_color=defender_color,
                    attacker_won=result.attacker_won,
                    soldiers=army.soldiers,
                )
            )
            if result.attacker_won:
                old_owner = target.owner
                CombatResolver.apply_result(result, target, army.attacker)
                self._check_elimination(old_owner)
                self._event_log.append(
                    f"{army.attacker.name} conquered {defender_name}; {result.surviving_attackers} survived"
                )
                self._sound_events.append("combat_win")
            else:
                self._event_log.append(f"{defender_name} defended against {army.attacker.name}")
                self._sound_events.append("combat_defend")
        else:
            zone = CombatZone(
                attacker=army.attacker,
                attacker_color=army.attacker.color,
                territory=target,
                soldier_count=army.soldiers,
            )
            self._combat_zones.append(zone)
            self._event_log.append(f"Battle! {army.attacker.name} ({army.soldiers}) vs {target.owner.name}")
            self._sound_events.append("combat_defend")

    def _resolve_combat_end(self, zone: CombatZone) -> None:
        result = zone.result
        if result is None:
            return
        target = zone.territory
        defender_color = getattr(target.owner, "color", (128, 128, 128))
        self._effects.append(
            CombatVisualEffect(
                position=target.centroid,
                attacker_color=zone.attacker_color,
                defender_color=defender_color,
                attacker_won=result.attacker_won,
                soldiers=result.surviving_attackers,
            )
        )
        if result.attacker_won:
            old_owner = target.owner
            defender_name = getattr(old_owner, "name", "Unknown")
            CombatResolver.apply_result(result, target, zone.attacker)
            self._check_elimination(old_owner)
            self._event_log.append(
                f"{zone.attacker.name} conquered {defender_name}! {result.surviving_attackers} survived"
            )
            self._sound_events.append("combat_win")
        else:
            self._event_log.append(f"{target.owner.name} repelled {zone.attacker.name}!")
            self._sound_events.append("combat_defend")

    def _check_elimination(self, player: object) -> None:
        """Eliminate player if they no longer own any territory with a living queen."""
        if not hasattr(player, "is_alive") or not player.is_alive:
            return
        has_territory = any(
            t.owner is player and t.queen.is_alive for t in self._territories
        )
        if not has_territory:
            player.eliminate()
            self._event_log.append(f"{player.name} has been eliminated!")


def _point_in_polygon(point: tuple[int, int], polygon: list[tuple[float, float]]) -> bool:
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        intersects = (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi
        if intersects:
            inside = not inside
        j = i
    return inside
