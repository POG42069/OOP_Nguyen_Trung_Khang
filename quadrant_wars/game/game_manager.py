from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Iterable

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.combat import CombatResolver
from quadrant_wars.core.map_generator import MapGenerator
from quadrant_wars.core.player import BotPlayer, HumanPlayer, Player, STRATEGIES
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
        return (
            self.start[0] + (self.end[0] - self.start[0]) * p,
            self.start[1] + (self.end[1] - self.start[1]) * p,
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
        self._home_by_player = {player.id: self._territories[player.id] for player in self._players}
        self._armies: list[MovingArmy] = []
        self._effects: list[CombatVisualEffect] = []
        self._sound_events: list[str] = []
        self._winner: Player | None = None
        self._elapsed = 0.0
        self._event_log: list[str] = []

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
    def effects(self) -> list[CombatVisualEffect]:
        return list(self._effects)

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

    def home_territory(self, player: Player) -> Territory | None:
        territory = self._home_by_player.get(player.id)
        if territory and territory.queen.is_alive and player.is_alive:
            return territory
        return None

    def living_players(self) -> list[Player]:
        return [p for p in self._players if p.is_alive]

    def territory_at(self, position: tuple[int, int]) -> Territory | None:
        for territory in self._territories:
            if _point_in_polygon(position, territory.polygon):
                return territory
        return None

    def issue_attack(self, source: Territory, target: Territory, soldiers: int) -> bool:
        if soldiers <= 0 or source.owner is target.owner:
            return False
        if not getattr(source.owner, "is_alive", False) or not getattr(target.owner, "is_alive", False):
            return False
        removed = source.remove_soldiers(min(soldiers, source.soldiers.count))
        if removed <= 0:
            return False
        sx, sy = source.centroid
        tx, ty = target.centroid
        distance = math.hypot(tx - sx, ty - sy)
        duration = max(0.6, distance / cfg.SOLDIER_TRAVEL_SPEED)
        self._armies.append(
            MovingArmy(source.owner, source.id, target.id, removed, (sx, sy), (tx, ty), duration=duration)
        )
        self._event_log.append(f"{source.owner.name} sent {removed} soldiers to {target.owner.name}")
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

        arrived: list[MovingArmy] = []
        for army in self._armies:
            army.elapsed += dt
            if army.progress >= 1.0:
                arrived.append(army)
        for army in arrived:
            self._armies.remove(army)
            self._resolve_arrival(army)

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

    def _resolve_arrival(self, army: MovingArmy) -> None:
        target = self._territories[army.target_id]
        if not army.attacker.is_alive:
            return
        if target.owner is army.attacker:
            target.add_soldiers(army.soldiers)
            return
        defender_color = target.owner.color
        result = CombatResolver.resolve(army.soldiers, target)
        defender_name = target.owner.name
        self._effects.append(
            CombatVisualEffect(
                position=target.centroid,
                attacker_color=army.attacker.color,
                defender_color=defender_color,
                attacker_won=result.attacker_won,
                soldiers=army.soldiers,
            )
        )
        CombatResolver.apply(result, target, army.attacker)
        if result.attacker_won:
            self._event_log.append(
                f"{army.attacker.name} eliminated {defender_name}; {result.surviving_attackers} soldiers survived"
            )
            self._sound_events.append("combat_win")
        else:
            self._event_log.append(f"{defender_name} defended against {army.attacker.name}")
            self._sound_events.append("combat_defend")


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
