
import pygame

from quadrant_wars import balance_config as cfg


class Button:
    def __init__(self, rect, label, action):
        self.rect = rect
        self.label = label
        self.action = action

    def draw(self, surface, font, active = True):
        mouse = pygame.mouse.get_pos()
        hover = self.rect.collidepoint(mouse)
        shadow = self.rect.move(0, 4)
        pygame.draw.rect(surface, (4, 8, 7), shadow, border_radius=5)

        if active:
            color = (234, 184, 82) if hover else (201, 148, 58)
            text_color = (24, 25, 20)
            stroke = (255, 228, 159) if hover else (230, 193, 119)
        else:
            color = (67, 72, 82)
            text_color = cfg.MUTED_TEXT
            stroke = (91, 96, 106)

        pygame.draw.rect(surface, color, self.rect, border_radius=5)
        shine = pygame.Rect(self.rect.x + 2, self.rect.y + 2, self.rect.width - 4, max(8, self.rect.height // 3))
        pygame.draw.rect(surface, _brighten(color, 18), shine, border_radius=4)
        pygame.draw.rect(surface, stroke, self.rect, 1, border_radius=5)
        text = font.render(self.label, True, text_color)
        surface.blit(text, text.get_rect(center=self.rect.center))

    def clicked(self, event):
        return event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos)


def _brighten(color, amount):
    return tuple(min(255, channel + amount) for channel in color)
