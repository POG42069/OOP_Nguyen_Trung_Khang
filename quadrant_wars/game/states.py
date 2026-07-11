from __future__ import annotations

from enum import Enum, auto

import pygame

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.player import HumanPlayer
from quadrant_wars.game.game_manager import Match
from quadrant_wars.ui.renderer import Renderer
from quadrant_wars.ui.widgets import Button


class PlayerMenuState(Enum):
    IDLE = auto()
    SUMMON = auto()
    ATTACK_TARGET = auto()
    ATTACK_AMOUNT = auto()


class PlayerInput:
    """Tracks the current menu state for one human player."""

    def __init__(self, player_index: int, keys: tuple[int, int, int]) -> None:
        self.player_index = player_index
        self.key1, self.key2, self.key3 = keys
        self.state = PlayerMenuState.IDLE
        self.target: object | None = None
        self.target_territory_ids: list[int] = []

    def reset(self) -> None:
        self.state = PlayerMenuState.IDLE
        self.target = None

    def to_dict(self) -> dict:
        return {
            "state": self.state.name.lower(),
            "target": self.target,
            "target_territories": self.target_territory_ids,
        }


# Key assignments: (Key1, Key2, Key3) for each player slot
PLAYER_KEYS = [
    (pygame.K_q, pygame.K_w, pygame.K_e),       # Player 1
    (pygame.K_i, pygame.K_o, pygame.K_p),       # Player 2
    (pygame.K_z, pygame.K_x, pygame.K_c),       # Player 3
    (pygame.K_b, pygame.K_n, pygame.K_m),       # Player 4
]

KEY_LABELS = [
    ("Q", "W", "E"),
    ("I", "O", "P"),
    ("Z", "X", "C"),
    ("B", "N", "M"),
]


def _other_territory_indices(home_id: int, total_territories: int) -> list[int]:
    """Returns the other territory indices."""
    return [i for i in range(total_territories) if i != home_id]


class GameState:
    def _queue_sound(self, name: str) -> None:
        if not hasattr(self, "_sound_events"):
            self._sound_events = []
        self._sound_events.append(name)

    def pop_sound_events(self) -> list[str]:
        events = getattr(self, "_sound_events", [])[:]
        if hasattr(self, "_sound_events"):
            self._sound_events.clear()
        return events

    def handle_event(self, event: pygame.event.Event) -> "GameState":
        return self

    def update(self, dt: float) -> "GameState":
        return self

    def draw(self, screen: pygame.Surface) -> None:
        raise NotImplementedError


class MenuState(GameState):
    def __init__(self) -> None:
        self._player_count = 4
        self._types = ["Player", "Bot", "Bot", "Bot"]
        self._font: pygame.font.Font | None = None
        self._small: pygame.font.Font | None = None
        self._title: pygame.font.Font | None = None
        self._big: pygame.font.Font | None = None
        self._buttons: list[Button] = []
        self._anim_t = 0.0

    def _ensure_fonts(self) -> None:
        if self._font is None:
            self._font = pygame.font.SysFont("segoe ui light", 24)
            self._small = pygame.font.SysFont("segoe ui light", 18)
            self._title = pygame.font.SysFont("century gothic", 52, bold=True)
            self._big = pygame.font.SysFont("century gothic", 32)

    def _layout(self) -> list[Button]:
        # Left sidebar buttons
        sidebar_x = 40
        buttons = [
            Button(pygame.Rect(sidebar_x, 400, 200, 40), "START MATCH", "start"),
            Button(pygame.Rect(sidebar_x, 460, 200, 40), "EXIT", "exit"),
        ]
        
        # Right side rows (Item Name < Value >)
        row_x = 400
        row_y = 200
        row_w = 600
        row_h = 50
        spacing = 60

        buttons.extend([
            Button(pygame.Rect(row_x + 350, row_y, 40, row_h), "<", "dec"),
            Button(pygame.Rect(row_x + 520, row_y, 40, row_h), ">", "inc"),
        ])

        for i in range(4): # Max 4 players
            y = row_y + spacing * (i + 1)
            buttons.extend([
                Button(pygame.Rect(row_x + 350, y, 40, row_h), "<", f"toggle_l:{i}"),
                Button(pygame.Rect(row_x + 520, y, 40, row_h), ">", f"toggle_r:{i}"),
            ])

        return buttons

    def handle_event(self, event: pygame.event.Event) -> GameState:
        for button in self._layout():
            if button.clicked(event):
                self._queue_sound("click")
                if button.action == "start":
                    types = ["human" if t == "Player" else "bot" for t in self._types[: self._player_count]]
                    next_state = PlayingState(Match(types))
                    next_state._queue_sound("click")
                    return next_state
                elif button.action == "exit":
                    import sys
                    sys.exit(0)
                elif button.action == "dec":
                    self._player_count = max(cfg.MIN_PLAYERS, self._player_count - 1)
                elif button.action == "inc":
                    self._player_count = min(cfg.MAX_PLAYERS, self._player_count + 1)
                elif button.action.startswith("toggle_"):
                    idx = int(button.action.split(":")[1])
                    if idx < self._player_count:
                        self._types[idx] = "Bot" if self._types[idx] == "Player" else "Player"
        return self

    def update(self, dt: float) -> GameState:
        self._anim_t += dt
        return self

    def draw(self, screen: pygame.Surface) -> None:
        self._ensure_fonts()
        
        # 1. Background
        _draw_menu_background(screen, self._anim_t)
        
        # 2. Left Sidebar panel
        sidebar = pygame.Surface((300, cfg.WINDOW_HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(sidebar, (10, 15, 20, 180), sidebar.get_rect())
        pygame.draw.line(sidebar, (40, 100, 140, 200), (298, 0), (298, cfg.WINDOW_HEIGHT), 2)
        screen.blit(sidebar, (0, 0))

        # Sidebar text
        title_surf = self._title.render("SETUP", True, (160, 200, 240))
        screen.blit(title_surf, (40, 200))
        pygame.draw.line(screen, (80, 140, 180), (40, 260), (200, 260), 2)

        start_btn = self._small.render("START BATTLE", True, (255, 255, 255))
        screen.blit(start_btn, (60, 410))
        exit_btn = self._small.render("EXIT GAME", True, (150, 160, 170))
        screen.blit(exit_btn, (60, 470))

        # Top Right Logo Area
        logo_surf = self._title.render("QUADRANT WARS", True, (255, 255, 255))
        screen.blit(logo_surf, (cfg.WINDOW_WIDTH - logo_surf.get_width() - 40, 40))

        # 3. Right Side Settings Rows
        row_x = 400
        row_y = 200
        row_w = 600
        row_h = 50
        spacing = 60

        mouse_pos = pygame.mouse.get_pos()

        def draw_row(y: int, name: str, value: str, inactive: bool = False):
            rect = pygame.Rect(row_x, y, row_w, row_h)
            hover = rect.collidepoint(mouse_pos) and not inactive
            # Row Background
            bg_color = (20, 40, 60, 150) if hover else (15, 25, 35, 120)
            row_surf = pygame.Surface((row_w, row_h), pygame.SRCALPHA)
            pygame.draw.rect(row_surf, bg_color, row_surf.get_rect())
            screen.blit(row_surf, rect)
            # Row Border
            border_color = (60, 120, 180, 255) if hover else (40, 80, 120, 150)
            pygame.draw.rect(screen, border_color, rect, 1)

            # Name
            text_color = (100, 110, 120) if inactive else (220, 230, 240)
            name_surf = self._font.render(name, True, text_color)
            screen.blit(name_surf, (row_x + 20, y + 8))

            # Arrows & Value
            if not inactive:
                arr_c = (150, 200, 250)
                l_arr = self._font.render("<", True, arr_c)
                r_arr = self._font.render(">", True, arr_c)
                screen.blit(l_arr, (row_x + 365, y + 8))
                screen.blit(r_arr, (row_x + 535, y + 8))
                
                val_surf = self._font.render(value, True, (255, 255, 255))
                screen.blit(val_surf, val_surf.get_rect(center=(row_x + 450, y + 25)))

        # Player Count Row
        draw_row(row_y, "NUMBER OF PLAYERS", str(self._player_count))

        # Slot Rows
        for i in range(4):
            y = row_y + spacing * (i + 1)
            if i < self._player_count:
                p_type = self._types[i]
                draw_row(y, f"PLAYER SLOT {i+1}", p_type)
                # Draw color indicator
                pygame.draw.circle(screen, cfg.PLAYER_COLORS[i], (row_x + 200, y + 25), 8)
            else:
                draw_row(y, f"PLAYER SLOT {i+1}", "CLOSED", True)

        # Custom buttons are handled implicitly by invisible layout rectangles

class PlayingState(GameState):
    def __init__(self, match: Match) -> None:
        self._match = match
        self._renderer: Renderer | None = None
        self._sound_events: list[str] = []
        self._player_inputs: dict[int, PlayerInput] = {}
        for i, player in enumerate(match.players):
            if isinstance(player, HumanPlayer):
                pi = PlayerInput(i, PLAYER_KEYS[i])
                self._player_inputs[i] = pi

    def handle_event(self, event: pygame.event.Event) -> GameState:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return PauseState(self)
            keys = pygame.key.get_pressed()
            for pi in self._player_inputs.values():
                if event.key in (pi.key1, pi.key2, pi.key3):
                    self._handle_player_key(pi, event.key, keys)
                    break
        return self

    def _handle_player_key(self, pi: PlayerInput, key: int, pressed_keys: pygame.key.ScancodeWrapper) -> None:
        player = self._match.players[pi.player_index]
        if not isinstance(player, HumanPlayer) or not player.is_alive:
            return
        home = self._match.home_territory(player)
        if home is None:
            return

        if pi.state == PlayerMenuState.IDLE:
            if key == pi.key1:
                pi.state = PlayerMenuState.SUMMON
                self._queue_sound("click")
            elif key == pi.key2:
                pi.state = PlayerMenuState.ATTACK_TARGET
                self._queue_sound("click")
            elif key == pi.key3:
                # Key 3 targets supply drop if it exists
                if getattr(self._match, "supply_drop", None) is not None and self._match.supply_drop.active:
                    pi.target = self._match.supply_drop
                    pi.state = PlayerMenuState.ATTACK_AMOUNT
                    self._queue_sound("click")

        elif pi.state == PlayerMenuState.SUMMON:
            if key == pi.key1:
                # Buy soldier on all affordable territories
                success = False
                for t in self._match.territories_of(player):
                    if t.buy_soldier():
                        success = True
                self._queue_sound("recruit" if success else "click")
                pi.reset()
            elif key == pi.key2:
                success = False
                for t in self._match.territories_of(player):
                    if t.buy_worker():
                        success = True
                self._queue_sound("recruit" if success else "click")
                pi.reset()
            elif key == pi.key3:
                pi.reset()
                self._queue_sound("click")

        elif pi.state == PlayerMenuState.ATTACK_TARGET:
            # Recompute target_territory_ids based on current home
            pi.target_territory_ids = _other_territory_indices(home.id, len(self._match.territories))
            
            key_to_idx = {pi.key1: 0, pi.key2: 1, pi.key3: 2}
            selected = key_to_idx.get(key, -1)
            if 0 <= selected < len(pi.target_territory_ids):
                target_id = pi.target_territory_ids[selected]
                pi.target = self._match.territories[target_id]
                pi.state = PlayerMenuState.ATTACK_AMOUNT
                self._queue_sound("click")
            elif selected == -1 and key == pi.key3 and len(pi.target_territory_ids) < 3:
                pi.reset()
                self._queue_sound("click")

        elif pi.state == PlayerMenuState.ATTACK_AMOUNT:
            ratios = {pi.key1: 0.33, pi.key2: 0.66, pi.key3: 1.0}
            ratio = ratios.get(key)
            if ratio is not None and pi.target is not None:
                success = False
                # Launch attacks from ALL owned territories!
                for source in self._match.territories_of(player):
                    if source is pi.target:
                        continue # Don't attack yourself from yourself
                    amount = max(1, int(source.soldiers.count * ratio))
                    if self._match.issue_attack(source, pi.target, amount):
                        success = True
                if success:
                    self._queue_sound("attack")
                else:
                    self._queue_sound("click")
                pi.reset()

    def update(self, dt: float) -> GameState:
        self._match.update(dt)
        for pi in self._player_inputs.values():
            player = self._match.players[pi.player_index]
            if not player.is_alive:
                pi.reset()
        self._sound_events.extend(self._match.pop_sound_events())
        if self._match.winner is not None:
            game_over = GameOverState(self._match)
            game_over._sound_events.extend(self.pop_sound_events())
            return game_over
        return self

    def draw(self, screen: pygame.Surface) -> None:
        if self._renderer is None:
            self._renderer = Renderer(screen)
        player_states = {
            idx: pi.to_dict() for idx, pi in self._player_inputs.items()
        }
        self._renderer.draw_match(self._match, player_states)


class GameOverState(GameState):
    def __init__(self, match: Match) -> None:
        self._match = match
        self._winner_name = match.winner.name if match.winner else "Nobody"
        self._font: pygame.font.Font | None = None
        self._title: pygame.font.Font | None = None
        self._small: pygame.font.Font | None = None
        self._sound_events: list[str] = ["win"]
        self._anim_t = 0.0

    def handle_event(self, event: pygame.event.Event) -> GameState:
        if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
            return MenuState()
        return self

    def update(self, dt: float) -> GameState:
        self._anim_t += dt
        return self

    def draw(self, screen: pygame.Surface) -> None:
        if self._font is None:
            self._font = pygame.font.SysFont("segoeui", 24)
            self._title = pygame.font.SysFont("georgia", 62, bold=True)
            self._small = pygame.font.SysFont("segoeui", 16)
        assert self._font is not None and self._title is not None and self._small is not None
        _draw_menu_background(screen, self._anim_t)
        panel = pygame.Rect(290, 170, 700, 340)
        _draw_glass_panel(screen, panel)

        # Winner color bar
        winner = self._match.winner
        if winner:
            pygame.draw.rect(screen, winner.color, (panel.x, panel.y, panel.width, 6), border_radius=3)

        # Crown icon
        crown_y = 218
        for i, dx in enumerate([-16, -8, 0, 8, 16]):
            h = 22 if i % 2 == 0 else 14
            pygame.draw.rect(screen, (248, 208, 48), (cfg.WINDOW_WIDTH // 2 + dx - 4, crown_y - h, 8, h + 8), border_radius=2)
        pygame.draw.rect(screen, (218, 168, 28), (cfg.WINDOW_WIDTH // 2 - 22, crown_y + 4, 44, 6), border_radius=3)

        text = self._title.render(f"{self._winner_name} Wins!", True, (255, 248, 218))
        screen.blit(text, text.get_rect(center=(cfg.WINDOW_WIDTH // 2, 294)))

        # Stats
        time_text = self._font.render(f"Match Duration: {int(self._match.elapsed // 60)}:{int(self._match.elapsed % 60):02d}", True, cfg.MUTED_TEXT)
        screen.blit(time_text, time_text.get_rect(center=(cfg.WINDOW_WIDTH // 2, 350)))

        # Territory count
        if winner:
            owned = sum(1 for t in self._match.territories if t.owner is winner)
            terr_text = self._font.render(f"Territories Controlled: {owned}/{len(self._match.territories)}", True, cfg.ACCENT)
            screen.blit(terr_text, terr_text.get_rect(center=(cfg.WINDOW_WIDTH // 2, 390)))

        hint = self._small.render("Press any key or click to return to menu", True, cfg.MUTED_TEXT)
        screen.blit(hint, hint.get_rect(center=(cfg.WINDOW_WIDTH // 2, 450)))


def _draw_menu_background(screen: pygame.Surface, t: float = 0.0) -> None:
    import math
    screen.fill(cfg.MENU_BG)
    # Rich gradient
    for y in range(cfg.WINDOW_HEIGHT):
        frac = y / cfg.WINDOW_HEIGHT
        r = int(18 + frac * 32 + math.sin(t * 0.3 + frac * 3) * 4)
        g = int(20 + frac * 18 + math.sin(t * 0.4 + frac * 2) * 3)
        b = int(28 + frac * 12)
        pygame.draw.line(screen, (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))), (0, y), (cfg.WINDOW_WIDTH, y))

    # Floating particles
    import random
    rng = random.Random(42)
    for i in range(40):
        speed = rng.uniform(0.3, 1.2)
        base_x = rng.randint(0, cfg.WINDOW_WIDTH)
        base_y = rng.randint(0, cfg.WINDOW_HEIGHT)
        px = int(base_x + math.sin(t * speed + i * 0.7) * 60) % cfg.WINDOW_WIDTH
        py = int(base_y + math.cos(t * speed * 0.8 + i * 0.9) * 40) % cfg.WINDOW_HEIGHT
        alpha = int(80 + math.sin(t * 1.5 + i) * 40)
        r = max(2, int(4 + math.sin(t + i) * 2))
        colors = [(248, 208, 68), (228, 138, 58), (168, 88, 48), (108, 178, 218)]
        c = colors[i % len(colors)]
        particle = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(particle, (*c, max(0, min(255, alpha))), (r, r), r)
        screen.blit(particle, (px - r, py - r))

    # Territory silhouettes
    shapes = [
        ([(90, 120), (300, 70), (365, 210), (210, 300), (70, 250)], cfg.PLAYER_COLORS[0]),
        ([(930, 92), (1160, 120), (1194, 294), (1018, 338), (900, 220)], cfg.PLAYER_COLORS[1]),
        ([(110, 470), (314, 405), (418, 570), (245, 650), (74, 610)], cfg.PLAYER_COLORS[2]),
        ([(900, 500), (1128, 430), (1224, 594), (1045, 670), (872, 624)], cfg.PLAYER_COLORS[3]),
    ]
    for polygon, color in shapes:
        shadow = [(x + 8, y + 10) for x, y in polygon]
        pygame.draw.polygon(screen, (7, 9, 11), shadow)
        dark = tuple(max(0, c - 80) for c in color)
        pygame.draw.polygon(screen, dark, polygon)
        pygame.draw.polygon(screen, tuple(min(255, c + 40) for c in color), polygon, 2)


def _draw_glass_panel(screen: pygame.Surface, rect: pygame.Rect) -> None:
    """Draw a frosted glass panel with glow border."""
    shadow = rect.move(0, 12)
    shadow_surf = pygame.Surface((shadow.width, shadow.height), pygame.SRCALPHA)
    pygame.draw.rect(shadow_surf, (0, 0, 0, 120), shadow_surf.get_rect(), border_radius=22)
    screen.blit(shadow_surf, shadow)

    panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(panel, (24, 28, 36, 220), panel.get_rect(), border_radius=22)
    screen.blit(panel, rect)

    # Inner highlight
    pygame.draw.rect(screen, (58, 62, 72), rect, 2, border_radius=22)
    inner = rect.inflate(-6, -6)
    pygame.draw.rect(screen, (78, 82, 92), inner, 1, border_radius=20)


def fast_blur(surface: pygame.Surface, amount: float = 8.0) -> pygame.Surface:
    """Fast box blur using downscale and upscale."""
    size = surface.get_size()
    small_size = (max(1, int(size[0] / amount)), max(1, int(size[1] / amount)))
    small = pygame.transform.smoothscale(surface, small_size)
    return pygame.transform.smoothscale(small, size)


class PauseState(GameState):
    def __init__(self, playing_state: PlayingState) -> None:
        self._playing = playing_state
        self._font = pygame.font.SysFont("segoeui", 28, bold=True)
        self._title = pygame.font.SysFont("georgia", 52, bold=True)
        self._buttons = [
            Button(pygame.Rect(540, 300, 200, 50), "Resume", "resume"),
            Button(pygame.Rect(540, 380, 200, 50), "Restart", "restart"),
            Button(pygame.Rect(540, 460, 200, 50), "Main Menu", "menu"),
        ]
        self._bg_cache: pygame.Surface | None = None
        self._sound_events: list[str] = []

    def handle_event(self, event: pygame.event.Event) -> GameState:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return self._playing
        for button in self._buttons:
            if button.clicked(event):
                self._queue_sound("click")
                if button.action == "resume":
                    return self._playing
                elif button.action == "restart":
                    # Restart match with same players
                    from quadrant_wars.game.game_manager import Match
                    m = self._playing._match
                    types = ["human" if getattr(p, "_name", "").startswith("Player") else "bot" for p in m.players]
                    return PlayingState(Match(types))
                elif button.action == "menu":
                    return MenuState()
        return self

    def update(self, dt: float) -> GameState:
        return self

    def draw(self, screen: pygame.Surface) -> None:
        if self._bg_cache is None:
            # Capture the current frame and blur it
            temp = pygame.Surface(screen.get_size())
            self._playing.draw(temp)
            self._bg_cache = fast_blur(temp, 10.0)

        screen.blit(self._bg_cache, (0, 0))

        # Dim overlay
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((10, 10, 15, 120))
        screen.blit(overlay, (0, 0))

        # Pause Panel
        panel = pygame.Rect(440, 150, 400, 420)
        _draw_glass_panel(screen, panel)

        title = self._title.render("PAUSED", True, (255, 248, 228))
        screen.blit(title, title.get_rect(center=(cfg.WINDOW_WIDTH // 2, 220)))

        for button in self._buttons:
            button.draw(screen, self._font)
