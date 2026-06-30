from __future__ import annotations

import pygame

from quadrant_wars import balance_config as cfg


class Button:
    def __init__(self, rect: pygame.Rect, label: str, action: str) -> None:
        self.rect = rect
        self.label = label
        self.action = action

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, active: bool = True) -> None:
        mouse = pygame.mouse.get_pos()
        hover = self.rect.collidepoint(mouse)
        shadow = self.rect.move(0, 4)
        pygame.draw.rect(surface, (0, 0, 0), shadow, border_radius=8)

        if active:
            color = cfg.ACCENT_2 if hover else cfg.ACCENT
            text_color = (13, 18, 24)
            stroke = (255, 239, 203) if hover else (117, 219, 228)
        else:
            color = (67, 72, 82)
            text_color = cfg.MUTED_TEXT
            stroke = (91, 96, 106)

        pygame.draw.rect(surface, color, self.rect, border_radius=8)
        shine = pygame.Rect(self.rect.x + 2, self.rect.y + 2, self.rect.width - 4, max(8, self.rect.height // 3))
        pygame.draw.rect(surface, _brighten(color, 22), shine, border_radius=7)
        pygame.draw.rect(surface, stroke, self.rect, 2, border_radius=8)
        text = font.render(self.label, True, text_color)
        surface.blit(text, text.get_rect(center=self.rect.center))

    def clicked(self, event: pygame.event.Event) -> bool:
        return event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos)


def _brighten(color: tuple[int, int, int], amount: int) -> tuple[int, int, int]:
    return tuple(min(255, channel + amount) for channel in color)
