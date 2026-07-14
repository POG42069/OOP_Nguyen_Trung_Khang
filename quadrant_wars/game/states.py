from __future__ import annotations

from enum import Enum, auto

import pygame

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.objective import WorldObjective
from quadrant_wars.core.player import HumanPlayer
from quadrant_wars.core.territory import TerritorySpecialization
from quadrant_wars.game.game_manager import Match
from quadrant_wars.ui.art import menu_background
from quadrant_wars.ui.renderer import Renderer
from quadrant_wars.ui.widgets import Button


class PlayerMenuState(Enum):
    IDLE = auto()
    SUMMON = auto()
    ATTACK_TARGET = auto()
    ATTACK_AMOUNT = auto()
    STRATEGY = auto()
    DEVELOPMENT = auto()


DEVELOPMENT_CHOICES: tuple[TerritorySpecialization | None, ...] = (
    TerritorySpecialization.ECONOMY,
    TerritorySpecialization.BARRACKS,
    TerritorySpecialization.FORTRESS,
    None,
)

RECRUIT_CHOICES: tuple[str | None, ...] = ("soldier", "worker", None)


class PlayerInput:
    """Tracks the current menu state for one human player."""

    def __init__(self, player_index: int, keys: tuple[int, int, int]) -> None:
        self.player_index = player_index
        self.key1, self.key2, self.key3 = keys
        self.state = PlayerMenuState.IDLE
        self.target: object | None = None
        self.target_territory_ids: list[int] = []
        self.summon_territory_ids: list[int] = []
        self.summon_territory_index = 0
        self.summon_choice_index = 0
        self.development_territory_ids: list[int] = []
        self.development_territory_index = 0
        self.development_choice_index = 0
        self.message = ""

    def reset(self) -> None:
        self.state = PlayerMenuState.IDLE
        self.target = None
        self.target_territory_ids = []
        self.summon_territory_ids = []
        self.summon_territory_index = 0
        self.summon_choice_index = 0
        self.development_territory_ids = []
        self.development_territory_index = 0
        self.development_choice_index = 0
        self.message = ""

    def to_dict(self) -> dict:
        return {
            "state": self.state.name.lower(),
            "target": self.target,
            "target_territories": self.target_territory_ids,
            "summon_territories": self.summon_territory_ids,
            "summon_index": self.summon_territory_index,
            "summon_choice": self.summon_choice_index,
            "development_territories": self.development_territory_ids,
            "development_index": self.development_territory_index,
            "development_choice": self.development_choice_index,
            "message": self.message,
        }


# Key assignments: (Key1, Key2, Key3) for each player slot
PLAYER_KEYS = [
    (pygame.K_q, pygame.K_w, pygame.K_e),       # Player 1
    (pygame.K_i, pygame.K_o, pygame.K_p),       # Player 2
    (pygame.K_z, pygame.K_x, pygame.K_c),       # Player 3
    (pygame.K_b, pygame.K_n, pygame.K_m),       # Player 4
]

# Keycodes are layout-aware while scancodes identify the physical key.  Keep
# both so the commands still work with an IME or a non-QWERTY keyboard layout.
PLAYER_SCANCODES = [
    (pygame.KSCAN_Q, pygame.KSCAN_W, pygame.KSCAN_E),
    (pygame.KSCAN_I, pygame.KSCAN_O, pygame.KSCAN_P),
    (pygame.KSCAN_Z, pygame.KSCAN_X, pygame.KSCAN_C),
    (pygame.KSCAN_B, pygame.KSCAN_N, pygame.KSCAN_M),
]

KEY_LABELS = [
    ("Q", "W", "E"),
    ("I", "O", "P"),
    ("Z", "X", "C"),
    ("B", "N", "M"),
]


def _command_key_from_event(event: pygame.event.Event, player_index: int) -> int | None:
    """Resolve a player command from keycode, physical key, or text input."""
    keys = PLAYER_KEYS[player_index]
    event_key = getattr(event, "key", None)
    if event_key in keys:
        return event_key

    scancode = getattr(event, "scancode", None)
    physical_keys = PLAYER_SCANCODES[player_index]
    if scancode in physical_keys:
        return keys[physical_keys.index(scancode)]

    character = getattr(event, "unicode", "").casefold()
    for key, label in zip(keys, KEY_LABELS[player_index]):
        if character == label.casefold():
            return key
    return None


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
        panel_x = 42
        buttons = [
            Button(pygame.Rect(panel_x, 530, 344, 52), "START BATTLE", "start"),
            Button(pygame.Rect(panel_x, 596, 344, 42), "EXIT", "exit"),
        ]

        row_x = panel_x
        row_y = 205
        row_h = 44
        spacing = 54

        buttons.extend([
            Button(pygame.Rect(row_x + 214, row_y, 34, row_h), "<", "dec"),
            Button(pygame.Rect(row_x + 300, row_y, 34, row_h), ">", "inc"),
        ])

        for i in range(4):
            y = row_y + spacing * (i + 1)
            buttons.extend([
                Button(pygame.Rect(row_x + 214, y, 34, row_h), "<", f"toggle_l:{i}"),
                Button(pygame.Rect(row_x + 300, y, 34, row_h), ">", f"toggle_r:{i}"),
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
        _draw_menu_background(screen, self._anim_t)
        panel_rect = pygame.Rect(20, 20, 400, cfg.WINDOW_HEIGHT - 40)
        _draw_glass_panel(screen, panel_rect)

        brand = self._title.render("QUADRANT", True, (255, 246, 219))
        brand_2 = self._big.render("WARS", True, cfg.ACCENT_2)
        screen.blit(brand, (42, 42))
        screen.blit(brand_2, (44, 101))
        sub = self._small.render("COMMAND THE FRONTIER", True, (183, 194, 187))
        screen.blit(sub, (45, 151))
        pygame.draw.line(screen, (215, 160, 65), (42, 184), (386, 184), 2)

        row_x = 42
        row_y = 205
        row_w = 344
        row_h = 44
        spacing = 54

        mouse_pos = pygame.mouse.get_pos()

        def draw_row(y: int, name: str, value: str, inactive: bool = False, color: tuple[int, int, int] | None = None) -> None:
            rect = pygame.Rect(row_x, y, row_w, row_h)
            hover = rect.collidepoint(mouse_pos) and not inactive
            bg_color = (36, 43, 42, 224) if hover else (23, 29, 29, 210)
            row_surf = pygame.Surface((row_w, row_h), pygame.SRCALPHA)
            pygame.draw.rect(row_surf, bg_color, row_surf.get_rect(), border_radius=5)
            screen.blit(row_surf, rect)
            border_color = (195, 156, 78) if hover else (76, 86, 82)
            pygame.draw.rect(screen, border_color, rect, 1, border_radius=5)

            text_color = (94, 101, 98) if inactive else (226, 230, 218)
            if color is not None:
                pygame.draw.circle(screen, color if not inactive else (72, 75, 72), (row_x + 17, y + row_h // 2), 7)
                label_x = row_x + 34
            else:
                label_x = row_x + 14
            name_surf = self._small.render(name, True, text_color)
            screen.blit(name_surf, (label_x, y + 12))

            if not inactive:
                arr_c = (239, 202, 126)
                for bx, symbol in ((row_x + 214, "<"), (row_x + 300, ">")):
                    button_rect = pygame.Rect(bx, y + 5, 34, 34)
                    pygame.draw.rect(screen, (45, 51, 49), button_rect, border_radius=4)
                    pygame.draw.rect(screen, (91, 101, 96), button_rect, 1, border_radius=4)
                    arrow = self._font.render(symbol, True, arr_c)
                    screen.blit(arrow, arrow.get_rect(center=button_rect.center))
                val_surf = self._small.render(value, True, (255, 247, 224))
                screen.blit(val_surf, val_surf.get_rect(center=(row_x + 274, y + row_h // 2)))

        draw_row(row_y, "ARMIES", str(self._player_count))

        for i in range(4):
            y = row_y + spacing * (i + 1)
            if i < self._player_count:
                p_type = "HUMAN" if self._types[i] == "Player" else "AI BOT"
                draw_row(y, f"PLAYER {i + 1}", p_type, color=cfg.PLAYER_COLORS[i])
            else:
                draw_row(y, f"PLAYER {i + 1}", "CLOSED", True, cfg.PLAYER_COLORS[i])

        layout = self._layout()
        layout[0].draw(screen, self._small)
        exit_button = layout[1]
        pygame.draw.rect(screen, (24, 29, 29), exit_button.rect, border_radius=5)
        pygame.draw.rect(screen, (90, 98, 94), exit_button.rect, 1, border_radius=5)
        exit_text = self._small.render("EXIT", True, (177, 184, 178))
        screen.blit(exit_text, exit_text.get_rect(center=exit_button.rect.center))

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
            for pi in self._player_inputs.values():
                command_key = _command_key_from_event(event, pi.player_index)
                if command_key is not None:
                    self._handle_player_key(pi, command_key, None)
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
                pi.summon_territory_ids = [
                    territory.id for territory in self._match.territories_of(player)
                ]
                pi.summon_territory_index = pi.summon_territory_ids.index(home.id)
                pi.summon_choice_index = 0
                pi.message = ""
                pi.state = PlayerMenuState.SUMMON
                self._queue_sound("click")
            elif key == pi.key2:
                pi.target_territory_ids = _other_territory_indices(home.id, len(self._match.territories))
                pi.state = PlayerMenuState.ATTACK_TARGET
                self._queue_sound("click")
            elif key == pi.key3:
                pi.state = PlayerMenuState.STRATEGY
                pi.message = ""
                self._queue_sound("click")

        elif pi.state == PlayerMenuState.SUMMON:
            self._refresh_summon_selection(pi, player)
            if not pi.summon_territory_ids:
                pi.reset()
                return
            if key == pi.key1:
                pi.summon_territory_index = (
                    pi.summon_territory_index + 1
                ) % len(pi.summon_territory_ids)
                pi.message = ""
                self._queue_sound("click")
            elif key == pi.key2:
                pi.summon_choice_index = (
                    pi.summon_choice_index + 1
                ) % len(RECRUIT_CHOICES)
                pi.message = ""
                self._queue_sound("click")
            elif key == pi.key3:
                choice = RECRUIT_CHOICES[pi.summon_choice_index]
                if choice is None:
                    pi.reset()
                    self._queue_sound("click")
                    return
                territory_id = pi.summon_territory_ids[pi.summon_territory_index]
                territory = self._match.territories[territory_id]
                success = territory.buy_soldier() if choice == "soldier" else territory.buy_worker()
                if success:
                    self._queue_sound("recruit")
                    pi.reset()
                else:
                    cost = territory.soldier_cost if choice == "soldier" else territory.worker_cost()
                    pi.message = f"Need {cost} gold in T{territory.id + 1}"
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
                    if isinstance(pi.target, WorldObjective):
                        issued = self._match.issue_objective_attack(source, amount)
                    else:
                        issued = self._match.issue_attack(source, pi.target, amount)
                    if issued:
                        success = True
                if success:
                    self._queue_sound("attack")
                else:
                    self._queue_sound("click")
                pi.reset()

        elif pi.state == PlayerMenuState.STRATEGY:
            if key == pi.key1:
                pi.development_territory_ids = [
                    territory.id for territory in self._match.territories_of(player)
                ]
                pi.development_territory_index = 0
                pi.development_choice_index = 0
                pi.message = ""
                pi.state = PlayerMenuState.DEVELOPMENT
                self._queue_sound("click")
            elif key == pi.key2:
                objective = self._match.world_objective
                if objective is not None and objective.active:
                    pi.target = objective
                    pi.state = PlayerMenuState.ATTACK_AMOUNT
                    pi.message = ""
                    self._queue_sound("click")
                else:
                    pi.message = "Objective is not ready"
                    self._queue_sound("click")
            elif key == pi.key3:
                pi.reset()
                self._queue_sound("click")

        elif pi.state == PlayerMenuState.DEVELOPMENT:
            self._refresh_development_selection(pi, player)
            if not pi.development_territory_ids:
                pi.reset()
                return
            if key == pi.key1:
                pi.development_territory_index = (
                    pi.development_territory_index + 1
                ) % len(pi.development_territory_ids)
                pi.message = ""
                self._queue_sound("click")
            elif key == pi.key2:
                pi.development_choice_index = (
                    pi.development_choice_index + 1
                ) % len(DEVELOPMENT_CHOICES)
                pi.message = ""
                self._queue_sound("click")
            elif key == pi.key3:
                choice = DEVELOPMENT_CHOICES[pi.development_choice_index]
                if choice is None:
                    pi.reset()
                    self._queue_sound("click")
                    return
                territory_id = pi.development_territory_ids[pi.development_territory_index]
                result = self._match.develop_territory(player, territory_id, choice)
                pi.message = result.message
                if result.success:
                    pi.reset()
                    self._queue_sound("develop")
                else:
                    self._queue_sound("click")

    def _refresh_development_selection(self, pi: PlayerInput, player: HumanPlayer) -> None:
        current_id = None
        if pi.development_territory_ids:
            current_id = pi.development_territory_ids[
                min(pi.development_territory_index, len(pi.development_territory_ids) - 1)
            ]
        owned_ids = [territory.id for territory in self._match.territories_of(player)]
        pi.development_territory_ids = owned_ids
        if current_id in owned_ids:
            pi.development_territory_index = owned_ids.index(current_id)
        else:
            pi.development_territory_index = 0

    def _refresh_summon_selection(self, pi: PlayerInput, player: HumanPlayer) -> None:
        current_id = None
        if pi.summon_territory_ids:
            current_id = pi.summon_territory_ids[
                min(pi.summon_territory_index, len(pi.summon_territory_ids) - 1)
            ]
        owned_ids = [territory.id for territory in self._match.territories_of(player)]
        pi.summon_territory_ids = owned_ids
        if current_id in owned_ids:
            pi.summon_territory_index = owned_ids.index(current_id)
        else:
            pi.summon_territory_index = 0

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
    art = menu_background(screen.get_size())
    if art is not None:
        screen.blit(art, (0, 0))
        grade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        grade.fill((10, 14, 12, 28))
        screen.blit(grade, (0, 0))

        left_shade = pygame.Surface((560, cfg.WINDOW_HEIGHT), pygame.SRCALPHA)
        for x in range(left_shade.get_width()):
            ratio = x / left_shade.get_width()
            alpha = int(138 * (1.0 - ratio) ** 1.7)
            pygame.draw.line(left_shade, (3, 7, 6, alpha), (x, 0), (x, cfg.WINDOW_HEIGHT))
        screen.blit(left_shade, (0, 0))
    else:
        screen.fill(cfg.MENU_BG)
        for y in range(cfg.WINDOW_HEIGHT):
            frac = y / cfg.WINDOW_HEIGHT
            color = (int(17 + frac * 20), int(23 + frac * 24), int(23 + frac * 18))
            pygame.draw.line(screen, color, (0, y), (cfg.WINDOW_WIDTH, y))

    # Sparse embers are animated separately from the painted background.
    import math
    import random

    rng = random.Random(42)
    for i in range(18):
        base_x = rng.randint(430, cfg.WINDOW_WIDTH)
        base_y = rng.randint(60, cfg.WINDOW_HEIGHT)
        px = int(base_x + math.sin(t * 0.35 + i) * 22)
        py = int((base_y - t * (7 + i % 5)) % cfg.WINDOW_HEIGHT)
        alpha = 70 + int(40 * math.sin(t * 1.3 + i))
        pygame.draw.circle(screen, (245, 181, 84, max(20, alpha)), (px, py), 1 + i % 2)


def _draw_glass_panel(screen: pygame.Surface, rect: pygame.Rect) -> None:
    """Draw a frosted glass panel with glow border."""
    shadow = rect.move(0, 12)
    shadow_surf = pygame.Surface((shadow.width, shadow.height), pygame.SRCALPHA)
    pygame.draw.rect(shadow_surf, (0, 0, 0, 130), shadow_surf.get_rect(), border_radius=8)
    screen.blit(shadow_surf, shadow)

    panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(panel, (13, 18, 18, 222), panel.get_rect(), border_radius=8)
    screen.blit(panel, rect)

    pygame.draw.rect(screen, (83, 91, 85), rect, 1, border_radius=8)
    inner = rect.inflate(-6, -6)
    pygame.draw.rect(screen, (43, 50, 47), inner, 1, border_radius=6)


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
