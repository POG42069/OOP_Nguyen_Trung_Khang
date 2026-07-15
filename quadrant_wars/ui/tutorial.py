from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

from quadrant_wars import balance_config as cfg
from quadrant_wars.ui.art import ArtAssets, menu_background


@dataclass(frozen=True)
class TutorialPage:
    nav_label: str
    title: str
    kicker: str
    bullets: tuple[str, ...]
    accent: tuple[int, int, int]
    preview: str


def tutorial_pages() -> tuple[TutorialPage, ...]:
    return (
        TutorialPage(
            "LUẬT CHƠI",
            "Chinh phục toàn bản đồ",
            "VÀNG LÀ CỤC BỘ, QUYẾT ĐỊNH LÀ TOÀN CỤC",
            (
                "Mỗi lãnh thổ giữ kho vàng riêng. Muốn tuyển quân hoặc phát triển ở đâu, vùng đó phải tự có đủ vàng.",
                f"Mỗi vùng sống tự tạo {cfg.BASE_TERRITORY_INCOME_PER_SECOND:.2f} vàng/giây, kể cả khi không còn Worker.",
                "Điều Soldier sang vùng khác để tiếp viện hoặc công thành. Quân sống sót giữ nguyên HP sau trận.",
                "Hạ Queen và lõi lâu đài để chiếm vùng. Người kiểm soát vương quốc cuối cùng sẽ chiến thắng.",
            ),
            (232, 177, 74),
            "gameplay",
        ),
        TutorialPage(
            "ĐƠN VỊ",
            "Biết rõ đội quân của bạn",
            "MỖI ĐƠN VỊ CÓ MỘT VAI TRÒ RIÊNG",
            (
                f"Soldier: {cfg.SOLDIER_HP} HP, {cfg.SOLDIER_ATK} damage, {cfg.SOLDIER_ATK_SPEED:.1f} đòn/giây. Đây là đơn vị duy nhất có thể hành quân.",
                f"Worker: {cfg.WORKER_HP} HP, tạo {cfg.FOOD_PER_WORKER_PER_SECOND:.2f} vàng/giây và trú ẩn khi lâu đài bị đánh.",
                f"Queen: {cfg.QUEEN_HP} HP, bắn trả {cfg.QUEEN_ATK} damage từ lâu đài và quyết định vùng còn hoạt động hay không.",
                f"Vệ binh: {cfg.DEFENDER_HP} HP, giáo {cfg.DEFENDER_ATK} damage, tự giữ cổng Fortress và hồi sinh sau {int(cfg.DEFENDER_RESPAWN_DELAY)} giây ngoài trận.",
            ),
            (102, 190, 151),
            "units",
        ),
        TutorialPage(
            "PHÁT TRIỂN",
            "Chọn bản sắc cho từng vùng",
            f"CẤP I {cfg.DEVELOPMENT_TIER_1_COST}G  •  CẤP II {cfg.DEVELOPMENT_TIER_2_COST}G  •  ĐỔI NHÁNH {cfg.DEVELOPMENT_CONVERSION_COST}G",
            (
                f"Economy: mỗi cấp tăng {int(cfg.ECONOMY_INCOME_BONUS_PER_LEVEL * 100)}% thu nhập Worker và giảm {int(cfg.ECONOMY_WORKER_DISCOUNT_PER_LEVEL * 100)}% giá Worker.",
                f"Barracks: mỗi cấp giảm {cfg.BARRACKS_SOLDIER_DISCOUNT_PER_LEVEL} vàng giá Soldier và giảm {int(cfg.BARRACKS_SPAWN_REDUCTION_PER_LEVEL * 100)}% thời gian huấn luyện.",
                f"Fortress: mỗi cấp có {cfg.FORTRESS_DEFENDERS_PER_LEVEL} Vệ binh và giảm {int(cfg.FORTRESS_DAMAGE_REDUCTION_PER_LEVEL * 100)}% sát thương phòng thủ.",
                "Công trình mất một cấp khi vùng bị chiếm. Phế tích cấp 0 có thể được sửa bằng cách chọn lại đúng nhánh.",
            ),
            (103, 166, 222),
            "development",
        ),
        TutorialPage(
            "MỤC TIÊU",
            "Tranh báu vật trung lập",
            f"XUẤT HIỆN TỪ {int(cfg.OBJECTIVE_FIRST_ACTIVE_AT)} GIÂY  •  {cfg.OBJECTIVE_GUARDS} LÍNH GÁC  •  LÕI {cfg.OBJECTIVE_CORE_HP} HP",
            (
                f"Caravan: cộng {int(cfg.OBJECTIVE_CARAVAN_GOLD)} vàng vào thủ đô hiện tại của người chiếm.",
                f"War Banner: tăng {round((cfg.WAR_BANNER_ATTACK_MULTIPLIER - 1) * 100)}% damage và tốc độ hành quân trong {int(cfg.WAR_BANNER_DURATION)} giây.",
                f"Ancient Shrine: hồi {int(cfg.OBJECTIVE_SHRINE_HEAL)} HP cho mọi Queen còn sống của người chiếm.",
                "Mục tiêu không tự hết hạn. Nếu nhiều phe cùng tới, họ phải loại nhau trước; phe cuối cùng mới tiếp tục đánh lính gác và lõi.",
            ),
            (204, 126, 86),
            "objectives",
        ),
        TutorialPage(
            "ĐIỀU KHIỂN",
            "Ba phím, toàn bộ chiến thuật",
            "P1 Q/W/E  •  P2 I/O/P  •  P3 Z/X/C  •  P4 B/N/M",
            (
                "Phím 1 mở Tuyển quân. Trong bảng này: phím 1 đổi vùng, phím 2 đổi Soldier/Worker/Hủy, phím 3 xác nhận.",
                "Phím 2 mở Tấn công. Chọn mục tiêu bằng ba phím, sau đó chọn 0% để hủy, 33% hoặc 66% Soldier mỗi vùng.",
                "Phím 3 mở Chiến lược. Chọn Development, mục tiêu trung lập hoặc hủy thao tác.",
                "Trong Development: phím 1 đổi vùng, phím 2 đổi Economy/Barracks/Fortress/Hủy, phím 3 xác nhận.",
                "Nhấn Esc để tạm dừng. Từ Pause có thể đọc lại cẩm nang mà trận đấu vẫn đóng băng.",
            ),
            (188, 123, 204),
            "controls",
        ),
    )


