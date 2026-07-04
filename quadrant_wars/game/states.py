from __future__ import annotations

import pygame

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.player import HumanPlayer
from quadrant_wars.game.game_manager import Match
from quadrant_wars.ui.renderer import Renderer, SIDEBAR_X
from quadrant_wars.ui.widgets import Button

PLAYER_SELECT_KEYS = {
    pygame.K_F1: 0,
    pygame.K_F2: 1,
    pygame.K_F3: 2,
    pygame.K_F4: 3,
}
PLAYER_RECRUIT_KEYS = {
    pygame.K_q: (0, "soldier"),
    pygame.K_a: (0, "worker"),
    pygame.K_w: (1, "soldier"),
    pygame.K_s: (1, "worker"),
    pygame.K_e: (2, "soldier"),
    pygame.K_d: (2, "worker"),
    pygame.K_r: (3, "soldier"),
    pygame.K_f: (3, "worker"),
}


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
        self._player_count = 2
        self._types = ["Human", "Bot", "Bot", "Bot"]
        self._font: pygame.font.Font | None = None
        self._small: pygame.font.Font | None = None
        self._title: pygame.font.Font | None = None
        self._buttons: list[Button] = []
        self._sound_events: list[str] = []

    def _ensure_fonts(self) -> None:
        if self._font is None:
            self._font = pygame.font.SysFont("segoeui", 22)
            self._small = pygame.font.SysFont("segoeui", 15)
            self._title = pygame.font.SysFont("georgia", 58, bold=True)

    def _layout(self) -> list[Button]:
        buttons = [
            Button(pygame.Rect(505, 238, 48, 42), "-", "dec"),
            Button(pygame.Rect(720, 238, 48, 42), "+", "inc"),
            Button(pygame.Rect(524, 604, 230, 56), "Start Match", "start"),
        ]
        for i in range(self._player_count):
            buttons.append(Button(pygame.Rect(616, 322 + i * 58, 150, 38), self._types[i], f"toggle:{i}"))
        return buttons

    def handle_event(self, event: pygame.event.Event) -> GameState:
        for button in self._layout():
            if button.clicked(event):
                self._queue_sound("click")
                if button.action == "dec":
                    self._player_count = max(cfg.MIN_PLAYERS, self._player_count - 1)
                elif button.action == "inc":
                    self._player_count = min(cfg.MAX_PLAYERS, self._player_count + 1)
                elif button.action.startswith("toggle:"):
                    idx = int(button.action.split(":")[1])
                    self._types[idx] = "Bot" if self._types[idx] == "Human" else "Human"
                elif button.action == "start":
                    types = [t.lower() for t in self._types[: self._player_count]]
                    next_state = PlayingState(Match(types))
                    next_state._queue_sound("click")
                    return next_state
        return self

    def draw(self, screen: pygame.Surface) -> None:
        self._ensure_fonts()
        _draw_menu_background(screen)
        assert self._font is not None and self._small is not None and self._title is not None
        panel = pygame.Rect(364, 72, 548, 604)
        _draw_panel(screen, panel, (31, 35, 42), (98, 83, 62))

        title = self._title.render("Quadrant Wars", True, cfg.TEXT)
        screen.blit(title, title.get_rect(center=(cfg.WINDOW_WIDTH // 2, 132)))
        subtitle = self._small.render("SETUP LOCAL MATCH", True, cfg.ACCENT_2)
        screen.blit(subtitle, subtitle.get_rect(center=(cfg.WINDOW_WIDTH // 2, 188)))

        pygame.draw.rect(screen, (43, 47, 55), (564, 236, 144, 46), border_radius=10)
        label = self._font.render(f"{self._player_count} Players", True, cfg.TEXT)
        screen.blit(label, label.get_rect(center=(636, 258)))

        for i in range(self._player_count):
            slot = pygame.Rect(504, 316 + i * 58, 274, 50)
            pygame.draw.rect(screen, (42, 46, 54), slot, border_radius=10)
            pygame.draw.rect(screen, cfg.PLAYER_COLORS[i], (slot.x, slot.y, 8, slot.height), border_radius=5)
            row = self._font.render(f"Slot {i + 1}", True, cfg.TEXT)
            screen.blit(row, (slot.x + 22, slot.y + 13))

        for button in self._layout():
            button.draw(screen, self._font)


class PlayingState(GameState):
    def __init__(self, match: Match) -> None:
        self._match = match
        self._selected = None
        self._selected_by_player = {}
        self._attack_ratio = cfg.ATTACK_DEFAULT_RATIO
        self._renderer: Renderer | None = None
        self._sound_events: list[str] = []

    def handle_event(self, event: pygame.event.Event) -> GameState:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return MenuState()
            if event.key in PLAYER_SELECT_KEYS:
                if self._select_home_for_player(PLAYER_SELECT_KEYS[event.key]):
                    self._queue_sound("click")
                return self
            if event.key in PLAYER_RECRUIT_KEYS:
                player_id, unit_type = PLAYER_RECRUIT_KEYS[event.key]
                if self._buy_for_player(player_id, unit_type):
                    self._queue_sound("recruit")
                else:
                    self._queue_sound("click")
                return self
            if event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_UP):
                self._attack_ratio = min(1.0, self._attack_ratio + 0.25)
                self._queue_sound("click")
            if event.key in (pygame.K_MINUS, pygame.K_DOWN):
                self._attack_ratio = max(0.25, self._attack_ratio - 0.25)
                self._queue_sound("click")
            if self._selected and event.key == pygame.K_1 and self._selected.buy_soldier():
                self._queue_sound("recruit")
            if self._selected and event.key == pygame.K_2 and self._selected.buy_worker():
                self._queue_sound("recruit")

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            command_sound = _handle_command_click(event.pos, self._selected) if self._selected is not None else None
            if command_sound:
                self._queue_sound(command_sound)
                return self
            territory = self._match.territory_at(event.pos)
            if territory is None:
                return self
            if self._selected is not None and territory.owner is not self._selected.owner:
                amount = max(1, int(self._selected.soldiers.count * self._attack_ratio))
                self._match.issue_attack(self._selected, territory, amount)
            elif isinstance(territory.owner, HumanPlayer) and getattr(territory.owner, "is_alive", False):
                self._select_territory(territory)
                self._queue_sound("click")
        return self

    def update(self, dt: float) -> GameState:
        self._match.update(dt)
        self._sound_events.extend(self._match.pop_sound_events())
        if self._match.winner is not None:
            game_over = GameOverState(self._match.winner.name)
            game_over._sound_events.extend(self.pop_sound_events())
            return game_over
        return self

    def draw(self, screen: pygame.Surface) -> None:
        if self._renderer is None:
            self._renderer = Renderer(screen)
        self._renderer.draw_match(self._match, self._selected, self._attack_ratio)

    def _select_territory(self, territory: object) -> None:
        self._selected = territory
        owner = getattr(territory, "owner", None)
        if isinstance(owner, HumanPlayer):
            self._selected_by_player[owner.id] = territory

    def _select_home_for_player(self, player_id: int) -> bool:
        if player_id >= len(self._match.players):
            return False
        player = self._match.players[player_id]
        if not isinstance(player, HumanPlayer) or not player.is_alive:
            return False
        territory = self._match.home_territory(player)
        if territory is None:
            return False
        self._select_territory(territory)
        return True

    def _buy_for_player(self, player_id: int, unit_type: str) -> bool:
        if player_id >= len(self._match.players):
            return False
        player = self._match.players[player_id]
        if not isinstance(player, HumanPlayer) or not player.is_alive:
            return False
        territory = self._selected_by_player.get(player_id) or self._match.home_territory(player)
        if territory is None or territory.owner is not player:
            territory = self._match.home_territory(player)
        if territory is None:
            return False
        self._select_territory(territory)
        if unit_type == "soldier":
            return territory.buy_soldier()
        return territory.buy_worker()


class GameOverState(GameState):
    def __init__(self, winner_name: str) -> None:
        self._winner_name = winner_name
        self._font: pygame.font.Font | None = None
        self._title: pygame.font.Font | None = None
        self._sound_events: list[str] = ["win"]

    def handle_event(self, event: pygame.event.Event) -> GameState:
        if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
            return MenuState()
        return self

    def draw(self, screen: pygame.Surface) -> None:
        if self._font is None:
            self._font = pygame.font.SysFont("segoeui", 24)
            self._title = pygame.font.SysFont("georgia", 56, bold=True)
        assert self._font is not None and self._title is not None
        _draw_menu_background(screen)
        panel = pygame.Rect(332, 205, 616, 258)
        _draw_panel(screen, panel, (34, 38, 44), cfg.ACCENT_2)
        text = self._title.render(f"{self._winner_name} wins", True, cfg.TEXT)
        screen.blit(text, text.get_rect(center=(cfg.WINDOW_WIDTH // 2, 300)))
        hint = self._font.render("Press any key or click to return to menu", True, cfg.MUTED_TEXT)
        screen.blit(hint, hint.get_rect(center=(cfg.WINDOW_WIDTH // 2, 374)))


def _handle_command_click(pos: tuple[int, int], selected: object) -> str | None:
    soldier_rect = pygame.Rect(SIDEBAR_X + 38, 320, 100, 24)
    worker_rect = pygame.Rect(SIDEBAR_X + 155, 320, 100, 24)
    if soldier_rect.collidepoint(pos):
        return "recruit" if selected.buy_soldier() else "click"
    if worker_rect.collidepoint(pos):
        return "recruit" if selected.buy_worker() else "click"
    return None


def _draw_menu_background(screen: pygame.Surface) -> None:
    screen.fill(cfg.MENU_BG)
    top = (25, 27, 28)
    bottom = (47, 38, 31)
    for y in range(cfg.WINDOW_HEIGHT):
        t = y / cfg.WINDOW_HEIGHT
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        pygame.draw.line(screen, color, (0, y), (cfg.WINDOW_WIDTH, y))

    shapes = [
        ([(90, 120), (300, 70), (365, 210), (210, 300), (70, 250)], cfg.PLAYER_COLORS[0]),
        ([(930, 92), (1160, 120), (1194, 294), (1018, 338), (900, 220)], cfg.PLAYER_COLORS[1]),
        ([(110, 470), (314, 405), (418, 570), (245, 650), (74, 610)], cfg.PLAYER_COLORS[2]),
        ([(900, 500), (1128, 430), (1224, 594), (1045, 670), (872, 624)], cfg.PLAYER_COLORS[3]),
    ]
    for polygon, color in shapes:
        shadow = [(x + 8, y + 10) for x, y in polygon]
        pygame.draw.polygon(screen, (7, 9, 11), shadow)
        pygame.draw.polygon(screen, color, polygon)
        pygame.draw.polygon(screen, (239, 226, 190), polygon, 2)


def _draw_panel(
    screen: pygame.Surface,
    rect: pygame.Rect,
    fill: tuple[int, int, int],
    stroke: tuple[int, int, int],
) -> None:
    shadow = rect.move(0, 10)
    pygame.draw.rect(screen, (0, 0, 0), shadow, border_radius=18)
    pygame.draw.rect(screen, fill, rect, border_radius=18)
    pygame.draw.rect(screen, stroke, rect, 2, border_radius=18)
    pygame.draw.rect(screen, (255, 255, 255), rect.inflate(-18, -18), 1, border_radius=14)
