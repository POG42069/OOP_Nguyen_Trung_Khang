from __future__ import annotations

import math
from enum import Enum, auto

import pygame

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.objective import WorldObjective
from quadrant_wars.core.player import HumanPlayer
from quadrant_wars.core.territory import TerritorySpecialization
from quadrant_wars.game.game_manager import Match, MatchResult
from quadrant_wars.ui.art import menu_background
from quadrant_wars.ui.renderer import Renderer
from quadrant_wars.ui.tutorial import TutorialView
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


def _attack_amount_for_ratio(soldiers: int, ratio: float) -> int:
    """Convert a percentage into whole units while preserving a defender."""
    if ratio <= 0.0 or soldiers <= 1:
        return 0
    return min(soldiers - 1, max(1, math.ceil(soldiers * ratio)))


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


class TransitionState(GameState):
    """Short fade-through-black that freezes both source and destination."""

    def __init__(
        self,
        source: GameState,
        target: GameState,
        duration: float = 0.4,
    ) -> None:
        self._source = source
        self._target = target
        self._duration = max(0.1, duration)
        self._elapsed = 0.0
        self._source_frame: pygame.Surface | None = None
        self._target_frame: pygame.Surface | None = None
        self._sound_events = source.pop_sound_events()

    @property
    def target(self) -> GameState:
        return self._target

    def handle_event(self, event: pygame.event.Event) -> GameState:
        return self

    def update(self, dt: float) -> GameState:
        self._elapsed += max(0.0, dt)
        if self._elapsed >= self._duration:
            for sound in self.pop_sound_events():
                self._target._queue_sound(sound)
            return self._target
        return self

    def draw(self, screen: pygame.Surface) -> None:
        if self._source_frame is None:
            self._source_frame = pygame.Surface(screen.get_size())
            self._source.draw(self._source_frame)
        if self._target_frame is None:
            self._target_frame = pygame.Surface(screen.get_size())
            self._target.draw(self._target_frame)

        progress = min(1.0, self._elapsed / self._duration)
        if progress < 0.5:
            screen.blit(self._source_frame, (0, 0))
            alpha = int(progress * 2.0 * 255)
        else:
            screen.blit(self._target_frame, (0, 0))
            alpha = int((1.0 - progress) * 2.0 * 255)
        veil = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        veil.fill((4, 8, 7, max(0, min(255, alpha))))
        screen.blit(veil, (0, 0))


