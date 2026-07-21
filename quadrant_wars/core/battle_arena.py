import math
from enum import Enum, auto

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.unit import DefenderState, SoldierState

SIMULATION_STEP = 1.0 / 30.0
COMBAT_MOVE_SPEED = 72.0
MELEE_RANGE = 34.0
AGENT_RADIUS = 13.0
MAX_MELEE_SLOTS = 6
ATTACK_IMPACT_DELAY = 0.22
ATTACK_ANIMATION_DURATION = 0.58
HIT_ANIMATION_DURATION = 0.16
DEATH_VISUAL_DURATION = 0.8


class BattleArenaType(Enum):
    TERRITORY = auto()
    OBJECTIVE = auto()


class BattleUnitType(Enum):
    SOLDIER = auto()
    DEFENDER = auto()


class BattlePhase(Enum):
    PLAYER_COMBAT = auto()
    NEUTRAL_COMBAT = auto()
    CORE_ASSAULT = auto()
    RESOLVED = auto()


class BattleAgent:
    def __init__(
        self,
        unit_id,
        owner,
        color,
        source_id,
        hp,
        max_hp,
        position,
        unit_type=BattleUnitType.SOLDIER,
        attack_damage=float(cfg.SOLDIER_ATK),
        attack_speed=cfg.SOLDIER_ATK_SPEED,
        move_speed=COMBAT_MOVE_SPEED,
        attack_range=MELEE_RANGE,
        impact_delay=ATTACK_IMPACT_DELAY,
        attack_animation_duration=ATTACK_ANIMATION_DURATION,
        guard_radius=None,
        home_position=None,
        velocity=(0.0, 0.0),
        facing=(1.0, 0.0),
        target_id=None,
        engagement_slot=0,
        attack_cooldown=0.0,
        opening_delay=0.0,
        impact_timer=0.0,
        pending_target_id=None,
        animation="run",
        animation_time=0.0,
        hit_flash=0.0,
        death_elapsed=0.0,
        neutral=False,
    ):
        self.unit_id = unit_id
        self.owner = owner
        self.color = color
        self.source_id = source_id
        self.hp = hp
        self.max_hp = max_hp
        self.position = position
        self.unit_type = unit_type
        self.attack_damage = attack_damage
        self.attack_speed = attack_speed
        self.move_speed = move_speed
        self.attack_range = attack_range
        self.impact_delay = impact_delay
        self.attack_animation_duration = attack_animation_duration
        self.guard_radius = guard_radius
        self.home_position = home_position
        self.velocity = velocity
        self.facing = facing
        self.target_id = target_id
        self.engagement_slot = engagement_slot
        self.attack_cooldown = attack_cooldown
        self.opening_delay = opening_delay
        self.impact_timer = impact_timer
        self.pending_target_id = pending_target_id
        self.animation = animation
        self.animation_time = animation_time
        self.hit_flash = hit_flash
        self.death_elapsed = death_elapsed
        self.neutral = neutral

    def __eq__(self, other):
        return isinstance(other, BattleAgent) and vars(self) == vars(other)

    @property
    def alive(self):
        return self.hp > 0.0

    @property
    def visible(self):
        return self.alive or self.death_elapsed < DEATH_VISUAL_DURATION

    @property
    def health_ratio(self):
        return max(0.0, min(1.0, self.hp / max(0.01, self.max_hp)))

    def export_state(self):
        state_type = (
            DefenderState
            if self.unit_type is BattleUnitType.DEFENDER
            else SoldierState
        )
        return state_type(self.unit_id, max(0.01, self.hp), self.source_id)


class BattleSurvivor:
    def __init__(self, owner, state):
        self.owner = owner
        self.state = state

    def __eq__(self, other):
        return isinstance(other, BattleSurvivor) and vars(self) == vars(other)


class BattleOutcome:
    def __init__(self, arena_type, target_id, winner, captured, survivors):
        self.arena_type = arena_type
        self.target_id = target_id
        self.winner = winner
        self.captured = captured
        self.survivors = survivors

    def __eq__(self, other):
        return isinstance(other, BattleOutcome) and vars(self) == vars(other)

    def survivors_for(self, owner):
        return tuple(
            item.state
            for item in self.survivors
            if item.owner is owner and isinstance(item.state, SoldierState)
        )

    def defender_survivors_for(self, owner):
        return tuple(
            item.state
            for item in self.survivors
            if item.owner is owner and isinstance(item.state, DefenderState)
        )


