"""Central gameplay constants for Quadrant Wars.

Balance changelog:
- Initial balanced profile favors 3-8 minute bot matches by making workers useful
  but increasingly expensive, while keeping queen defense strong enough to stop
  early all-in rushes.
- Soldier travel is distance-based to preserve real-time counterplay.
- Bot balance pass: strategies use distinct worker caps and late-game pressure.
  In a 50-match batch for 2/3/4 players, no personality exceeded 65% wins,
  average match time stayed around 5.8-7.4 minutes, and no match ended under 30s.
"""

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
FPS = 60

MIN_PLAYERS = 2
MAX_PLAYERS = 4

STARTING_FOOD = 45.0
STARTING_SOLDIERS = 6
STARTING_WORKERS = 1
STARTING_QUEENS = 1

FOOD_PER_WORKER_PER_SECOND = 4.2
SOLDIER_COST = 18
WORKER_BASE_COST = 55
WORKER_COST_GROWTH = 1.34

QUEEN_COMBAT_VALUE = 4
WORKER_COMBAT_VALUE = 2

SOLDIER_TRAVEL_SPEED = 165.0
BOT_DECISION_INTERVAL = 0.75
BOT_MIN_ATTACK_INTERVAL = 5.0

BOT_DEFENSE_RESERVE_RATIO = 0.35
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