class TutorialView:
    def __init__(self, screen: pygame.Surface) -> None:
        self._screen = screen
        self._art = ArtAssets(screen.get_size())
        self._title = pygame.font.SysFont("segoeui", 36, bold=True)
        self._heading = pygame.font.SysFont("segoeui", 24, bold=True)
        self._body = pygame.font.SysFont("segoeui", 18)
        self._small = pygame.font.SysFont("segoeui", 14)
        self._tiny = pygame.font.SysFont("segoeui", 12, bold=True)
        self._pages = tutorial_pages()

    @property
    def pages(self) -> tuple[TutorialPage, ...]:
        return self._pages

    @property
    def target_surface(self) -> pygame.Surface:
        return self._screen

    def bind_surface(self, screen: pygame.Surface) -> None:
        if screen is self._screen:
            return
        if screen.get_size() != self._screen.get_size():
            self._art = ArtAssets(screen.get_size())
        self._screen = screen

    @property
    def back_rect(self) -> pygame.Rect:
        return pygame.Rect(40, 648, 172, 42)

    @property
    def previous_rect(self) -> pygame.Rect:
        return pygame.Rect(1040, 648, 62, 42)

    @property
    def next_rect(self) -> pygame.Rect:
        return pygame.Rect(1114, 648, 126, 42)

    def tab_rects(self) -> tuple[pygame.Rect, ...]:
        return tuple(
            pygame.Rect(40, 150 + index * 78, 236, 58)
            for index in range(len(self._pages))
        )

    def max_scroll(self, page_index: int) -> float:
        body_height = 0
        for bullet in self._pages[page_index].bullets:
            body_height += len(_wrap_text(self._body, bullet, 322)) * 23 + 17
        return float(max(0, body_height - 354))

    def draw(
        self,
        page_index: int,
        elapsed: float,
        reveal: float,
        scroll: float,
    ) -> None:
        background = menu_background(self._screen.get_size())
        if background is not None:
            self._screen.blit(background, (0, 0))
        else:
            self._screen.fill((15, 21, 20))
        veil = pygame.Surface(self._screen.get_size(), pygame.SRCALPHA)
        veil.fill((5, 10, 10, 174))
        self._screen.blit(veil, (0, 0))

        page = self._pages[page_index]
        self._draw_header(page_index)
        self._draw_tabs(page_index, elapsed)

        content = pygame.Surface((924, 512), pygame.SRCALPHA)
        pygame.draw.rect(content, (12, 18, 18, 232), content.get_rect(), border_radius=8)
        pygame.draw.rect(content, (*page.accent, 185), content.get_rect(), 1, border_radius=8)
        pygame.draw.rect(content, (*page.accent, 210), (0, 0, 7, content.get_height()), border_radius=4)

        offset_x = int((1.0 - reveal) * 18)
        title = self._heading.render(page.title, True, (255, 247, 224))
        content.blit(title, (36 + offset_x, 28))
        kicker = self._tiny.render(page.kicker, True, page.accent)
        content.blit(kicker, (38 + offset_x, 70))

        max_scroll = self.max_scroll(page_index)
        scroll = max(0.0, min(max_scroll, scroll))
        body_y = 112 - int(scroll)
        for bullet in page.bullets:
            if 82 <= body_y <= 466:
                pygame.draw.circle(content, page.accent, (45 + offset_x, body_y + 9), 4)
            lines = _wrap_text(self._body, bullet, 322)
            for line in lines:
                if 82 <= body_y <= 466:
                    text = self._body.render(line, True, (215, 222, 211))
                    content.blit(text, (62 + offset_x, body_y))
                body_y += 23
            body_y += 17

        if max_scroll > 0.0:
            track = pygame.Rect(411, 112, 3, 354)
            pygame.draw.rect(content, (58, 68, 63), track, border_radius=2)
            thumb_height = max(42, round(track.height * track.height / (track.height + max_scroll)))
            thumb_travel = track.height - thumb_height
            thumb_y = track.y + round(thumb_travel * scroll / max_scroll)
            pygame.draw.rect(
                content,
                page.accent,
                (track.x, thumb_y, track.width, thumb_height),
                border_radius=2,
            )

        preview_rect = pygame.Rect(432, 100, 456, 354)
        self._draw_preview(content, preview_rect, page.preview, elapsed, page.accent)
        preview_label = self._small.render("SA BÀN MINH HỌA", True, (151, 162, 154))
        content.blit(preview_label, (preview_rect.x, preview_rect.bottom + 12))

        content.set_alpha(max(0, min(255, int(255 * reveal))))
        self._screen.blit(content, (316, 116))
        self._draw_navigation(page_index)

    def _draw_header(self, page_index: int) -> None:
        eyebrow = self._small.render("QUADRANT WARS  /  CẨM NANG CHỈ HUY", True, (199, 171, 106))
        self._screen.blit(eyebrow, (40, 28))
        title = self._title.render("HỌC NHANH. ĐÁNH CHẮC.", True, (255, 247, 224))
        self._screen.blit(title, (38, 52))
        progress = self._small.render(f"{page_index + 1:02d} / {len(self._pages):02d}", True, (186, 196, 188))
        self._screen.blit(progress, progress.get_rect(topright=(1240, 64)))
        pygame.draw.line(self._screen, (106, 91, 60), (40, 108), (1240, 108), 1)

    def _draw_tabs(self, page_index: int, elapsed: float) -> None:
        mouse = pygame.mouse.get_pos()
        for index, (page, rect) in enumerate(zip(self._pages, self.tab_rects())):
            active = index == page_index
            hover = rect.collidepoint(mouse)
            layer = pygame.Surface(rect.size, pygame.SRCALPHA)
            fill = (30, 38, 36, 232) if active else (17, 24, 23, 195 if hover else 165)
            pygame.draw.rect(layer, fill, layer.get_rect(), border_radius=6)
            if active:
                pygame.draw.rect(layer, (*page.accent, 230), (0, 0, 5, rect.height), border_radius=3)
            pygame.draw.rect(layer, (*page.accent, 150 if active or hover else 70), layer.get_rect(), 1, border_radius=6)
            self._screen.blit(layer, rect)
            number = self._tiny.render(f"0{index + 1}", True, page.accent if active else (124, 135, 128))
            self._screen.blit(number, (rect.x + 16, rect.y + 12))
            label = self._small.render(page.nav_label, True, (250, 242, 220) if active else (171, 181, 174))
            self._screen.blit(label, (rect.x + 51, rect.y + 18))
            if active:
                pulse = 3 + int((math.sin(elapsed * 4.0) + 1.0) * 1.5)
                pygame.draw.circle(self._screen, page.accent, (rect.right - 17, rect.centery), pulse)

    def _draw_navigation(self, page_index: int) -> None:
        _draw_button(self._screen, self.back_rect, "←  QUAY LẠI", self._small, (188, 166, 108))
        _draw_button(
            self._screen,
            self.previous_rect,
            "←",
            self._heading,
            (112, 126, 119),
            active=page_index > 0,
        )
        label = "HOÀN TẤT" if page_index == len(self._pages) - 1 else "TIẾP  →"
        _draw_button(
            self._screen,
            self.next_rect,
            label,
            self._small,
            self._pages[page_index].accent,
        )

    def _draw_preview(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        preview: str,
        elapsed: float,
        accent: tuple[int, int, int],
    ) -> None:
        field = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(field, (22, 35, 27, 235), field.get_rect(), border_radius=7)
        pygame.draw.rect(field, (*accent, 120), field.get_rect(), 1, border_radius=7)
        if preview == "gameplay":
            self._draw_gameplay_preview(field, elapsed)
        elif preview == "units":
            self._draw_units_preview(field, elapsed)
        elif preview == "development":
            self._draw_development_preview(field, elapsed)
        elif preview == "objectives":
            self._draw_objective_preview(field, elapsed)
        else:
            self._draw_controls_preview(field, elapsed)
        surface.blit(field, rect)

    def _draw_gameplay_preview(self, field: pygame.Surface, elapsed: float) -> None:
        w, h = field.get_size()
        colors = cfg.PLAYER_COLORS
        polygons = (
            [(10, 10), (224, 10), (205, 167), (10, 178)],
            [(232, 10), (w - 10, 10), (w - 10, 175), (249, 165)],
            [(10, 186), (207, 174), (220, h - 10), (10, h - 10)],
            [(246, 174), (w - 10, 184), (w - 10, h - 10), (232, h - 10)],
        )
        for color, polygon in zip(colors, polygons):
            pygame.draw.polygon(field, (*color, 58), polygon)
            pygame.draw.lines(field, (*_brighten(color, 35), 205), True, polygon, 2)
        for index, position in enumerate(((104, 91), (352, 90), (108, 267), (350, 267))):
            building = self._art.building(
                ("fortress_western", "fortress_northern", "fortress_forest", "fortress_sun")[index],
                68,
            )
            if building is not None:
                field.blit(building, building.get_rect(midbottom=(position[0], position[1] + 24)))
        progress = (elapsed * 0.16) % 1.0
        sx = 116 + (337 - 116) * progress
        sy = 105 + math.sin(progress * math.pi) * 34
        self._blit_unit(field, "soldier", (round(sx), round(sy)), colors[0], elapsed, "walk", 0.58)
        pygame.draw.circle(field, (242, 193, 66), (76, 134), 7)
        gold = self._small.render(f"+{cfg.FOOD_PER_WORKER_PER_SECOND:.2f}/s", True, (255, 229, 139))
        field.blit(gold, (89, 126))

    def _draw_units_preview(self, field: pygame.Surface, elapsed: float) -> None:
        entries = (
            ("queen", "QUEEN", (92, 184)),
            ("worker", "WORKER", (202, 184)),
            ("soldier", "SOLDIER", (314, 184)),
            ("defender", "VỆ BINH", (410, 184)),
        )
        for index, (role, label, position) in enumerate(entries):
            cycle = (elapsed + index * 0.41) % 3.0
            if role == "worker":
                action = "work" if cycle > 1.5 else "walk"
            elif role in ("soldier", "defender", "queen"):
                action = "attack" if cycle > 1.75 else "idle"
            else:
                action = "idle"
            phase = cycle - 1.75 if action == "attack" else elapsed + index * 0.2
            self._blit_unit(field, role, position, cfg.PLAYER_COLORS[index % 4], phase, action, 0.92)
            text = self._tiny.render(label, True, (235, 229, 207))
            field.blit(text, text.get_rect(center=(position[0], 244)))
        pygame.draw.line(field, (95, 118, 95), (28, 262), (428, 262), 1)
        hint = self._small.render("Idle  •  Di chuyển  •  Tấn công  •  Trúng đòn", True, (148, 165, 151))
        field.blit(hint, hint.get_rect(center=(field.get_width() // 2, 292)))

    def _draw_development_preview(self, field: pygame.Surface, elapsed: float) -> None:
        centers = (78, 228, 378)
        labels = ("ECONOMY", "BARRACKS", "FORTRESS")
        colors = ((91, 178, 104), (205, 118, 72), (102, 157, 208))
        for index, (x, label, color) in enumerate(zip(centers, labels, colors)):
            pygame.draw.ellipse(field, (7, 13, 9, 115), (x - 55, 224, 110, 30))
            if index == 0:
                pygame.draw.rect(field, (143, 104, 56), (x - 24, 142, 48, 61), border_radius=3)
                pygame.draw.polygon(field, color, [(x - 34, 144), (x, 116), (x + 34, 144)])
                for coin in range(2):
                    pygame.draw.circle(field, (243, 195, 67), (x + 31 + coin * 10, 173 - coin * 8), 5)
            elif index == 1:
                for tent in (-18, 18):
                    pygame.draw.polygon(field, color, [(x + tent - 24, 204), (x + tent, 126), (x + tent + 24, 204)])
                pygame.draw.line(field, (194, 194, 181), (x - 40, 211), (x + 42, 126), 3)
            else:
                pygame.draw.rect(field, (132, 139, 135), (x - 49, 147, 98, 62), border_radius=3)
                for tower in (-42, 31):
                    pygame.draw.rect(field, (113, 121, 119), (x + tower, 123, 20, 88), border_radius=3)
                pygame.draw.rect(field, (57, 45, 31), (x - 10, 177, 20, 34), border_radius=9)
                for spear in range(3):
                    pygame.draw.line(field, (204, 205, 190), (x + 52 + spear * 7, 206), (x + 55 + spear * 7, 135), 2)
            label_surf = self._tiny.render(label, True, color)
            field.blit(label_surf, label_surf.get_rect(center=(x, 279)))
            level = 1 + int((elapsed * 0.35 + index * 0.4) % 2)
            level_surf = self._small.render(f"CẤP {level}", True, (225, 220, 199))
            field.blit(level_surf, level_surf.get_rect(center=(x, 306)))

    def _draw_objective_preview(self, field: pygame.Surface, elapsed: float) -> None:
        centers = ((92, 172), (228, 172), (364, 172))
        labels = ("CARAVAN", "WAR BANNER", "ANCIENT SHRINE")
        for index, ((x, y), label) in enumerate(zip(centers, labels)):
            pulse = 30 + int(math.sin(elapsed * 3.0 + index) * 4)
            pygame.draw.circle(field, (232, 186, 74, 35), (x, y), pulse + 10)
            pygame.draw.circle(field, (232, 186, 74, 160), (x, y), pulse, 2)
            if index == 0:
                pygame.draw.rect(field, (126, 81, 42), (x - 27, y - 17, 54, 30), border_radius=3)
                pygame.draw.circle(field, (55, 42, 30), (x - 20, y + 18), 9)
                pygame.draw.circle(field, (55, 42, 30), (x + 20, y + 18), 9)
                pygame.draw.circle(field, (242, 193, 66), (x, y - 4), 7)
            elif index == 1:
                pygame.draw.line(field, (110, 78, 42), (x - 7, y + 28), (x - 7, y - 37), 4)
                pygame.draw.polygon(field, (194, 70, 58), [(x - 5, y - 34), (x + 32, y - 22), (x - 5, y - 8)])
            else:
                for offset, height in ((-21, 39), (0, 55), (21, 39)):
                    pygame.draw.polygon(field, (103, 126, 129), [(x + offset - 7, y + 27), (x + offset + 7, y + 27), (x + offset + 3, y + 27 - height)])
                pygame.draw.circle(field, (111, 228, 216), (x, y - 3), 7)
            text = self._tiny.render(label, True, (235, 226, 199))
            field.blit(text, text.get_rect(center=(x, 247)))
        phase = int(elapsed * 2.0) % 3
        reward = (
            f"+{int(cfg.OBJECTIVE_CARAVAN_GOLD)} VÀNG",
            f"BUFF {int(cfg.WAR_BANNER_DURATION)} GIÂY",
            f"+{int(cfg.OBJECTIVE_SHRINE_HEAL)} HP QUEEN",
        )[phase]
        reward_surf = self._small.render(reward, True, (247, 205, 105))
        field.blit(reward_surf, reward_surf.get_rect(center=(field.get_width() // 2, 304)))

    def _draw_controls_preview(self, field: pygame.Surface, elapsed: float) -> None:
        keysets = (("Q", "W", "E"), ("I", "O", "P"), ("Z", "X", "C"), ("B", "N", "M"))
        active = int(elapsed * 1.4) % 3
        for row, keys in enumerate(keysets):
            y = 55 + row * 66
            player = self._tiny.render(f"P{row + 1}", True, cfg.PLAYER_COLORS[row])
            field.blit(player, (35, y + 10))
            for index, key in enumerate(keys):
                rect = pygame.Rect(89 + index * 72, y, 52, 42)
                fill = _brighten(cfg.PLAYER_COLORS[row], 18) if index == active else (35, 43, 42)
                pygame.draw.rect(field, fill, rect, border_radius=5)
                pygame.draw.rect(field, _brighten(cfg.PLAYER_COLORS[row], 38), rect, 2, border_radius=5)
                text = self._heading.render(key, True, (255, 247, 224))
                field.blit(text, text.get_rect(center=rect.center))
            action = ("TUYỂN", "TẤN CÔNG", "CHIẾN LƯỢC")[active]
            action_surf = self._small.render(action, True, (229, 219, 190))
            field.blit(action_surf, (326, y + 11))

    def _blit_unit(
        self,
        surface: pygame.Surface,
        role: str,
        center: tuple[int, int],
        color: tuple[int, int, int],
        phase: float,
        action: str,
        scale: float,
    ) -> None:
        base_height = {"queen": 78, "worker": 62, "soldier": 60, "defender": 64}[role]
        frame_count = self._art.animation_count(role, action)
        frame = 0 if frame_count <= 1 else int(max(0.0, phase) * (8 if action == "walk" else 6)) % frame_count
        sprite = self._art.animation_frame(role, action, frame, round(base_height * scale))
        if sprite is None:
            return
        marker = pygame.Surface((38, 14), pygame.SRCALPHA)
        pygame.draw.ellipse(marker, (*color, 155), marker.get_rect())
        pygame.draw.ellipse(marker, (*_brighten(color, 45), 225), marker.get_rect(), 2)
        surface.blit(marker, marker.get_rect(center=(center[0], center[1] + 11)))
        surface.blit(sprite, sprite.get_rect(midbottom=(center[0], center[1] + 11)))


def _wrap_text(font: pygame.font.Font, text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if current and font.size(candidate)[0] > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _draw_button(
    screen: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    font: pygame.font.Font,
    accent: tuple[int, int, int],
    *,
    active: bool = True,
) -> None:
    hover = active and rect.collidepoint(pygame.mouse.get_pos())
    fill = _brighten(accent, 12) if hover else accent if active else (55, 62, 59)
    text_color = (22, 27, 24) if active else (119, 128, 121)
    pygame.draw.rect(screen, (2, 6, 5), rect.move(0, 4), border_radius=6)
    pygame.draw.rect(screen, fill, rect, border_radius=6)
    pygame.draw.rect(screen, _brighten(fill, 42), rect, 1, border_radius=6)
    text = font.render(label, True, text_color)
    screen.blit(text, text.get_rect(center=rect.center))


def _brighten(color: tuple[int, int, int], amount: int) -> tuple[int, int, int]:
    return tuple(min(255, channel + amount) for channel in color)
