"""Central gameplay constants for Quadrant Wars.

Balance changelog:
- Initial balanced profile favors 3-8 minute bot matches by making workers useful
  but increasingly expensive, while keeping queen defense strong enough to stop
  early all-in rushes.
- Soldier travel is distance-based to preserve real-time counterplay.
- Tempo pass: food and recruitment are faster, bots reserve fewer soldiers, and
  attack cooldowns are shorter so fights start earlier instead of waiting for a
  large safe advantage. In a 100-match batch for 2/3/4 bot players, average
  match time landed around 1.27-1.54 minutes, no match ended under 30 seconds,
  and the top strategy stayed at or below 60% wins.
"""

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
FPS = 60

MIN_PLAYERS = 2
MAX_PLAYERS = 4

STARTING_FOOD = 60.0
STARTING_SOLDIERS = 8
STARTING_WORKERS = 1
STARTING_QUEENS = 1

FOOD_PER_WORKER_PER_SECOND = 6.0
SOLDIER_COST = 14
WORKER_BASE_COST = 48
WORKER_COST_GROWTH = 1.34

QUEEN_COMBAT_VALUE = 4
WORKER_COMBAT_VALUE = 2

SOLDIER_TRAVEL_SPEED = 185.0
BOT_DECISION_INTERVAL = 0.55
BOT_MIN_ATTACK_INTERVAL = 2.8

BOT_DEFENSE_RESERVE_RATIO = 0.18
ATTACK_DEFAULT_RATIO = 0.5

MENU_BG = (17, 20, 26)
PANEL_BG = (29, 33, 40)
PANEL_BG_2 = (38, 42, 50)
CARD_BG = (244, 240, 229)
CARD_TEXT = (31, 34, 38)
CARD_MUTED = (91, 96, 104)
STROKE = (9, 12, 17)
TEXT = (244, 246, 240)
MUTED_TEXT = (178, 183, 188)
ACCENT = (68, 183, 201)
ACCENT_2 = (238, 159, 77)
WARNING = (245, 191, 89)
SUCCESS = (108, 195, 132)
SHADOW = (4, 7, 10)

PLAYER_COLORS = [
    (214, 84, 76),
    (70, 137, 214),
    (72, 170, 112),
    (219, 175, 73),
]
