from __future__ import annotations

import math

import pygame

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.territory import Territory
from quadrant_wars.game.game_manager import Match

SIDEBAR_WIDTH = 292
SIDEBAR_X = cfg.WINDOW_WIDTH - SIDEBAR_WIDTH


class Renderer:
    def __init__(self, screen: pygame.Surface) -> None:
        self._screen = screen
        self._font = pygame.font.SysFont("segoeui", 19)
        self._small = pygame.font.SysFont("segoeui", 15)
        self._tiny = pygame.font.SysFont("segoeui", 12)
        self._title = pygame.font.SysFont("georgia", 33, bold=True)
        self._subtitle = pygame.font.SysFont("segoeui", 22, bold=True)
        self._background = self._build_background()

    @property
    def font(self) -> pygame.font.Font:
        return self._font

    @property
    def small_font(self) -> pygame.font.Font:
        return self._small

    @property
    def title_font(self) -> pygame.font.Font:
        return self._title

    def draw_match(self, match: Match, selected: Territory | None, attack_ratio: float) -> None:
        self._screen.blit(self._background, (0, 0))
        self._draw_map_frame()

        for territory in match.territories:
            self._draw_territory(territory, selected is territory)

        for territory in match.territories:
            self._draw_wandering_units(territory, match.elapsed, selected is territory)

        for army in match.armies:
            self._draw_army(army)

        for territory in match.territories:
            self._draw_territory_label(territory, selected is territory)

        for effect in match.effects:
            self._draw_combat_effect(effect)

        self._draw_sidebar(match, selected, attack_ratio)

    def _build_background(self) -> pygame.Surface:
        surface = pygame.Surface((cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT))
        top = (28, 31, 30)
        bottom = (45, 38, 32)
        for y in range(cfg.WINDOW_HEIGHT):
            t = y / cfg.WINDOW_HEIGHT
            color = _mix(top, bottom, t)
            pygame.draw.line(surface, color, (0, y), (cfg.WINDOW_WIDTH, y))

        for x in range(-cfg.WINDOW_HEIGHT, cfg.WINDOW_WIDTH, 48):
            pygame.draw.line(surface, (55, 54, 48), (x, cfg.WINDOW_HEIGHT), (x + cfg.WINDOW_HEIGHT, 0), 1)
        for x in range(0, cfg.WINDOW_WIDTH, 92):
            pygame.draw.line(surface, (31, 36, 35), (x, 0), (x, cfg.WINDOW_HEIGHT), 1)
        return surface

    def _draw_map_frame(self) -> None:
        frame = pygame.Rect(42, 42, SIDEBAR_X - 70, cfg.WINDOW_HEIGHT - 84)
        _draw_shadow_rect(self._screen, frame, radius=14, alpha=95, offset=(0, 8))
        pygame.draw.rect(self._screen, (25, 28, 26), frame, border_radius=14)
        pygame.draw.rect(self._screen, (92, 82, 66), frame, 2, border_radius=14)

        label = self._tiny.render("LIVE TERRITORY MAP", True, (206, 194, 160))
        pygame.draw.rect(self._screen, (42, 37, 30), (62, 28, 148, 24), border_radius=6)
        self._screen.blit(label, (74, 33))

    def _draw_territory(self, territory: Territory, selected: bool) -> None:
        alive = getattr(territory.owner, "is_alive", False)
        base = territory.owner.color if alive else (86, 83, 79)
        fill = _brighten(base, 10) if alive else base
        shadow_points = [(int(x + 3), int(y + 4)) for x, y in territory.polygon]
        pygame.draw.polygon(self._screen, (6, 9, 10), shadow_points)
        pygame.draw.polygon(self._screen, fill, territory.polygon)

        cx, cy = territory.centroid
        glow = pygame.Surface((170, 118), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (*_brighten(base, 32), 24), glow.get_rect())
        self._screen.blit(glow, glow.get_rect(center=(int(cx), int(cy))), special_flags=pygame.BLEND_PREMULTIPLIED)

        outline = cfg.ACCENT_2 if selected else (19, 23, 25)
        pygame.draw.polygon(self._screen, outline, territory.polygon, 4 if selected else 2)
        pygame.draw.polygon(self._screen, _brighten(base, 48), territory.polygon, 1)

    def _draw_territory_label(self, territory: Territory, selected: bool) -> None:
        cx, cy = territory.centroid
        center = (int(cx), int(cy))
        owner_color = territory.owner.color
        label_rect = pygame.Rect(0, 0, 178, 24)
        label_rect.center = (center[0], center[1] - 82)
        pygame.draw.rect(self._screen, (29, 32, 36), label_rect, border_radius=12)
        pygame.draw.rect(self._screen, _brighten(owner_color, 24), label_rect, 2, border_radius=12)
        owner = _fit_text(self._tiny, territory.owner.name, 150)
        owner_text = self._tiny.render(owner, True, cfg.TEXT)
        self._screen.blit(owner_text, owner_text.get_rect(center=label_rect.center))

        if selected:
            pygame.draw.circle(self._screen, cfg.ACCENT_2, center, 92, 4)

    def _draw_wandering_units(self, territory: Territory, elapsed: float, selected: bool) -> None:
        color = territory.owner.color
        sprites: list[tuple[str, int]] = []
        if territory.queen.is_alive:
            sprites.append(("queen", 0))
        for i in range(min(territory.workers.count, 5)):
            sprites.append(("worker", i))
        for i in range(min(territory.soldiers.count, 16)):
            sprites.append(("soldier", i))

        if selected:
            cx, cy = territory.centroid
            glow = pygame.Surface((190, 150), pygame.SRCALPHA)
            pygame.draw.ellipse(glow, (*cfg.ACCENT_2, 24), glow.get_rect())
            self._screen.blit(glow, glow.get_rect(center=(int(cx), int(cy))))

        for role, index in sprites:
            position, scale = _wandering_position(territory, role, index, elapsed)
            self._draw_unit_sprite(position, color, scale, role, elapsed + index)

    def _draw_army(self, army: object) -> None:
        pos = army.position
        current = (int(pos[0]), int(pos[1]))
        start = (int(army.start[0]), int(army.start[1]))
        end = (int(army.end[0]), int(army.end[1]))
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = max(1.0, math.hypot(dx, dy))
        nx = -dy / length
        ny = dx / length

        visible = max(3, min(9, army.soldiers // 5 + 3))
        for i in range(visible):
            row = i - (visible - 1) / 2
            wave = math.sin(army.elapsed * 10 + i) * 2
            back = (i % 3) * 13
            sprite_pos = (
                int(current[0] + nx * row * 13 - dx / length * back),
                int(current[1] + ny * row * 13 - dy / length * back + wave),
            )
            scale = 1.0 if i == 0 else 0.86
            self._draw_unit_sprite(sprite_pos, army.attacker.color, scale, "soldier", army.elapsed + i)

        flag_tip = (int(current[0] + dx / length * 18), int(current[1] + dy / length * 18))
        pygame.draw.line(self._screen, (245, 236, 212), current, flag_tip, 3)

    def _draw_unit_sprite(
        self,
        center: tuple[int, int],
        color: tuple[int, int, int],
        scale: float,
        role: str,
        phase: float,
    ) -> None:
        r = max(5, int((10 if role == "queen" else 8) * scale))
        x, y = center
        bob = int(math.sin(phase * 5.0) * 2)
        y += bob
        pygame.draw.ellipse(self._screen, (3, 5, 7), (x - r, y + r, r * 2, max(4, r // 2)))
        pygame.draw.circle(self._screen, _darken(color, 24), (x, y), r + 3)
        body = _brighten(color, 34 if role == "queen" else 22)
        pygame.draw.circle(self._screen, body, (x, y), r + 1)
        pygame.draw.circle(self._screen, (244, 236, 213), (x, y), r + 1, 2)
        if role == "queen":
            crown = [
                (x - r - 2, y - r + 1),
                (x - r // 2, y - r - 9),
                (x, y - r - 1),
                (x + r // 2, y - r - 9),
                (x + r + 2, y - r + 1),
            ]
            pygame.draw.polygon(self._screen, (250, 210, 78), crown)
            pygame.draw.line(self._screen, (95, 70, 28), (x - r, y - r + 3), (x + r, y - r + 3), 2)
        elif role == "worker":
            pygame.draw.rect(self._screen, (129, 91, 48), (x - r - 2, y - 1, r * 2 + 4, r + 4), border_radius=3)
            pygame.draw.line(self._screen, (235, 226, 198), (x - r - 6, y - r - 2), (x + r + 7, y - r - 9), 3)
            pygame.draw.circle(self._screen, (185, 171, 140), (x + r + 8, y - r - 10), 3)
        else:
            helmet = [(x - r, y - 1), (x, y - r - 7), (x + r, y - 1)]
            pygame.draw.polygon(self._screen, _darken(color, 38), helmet)
            pygame.draw.line(self._screen, (245, 239, 220), (x + r - 1, y - r), (x + r + 9, y - r - 7), 2)
            pygame.draw.circle(self._screen, (246, 220, 116), (x + r + 10, y - r - 8), 2)

    def _draw_combat_effect(self, effect: object) -> None:
        p = effect.progress
        alpha = int(230 * (1.0 - p))
        center = (int(effect.position[0]), int(effect.position[1]))
        radius = int(24 + p * 78)
        burst = pygame.Surface((radius * 2 + 30, radius * 2 + 30), pygame.SRCALPHA)
        local = burst.get_rect().center
        pygame.draw.circle(burst, (*effect.attacker_color, max(0, alpha // 3)), local, radius, 5)
        pygame.draw.circle(burst, (*effect.defender_color, max(0, alpha // 3)), local, max(8, radius - 14), 4)

        for i in range(12):
            angle = i * math.tau / 12 + p * 2.5
            inner = 14 + p * 20
            outer = 30 + p * 66
            start = (int(local[0] + math.cos(angle) * inner), int(local[1] + math.sin(angle) * inner))
            end = (int(local[0] + math.cos(angle) * outer), int(local[1] + math.sin(angle) * outer))
            color = effect.attacker_color if i % 2 == 0 else effect.defender_color
            pygame.draw.line(burst, (*_brighten(color, 35), alpha), start, end, 4)

        sword_a = [(local[0] - 30, local[1] - 24), (local[0] + 28, local[1] + 26)]
        sword_b = [(local[0] + 30, local[1] - 24), (local[0] - 28, local[1] + 26)]
        pygame.draw.line(burst, (250, 244, 220, alpha), sword_a[0], sword_a[1], 5)
        pygame.draw.line(burst, (250, 244, 220, alpha), sword_b[0], sword_b[1], 5)
        pygame.draw.circle(burst, (255, 224, 99, alpha), local, 8 + int(p * 8))

        for i in range(10):
            angle = i * math.tau / 10 + 0.7
            drift = 22 + p * (34 + i * 3)
            smoke_x = int(local[0] + math.cos(angle) * drift)
            smoke_y = int(local[1] + math.sin(angle) * drift - p * 24)
            smoke_r = int(10 + p * 22 + (i % 3) * 3)
            smoke_alpha = max(0, int(125 * (1.0 - p)))
            pygame.draw.circle(burst, (72, 70, 65, smoke_alpha), (smoke_x, smoke_y), smoke_r)
            pygame.draw.circle(burst, (142, 137, 124, smoke_alpha // 2), (smoke_x - 3, smoke_y - 3), max(3, smoke_r // 2))

        self._screen.blit(burst, burst.get_rect(center=center))

    def _draw_sidebar(self, match: Match, selected: Territory | None, attack_ratio: float) -> None:
        panel = pygame.Rect(SIDEBAR_X, 0, SIDEBAR_WIDTH, cfg.WINDOW_HEIGHT)
        pygame.draw.rect(self._screen, cfg.PANEL_BG, panel)
        pygame.draw.line(self._screen, (98, 87, 69), (SIDEBAR_X, 0), (SIDEBAR_X, cfg.WINDOW_HEIGHT), 2)

        y = 22
        title = self._title.render("Quadrant Wars", True, cfg.TEXT)
        self._screen.blit(title, (SIDEBAR_X + 22, y))
        y += 42
        subtitle = self._tiny.render("REAL-TIME COMMAND", True, cfg.ACCENT_2)
        self._screen.blit(subtitle, (SIDEBAR_X + 24, y))
        y += 34

        self._draw_stat_row(y, "Time", _format_time(match.elapsed), "Attack", f"{int(attack_ratio * 100)}%")
        y += 72

        if selected:
            y = self._draw_selected_card(selected, y)
        else:
            y = self._draw_hint_card(y)

        y = self._draw_players(match, y + 14)
        self._draw_log(match, y + 12)

    def _draw_stat_row(self, y: int, left_label: str, left: str, right_label: str, right: str) -> None:
        card_w = 116
        self._draw_metric_card(pygame.Rect(SIDEBAR_X + 22, y, card_w, 58), left_label, left, cfg.ACCENT)
        self._draw_metric_card(pygame.Rect(SIDEBAR_X + 154, y, card_w, 58), right_label, right, cfg.WARNING)

    def _draw_metric_card(self, rect: pygame.Rect, label: str, value: str, accent: tuple[int, int, int]) -> None:
        _draw_shadow_rect(self._screen, rect, radius=9, alpha=72, offset=(0, 4))
        pygame.draw.rect(self._screen, cfg.PANEL_BG_2, rect, border_radius=9)
        pygame.draw.rect(self._screen, _darken(accent, 35), rect, 1, border_radius=9)
        self._screen.blit(self._tiny.render(label.upper(), True, cfg.MUTED_TEXT), (rect.x + 12, rect.y + 8))
        self._screen.blit(self._subtitle.render(value, True, accent), (rect.x + 12, rect.y + 24))

    def _draw_selected_card(self, selected: Territory, y: int) -> int:
        rect = pygame.Rect(SIDEBAR_X + 22, y, 248, 184)
        _draw_shadow_rect(self._screen, rect, radius=10, alpha=90, offset=(0, 5))
        pygame.draw.rect(self._screen, (243, 235, 215), rect, border_radius=10)
        pygame.draw.rect(self._screen, cfg.ACCENT_2, rect, 2, border_radius=10)
        self._screen.blit(self._tiny.render("SELECTED TERRITORY", True, cfg.CARD_MUTED), (rect.x + 16, rect.y + 14))
        name = self._subtitle.render(_fit_text(self._subtitle, selected.owner.name, 210), True, cfg.CARD_TEXT)
        self._screen.blit(name, (rect.x + 16, rect.y + 32))

        stats = [
            ("Soldiers", selected.soldiers.count),
            ("Workers", selected.workers.count),
            ("Food", int(selected.food)),
            ("Worker cost", selected.worker_cost()),
        ]
        for i, (label, value) in enumerate(stats):
            x = rect.x + 16 + (i % 2) * 116
            yy = rect.y + 72 + (i // 2) * 42
            self._screen.blit(self._tiny.render(label, True, cfg.CARD_MUTED), (x, yy))
            self._screen.blit(self._font.render(str(value), True, cfg.CARD_TEXT), (x, yy + 14))

        self._draw_command_key(rect.x + 16, rect.y + 150, "1", "Buy Soldier")
        self._draw_command_key(rect.x + 133, rect.y + 150, "2", "Buy Worker")
        return rect.bottom

    def _draw_hint_card(self, y: int) -> int:
        rect = pygame.Rect(SIDEBAR_X + 22, y, 248, 124)
        _draw_shadow_rect(self._screen, rect, radius=10, alpha=72, offset=(0, 5))
        pygame.draw.rect(self._screen, cfg.PANEL_BG_2, rect, border_radius=10)
        pygame.draw.rect(self._screen, (82, 91, 100), rect, 1, border_radius=10)
        lines = [
            "Select your territory.",
            "Click an enemy to send troops.",
            "Use 1/2 to recruit, +/- to tune attack.",
        ]
        self._screen.blit(self._tiny.render("COMMANDS", True, cfg.ACCENT_2), (rect.x + 16, rect.y + 14))
        for i, line in enumerate(lines):
            self._screen.blit(self._small.render(line, True, cfg.TEXT), (rect.x + 16, rect.y + 38 + i * 24))
        return rect.bottom

    def _draw_command_key(self, x: int, y: int, key: str, label: str) -> None:
        rect = pygame.Rect(x, y, 100, 24)
        pygame.draw.rect(self._screen, (40, 44, 50), rect, border_radius=6)
        pygame.draw.rect(self._screen, (13, 17, 22), (x + 4, y + 4, 22, 16), border_radius=4)
        self._screen.blit(self._tiny.render(key, True, cfg.TEXT), (x + 12, y + 5))
        self._screen.blit(self._tiny.render(label, True, cfg.TEXT), (x + 32, y + 5))

    def _draw_players(self, match: Match, y: int) -> int:
        rect = pygame.Rect(SIDEBAR_X + 22, y, 248, 36 + len(match.players) * 30)
        pygame.draw.rect(self._screen, cfg.PANEL_BG_2, rect, border_radius=10)
        pygame.draw.rect(self._screen, (72, 76, 82), rect, 1, border_radius=10)
        self._screen.blit(self._tiny.render("PLAYERS", True, cfg.ACCENT_2), (rect.x + 14, rect.y + 12))
        for i, player in enumerate(match.players):
            yy = rect.y + 34 + i * 30
            pygame.draw.circle(self._screen, player.color, (rect.x + 18, yy + 10), 7)
            name = _fit_text(self._small, player.name, 150)
            self._screen.blit(self._small.render(name, True, cfg.TEXT), (rect.x + 32, yy))
            status_color = cfg.SUCCESS if player.is_alive else (138, 142, 148)
            status = "alive" if player.is_alive else "out"
            status_text = self._tiny.render(status.upper(), True, status_color)
            self._screen.blit(status_text, (rect.right - status_text.get_width() - 14, yy + 3))
        return rect.bottom

    def _draw_log(self, match: Match, y: int) -> None:
        rect = pygame.Rect(SIDEBAR_X + 22, y, 248, cfg.WINDOW_HEIGHT - y - 22)
        pygame.draw.rect(self._screen, (24, 27, 32), rect, border_radius=10)
        pygame.draw.rect(self._screen, (58, 62, 68), rect, 1, border_radius=10)
        self._screen.blit(self._tiny.render("BATTLE LOG", True, cfg.ACCENT_2), (rect.x + 14, rect.y + 12))
        yy = rect.y + 36
        for line in match.event_log[-5:]:
            for part in _wrap_text(self._tiny, line, 212):
                self._screen.blit(self._tiny.render(part, True, cfg.MUTED_TEXT), (rect.x + 14, yy))
                yy += 15
            yy += 8


def _draw_shadow_rect(
    surface: pygame.Surface,
    rect: pygame.Rect,
    radius: int,
    alpha: int,
    offset: tuple[int, int],
) -> None:
    shadow = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, alpha), shadow.get_rect(), border_radius=radius)
    surface.blit(shadow, rect.move(offset))


def _wandering_position(territory: Territory, role: str, index: int, elapsed: float) -> tuple[tuple[int, int], float]:
    polygon = territory.polygon
    cx, cy = territory.centroid
    xs = [point[0] for point in polygon]
    ys = [point[1] for point in polygon]
    spread = max(34.0, min(max(xs) - min(xs), max(ys) - min(ys)) * 0.28)
    role_bias = {"queen": 0.16, "worker": 0.36, "soldier": 0.62}[role]
    seed = (territory.id + 1) * 31 + index * 17 + len(role) * 13
    base_angle = (seed * 2.399963) % math.tau
    speed = {"queen": 0.35, "worker": 0.72, "soldier": 0.95}[role]
    orbit = base_angle + math.sin(elapsed * speed + seed) * 0.65
    radius = spread * (role_bias + 0.16 * math.sin(elapsed * speed * 0.7 + seed * 0.3))
    wobble = math.cos(elapsed * (speed + 0.35) + seed) * 18
    x = cx + math.cos(orbit) * radius + math.cos(base_angle + math.pi / 2) * wobble
    y = cy + math.sin(orbit) * radius + math.sin(base_angle + math.pi / 2) * wobble

    for factor in (1.0, 0.82, 0.64, 0.46, 0.28, 0.1):
        px = cx + (x - cx) * factor
        py = cy + (y - cy) * factor
        if _point_in_polygon((px, py), polygon):
            return (int(px), int(py)), 1.08 if role == "queen" else 0.92 if role == "worker" else 0.86
    return (int(cx), int(cy)), 1.0


def _point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if (yi > y) != (yj > y):
            x_intersect = (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi
            if x < x_intersect:
                inside = not inside
        j = i
    return inside


def _mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _brighten(color: tuple[int, int, int], amount: int) -> tuple[int, int, int]:
    return tuple(min(255, channel + amount) for channel in color)


def _darken(color: tuple[int, int, int], amount: int) -> tuple[int, int, int]:
    return tuple(max(0, channel - amount) for channel in color)


def _format_time(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 60}:{total % 60:02d}"


def _fit_text(font: pygame.font.Font, text: str, max_width: int) -> str:
    if font.size(text)[0] <= max_width:
        return text
    clipped = text
    while clipped and font.size(clipped + "...")[0] > max_width:
        clipped = clipped[:-1]
    return clipped + "..." if clipped else "..."


def _wrap_text(font: pygame.font.Font, text: str, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if font.size(candidate)[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines
