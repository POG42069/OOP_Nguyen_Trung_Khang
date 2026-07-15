from __future__ import annotations

import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

import pygame

from quadrant_wars import balance_config as cfg
from quadrant_wars.game.states import MenuState
from quadrant_wars.ui.sound import SoundManager


def main() -> None:
    pygame.mixer.pre_init(44100, -16, 1, 512)
    pygame.init()
    sound = SoundManager()
    pygame.display.set_caption("Quadrant Wars")
    flags = pygame.SCALED | pygame.RESIZABLE
    screen = pygame.display.set_mode((cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT), flags)
    clock = pygame.time.Clock()
    state = MenuState()
    running = True
    while running:
        dt = clock.tick(cfg.FPS) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            else:
                state = state.handle_event(event)
        state = state.update(dt)
        sound.play_many(state.pop_sound_events())
        state.draw(screen)
        pygame.display.flip()
    pygame.quit()


if __name__ == "__main__":
    main()