class MenuState(GameState):
    def __init__(self) -> None:
        self._player_count = 4
        self._types = ["Player", "Bot", "Bot", "Bot"]
        self._font: pygame.font.Font | None = None
        self._small: pygame.font.Font | None = None
        self._tiny: pygame.font.Font | None = None
        self._title: pygame.font.Font | None = None
        self._big: pygame.font.Font | None = None
        self._buttons: list[Button] = []
        self._anim_t = 0.0

    def _ensure_fonts(self) -> None:
        if self._font is None:
            self._font = pygame.font.SysFont("segoeui", 24)
            self._small = pygame.font.SysFont("segoeui", 18)
            self._tiny = pygame.font.SysFont("segoeui", 15)
            self._title = pygame.font.SysFont("segoeui", 52, bold=True)
            self._big = pygame.font.SysFont("segoeui", 32)

    def _layout(self) -> list[Button]:
        panel_x = 42
        buttons = [
            Button(pygame.Rect(panel_x, 518, 344, 50), "BẮT ĐẦU TRẬN", "start"),
            Button(pygame.Rect(panel_x, 578, 344, 44), "CẨM NANG", "tutorial"),
            Button(pygame.Rect(panel_x, 634, 344, 40), "THOÁT", "exit"),
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
                    intro = MatchIntroState(PlayingState(Match(types)))
                    return TransitionState(self, intro)
                elif button.action == "tutorial":
                    return TransitionState(self, TutorialState(self))
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
        sub = self._small.render("CHỈ HUY TOÀN CHIẾN TUYẾN", True, (183, 194, 187))
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
                assert self._tiny is not None
                val_surf = self._tiny.render(value, True, (255, 247, 224))
                screen.blit(val_surf, val_surf.get_rect(center=(row_x + 274, y + row_h // 2)))

        draw_row(row_y, "SỐ PHE", str(self._player_count))

        for i in range(4):
            y = row_y + spacing * (i + 1)
            if i < self._player_count:
                p_type = "NGƯỜI" if self._types[i] == "Player" else "AI BOT"
                draw_row(y, f"PLAYER {i + 1}", p_type, color=cfg.PLAYER_COLORS[i])
            else:
                draw_row(y, f"PLAYER {i + 1}", "ĐÓNG", True, cfg.PLAYER_COLORS[i])

        layout = self._layout()
        layout[0].draw(screen, self._small)
        tutorial_button = layout[1]
        pygame.draw.rect(screen, (34, 43, 41), tutorial_button.rect, border_radius=5)
        pygame.draw.rect(screen, (177, 144, 76), tutorial_button.rect, 1, border_radius=5)
        tutorial_text = self._small.render("CẨM NANG", True, (238, 222, 181))
        screen.blit(tutorial_text, tutorial_text.get_rect(center=tutorial_button.rect.center))
        exit_button = layout[2]
        pygame.draw.rect(screen, (24, 29, 29), exit_button.rect, border_radius=5)
        pygame.draw.rect(screen, (90, 98, 94), exit_button.rect, 1, border_radius=5)
        exit_text = self._small.render("THOÁT", True, (177, 184, 178))
        screen.blit(exit_text, exit_text.get_rect(center=exit_button.rect.center))


class TutorialState(GameState):
    def __init__(self, return_state: GameState) -> None:
        self._return_state = return_state
        self._view: TutorialView | None = None
        self._page_index = 0
        self._elapsed = 0.0
        self._page_elapsed = 0.18
        self._scroll = 0.0
        self._sound_events: list[str] = []

    @property
    def page_index(self) -> int:
        return self._page_index

    def _ensure_view(self, screen: pygame.Surface) -> TutorialView:
        if self._view is None:
            self._view = TutorialView(screen)
        else:
            self._view.bind_surface(screen)
        return self._view

    def _go_back(self) -> GameState:
        self._queue_sound("click")
        return TransitionState(self, self._return_state)

    def _change_page(self, page_index: int) -> None:
        page_count = len(self._view.pages) if self._view is not None else 5
        page_index = max(0, min(page_count - 1, page_index))
        if page_index == self._page_index:
            return
        self._page_index = page_index
        self._page_elapsed = 0.0
        self._scroll = 0.0
        self._queue_sound("page_turn")

    def handle_event(self, event: pygame.event.Event) -> GameState:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return self._go_back()
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self._change_page(self._page_index - 1)
            elif event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_RETURN, pygame.K_SPACE):
                if self._page_index >= 4:
                    return self._go_back()
                self._change_page(self._page_index + 1)
            elif event.key in (pygame.K_UP, pygame.K_PAGEUP):
                self._scroll = max(0.0, self._scroll - 42.0)
            elif event.key in (pygame.K_DOWN, pygame.K_PAGEDOWN):
                self._scroll = min(self._max_scroll(), self._scroll + 42.0)
        elif event.type == pygame.MOUSEWHEEL:
            self._scroll = max(
                0.0,
                min(self._max_scroll(), self._scroll - event.y * 34.0),
            )
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self._view is not None:
            if self._view.back_rect.collidepoint(event.pos):
                return self._go_back()
            for index, rect in enumerate(self._view.tab_rects()):
                if rect.collidepoint(event.pos):
                    self._change_page(index)
                    return self
            if self._view.previous_rect.collidepoint(event.pos):
                self._change_page(self._page_index - 1)
            elif self._view.next_rect.collidepoint(event.pos):
                if self._page_index == len(self._view.pages) - 1:
                    return self._go_back()
                self._change_page(self._page_index + 1)
        return self

    def _max_scroll(self) -> float:
        if self._view is None:
            return 170.0
        return self._view.max_scroll(self._page_index)

    def update(self, dt: float) -> GameState:
        self._elapsed += max(0.0, dt)
        self._page_elapsed = min(0.18, self._page_elapsed + max(0.0, dt))
        return self

    def draw(self, screen: pygame.Surface) -> None:
        view = self._ensure_view(screen)
        reveal = _ease_out_cubic(self._page_elapsed / 0.18)
        view.draw(self._page_index, self._elapsed, reveal, self._scroll)


class MatchIntroState(GameState):
    def __init__(self, playing_state: "PlayingState", duration: float = 2.4) -> None:
        self._playing = playing_state
        self._duration = duration
        self._elapsed = 0.0
        self._last_token = ""
        self._sound_events: list[str] = []
        self._title: pygame.font.Font | None = None
        self._number: pygame.font.Font | None = None
        self._small: pygame.font.Font | None = None

    @property
    def playing_state(self) -> "PlayingState":
        return self._playing

    def handle_event(self, event: pygame.event.Event) -> GameState:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._queue_sound("click")
            return TransitionState(self, MenuState())
        return self

    def update(self, dt: float) -> GameState:
        self._elapsed += max(0.0, dt)
        token = self._token()
        if token != self._last_token:
            if token in ("3", "2", "1"):
                self._queue_sound("countdown")
            self._last_token = token
        if self._elapsed >= self._duration:
            for sound in self.pop_sound_events():
                self._playing._queue_sound(sound)
            self._playing._queue_sound("battle_start")
            return self._playing
        return self

    def _token(self) -> str:
        if self._elapsed < 0.6:
            return "3"
        if self._elapsed < 1.2:
            return "2"
        if self._elapsed < 1.8:
            return "1"
        return "BẮT ĐẦU"

    def draw(self, screen: pygame.Surface) -> None:
        self._playing.draw(screen)
        if self._title is None:
            self._title = pygame.font.SysFont("segoeui", 28, bold=True)
            self._number = pygame.font.SysFont("segoeui", 76, bold=True)
            self._small = pygame.font.SysFont("segoeui", 15, bold=True)
        assert self._title is not None and self._number is not None and self._small is not None

        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((4, 9, 8, 148))
        screen.blit(overlay, (0, 0))

        banner = pygame.Rect(250, 142, 780, 418)
        _draw_glass_panel(screen, banner)
        eyebrow = self._small.render("TRẬN CHIẾN SẮP BẮT ĐẦU", True, (224, 181, 84))
        screen.blit(eyebrow, eyebrow.get_rect(center=(cfg.WINDOW_WIDTH // 2, 178)))
        heading = self._title.render("CÁC VƯƠNG QUỐC ĐÃ SẴN SÀNG", True, (255, 247, 224))
        screen.blit(heading, heading.get_rect(center=(cfg.WINDOW_WIDTH // 2, 216)))

        players = self._playing._match.players
        card_w = 164
        gap = 16
        total = len(players) * card_w + max(0, len(players) - 1) * gap
        start_x = cfg.WINDOW_WIDTH // 2 - total // 2
        for index, player in enumerate(players):
            rect = pygame.Rect(start_x + index * (card_w + gap), 252, card_w, 78)
            layer = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(layer, (18, 26, 24, 224), layer.get_rect(), border_radius=6)
            pygame.draw.rect(layer, (*player.color, 230), (0, 0, 6, rect.height), border_radius=3)
            pygame.draw.rect(layer, (*_brighten(player.color, 32), 160), layer.get_rect(), 1, border_radius=6)
            screen.blit(layer, rect)
            name = self._small.render(_fit_label(self._small, player.name.upper(), card_w - 24), True, (246, 239, 217))
            screen.blit(name, name.get_rect(center=(rect.centerx + 3, rect.y + 27)))
            key_label = " / ".join(KEY_LABELS[index]) if index < len(KEY_LABELS) else "AI BOT"
            if not isinstance(player, HumanPlayer):
                key_label = "AI BOT"
            keys = self._small.render(key_label, True, _brighten(player.color, 55))
            screen.blit(keys, keys.get_rect(center=(rect.centerx + 3, rect.y + 54)))

        token = self._token()
        token_font = self._number if len(token) == 1 else self._title
        token_surface = token_font.render(token, True, (255, 221, 126))
        pulse = 1.0 + math.sin(self._elapsed * 8.0) * 0.025
        if pulse != 1.0:
            token_surface = pygame.transform.smoothscale(
                token_surface,
                (
                    max(1, int(token_surface.get_width() * pulse)),
                    max(1, int(token_surface.get_height() * pulse)),
                ),
            )
        screen.blit(token_surface, token_surface.get_rect(center=(cfg.WINDOW_WIDTH // 2, 438)))
        hint = self._small.render("Trận đấu chưa tính thời gian trong lúc chuẩn bị", True, (166, 179, 169))
        screen.blit(hint, hint.get_rect(center=(cfg.WINDOW_WIDTH // 2, 518)))

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
            ratios = {pi.key1: 0.0, pi.key2: 0.33, pi.key3: 0.66}
            ratio = ratios.get(key)
            if ratio is not None and pi.target is not None:
                if ratio == 0.0:
                    pi.reset()
                    self._queue_sound("click")
                    return
                success = False
                for source in self._match.territories_of(player):
                    if source is pi.target:
                        continue
                    amount = _attack_amount_for_ratio(source.soldiers.count, ratio)
                    if amount <= 0:
                        continue
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
            return TransitionState(
                self,
                GameOverState(self._match.result_snapshot()),
                duration=0.6,
            )
        return self

    def draw(self, screen: pygame.Surface) -> None:
        if self._renderer is None:
            self._renderer = Renderer(screen)
        else:
            self._renderer.bind_surface(screen)
        player_states = {
            idx: pi.to_dict() for idx, pi in self._player_inputs.items()
        }
        self._renderer.draw_match(self._match, player_states)


class GameOverState(GameState):
    def __init__(self, result: MatchResult) -> None:
        self._result = result
        self._font: pygame.font.Font | None = None
        self._title: pygame.font.Font | None = None
        self._small: pygame.font.Font | None = None
        self._tiny: pygame.font.Font | None = None
        self._sound_events: list[str] = ["win"]
        self._anim_t = 0.0
        self._buttons = [
            Button(pygame.Rect(470, 626, 164, 46), "ĐẤU LẠI", "rematch"),
            Button(pygame.Rect(650, 626, 164, 46), "MENU CHÍNH", "menu"),
        ]

    @property
    def result(self) -> MatchResult:
        return self._result

    def handle_event(self, event: pygame.event.Event) -> GameState:
        for button in self._buttons:
            if not button.clicked(event):
                continue
            self._queue_sound("click")
            if button.action == "rematch":
                match = Match.from_setup(self._result.setup, new_seed=True)
                return TransitionState(self, MatchIntroState(PlayingState(match)))
            return TransitionState(self, MenuState())
        return self

    def update(self, dt: float) -> GameState:
        self._anim_t += max(0.0, dt)
        return self

    def draw(self, screen: pygame.Surface) -> None:
        if self._font is None:
            self._font = pygame.font.SysFont("segoeui", 22, bold=True)
            self._title = pygame.font.SysFont("segoeui", 48, bold=True)
            self._small = pygame.font.SysFont("segoeui", 16)
            self._tiny = pygame.font.SysFont("segoeui", 13, bold=True)
        assert self._font is not None and self._title is not None and self._small is not None and self._tiny is not None
        _draw_menu_background(screen, self._anim_t)
        shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        shade.fill((4, 8, 7, 96))
        screen.blit(shade, (0, 0))

        panel = pygame.Rect(150, 58, 980, 542)
        _draw_glass_panel(screen, panel)
        winner = self._result.winner
        winner_color = winner.color if winner is not None else (185, 163, 103)
        pygame.draw.rect(screen, winner_color, (panel.x, panel.y, panel.width, 7), border_radius=3)

        crown_center = (cfg.WINDOW_WIDTH // 2, 116)
        crown = [
            (crown_center[0] - 28, crown_center[1] + 12),
            (crown_center[0] - 23, crown_center[1] - 18),
            (crown_center[0] - 7, crown_center[1] - 2),
            (crown_center[0], crown_center[1] - 25),
            (crown_center[0] + 8, crown_center[1] - 2),
            (crown_center[0] + 24, crown_center[1] - 18),
            (crown_center[0] + 28, crown_center[1] + 12),
        ]
        pygame.draw.polygon(screen, (245, 199, 72), crown)
        pygame.draw.lines(screen, (255, 232, 143), True, crown, 2)

        winner_name = winner.name if winner is not None else "KHÔNG CÓ NGƯỜI THẮNG"
        title = self._title.render(f"{winner_name.upper()} CHIẾN THẮNG", True, (255, 247, 222))
        reveal = _ease_out_cubic(min(1.0, self._anim_t / 0.8))
        title.set_alpha(int(255 * reveal))
        screen.blit(title, title.get_rect(center=(cfg.WINDOW_WIDTH // 2, 173)))

        duration = f"{int(self._result.duration // 60)}:{int(self._result.duration % 60):02d}"
        duration_text = self._small.render(f"THỜI LƯỢNG TRẬN  {duration}", True, (183, 194, 185))
        screen.blit(duration_text, duration_text.get_rect(center=(cfg.WINDOW_WIDTH // 2, 214)))

        header_y = 254
        columns = (("VƯƠNG QUỐC", 215), ("VÙNG", 605), ("LÍNH", 703), ("WORKER", 796), ("VỆ BINH", 899), ("MỤC TIÊU", 1010))
        for label, x in columns:
            text = self._tiny.render(label, True, (155, 168, 159))
            screen.blit(text, text.get_rect(center=(x, header_y)))
        pygame.draw.line(screen, (74, 84, 78), (180, 275), (1100, 275), 1)

        for row, player in enumerate(self._result.players):
            y = 294 + row * 65
            row_rect = pygame.Rect(180, y, 920, 52)
            active = player.player_id == self._result.winner_id
            layer = pygame.Surface(row_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(layer, (*player.color, 46 if active else 22), layer.get_rect(), border_radius=6)
            pygame.draw.rect(layer, (*_brighten(player.color, 30), 190 if active else 95), layer.get_rect(), 1, border_radius=6)
            pygame.draw.rect(layer, (*player.color, 230), (0, 0, 6, row_rect.height), border_radius=3)
            screen.blit(layer, row_rect)

            name = self._small.render(_fit_label(self._small, player.name.upper(), 300), True, (246, 239, 216))
            screen.blit(name, (row_rect.x + 24, y + 16))
            values = (
                (str(player.territories), 605),
                (str(player.soldiers), 703),
                (str(player.workers), 796),
                (str(player.defenders), 899),
                (str(player.objectives_claimed), 1010),
            )
            for value, x in values:
                value_surface = self._font.render(value, True, (239, 228, 198))
                screen.blit(value_surface, value_surface.get_rect(center=(x, y + 26)))

        for button in self._buttons:
            button.draw(screen, self._small)


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
        self._font = pygame.font.SysFont("segoeui", 19, bold=True)
        self._title = pygame.font.SysFont("segoeui", 44, bold=True)
        self._small = pygame.font.SysFont("segoeui", 15)
        self._buttons = [
            Button(pygame.Rect(520, 282, 240, 48), "TIẾP TỤC", "resume"),
            Button(pygame.Rect(520, 344, 240, 48), "CHƠI LẠI", "restart"),
            Button(pygame.Rect(520, 406, 240, 48), "CẨM NANG", "tutorial"),
            Button(pygame.Rect(520, 468, 240, 48), "MENU CHÍNH", "menu"),
        ]
        self._confirm_buttons = [
            Button(pygame.Rect(505, 451, 126, 42), "HỦY", "cancel"),
            Button(pygame.Rect(649, 451, 126, 42), "XÁC NHẬN", "confirm"),
        ]
        self._bg_cache: pygame.Surface | None = None
        self._sound_events: list[str] = []
        self._opened = 0.0
        self._confirm_action: str | None = None

    @property
    def playing_state(self) -> PlayingState:
        return self._playing

    def handle_event(self, event: pygame.event.Event) -> GameState:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._queue_sound("click")
            if self._confirm_action is not None:
                self._confirm_action = None
                return self
            return _handoff_sounds(self, ResumeCountdownState(self._playing))

        if self._confirm_action is not None:
            for button in self._confirm_buttons:
                if not button.clicked(event):
                    continue
                self._queue_sound("click")
                if button.action == "cancel":
                    self._confirm_action = None
                    return self
                if self._confirm_action == "restart":
                    match = Match.from_setup(self._playing._match.setup)
                    return TransitionState(
                        self,
                        MatchIntroState(PlayingState(match)),
                    )
                return TransitionState(self, MenuState())
            return self

        for button in self._buttons:
            if button.clicked(event):
                self._queue_sound("click")
                if button.action == "resume":
                    return _handoff_sounds(self, ResumeCountdownState(self._playing))
                elif button.action == "restart":
                    self._confirm_action = "restart"
                elif button.action == "tutorial":
                    return TransitionState(self, TutorialState(self))
                elif button.action == "menu":
                    self._confirm_action = "menu"
        return self

    def update(self, dt: float) -> GameState:
        self._opened = min(0.18, self._opened + max(0.0, dt))
        return self

    def draw(self, screen: pygame.Surface) -> None:
        if self._bg_cache is None:
            temp = pygame.Surface(screen.get_size())
            self._playing.draw(temp)
            self._bg_cache = fast_blur(temp, 10.0)

        screen.blit(self._bg_cache, (0, 0))

        # Dim overlay
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((7, 11, 11, 148))
        screen.blit(overlay, (0, 0))

        reveal = _ease_out_cubic(self._opened / 0.18)
        offset_y = int((1.0 - reveal) * 24)
        menu_layer = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        panel = pygame.Rect(430, 126, 420, 430)
        _draw_glass_panel(menu_layer, panel)
        pygame.draw.rect(
            menu_layer,
            (201, 159, 70),
            (panel.x, panel.y, panel.width, 6),
            border_radius=3,
        )

        eyebrow = self._small.render("TRẬN ĐẤU ĐANG ĐÓNG BĂNG", True, (184, 164, 111))
        menu_layer.blit(eyebrow, eyebrow.get_rect(center=(cfg.WINDOW_WIDTH // 2, panel.y + 54)))
        title = self._title.render("TẠM DỪNG", True, (255, 248, 228))
        menu_layer.blit(title, title.get_rect(center=(cfg.WINDOW_WIDTH // 2, panel.y + 99)))
        hint = self._small.render("Esc để tiếp tục với đếm ngược an toàn", True, (159, 171, 163))
        menu_layer.blit(hint, hint.get_rect(center=(cfg.WINDOW_WIDTH // 2, panel.y + 136)))

        for button in self._buttons:
            button.draw(menu_layer, self._font)
        menu_layer.set_alpha(max(0, min(255, int(255 * reveal))))
        screen.blit(menu_layer, (0, offset_y))

        if self._confirm_action is not None:
            modal_shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            modal_shade.fill((2, 5, 5, 142))
            screen.blit(modal_shade, (0, 0))
            modal = pygame.Rect(430, 260, 420, 258)
            _draw_glass_panel(screen, modal)
            action = "chơi lại từ đầu" if self._confirm_action == "restart" else "rời về Menu chính"
            heading = self._font.render("XÁC NHẬN THAO TÁC", True, (255, 230, 162))
            screen.blit(heading, heading.get_rect(center=(modal.centerx, modal.y + 54)))
            warning = self._small.render(f"Bạn có chắc muốn {action}?", True, (219, 222, 211))
            screen.blit(warning, warning.get_rect(center=(modal.centerx, modal.y + 104)))
            detail = self._small.render("Tiến trình của trận hiện tại sẽ không được lưu.", True, (164, 174, 167))
            screen.blit(detail, detail.get_rect(center=(modal.centerx, modal.y + 137)))
            for button in self._confirm_buttons:
                button.draw(screen, self._small)


class ResumeCountdownState(GameState):
    def __init__(self, playing_state: PlayingState, duration: float = 1.8) -> None:
        self._playing = playing_state
        self._duration = duration
        self._elapsed = 0.0
        self._last_token = ""
        self._sound_events: list[str] = []
        self._number = pygame.font.SysFont("segoeui", 72, bold=True)
        self._title = pygame.font.SysFont("segoeui", 30, bold=True)
        self._small = pygame.font.SysFont("segoeui", 15, bold=True)

    @property
    def playing_state(self) -> PlayingState:
        return self._playing

    def handle_event(self, event: pygame.event.Event) -> GameState:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._queue_sound("click")
            return _handoff_sounds(self, PauseState(self._playing))
        return self

    def update(self, dt: float) -> GameState:
        self._elapsed += max(0.0, dt)
        token = self._token()
        if token != self._last_token:
            if token in ("3", "2", "1"):
                self._queue_sound("countdown")
            self._last_token = token
        if self._elapsed >= self._duration:
            for sound in self.pop_sound_events():
                self._playing._queue_sound(sound)
            self._playing._queue_sound("battle_start")
            return self._playing
        return self

    def _token(self) -> str:
        if self._elapsed < 0.55:
            return "3"
        if self._elapsed < 1.10:
            return "2"
        if self._elapsed < 1.65:
            return "1"
        return "TIẾP TỤC"

    def draw(self, screen: pygame.Surface) -> None:
        self._playing.draw(screen)
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((4, 9, 8, 126))
        screen.blit(overlay, (0, 0))
        token = self._token()
        font = self._number if len(token) == 1 else self._title
        text = font.render(token, True, (255, 225, 137))
        screen.blit(text, text.get_rect(center=(cfg.WINDOW_WIDTH // 2, cfg.WINDOW_HEIGHT // 2 - 12)))
        hint = self._small.render("Trận đấu vẫn đang đóng băng", True, (205, 214, 205))
        screen.blit(hint, hint.get_rect(center=(cfg.WINDOW_WIDTH // 2, cfg.WINDOW_HEIGHT // 2 + 72)))


def _ease_out_cubic(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return 1.0 - (1.0 - value) ** 3


def _brighten(color: tuple[int, int, int], amount: int) -> tuple[int, int, int]:
    return tuple(min(255, channel + amount) for channel in color)


def _fit_label(font: pygame.font.Font, text: str, width: int) -> str:
    if font.size(text)[0] <= width:
        return text
    suffix = "..."
    while text and font.size(text + suffix)[0] > width:
        text = text[:-1]
    return text + suffix


def _handoff_sounds(source: GameState, target: GameState) -> GameState:
    for sound in source.pop_sound_events():
        target._queue_sound(sound)
    return target
