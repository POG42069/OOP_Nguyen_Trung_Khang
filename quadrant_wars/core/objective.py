
from enum import Enum, auto

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.unit import Queen, Soldier, SoldierState, Worker


class WorldObjectiveType(Enum):
    CARAVAN = auto()
    WAR_BANNER = auto()
    ANCIENT_SHRINE = auto()


class WorldObjectiveState(Enum):
    TELEGRAPHING = auto()
    ACTIVE = auto()
    CONTESTED = auto()
    RESOLVED = auto()


class NeutralGuardian:
    name = "Neutral Guardians"
    color = (143, 132, 105)
    is_alive = True
    attack_multiplier = 1.0


class WorldObjective:
    """A persistent neutral combat target that never becomes territory."""

    def __init__(
        self,
        objective_id,
        objective_type,
        position,
    ):
        self._id = objective_id
        self._objective_type = objective_type
        self._position = position
        self._state = WorldObjectiveState.TELEGRAPHING
        self._owner = NeutralGuardian()
        self._queen = Queen(1)
        self._queen.take_damage(max(0.0, self._queen.front_hp - cfg.OBJECTIVE_CORE_HP))
        self._workers = Worker(0)
        self._soldiers = Soldier(cfg.OBJECTIVE_GUARDS)
        self._elapsed = 0.0
        self._captured_by = None
        self._surviving_attackers = 0

    @property
    def id(self):
        return self._id

    @property
    def objective_type(self):
        return self._objective_type

    @property
    def state(self):
        return self._state

    @property
    def active(self):
        return self._state in (WorldObjectiveState.ACTIVE, WorldObjectiveState.CONTESTED)

    @property
    def elapsed(self):
        return self._elapsed

    @property
    def centroid(self):
        return self._position

    @property
    def polygon(self):
        x, y = self._position
        return [(x - 28, y - 20), (x + 28, y - 20), (x + 28, y + 20), (x - 28, y + 20)]

    @property
    def owner(self):
        return self._owner

    @owner.setter
    def owner(self, value):
        return None

    @property
    def queen(self):
        return self._queen

    @property
    def workers(self):
        return self._workers

    @property
    def soldiers(self):
        return self._soldiers

    @property
    def damage_taken_multiplier(self):
        return 1.0

    @property
    def core_hp(self):
        return self._queen.front_hp

    @property
    def core_max_hp(self):
        return cfg.OBJECTIVE_CORE_HP

    @property
    def captured_by(self):
        return self._captured_by

    @property
    def surviving_attackers(self):
        return self._surviving_attackers

    @property
    def display_name(self):
        return self._objective_type.name.replace("_", " ").title()

    @property
    def defense_value_legacy(self):
        return self._soldiers.total_combat_value + 2

    def update(self, dt):
        self._elapsed += dt

    def activate(self):
        if self._state is WorldObjectiveState.TELEGRAPHING:
            self._state = WorldObjectiveState.ACTIVE

    def start_contest(self):
        if self.active:
            self._state = WorldObjectiveState.CONTESTED

    def end_contest(self):
        if self._state is WorldObjectiveState.CONTESTED:
            self._state = WorldObjectiveState.ACTIVE

    def add_soldiers(self, amount):
        self._soldiers.add(amount)

    def remove_soldiers(self, amount):
        return self._soldiers.remove(amount)

    def detach_soldiers(self, amount):
        return [
            SoldierState(unit_id=-1, hp=hp, source_id=-1)
            for hp in self._soldiers.detach_hp(amount)
        ]

    def receive_soldiers(self, soldiers):
        self._soldiers.add_with_hp([soldier.hp for soldier in soldiers])

    def reset_after_capture(
        self,
        new_owner,
        surviving_soldiers,
    ):
        self._captured_by = new_owner
        if isinstance(surviving_soldiers, int):
            self._surviving_attackers = surviving_soldiers
        else:
            self._surviving_attackers = sum(1 for _ in surviving_soldiers)
        self._state = WorldObjectiveState.RESOLVED