class BattleImpact:
    def __init__(self, position, color, kind, ttl=0.32):
        self.position = position
        self.color = color
        self.kind = kind
        self.ttl = ttl

    def __eq__(self, other):
        return isinstance(other, BattleImpact) and vars(self) == vars(other)


class BattleArena:
    """Deterministic multi-faction battle with one visual agent per Soldier."""

    def __init__(
        self,
        arena_type,
        target,
    ):
        self.arena_type = arena_type
        self.target = target
        self.target_id = int(target.id)
        self.center = (
            target.centroid
            if arena_type is BattleArenaType.OBJECTIVE
            else target.battle_position
        )
        self.phase = BattlePhase.PLAYER_COMBAT
        self.elapsed = 0.0
        self.damage_flash = 0.0
        self.agents = []
        self.impacts = []
        self._impact_pool = []
        self._accumulator = 0.0
        self._queen_cooldown = 0.0
        self._pending_outcome = None
        self._resolution_timer = 0.0
        self._finished = False
        self._result = None
        self._sound_events = []
        self._sound_cooldowns = {}

    @property
    def finished(self):
        return self._finished

    @property
    def result(self):
        return self._result

    @property
    def captured_pending(self):
        return self._pending_outcome is not None and self._pending_outcome.captured

    @property
    def pending_winner(self):
        return self._pending_outcome.winner if self._pending_outcome is not None else None

    @property
    def position(self):
        return self.center

    @property
    def living_agents(self):
        return [agent for agent in self.agents if agent.alive]

    @property
    def visible_agents(self):
        return [agent for agent in self.agents if agent.visible]

    @property
    def player_factions(self):
        factions = []
        for agent in self.living_agents:
            if agent.neutral or any(owner is agent.owner for owner in factions):
                continue
            factions.append(agent.owner)
        return tuple(factions)

    def commitment_count(self, player):
        return sum(1 for agent in self.living_agents if agent.owner is player)

    def pop_sound_events(self):
        events = self._sound_events[:]
        self._sound_events.clear()
        return events

    def add_army(
        self,
        owner,
        color,
        units,
        approach_vector = (1.0, 0.0),
        *,
        neutral = False,
        defending = False,
        entry_positions = None,
    ):
        states = list(units)
        if not states:
            return
        positions = list(entry_positions) if entry_positions is not None else []
        length = max(0.01, math.hypot(*approach_vector))
        ux, uy = approach_vector[0] / length, approach_vector[1] / length
        side_x, side_y = -uy, ux
        columns = max(1, min(10, math.ceil(math.sqrt(len(states) * 1.4))))
        for index, state in enumerate(states):
            if index < len(positions):
                position = positions[index]
            elif defending or neutral:
                ring = index // 12
                slot = index % 12
                ring_count = min(12, len(states) - ring * 12)
                angle = slot * math.tau / max(1, ring_count) + ring * 0.17
                radius = 52.0 + ring * 23.0
                position = (
                    self.center[0] + math.cos(angle) * radius,
                    self.center[1] + math.sin(angle) * radius * 0.68,
                )
            else:
                row = index // columns
                column = index % columns
                row_count = min(columns, len(states) - row * columns)
                lateral = (column - (row_count - 1) / 2.0) * 12.0
                position = (
                    self.center[0] - ux * (92.0 + row * 11.0) + side_x * lateral,
                    self.center[1] - uy * (92.0 + row * 11.0) + side_y * lateral,
                )
            self.agents.append(
                BattleAgent(
                    unit_id=state.unit_id,
                    owner=owner,
                    color=color,
                    source_id=state.source_id,
                    hp=max(0.01, min(float(cfg.SOLDIER_HP), state.hp)),
                    max_hp=float(cfg.SOLDIER_HP),
                    position=position,
                    home_position=position,
                    facing=(ux, uy),
                    opening_delay=(index % 8) * 0.055,
                    neutral=neutral,
                )
            )

        self._reopen_for_reinforcement()

    def add_defenders(
        self,
        owner,
        color,
        units,
    ):
        states = list(units)
        if not states:
            return
        for index, state in enumerate(states):
            angle = -math.pi / 2.0 + index * math.tau / max(1, len(states))
            radius = 38.0 + (index % 2) * 5.0
            position = (
                self.center[0] + math.cos(angle) * radius,
                self.center[1] + math.sin(angle) * radius * 0.62 + 6.0,
            )
            facing = self._direction(position, self.center, (1.0, 0.0))
            self.agents.append(
                BattleAgent(
                    unit_id=state.unit_id,
                    owner=owner,
                    color=color,
                    source_id=state.source_id,
                    hp=max(0.01, min(float(cfg.DEFENDER_HP), state.hp)),
                    max_hp=float(cfg.DEFENDER_HP),
                    position=position,
                    unit_type=BattleUnitType.DEFENDER,
                    attack_damage=float(cfg.DEFENDER_ATK),
                    attack_speed=cfg.DEFENDER_ATK_SPEED,
                    move_speed=cfg.DEFENDER_COMBAT_MOVE_SPEED,
                    attack_range=cfg.DEFENDER_ATTACK_RANGE,
                    impact_delay=cfg.DEFENDER_ATTACK_IMPACT_DELAY,
                    attack_animation_duration=cfg.DEFENDER_ATTACK_ANIMATION_DURATION,
                    guard_radius=cfg.DEFENDER_GUARD_RADIUS,
                    home_position=position,
                    facing=facing,
                    opening_delay=(index % 4) * 0.07,
                )
            )

        self._reopen_for_reinforcement()

    def _reopen_for_reinforcement(self):

        # A fresh rival reopens a defended/failed arena and interrupts core hits.
        if self._pending_outcome is not None and not self._pending_outcome.captured:
            self._pending_outcome = None
            self._resolution_timer = 0.0
            self._finished = False
            self._result = None
        for agent in self.living_agents:
            agent.target_id = None
            agent.pending_target_id = None
            agent.impact_timer = 0.0
        self._refresh_phase()

    def eliminate_owner(self, owner):
        """Remove an eliminated faction without skipping death visuals."""
        changed = False
        for agent in self.living_agents:
            if agent.owner is not owner:
                continue
            agent.hp = 0.0
            agent.animation = "death"
            agent.animation_time = 0.0
            agent.death_elapsed = 0.0
            agent.target_id = None
            agent.pending_target_id = None
            changed = True
        if changed:
            self._refresh_phase()

    def update(self, dt):
        if self._finished:
            return self._result
        dt = max(0.0, dt)
        self.elapsed += dt
        self.damage_flash = max(0.0, self.damage_flash - dt * 3.4)
        active_impacts = []
        for impact in self.impacts:
            impact.ttl -= dt
            if impact.ttl > 0.0:
                active_impacts.append(impact)
            elif len(self._impact_pool) < 48:
                self._impact_pool.append(impact)
        self.impacts = active_impacts

        if self._pending_outcome is not None:
            self._advance_visual_timers(dt)
            self._resolution_timer -= dt
            if self._resolution_timer <= 0.0:
                self._finished = True
                self._result = self._pending_outcome
                return self._result
            return None

        self._accumulator += dt
        while self._accumulator + 1e-9 >= SIMULATION_STEP and self._pending_outcome is None:
            self._accumulator -= SIMULATION_STEP
            self._step(SIMULATION_STEP)
        if self._pending_outcome is not None and self._accumulator > 0.0:
            visual_dt = min(self._accumulator, self._resolution_timer)
            self._advance_visual_timers(visual_dt)
            self._resolution_timer -= self._accumulator
            self._accumulator = 0.0
            if self._resolution_timer <= 0.0:
                self._finished = True
                self._result = self._pending_outcome
                return self._result
        return None

    def _step(self, dt):
        self._advance_visual_timers(dt)
        for name in tuple(self._sound_cooldowns):
            remaining = self._sound_cooldowns[name] - dt
            if remaining <= 0.0:
                del self._sound_cooldowns[name]
            else:
                self._sound_cooldowns[name] = remaining
        self._queen_cooldown = max(0.0, self._queen_cooldown - dt)
        self._refresh_phase()
        if self._pending_outcome is not None:
            return

        if self.phase is BattlePhase.PLAYER_COMBAT:
            active = [agent for agent in self.living_agents if not agent.neutral]
            self._step_agent_combat(
                active,
                dt,
                resolve_overlaps=self.arena_type is not BattleArenaType.OBJECTIVE,
            )
            if self.arena_type is BattleArenaType.OBJECTIVE:
                self._step_neutral_retreat(dt)
                self._resolve_overlaps(self.living_agents)
            if self.arena_type is BattleArenaType.TERRITORY:
                self._static_defender_attack(dt)
        elif self.phase is BattlePhase.NEUTRAL_COMBAT:
            self._step_agent_combat(self.living_agents, dt)
            self._static_defender_attack(dt)
        elif self.phase is BattlePhase.CORE_ASSAULT:
            self._step_core_assault(dt)

        if any(agent.alive and agent.animation == "run" for agent in self.agents):
            self._emit_sound("footstep", 0.18)

        self._refresh_phase()

    def _advance_visual_timers(self, dt):
        for agent in self.agents:
            agent.animation_time += dt
            agent.hit_flash = max(0.0, agent.hit_flash - dt * 4.5)
            if not agent.alive:
                agent.death_elapsed += dt
                damping = max(0.0, 1.0 - dt * 5.0)
                agent.position = (
                    agent.position[0] + agent.velocity[0] * dt,
                    agent.position[1] + agent.velocity[1] * dt,
                )
                agent.velocity = (agent.velocity[0] * damping, agent.velocity[1] * damping)

    def _refresh_phase(self):
        if self._pending_outcome is not None:
            return
        living = self.living_agents
        if self.arena_type is BattleArenaType.OBJECTIVE:
            players = self._distinct_owners(agent for agent in living if not agent.neutral)
            if len(players) >= 2:
                self._set_phase(BattlePhase.PLAYER_COMBAT)
                return
            if len(players) == 1:
                neutral_alive = any(agent.neutral for agent in living)
                self._set_phase(
                    BattlePhase.NEUTRAL_COMBAT if neutral_alive else BattlePhase.CORE_ASSAULT
                )
                return
            self._queue_outcome(None, False, self._survivors(living))
            return

        owner = self.target.owner
        attackers = [agent for agent in living if agent.owner is not owner and not agent.neutral]
        if not attackers:
            defenders = [agent for agent in living if agent.owner is owner]
            self._queue_outcome(owner, False, self._survivors(defenders))
            return
        mobile_factions = self._distinct_owners(agent for agent in living if not agent.neutral)
        if len(mobile_factions) >= 2:
            self._set_phase(BattlePhase.PLAYER_COMBAT)
            return
        self._set_phase(BattlePhase.CORE_ASSAULT)

    def _set_phase(self, phase):
        if self.phase is phase:
            return
        self.phase = phase
        for agent in self.living_agents:
            agent.target_id = None
            agent.pending_target_id = None
            agent.impact_timer = 0.0
            if agent.neutral and phase is BattlePhase.PLAYER_COMBAT:
                agent.animation = "idle"
                agent.velocity = (0.0, 0.0)

    @staticmethod
    def _distinct_owners(agents):
        owners = []
        for agent in agents:
            if not any(owner is agent.owner for owner in owners):
                owners.append(agent.owner)
        return owners

    def _step_agent_combat(
        self,
        active,
        dt,
        *,
        resolve_overlaps = True,
    ):
        if not active:
            return
        active = sorted(active, key=lambda item: item.unit_id)
        lookup = {agent.unit_id: agent for agent in active}
        queued_damage = []

        for agent in active:
            agent.attack_cooldown = max(0.0, agent.attack_cooldown - dt)
            if agent.impact_timer <= 0.0:
                continue
            agent.impact_timer -= dt
            if agent.impact_timer > 0.0 or agent.pending_target_id is None:
                continue
            target = lookup.get(agent.pending_target_id)
            if (
                target is not None
                and target.alive
                and math.dist(agent.position, target.position)
                <= agent.attack_range * 1.8
            ):
                damage = agent.attack_damage * float(
                    getattr(agent.owner, "attack_multiplier", 1.0)
                )
                queued_damage.append((agent, target, damage))
            agent.pending_target_id = None

        reservations = {}
        for agent in sorted(
            active,
            key=lambda item: (item.pending_target_id is None, item.unit_id),
        ):
            target = lookup.get(agent.target_id) if agent.target_id is not None else None
            if (
                target is None
                or not target.alive
                or target.owner is agent.owner
                or len(reservations.get(target.unit_id, ())) >= MAX_MELEE_SLOTS
                or (
                    agent.guard_radius is not None
                    and math.dist(self.center, target.position)
                    > agent.guard_radius + agent.attack_range
                )
            ):
                agent.target_id = None
                continue
            reservations.setdefault(target.unit_id, []).append(agent)

        for agent in active:
            if (
                not agent.alive
                or agent.pending_target_id is not None
                or agent.target_id is not None
            ):
                continue
            target = None
            best_key = (float("inf"), 2**63)
            for candidate in active:
                if (
                    not candidate.alive
                    or candidate.owner is agent.owner
                    or len(reservations.get(candidate.unit_id, ())) >= MAX_MELEE_SLOTS
                ):
                    continue
                if (
                    agent.guard_radius is not None
                    and math.dist(self.center, candidate.position)
                    > agent.guard_radius + agent.attack_range
                ):
                    continue
                dx = candidate.position[0] - agent.position[0]
                dy = candidate.position[1] - agent.position[1]
                key = (dx * dx + dy * dy, candidate.unit_id)
                if key < best_key:
                    best_key = key
                    target = candidate
            if target is None:
                agent.target_id = None
                self._return_to_guard_post(agent, active, dt)
                continue
            agent.target_id = target.unit_id
            reservations.setdefault(target.unit_id, []).append(agent)

        for assigned in reservations.values():
            for index, agent in enumerate(sorted(assigned, key=lambda item: item.unit_id)):
                agent.engagement_slot = index

        for agent in active:
            if not agent.alive or agent.pending_target_id is not None:
                continue
            if agent.animation == "hit" and agent.animation_time < HIT_ANIMATION_DURATION:
                agent.velocity = (0.0, 0.0)
                continue
            if (
                agent.animation == "attack"
                and agent.animation_time < agent.attack_animation_duration
            ):
                agent.velocity = (0.0, 0.0)
                continue
            target = lookup.get(agent.target_id) if agent.target_id is not None else None
            if target is None or not target.alive:
                self._return_to_guard_post(agent, active, dt)
                continue
            slot = agent.engagement_slot % MAX_MELEE_SLOTS
            angle = slot * math.tau / MAX_MELEE_SLOTS + (target.unit_id % 13) * 0.07
            radius = agent.attack_range - 2.0
            desired = (
                target.position[0] + math.cos(angle) * radius,
                target.position[1] + math.sin(angle) * radius * 0.72,
            )
            distance = math.dist(agent.position, target.position)
            if distance <= agent.attack_range + 2.0 and agent.opening_delay > 0.0:
                agent.opening_delay = max(0.0, agent.opening_delay - dt)
                agent.animation = "idle"
                agent.velocity = (0.0, 0.0)
            elif distance <= agent.attack_range + 2.0 and agent.attack_cooldown <= 0.0:
                agent.facing = self._direction(agent.position, target.position, agent.facing)
                agent.animation = "attack"
                agent.animation_time = 0.0
                agent.pending_target_id = target.unit_id
                agent.impact_timer = agent.impact_delay
                agent.attack_cooldown = 1.0 / max(0.01, agent.attack_speed)
                agent.opening_delay = 0.0
                agent.velocity = (0.0, 0.0)
                sound = (
                    "spear_thrust"
                    if agent.unit_type is BattleUnitType.DEFENDER
                    else "sword_swing"
                )
                self._emit_sound(sound, 0.08)
            elif distance > agent.attack_range:
                self._move_agent(agent, desired, active, dt)
            else:
                agent.animation = "idle"
                agent.velocity = (0.0, 0.0)

        if resolve_overlaps:
            self._resolve_overlaps(active)
        self._apply_agent_damage(queued_damage)

    def _return_to_guard_post(
        self,
        agent,
        active,
        dt,
    ):
        if (
            agent.unit_type is BattleUnitType.DEFENDER
            and agent.home_position is not None
            and math.dist(agent.position, agent.home_position) > 3.0
        ):
            self._move_agent(agent, agent.home_position, active, dt)
            return
        agent.animation = "idle"
        agent.velocity = (0.0, 0.0)

    def _move_agent(
        self,
        agent,
        destination,
        active,
        dt,
    ):
        dx = destination[0] - agent.position[0]
        dy = destination[1] - agent.position[1]
        distance = max(0.01, math.hypot(dx, dy))
        if agent.guard_radius is not None:
            destination = self._clamp_to_guard_radius(destination, agent.guard_radius)
            dx = destination[0] - agent.position[0]
            dy = destination[1] - agent.position[1]
            distance = max(0.01, math.hypot(dx, dy))
        vx = dx / distance * agent.move_speed
        vy = dy / distance * agent.move_speed
        speed = max(0.01, math.hypot(vx, vy))
        if speed > agent.move_speed:
            vx *= agent.move_speed / speed
            vy *= agent.move_speed / speed
        agent.velocity = (vx, vy)
        agent.facing = self._direction((0.0, 0.0), agent.velocity, agent.facing)
        agent.position = (agent.position[0] + vx * dt, agent.position[1] + vy * dt)
        agent.animation = "run"

    def _clamp_to_guard_radius(self, point, radius):
        dx = point[0] - self.center[0]
        dy = point[1] - self.center[1]
        distance = math.hypot(dx, dy)
        if distance <= radius or distance <= 0.01:
            return point
        return (
            self.center[0] + dx / distance * radius,
            self.center[1] + dy / distance * radius,
        )

    def _step_neutral_retreat(self, dt):
        neutral_agents = sorted(
            (agent for agent in self.living_agents if agent.neutral),
            key=lambda item: item.unit_id,
        )
        for index, agent in enumerate(neutral_agents):
            angle = index * math.tau / max(1, len(neutral_agents)) - math.pi / 2.0
            destination = (
                self.center[0] + math.cos(angle) * 112.0,
                self.center[1] + math.sin(angle) * 76.0,
            )
            if math.dist(agent.position, destination) > 3.0:
                self._move_agent(agent, destination, neutral_agents, dt)
            else:
                agent.animation = "idle"
                agent.velocity = (0.0, 0.0)

    def _apply_agent_damage(
        self,
        queued_damage,
    ):
        grouped = {}
        targets = {}
        for attacker, target, damage in queued_damage:
            grouped.setdefault(target.unit_id, []).append((attacker, damage))
            targets[target.unit_id] = target
        for target_id in sorted(grouped):
            target = targets[target_id]
            if not target.alive:
                continue
            entries = grouped[target_id]
            damage = sum(item[1] for item in entries)
            if (
                self.arena_type is BattleArenaType.TERRITORY
                and target.owner is self.target.owner
            ):
                damage *= float(getattr(self.target, "damage_taken_multiplier", 1.0))
            target.hp -= damage
            target.hit_flash = 1.0
            self.damage_flash = 1.0
            attacker = entries[0][0]
            self._spawn_impact(target.position, attacker.color, "steel")
            self._emit_sound("metal_hit", 0.07)
            if target.hp <= 0.0:
                target.hp = 0.0
                target.animation = "death"
                target.animation_time = 0.0
                target.death_elapsed = 0.0
                target.target_id = None
                target.pending_target_id = None
                target.velocity = self._knockback_velocity(attacker.position, target.position)
                sound = (
                    "defender_down"
                    if target.unit_type is BattleUnitType.DEFENDER
                    else "soldier_down"
                )
                self._emit_sound(sound, 0.14)
            else:
                target.animation = "hit"
                target.animation_time = 0.0

    def _static_defender_attack(self, dt):
        if self.arena_type is not BattleArenaType.TERRITORY:
            return
        if self._queen_cooldown > 0.0 or not self.target.queen.is_alive:
            return
        targets = [
            agent
            for agent in self.living_agents
            if not agent.neutral and agent.owner is not self.target.owner
        ]
        if not targets:
            return
        target = min(targets, key=lambda agent: (math.dist(self.center, agent.position), agent.unit_id))
        damage = cfg.QUEEN_ATK * float(getattr(self.target.owner, "attack_multiplier", 1.0))
        target.hp -= damage
        target.hit_flash = 1.0
        target.animation = "death" if target.hp <= 0.0 else "hit"
        target.animation_time = 0.0
        if target.hp <= 0.0:
            target.hp = 0.0
            target.death_elapsed = 0.0
            target.target_id = None
            target.pending_target_id = None
            target.velocity = self._knockback_velocity(self.center, target.position)
        self._queen_cooldown = 1.0 / max(0.01, cfg.QUEEN_ATK_SPEED)
        self.damage_flash = 1.0
        self._spawn_impact(target.position, self.target.owner.color, "magic")
        self._emit_sound("shield_hit", 0.11)

    def _step_core_assault(self, dt):
        attackers = [
            agent
            for agent in self.living_agents
            if not agent.neutral and agent.owner is not self.target.owner
        ]
        if self.arena_type is BattleArenaType.OBJECTIVE:
            attackers = [agent for agent in self.living_agents if not agent.neutral]
        if not attackers:
            self._refresh_phase()
            return
        winner = attackers[0].owner
        core_damage = 0.0
        ordered = sorted(attackers, key=lambda item: item.unit_id)
        for index, agent in enumerate(ordered):
            agent.attack_cooldown = max(0.0, agent.attack_cooldown - dt)
            if agent.impact_timer > 0.0:
                agent.impact_timer -= dt
                if agent.impact_timer <= 0.0 and agent.pending_target_id == -1:
                    core_damage += agent.attack_damage * float(
                        getattr(agent.owner, "attack_multiplier", 1.0)
                    )
                    agent.pending_target_id = None
                continue
            slots_per_ring = 12
            ring = index // slots_per_ring
            slot = index % slots_per_ring
            angle = slot * math.tau / min(slots_per_ring, max(1, len(ordered) - ring * slots_per_ring))
            radius = 64.0 + ring * 24.0
            destination = (
                self.center[0] + math.cos(angle) * radius,
                self.center[1] + math.sin(angle) * radius * 0.68 + 8.0,
            )
            if math.dist(agent.position, destination) > 3.0:
                self._move_agent(agent, destination, attackers, dt)
            elif agent.opening_delay > 0.0:
                agent.opening_delay = max(0.0, agent.opening_delay - dt)
                agent.animation = "idle"
                agent.velocity = (0.0, 0.0)
            elif agent.attack_cooldown <= 0.0:
                agent.facing = self._direction(agent.position, self.center, agent.facing)
                agent.animation = "attack"
                agent.animation_time = 0.0
                agent.pending_target_id = -1
                agent.impact_timer = agent.impact_delay
                agent.attack_cooldown = 1.0 / max(0.01, agent.attack_speed)
                agent.opening_delay = 0.0
                agent.velocity = (0.0, 0.0)
                self._emit_sound("sword_swing", 0.08)
            else:
                agent.animation = "idle"
                agent.velocity = (0.0, 0.0)

        self._resolve_overlaps(attackers)

        # Queen/core retaliation and Soldier impacts are resolved in the same step.
        queen_target = None
        queen_damage = 0.0
        if (
            self.arena_type is BattleArenaType.TERRITORY
            and self._queen_cooldown <= 0.0
            and self.target.queen.is_alive
        ):
            queen_target = min(
                attackers,
                key=lambda agent: (math.dist(self.center, agent.position), agent.unit_id),
            )
            queen_damage = cfg.QUEEN_ATK * float(
                getattr(self.target.owner, "attack_multiplier", 1.0)
            )
            self._queen_cooldown = 1.0 / max(0.01, cfg.QUEEN_ATK_SPEED)

        if core_damage > 0.0:
            core_damage *= float(getattr(self.target, "damage_taken_multiplier", 1.0))
            remaining = core_damage
            if self.arena_type is BattleArenaType.TERRITORY and self.target.workers.is_alive:
                remaining -= self.target.workers.take_damage(remaining)
            if remaining > 0.0 and self.target.queen.is_alive:
                self.target.queen.take_damage(remaining)
            self.damage_flash = 1.0
            self._spawn_impact(self.center, attackers[0].color, "stone", 0.42)
            self._emit_sound("stone_hit", 0.09)

        if queen_target is not None and queen_damage > 0.0:
            queen_target.hp -= queen_damage
            queen_target.hit_flash = 1.0
            queen_target.animation = "death" if queen_target.hp <= 0.0 else "hit"
            queen_target.animation_time = 0.0
            if queen_target.hp <= 0.0:
                queen_target.hp = 0.0
                queen_target.death_elapsed = 0.0
                queen_target.target_id = None
                queen_target.pending_target_id = None
                queen_target.velocity = self._knockback_velocity(
                    self.center, queen_target.position
                )
            self.damage_flash = 1.0
            self._spawn_impact(queen_target.position, self.target.owner.color, "magic")
            self._emit_sound("shield_hit", 0.11)

        if not self.target.queen.is_alive:
            survivors = [agent for agent in self.living_agents if agent.owner is winner]
            self._queue_outcome(winner, True, self._survivors(survivors))
        elif not any(agent.alive for agent in attackers):
            if self.arena_type is BattleArenaType.OBJECTIVE:
                neutral = [agent for agent in self.living_agents if agent.neutral]
                self._queue_outcome(None, False, self._survivors(neutral))
            else:
                defenders = [agent for agent in self.living_agents if agent.owner is self.target.owner]
                self._queue_outcome(self.target.owner, False, self._survivors(defenders))

    @staticmethod
    def _survivors(agents):
        return tuple(
            BattleSurvivor(agent.owner, agent.export_state())
            for agent in sorted(agents, key=lambda item: item.unit_id)
            if agent.alive
        )

    def _queue_outcome(
        self,
        winner,
        captured,
        survivors,
    ):
        if self._pending_outcome is not None:
            return
        self.phase = BattlePhase.RESOLVED
        self._pending_outcome = BattleOutcome(
            arena_type=self.arena_type,
            target_id=self.target_id,
            winner=winner,
            captured=captured,
            survivors=survivors,
        )
        self._resolution_timer = DEATH_VISUAL_DURATION

    @staticmethod
    def _direction(start, end, fallback):
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = math.hypot(dx, dy)
        if length <= 0.01:
            return fallback
        return dx / length, dy / length

    @staticmethod
    def _knockback_velocity(attacker, target):
        dx = target[0] - attacker[0]
        dy = target[1] - attacker[1]
        length = max(0.01, math.hypot(dx, dy))
        return dx / length * 28.0, dy / length * 18.0

    def _emit_sound(self, name, cooldown):
        if name in self._sound_cooldowns:
            return
        self._sound_cooldowns[name] = cooldown
        self._sound_events.append(name)

    def _spawn_impact(
        self,
        position,
        color,
        kind,
        ttl = 0.32,
    ):
        if self._impact_pool:
            impact = self._impact_pool.pop()
            impact.position = position
            impact.color = color
            impact.kind = kind
            impact.ttl = ttl
        else:
            impact = BattleImpact(position, color, kind, ttl)
        self.impacts.append(impact)

    @staticmethod
    def _resolve_overlaps(agents):
        """Deterministic positional correction after local steering."""
        living = sorted((agent for agent in agents if agent.alive), key=lambda item: item.unit_id)
        minimum = AGENT_RADIUS * 2.0
        # One grid pass is sufficient in mass battles and avoids doubling the
        # neighbor scan when 120+ individually rendered agents are active.
        passes = 1 if len(living) > 120 else 2
        for _ in range(passes):
            buckets = {}
            for agent in living:
                cell = (
                    math.floor(agent.position[0] / minimum),
                    math.floor(agent.position[1] / minimum),
                )
                buckets.setdefault(cell, []).append(agent)
            for first in living:
                cell_x = math.floor(first.position[0] / minimum)
                cell_y = math.floor(first.position[1] / minimum)
                neighbors = (
                    second
                    for offset_y in (-1, 0, 1)
                    for offset_x in (-1, 0, 1)
                    for second in buckets.get((cell_x + offset_x, cell_y + offset_y), ())
                    if second.unit_id > first.unit_id
                )
                for second in neighbors:
                    dx = second.position[0] - first.position[0]
                    dy = second.position[1] - first.position[1]
                    distance = math.hypot(dx, dy)
                    if distance >= minimum:
                        continue
                    if distance <= 0.01:
                        angle = ((first.unit_id * 37 + second.unit_id * 17) % 360) * math.pi / 180.0
                        nx, ny = math.cos(angle), math.sin(angle)
                        distance = 0.01
                    else:
                        nx, ny = dx / distance, dy / distance
                    correction = (minimum - distance) * 0.5
                    first.position = (
                        first.position[0] - nx * correction,
                        first.position[1] - ny * correction,
                    )
                    second.position = (
                        second.position[0] + nx * correction,
                        second.position[1] + ny * correction,
                    )
