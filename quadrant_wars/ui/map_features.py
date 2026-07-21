import math

import pygame

from quadrant_wars.core.terrain import GATE_HALF_WIDTH


def draw_map_features(screen, terrain, elapsed):
    draw_mountains(screen, terrain)
    draw_border_walls(screen, terrain, elapsed)


def draw_mountains(screen, terrain):
    for obstacle in terrain.obstacles:
        cx, cy = map(int, obstacle.center)
        radius = int(obstacle.radius)
        shadow = pygame.Rect(0, 0, radius * 2, max(18, radius // 2))
        shadow.center = (cx + 5, cy + radius // 2)
        pygame.draw.ellipse(screen, (30, 37, 27), shadow)

        peaks = (
            (cx - radius // 2, cy + radius // 3, radius * 0.72),
            (cx + radius // 3, cy + radius // 3, radius * 0.82),
            (cx, cy + radius // 3, radius * 1.05),
        )
        for px, base_y, height in peaks:
            half = int(height * 0.55)
            top = (px, int(base_y - height))
            left = (px - half, base_y)
            right = (px + half, base_y)
            pygame.draw.polygon(screen, (68, 75, 65), (top, left, right))
            pygame.draw.polygon(
                screen,
                (103, 108, 91),
                (top, left, (px, base_y), (px + int(half * 0.18), int(base_y - height * 0.45))),
            )
            snow_y = int(base_y - height * 0.63)
            pygame.draw.polygon(
                screen,
                (191, 195, 177),
                (top, (px - int(half * 0.28), snow_y), (px, snow_y + 7), (px + int(half * 0.25), snow_y)),
            )


def draw_border_walls(screen, terrain, elapsed):
    for wall in terrain.walls:
        for start, end in wall.drawing_pieces():
            start = tuple(map(round, start))
            end = tuple(map(round, end))
            pygame.draw.line(screen, (29, 31, 27), start, end, 13)
            pygame.draw.line(screen, (102, 101, 88), start, end, 9)
            pygame.draw.line(screen, (154, 150, 128), start, end, 4)
            _draw_wall_stones(screen, start, end)

        if wall.gate is not None:
            _draw_gate(screen, wall, elapsed)


def _draw_wall_stones(screen, start, end):
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if length < 12:
        return
    steps = max(1, int(length // 23))
    for index in range(1, steps):
        ratio = index / steps
        point = (
            round(start[0] + dx * ratio),
            round(start[1] + dy * ratio),
        )
        pygame.draw.circle(screen, (193, 184, 151), point, 3)
        pygame.draw.circle(screen, (75, 76, 67), point, 3, 1)


def _draw_gate(screen, wall, elapsed):
    dx = wall.end[0] - wall.start[0]
    dy = wall.end[1] - wall.start[1]
    length = max(1.0, math.hypot(dx, dy))
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux
    cx, cy = wall.gate.center

    road_start = (round(cx - nx * 25), round(cy - ny * 25))
    road_end = (round(cx + nx * 25), round(cy + ny * 25))
    pygame.draw.line(screen, (89, 67, 43), road_start, road_end, 12)
    pygame.draw.line(screen, (154, 126, 79), road_start, road_end, 4)

    for direction in (-1, 1):
        px = round(cx + ux * GATE_HALF_WIDTH * direction)
        py = round(cy + uy * GATE_HALF_WIDTH * direction)
        pygame.draw.circle(screen, (43, 45, 40), (px + 2, py + 3), 13)
        pygame.draw.circle(screen, (119, 118, 102), (px, py), 12)
        pygame.draw.circle(screen, (176, 168, 139), (px - 2, py - 2), 7)
        pygame.draw.circle(screen, (67, 69, 62), (px, py), 12, 2)

    pulse = 128 + int(math.sin(elapsed * 2.4 + cx * 0.01) * 35)
    marker = pygame.Surface((18, 18), pygame.SRCALPHA)
    pygame.draw.circle(marker, (236, 195, 94, pulse), (9, 9), 5)
    screen.blit(marker, marker.get_rect(center=(round(cx), round(cy))))
