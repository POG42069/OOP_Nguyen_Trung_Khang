from __future__ import annotations

import math
import random

import pygame

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.territory import Territory
from quadrant_wars.game.game_manager import Match

# Key labels for player HUD popups
KEY_LABELS = [
    ("Q", "W", "E"),
    ("I", "O", "P"),
    ("Z", "X", "C"),
    ("B", "N", "M"),
]


class Renderer:
    def __init__(self, screen: pygame.Surface) -> None:
        self._screen = screen
        self._font = pygame.font.SysFont("segoeui", 18)
        self._small = pygame.font.SysFont("segoeui", 14)
        self._tiny = pygame.font.SysFont("segoeui", 11)
        self._title = pygame.font.SysFont("georgia", 28, bold=True)
        self._subtitle = pygame.font.SysFont("segoeui", 20, bold=True)
        self._bold_small = pygame.font.SysFont("segoeui", 13, bold=True)
        self._background = self._build_background()
        self._unit_positions: dict[str, tuple[float, float]] = {}
        self._unit_targets: dict[str, tuple[float, float]] = {}
        self._sprite_cache: dict[str, pygame.Surface] = {}

    def draw_match(self, match: object, player_states: dict[int, dict]) -> None:
        self._screen.blit(self._background, (0, 0))

        # Dynamic drifting cloud shadows
        for i in range(8):
            fx = (int(match.elapsed * 15.0 * (1 + (i % 3))) + i * 200) % cfg.WINDOW_WIDTH
            fy = (int(math.sin(match.elapsed * 0.2 + i) * 50) + i * 100) % cfg.WINDOW_HEIGHT
            cloud = pygame.Surface((400, 300), pygame.SRCALPHA)
            pygame.draw.ellipse(cloud, (0, 0, 0, 25), cloud.get_rect())
            self._screen.blit(cloud, (fx - 200, fy - 150))

        # Draw territories (base terrain)
        for territory in match.territories:
            self._draw_territory(territory, match.elapsed)
            self._draw_base_building(territory, match.elapsed)

        # Environmental decor 
        for territory in match.territories:
            self._draw_territory_decor(territory, match.elapsed)

        # Supply Drop
        if getattr(match, "supply_drop", None) is not None:
            self._draw_supply_drop(match.supply_drop, match.elapsed)

        # Wandering units
        for territory in match.territories:
            self._draw_wandering_units(match, territory, match.elapsed)

        # Spawn effects
        for territory in match.territories:
            self._draw_spawn_effects(territory)

        # Moving armies
        for army in match.armies:
            self._draw_army(army)

        # Combat zones
        for zone in match.combat_zones:
            self._draw_combat_zone(zone, match.elapsed)

        # Combat result effects
        for effect in match.effects:
            self._draw_combat_effect(effect)

        # Territory labels (on top)
        for territory in match.territories:
            self._draw_territory_hud(territory)

        # Player popup menus
        for idx, state_info in player_states.items():
            if state_info["state"] != "idle":
                self._draw_player_popup(match, idx, state_info)

        # Minimal top-bar (time only)
        self._draw_top_bar(match)

    def _build_background(self) -> pygame.Surface:
        surface = pygame.Surface((cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT))
        # Rich green gradient for RTS feel
        for y in range(cfg.WINDOW_HEIGHT):
            t = y / cfg.WINDOW_HEIGHT
            r = int(28 + t * 24)
            g = int(52 + t * 38 + math.sin(t * 6) * 8)
            b = int(22 + t * 20)
            pygame.draw.line(surface, (r, g, b), (0, y), (cfg.WINDOW_WIDTH, y))

        # Subtle diamond grid pattern
        rng = random.Random(456)
        for x in range(0, cfg.WINDOW_WIDTH + 60, 60):
            for y in range(0, cfg.WINDOW_HEIGHT + 60, 60):
                ox = rng.randint(-4, 4)
                oy = rng.randint(-4, 4)
                c = rng.choice([(38, 72, 32), (42, 78, 36), (48, 82, 38)])
                pygame.draw.circle(surface, c, (x + ox, y + oy), rng.randint(1, 3))

        # Atmospheric fog patches
        for i in range(12):
            fx = rng.randint(0, cfg.WINDOW_WIDTH)
            fy = rng.randint(0, cfg.WINDOW_HEIGHT)
            fog = pygame.Surface((200, 120), pygame.SRCALPHA)
            pygame.draw.ellipse(fog, (58, 88, 48, 12), fog.get_rect())
            surface.blit(fog, (fx - 100, fy - 60))

        return surface

    def _draw_territory(self, territory: Territory, elapsed: float) -> None:
        alive = getattr(territory.owner, "is_alive", False)
        base = territory.owner.color if alive else (72, 72, 68)

        # Main terrain color with owner tint (much more distinct color, less generic green)
        grass = _mix(_brighten(base, 20), (88, 158, 62), 0.2) if alive else (82, 82, 78)

        # Shadow polygon
        shadow_pts = [(int(x + 5), int(y + 6)) for x, y in territory.polygon]
        pygame.draw.polygon(self._screen, (12, 18, 8), shadow_pts)

        # Fill with terrain gradient
        pygame.draw.polygon(self._screen, grass, territory.polygon)

        # Inner terrain texture (subtle stripes & rocky bumps)
        cx, cy = territory.centroid
        for i in range(15):
            x, y = _decor_point(territory, 200 + i, 0.88)
            stripe_c = _mix(grass, _brighten(grass, 18), 0.5)
            pygame.draw.line(self._screen, stripe_c, (x - 8, y), (x + 8, y), 1)

        # Rocky bumps
        for i in range(20):
            x, y = _decor_point(territory, 300 + i, 0.95)
            bump_c = _darken(grass, 15 + (i % 10))
            pygame.draw.circle(self._screen, bump_c, (x, y), 2 + (i % 2))
            pygame.draw.circle(self._screen, _brighten(grass, 10), (x - 1, y - 1), 1)

        # Inner glow around centroid
        glow = pygame.Surface((200, 140), pygame.SRCALPHA)
        glow_c = _brighten(base, 28) if alive else (68, 68, 64)
        pygame.draw.ellipse(glow, (*glow_c, 22), glow.get_rect())
        self._screen.blit(glow, glow.get_rect(center=(int(cx), int(cy))))

        # Animated border pulse for alive territories
        if alive:
            pulse = 0.5 + 0.5 * math.sin(elapsed * 1.8 + territory.id * 1.5)
            border_alpha = int(40 + pulse * 40)
            border_c = _brighten(base, 42)
            border_surf = pygame.Surface((cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT), pygame.SRCALPHA)
            pygame.draw.polygon(border_surf, (*border_c, border_alpha), territory.polygon, 3)
            self._screen.blit(border_surf, (0, 0))
        else:
            pygame.draw.polygon(self._screen, (52, 52, 48), territory.polygon, 2)

        # Inner edge highlight
        inner_pts = _shrink_polygon(territory.polygon, 6)
        if len(inner_pts) >= 3:
            highlight_surf = pygame.Surface((cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT), pygame.SRCALPHA)
            pygame.draw.polygon(highlight_surf, (255, 248, 218, 12), inner_pts, 1)
            self._screen.blit(highlight_surf, (0, 0))

    def _draw_territory_hud(self, territory: Territory) -> None:
        """Compact on-territory HUD showing key info."""
        cx, cy = territory.centroid
        cx, cy = int(cx), int(cy)
        owner_color = territory.owner.color
        alive = getattr(territory.owner, "is_alive", False)

        # Owner name badge (smaller, elegant)
        name = _fit_text(self._tiny, territory.owner.name, 120)
        name_surf = self._tiny.render(name, True, (248, 242, 228))
        badge_w = max(name_surf.get_width() + 28, 100)
        badge = pygame.Rect(cx - badge_w // 2, cy - 72, badge_w, 22)
        _draw_pill(self._screen, badge, (18, 22, 28, 200), owner_color if alive else (88, 88, 84))
        self._screen.blit(name_surf, name_surf.get_rect(center=badge.center))

        # Capital star indicator
        if territory.is_capital and alive:
            star_x = badge.right - 14
            star_y = badge.centery
            _draw_star(self._screen, (star_x, star_y), 5, (248, 208, 48))

        # Stats strip
        strip_w = 172
        strip = pygame.Rect(cx - strip_w // 2, cy + 62, strip_w, 24)
        strip_surf = pygame.Surface((strip.width, strip.height), pygame.SRCALPHA)
        pygame.draw.rect(strip_surf, (18, 22, 28, 180), strip_surf.get_rect(), border_radius=12)
        self._screen.blit(strip_surf, strip)
        pygame.draw.rect(self._screen, _darken(owner_color, 20) if alive else (68, 68, 64), strip, 1, border_radius=12)

        sx = strip.x + 10
        sy = strip.centery
        # Sword icon + soldier count
        pygame.draw.line(self._screen, (198, 138, 58), (sx, sy + 4), (sx + 6, sy - 4), 2)
        s_text = self._tiny.render(f"{territory.soldiers.count}", True, (248, 238, 218))
        self._screen.blit(s_text, (sx + 10, sy - 6))
        # Pickaxe + worker count
        sx2 = sx + 42
        pygame.draw.line(self._screen, (88, 158, 68), (sx2, sy + 3), (sx2 + 5, sy - 3), 2)
        w_text = self._tiny.render(f"{territory.workers.count}/{cfg.MAX_WORKERS_PER_TERRITORY}", True, (248, 238, 218))
        self._screen.blit(w_text, (sx2 + 9, sy - 6))
        # Coin + food
        sx3 = sx + 98
        pygame.draw.circle(self._screen, (228, 188, 48), (sx3 + 3, sy - 1), 3)
        f_text = self._tiny.render(f"{int(territory.food)}", True, (248, 238, 218))
        self._screen.blit(f_text, (sx3 + 9, sy - 6))

        # Spawn queue indicator
        if territory.spawn_queue_size > 0:
            q_text = self._tiny.render(f"+{territory.spawn_queue_size}", True, cfg.ACCENT_2)
            self._screen.blit(q_text, (strip.right + 4, strip.centery - 6))

        # Queen HP bar
        if territory.queen.is_alive:
            q_hp = territory.queen.front_hp
            q_max = territory.queen.max_hp
            if q_hp < q_max:
                bar_w = 72
                bar_h = 7
                bar_rect = pygame.Rect(cx - bar_w // 2, strip.bottom + 6, bar_w, bar_h)
                pygame.draw.rect(self._screen, (32, 14, 14), bar_rect, border_radius=3)
                fill_w = max(1, int(bar_w * q_hp / q_max))
                hp_ratio = q_hp / q_max
                bar_color = (68, 198, 82) if hp_ratio > 0.5 else (228, 178, 48) if hp_ratio > 0.25 else (218, 52, 42)
                pygame.draw.rect(self._screen, bar_color, (bar_rect.x, bar_rect.y, fill_w, bar_h), border_radius=3)
                pygame.draw.rect(self._screen, (228, 218, 188), bar_rect, 1, border_radius=3)
                hp_label = self._tiny.render(f"♛{int(q_hp)}", True, (255, 228, 108))
                self._screen.blit(hp_label, hp_label.get_rect(center=(cx, bar_rect.bottom + 8)))

    def _draw_territory_decor(self, territory: Territory, elapsed: float) -> None:
        # Draw lake first so it's under everything
        if territory.id % 3 == 0:  # 1/3 of territories get a lake
            x, y = _decor_point(territory, 99, 0.6)
            _draw_lake(self._screen, (x, y), territory.id, elapsed)

        # Draw grass patches
        for i in range(25):
            x, y = _decor_point(territory, 150 + i, 0.9)
            _draw_grass(self._screen, (x, y), elapsed + i)

        # Draw rocks
        for i in range(4):
            x, y = _decor_point(territory, 80 + i, 0.75)
            _draw_rock(self._screen, (x, y), 0.5 + i * 0.1)

        # Draw bushes
        for i in range(6):
            x, y = _decor_point(territory, 60 + i, 0.8)
            _draw_bush(self._screen, (x, y), 0.6 + i * 0.1)

        # Draw 3D Trees (draw last to sort on top)
        for i in range(8):
            x, y = _decor_point(territory, 40 + i, 0.85)
            _draw_tree(self._screen, (x, y), 0.8 + (i % 4) * 0.15)
            
        # Draw flowers
        for i in range(5):
            x, y = _decor_point(territory, 100 + i, 0.82)
            _draw_flower(self._screen, (x, y), territory.owner.color, elapsed + i * 1.3)

    def _draw_base_building(self, territory: Territory, elapsed: float) -> None:
        x, y = _decor_point(territory, 7, 0.28)
        color = territory.owner.color
        alive = getattr(territory.owner, "is_alive", False)

        # Ground shadow
        pygame.draw.ellipse(self._screen, (12, 22, 10), (x - 48, y + 22, 100, 28))

        if not alive:
            # Ruined building
            pygame.draw.rect(self._screen, (88, 78, 62), (x - 28, y, 60, 24), border_radius=4)
            pygame.draw.line(self._screen, (68, 58, 42), (x - 20, y + 12), (x + 20, y + 12), 1)
            return

        # Castle base
        base_front = [(x - 32, y + 20), (x + 38, y + 20), (x + 38, y - 4), (x - 32, y - 4)]
        base_side = [(x + 38, y + 20), (x + 50, y + 12), (x + 50, y - 10), (x + 38, y - 4)]
        base_top = [(x - 32, y - 4), (x + 38, y - 4), (x + 50, y - 10), (x - 20, y - 10)]
        pygame.draw.polygon(self._screen, (178, 142, 72), base_front)
        pygame.draw.polygon(self._screen, (138, 102, 52), base_side)
        pygame.draw.polygon(self._screen, (198, 162, 88), base_top)

        # Stone lines
        for row in range(4):
            ry = y + 16 - row * 6
            pygame.draw.line(self._screen, (158, 118, 62), (x - 30, ry), (x + 36, ry), 1)

        # Door with warm light
        door = pygame.Rect(x - 5, y + 4, 16, 16)
        pygame.draw.rect(self._screen, (62, 42, 26), door, border_radius=3)
        
        # Open door if spawning!
        is_spawning = bool(territory.visual_spawns or territory.spawn_queue_size > 0)
        door_glow_c = (255, 128, 48) if is_spawning else (248, 198, 88)
        glow_alpha = int(180 + math.sin(elapsed * 8) * 60) if is_spawning else int(100 + math.sin(elapsed * 2.5 + territory.id) * 40)
        
        door_glow = pygame.Surface((20, 20), pygame.SRCALPHA)
        pygame.draw.rect(door_glow, (*door_glow_c, glow_alpha), door_glow.get_rect(), border_radius=4)
        self._screen.blit(door_glow, (x - 7, y + 2))

        # Colored roof
        roof_pts = [(x - 36, y - 4), (x + 42, y - 4), (x + 3, y - 26)]
        roof_side = [(x + 42, y - 4), (x + 52, y - 12), (x + 3, y - 26)]
        pygame.draw.polygon(self._screen, _darken(color, 8), roof_pts)
        pygame.draw.polygon(self._screen, _darken(color, 28), roof_side)
        # Roof shine
        pygame.draw.polygon(self._screen, _brighten(color, 32), [(x - 36, y - 4), (x + 3, y - 26), (x - 12, y - 14)])
        pygame.draw.polygon(self._screen, (62, 48, 28), roof_pts, 2)

        # Turrets
        for tx_off in [-30, 34]:
            pygame.draw.rect(self._screen, (168, 132, 68), (x + tx_off - 4, y - 12, 10, 16), border_radius=2)
            for j in range(3):
                pygame.draw.rect(self._screen, (138, 102, 48), (x + tx_off - 3 + j * 4, y - 14, 3, 5))

        # Animated flag
        pygame.draw.line(self._screen, (62, 48, 28), (x + 3, y - 26), (x + 3, y - 48), 2)
        wave = int(math.sin(elapsed * 3.0 + territory.id) * 4)
        flag = [(x + 3, y - 48), (x + 28, y - 40 + wave), (x + 3, y - 32)]
        pygame.draw.polygon(self._screen, _brighten(color, 38), flag)
        pygame.draw.polygon(self._screen, _darken(color, 14), flag, 2)
        # Emblem
        pygame.draw.circle(self._screen, (255, 238, 178), (x + 14, y - 40 + wave // 2), 3)

    def _draw_spawn_effects(self, territory: Territory) -> None:
        """Draw birth animation when units spawn from queen."""
        cx, cy = territory.centroid
        for t in territory.spawn_effects:
            progress = 1.0 - t
            alpha = int(180 * t)
            scale = 0.3 + progress * 0.7
            r = int(14 * scale)
            spawn_surf = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
            center = spawn_surf.get_rect().center
            # Glowing ring expanding outward
            ring_r = int(r + progress * 20)
            pygame.draw.circle(spawn_surf, (*territory.owner.color, max(0, alpha // 2)), center, ring_r, 2)
            # Core glow
            pygame.draw.circle(spawn_surf, (255, 248, 198, max(0, alpha)), center, r)
            pygame.draw.circle(spawn_surf, (*_brighten(territory.owner.color, 48), max(0, alpha // 2)), center, max(2, r - 3))
            # Sparkles
            for i in range(6):
                angle = i * math.tau / 6 + progress * 3
                sx = center[0] + int(math.cos(angle) * ring_r)
                sy = center[1] + int(math.sin(angle) * ring_r)
                pygame.draw.circle(spawn_surf, (248, 228, 128, max(0, alpha)), (sx, sy), max(1, int(3 * t)))
            self._screen.blit(spawn_surf, spawn_surf.get_rect(center=(int(cx), int(cy) - 8)))

    def _draw_wandering_units(self, match: object, territory: Territory, elapsed: float) -> None:
        color = territory.owner.color
        alive = getattr(territory.owner, "is_alive", False)
        if not alive:
            return
            
        vs_soldiers = [vs for vs in territory.visual_spawns if vs["role"] == "soldier"]
        vs_workers = [vs for vs in territory.visual_spawns if vs["role"] == "worker"]
        
        sprites: list[tuple[str, int]] = []
        if territory.queen.is_alive:
            sprites.append(("queen", 0))
            
        w_drawn = min(territory.workers.count - len(vs_workers), 6 - len(vs_workers))
        for i in range(w_drawn):
            sprites.append(("worker", i))
            
        s_drawn = min(territory.soldiers.count - len(vs_soldiers), 18 - len(vs_soldiers))
        for i in range(s_drawn):
            sprites.append(("soldier", i))

        for role, index in sprites:
            key = f"{territory.id}:{role}:{index}"
            
            # If under attack, defenders converge on attackers!
            active_zone = next((z for z in getattr(match, "combat_zones", []) if z.territory is territory), None)
            
            if active_zone and role in ("soldier", "queen"):
                atk_idx = index % max(1, active_zone.attacking_soldiers.count)
                angle = atk_idx * 1.5 + elapsed * 0.5
                target_pos = (active_zone.position[0] + math.cos(angle) * 35, active_zone.position[1] + math.sin(angle) * 35)
                scale = 0.8
                
                # Add attack lunge animation for defenders
                lunge = math.sin(elapsed * 10 + index * 1.3) * 6
                target_pos = (target_pos[0] + math.cos(angle + math.pi) * max(0, lunge), target_pos[1] + math.sin(angle + math.pi) * max(0, lunge))
            else:
                target_pos, scale = _wandering_position(territory, role, index, elapsed)
                
            # Smooth interpolation to target
            current = self._unit_positions.get(key, target_pos)
            lerp_speed = 2.5
            dt_approx = 1.0 / max(30, cfg.FPS)
            nx = current[0] + (target_pos[0] - current[0]) * min(1.0, lerp_speed * dt_approx)
            ny = current[1] + (target_pos[1] - current[1]) * min(1.0, lerp_speed * dt_approx)
            self._unit_positions[key] = (nx, ny)
            # Facing direction for animation
            facing = 1 if target_pos[0] > current[0] else -1
            self._draw_unit_sprite((int(nx), int(ny)), color, scale, role, elapsed + index * 0.7, facing)

        # Draw spawning units emerging from base building
        base_pos = _decor_point(territory, 7, 0.28)
        base_pos = (base_pos[0] + 3, base_pos[1] + 12) # Door position
        
        for vs in territory.visual_spawns:
            role = vs["role"]
            index = vs["index"]
            progress = vs["progress"] # 0.0 to 1.0
            
            target_pos, scale = _wandering_position(territory, role, index, elapsed)
            nx = base_pos[0] + (target_pos[0] - base_pos[0]) * progress
            ny = base_pos[1] + (target_pos[1] - base_pos[1]) * progress
            facing = 1 if target_pos[0] > base_pos[0] else -1
            
            self._draw_unit_sprite((int(nx), int(ny)), color, scale, role, elapsed * 2.0, facing)

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
        color = army.attacker.color

        # Glowing trail
        trail_surf = pygame.Surface((cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT), pygame.SRCALPHA)
        trail_color = (*_brighten(color, 52), 60)
        pygame.draw.line(trail_surf, trail_color, start, end, 6)
        self._screen.blit(trail_surf, (0, 0))
        pygame.draw.line(self._screen, _brighten(color, 28), start, end, 2)

        # March dust particles
        for i in range(8):
            t = (army.progress - i * 0.03) % 1.0
            if t < 0:
                continue
            dot = (int(start[0] + dx * t), int(start[1] + dy * t))
            dot_r = 2 + int(math.sin(army.elapsed * 6 + i) * 1)
            dust_alpha = int(80 * (1.0 - abs(t - army.progress) * 8))
            if dust_alpha > 0:
                dust = pygame.Surface((dot_r * 2 + 4, dot_r * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(dust, (*_brighten(color, 48), max(0, min(255, dust_alpha))), (dot_r + 2, dot_r + 2), dot_r)
                self._screen.blit(dust, (dot[0] - dot_r - 2, dot[1] - dot_r - 2))

        # Marching soldiers with formation
        facing = 1 if dx >= 0 else -1
        visible = max(3, min(9, army.soldiers // 3 + 3))
        for i in range(visible):
            row = i - (visible - 1) / 2
            wave = math.sin(army.elapsed * 7 + i * 1.1) * 3
            back = (i % 3) * 12
            sprite_pos = (
                int(current[0] + nx * row * 12 - dx / length * back),
                int(current[1] + ny * row * 12 - dy / length * back + wave),
            )
            scale = 1.0 if i == 0 else 0.85
            self._draw_unit_sprite(sprite_pos, color, scale, "soldier", army.elapsed + i, facing)

        # Count badge
        badge_surf = self._tiny.render(str(army.soldiers), True, (255, 255, 255))
        badge_rect = badge_surf.get_rect(center=(current[0], current[1] - 20))
        bg = badge_rect.inflate(10, 4)
        pill_surf = pygame.Surface((bg.width, bg.height), pygame.SRCALPHA)
        pygame.draw.rect(pill_surf, (*color, 200), pill_surf.get_rect(), border_radius=8)
        self._screen.blit(pill_surf, bg)
        pygame.draw.rect(self._screen, (248, 238, 218), bg, 1, border_radius=8)
        self._screen.blit(badge_surf, badge_rect)

    def _draw_combat_zone(self, zone: object, elapsed: float) -> None:
        pos = zone.position
        cx, cy = int(pos[0]), int(pos[1])
        t = zone.elapsed

        # Pulsing danger area
        ring_r = int(48 + math.sin(t * 4.5) * 10)
        ring_surf = pygame.Surface((ring_r * 2 + 30, ring_r * 2 + 30), pygame.SRCALPHA)
        rc = ring_surf.get_rect().center
        alpha_base = int(128 + math.sin(t * 6) * 50)
        pygame.draw.circle(ring_surf, (228, 48, 38, max(0, min(255, alpha_base // 3))), rc, ring_r, 4)
        pygame.draw.circle(ring_surf, (255, 148, 38, max(0, min(255, alpha_base // 4))), rc, ring_r + 8, 2)
        self._screen.blit(ring_surf, ring_surf.get_rect(center=(cx, cy)))

        # Individual attackers spreading out to fight
        atk_count = zone.attacking_soldiers.count

        for i in range(atk_count):
            key = f"atk_{zone.territory.id}_{id(zone)}_{i}"
            angle = i * 1.5 + t * 0.5
            dist = 30 + math.sin(i * 45) * 10
            target_x = cx + int(math.cos(angle) * dist)
            target_y = cy + int(math.sin(angle) * dist)
            
            # Start them slightly off-center when they arrive
            current = self._unit_positions.get(key, (cx + math.cos(angle)*100, cy + math.sin(angle)*100))
            
            lerp_speed = 3.5
            dt_approx = 1.0 / max(30, cfg.FPS)
            nx = current[0] + (target_x - current[0]) * min(1.0, lerp_speed * dt_approx)
            ny = current[1] + (target_y - current[1]) * min(1.0, lerp_speed * dt_approx)
            self._unit_positions[key] = (nx, ny)

            # Attack animation: lunge forward
            lunge = math.sin(t * 12 + i * 2.3) * 6
            ax = nx + int(math.cos(angle + math.pi) * max(0, lunge))
            ay = ny + int(math.sin(angle + math.pi) * max(0, lunge))
            
            facing = 1 if math.cos(angle + math.pi) > 0 else -1
            self._draw_unit_sprite((int(ax), int(ay)), zone.attacker_color, 0.8, "soldier", t + i, facing)
            
            # Weapon swing arc
            if lunge > 3:
                swing_angle = angle + math.pi + math.sin(t * 15 + i) * 0.5
                sw_x = ax + int(math.cos(swing_angle) * 14)
                sw_y = ay + int(math.sin(swing_angle) * 14)
                pygame.draw.line(self._screen, (248, 228, 168), (ax, ay - 4), (sw_x, sw_y - 4), 2)
                # Impact spark
                spark = pygame.Surface((12, 12), pygame.SRCALPHA)
                pygame.draw.circle(spark, (255, 228, 88, 180), (6, 6), 4)
                self._screen.blit(spark, (sw_x - 6, sw_y - 10))

        # Damage flash: shockwave + particles
        if zone.damage_flash > 0:
            flash_r = int(18 + zone.damage_flash * 28)
            flash_surf = pygame.Surface((flash_r * 2 + 8, flash_r * 2 + 8), pygame.SRCALPHA)
            flash_center = flash_surf.get_rect().center
            flash_alpha = int(zone.damage_flash * 180)
            pygame.draw.circle(flash_surf, (255, 228, 88, max(0, min(255, flash_alpha))), flash_center, flash_r, 3)
            self._screen.blit(flash_surf, flash_surf.get_rect(center=(cx, cy)))
            # Flying particles
            for j in range(8):
                pa = j * math.tau / 8 + t * 2.5
                pd = 18 + zone.damage_flash * 28
                px = cx + int(math.cos(pa) * pd)
                py = cy + int(math.sin(pa) * pd)
                pc = zone.attacker_color if j % 2 == 0 else (255, 198, 48)
                r = max(1, int(2 + zone.damage_flash * 3))
                psf = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(psf, (*pc, max(0, min(255, int(zone.damage_flash * 220)))), (r + 1, r + 1), r)
                self._screen.blit(psf, (px - r - 1, py - r - 1))

        # Battle info badge
        atk_total = zone.attacking_soldiers.count
        def_total = zone.territory.soldiers.count + zone.territory.workers.count + (1 if zone.territory.queen.is_alive else 0)
        battle_text = f"{atk_total} ⚔ {def_total}"
        battle_surf = self._bold_small.render(battle_text, True, (255, 248, 218))
        battle_rect = battle_surf.get_rect(center=(cx, cy - 42))
        bg = battle_rect.inflate(14, 6)
        bg_surf = pygame.Surface((bg.width, bg.height), pygame.SRCALPHA)
        pygame.draw.rect(bg_surf, (32, 14, 8, 200), bg_surf.get_rect(), border_radius=8)
        self._screen.blit(bg_surf, bg)
        self._screen.blit(battle_surf, battle_rect)

    def _get_cached_sprite(self, role: str, color: tuple[int, int, int], scale: float) -> pygame.Surface:
        key = f"humanoid_{role}_{color[0]}_{color[1]}_{color[2]}_{scale:.2f}"
        if key in self._sprite_cache:
            return self._sprite_cache[key]
        
        base_r = max(6, int((12 if role == "queen" else 8) * scale))
        surf = pygame.Surface((base_r * 6, base_r * 6), pygame.SRCALPHA)
        cx, cy = base_r * 3, base_r * 3
        
        skin_color = (255, 218, 185)
        skin_dark = _darken(skin_color, 40)
        body_color = _darken(color, 10)
        armor_color = (110, 120, 130)
        
        # Shadow
        pygame.draw.ellipse(surf, (0, 0, 0, 80), (cx - base_r, cy + base_r * 1.5, base_r * 2, base_r))

        if role == "worker":
            # Legs
            pygame.draw.rect(surf, _darken(body_color, 30), (cx - base_r//2, cy + base_r, base_r//2, base_r))
            pygame.draw.rect(surf, _darken(body_color, 30), (cx + 1, cy + base_r, base_r//2, base_r))
            # Torso
            pygame.draw.rect(surf, body_color, (cx - base_r//1.2, cy, base_r*1.6, base_r))
            # Left Arm (holding tool)
            pygame.draw.rect(surf, skin_dark, (cx - base_r*1.2, cy + 1, base_r//2, base_r))
            # Pickaxe
            px, py = cx - base_r*1.2, cy + base_r
            pygame.draw.line(surf, (139, 69, 19), (px - base_r, py + base_r), (px + base_r, py - base_r), max(2, int(scale*2)))
            pygame.draw.polygon(surf, (150, 150, 150), [(px + base_r, py - base_r), (px + base_r + 4, py - base_r + 2), (px + base_r - 2, py - base_r + 6)])
            pygame.draw.polygon(surf, (150, 150, 150), [(px - base_r, py + base_r), (px - base_r - 4, py + base_r - 2), (px - base_r + 2, py + base_r - 6)])
            # Right arm
            pygame.draw.rect(surf, skin_dark, (cx + base_r//1.2, cy + 1, base_r//2, base_r))
            # Head
            pygame.draw.circle(surf, skin_color, (cx, cy - base_r//1.5), int(base_r * 0.8))
            # Hardhat
            pygame.draw.ellipse(surf, (255, 215, 0), (cx - base_r, cy - base_r*1.8, base_r*2, base_r*1.2))
            pygame.draw.ellipse(surf, (255, 235, 100), (cx - base_r//2, cy - base_r*1.6, base_r, base_r//2))

        elif role == "soldier":
            # Legs (Armor)
            pygame.draw.rect(surf, _darken(armor_color, 20), (cx - base_r//2, cy + base_r, base_r//2, base_r))
            pygame.draw.rect(surf, _darken(armor_color, 20), (cx + 1, cy + base_r, base_r//2, base_r))
            # Torso (Armor over color)
            pygame.draw.rect(surf, body_color, (cx - base_r, cy, base_r*2, base_r*1.2))
            pygame.draw.rect(surf, armor_color, (cx - base_r//1.2, cy, base_r*1.6, base_r))
            # Right Arm (Sword)
            pygame.draw.rect(surf, armor_color, (cx + base_r, cy + 1, base_r//2, base_r))
            sw_x, sw_y = cx + base_r + base_r//4, cy + base_r
            pygame.draw.line(surf, (192, 192, 192), (sw_x, sw_y), (sw_x, sw_y - base_r * 2), max(2, int(scale*3)))
            pygame.draw.line(surf, (255, 255, 255), (sw_x - 1, sw_y), (sw_x - 1, sw_y - base_r * 2 + 2), 1)
            pygame.draw.line(surf, (100, 50, 20), (sw_x - 4, sw_y - 2), (sw_x + 4, sw_y - 2), max(2, int(scale*2))) # Hilt
            # Left Arm (Shield)
            pygame.draw.rect(surf, armor_color, (cx - base_r*1.5, cy + 1, base_r//2, base_r))
            sh_rect = pygame.Rect(cx - base_r*2.2, cy, base_r*1.5, base_r*1.8)
            pygame.draw.ellipse(surf, _darken(color, 20), sh_rect)
            pygame.draw.ellipse(surf, (200, 200, 200), sh_rect, max(1, int(scale*2)))
            # Head
            pygame.draw.circle(surf, skin_color, (cx, cy - base_r//1.5), int(base_r * 0.8))
            # Helmet
            pygame.draw.arc(surf, armor_color, (cx - base_r, cy - base_r*1.8, base_r*2, base_r*1.8), 0, math.pi, max(4, int(scale*4)))
            pygame.draw.line(surf, armor_color, (cx, cy - base_r*1.8), (cx, cy - base_r), max(2, int(scale*3)))

        elif role == "queen":
            # Robe/Dress
            pygame.draw.polygon(surf, body_color, [(cx, cy - base_r), (cx - base_r*1.5, cy + base_r*2), (cx + base_r*1.5, cy + base_r*2)])
            pygame.draw.polygon(surf, _brighten(body_color, 20), [(cx, cy - base_r), (cx - base_r*1.5, cy + base_r*2), (cx + base_r*1.5, cy + base_r*2)], 2)
            # Cape
            pygame.draw.polygon(surf, (200, 20, 40), [(cx - base_r//2, cy - base_r//2), (cx - base_r*2, cy + base_r*1.5), (cx + base_r*2, cy + base_r*1.5)])
            # Head
            pygame.draw.circle(surf, skin_color, (cx, cy - base_r*1.2), int(base_r * 0.9))
            # Crown
            cr = int(base_r * 0.9)
            pygame.draw.polygon(surf, (255, 215, 0), [(cx - cr, cy - base_r*1.5), (cx - cr//2, cy - base_r*2.5), (cx, cy - base_r*1.5 - cr//2), (cx + cr//2, cy - base_r*2.5), (cx + cr, cy - base_r*1.5)])
            pygame.draw.circle(surf, (255, 50, 50), (cx, cy - base_r*1.5 - cr//2), max(2, int(scale*2)))
            # Staff
            pygame.draw.line(surf, (200, 150, 50), (cx + base_r, cy), (cx + base_r, cy + base_r*2), max(2, int(scale*2)))
            pygame.draw.circle(surf, (50, 200, 255), (cx + base_r, cy), max(3, int(scale*3)))
            
        self._sprite_cache[key] = surf
        return surf

    def _draw_supply_drop(self, drop: SupplyDrop, elapsed: float) -> None:
        cx, cy = drop.centroid
        
        # Draw shadow
        shadow = pygame.Surface((60, 40), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 100), shadow.get_rect())
        self._screen.blit(shadow, (cx - 30, cy + 10))
        
        # Parachute if still falling (elapsed < delay)
        falling = drop.elapsed < cfg.SUPPLY_DROP_DELAY
        z_off = 0
        if falling:
            progress = drop.elapsed / cfg.SUPPLY_DROP_DELAY
            z_off = int((1.0 - progress) * 300)
            # Draw parachute
            para_y = cy - z_off - 60
            pygame.draw.ellipse(self._screen, (220, 220, 230), (cx - 40, para_y, 80, 40))
            pygame.draw.line(self._screen, (200, 200, 200), (cx - 40, para_y + 20), (cx - 15, cy - z_off - 10), 1)
            pygame.draw.line(self._screen, (200, 200, 200), (cx + 40, para_y + 20), (cx + 15, cy - z_off - 10), 1)
        
        # Draw Box (Pseudo-3D cube)
        bx, by = int(cx), int(cy - z_off)
        size = 30
        c_top = (100, 160, 220)
        c_left = (60, 110, 160)
        c_right = (40, 80, 120)
        
        # Right face
        pygame.draw.polygon(self._screen, c_right, [(bx, by), (bx + size, by - size//2), (bx + size, by + size//2), (bx, by + size)])
        # Left face
        pygame.draw.polygon(self._screen, c_left, [(bx, by), (bx - size, by - size//2), (bx - size, by + size//2), (bx, by + size)])
        # Top face
        pygame.draw.polygon(self._screen, c_top, [(bx, by), (bx + size, by - size//2), (bx, by - size), (bx - size, by - size//2)])
        
        # Medical cross
        pygame.draw.rect(self._screen, (255, 50, 50), (bx - 12, by + 2, 8, 16))
        pygame.draw.rect(self._screen, (255, 50, 50), (bx - 16, by + 6, 16, 8))

        if not falling:
            # Glow when active
            glow = pygame.Surface((80, 80), pygame.SRCALPHA)
            pulse = int(128 + math.sin(elapsed * 5) * 60)
            pygame.draw.circle(glow, (100, 200, 255, pulse // 3), (40, 40), 30)
            pygame.draw.circle(glow, (100, 200, 255, pulse // 2), (40, 40), 20)
            self._screen.blit(glow, (bx - 40, by - 40))

    def _draw_unit_sprite(
        self,
        center: tuple[int, int],
        color: tuple[int, int, int],
        scale: float,
        role: str,
        phase: float,
        facing: int = 1,
    ) -> None:
        surf = self._get_cached_sprite(role, color, scale)
        # width = base_r * 6
        w = surf.get_width()
        x, y = center
        bob = int(math.sin(phase * 6.0) * 3) if role != "queen" else int(math.sin(phase * 3.0) * 2)
        
        # Directional flip (if facing right, we mirror it)
        if facing > 0:
            surf = pygame.transform.flip(surf, True, False)
            
        self._screen.blit(surf, (x - w // 2, y - w // 2 + bob))
        
        # Health bar (optional, drawn on top)
        if role == "queen":
            hp_w = 20
            pygame.draw.rect(self._screen, (40, 0, 0), (x - hp_w//2, y - w // 2 - 4, hp_w, 4))
            pygame.draw.rect(self._screen, (0, 200, 50), (x - hp_w//2, y - w // 2 - 4, hp_w, 4))

    def _draw_combat_effect(self, effect: object) -> None:
        p = effect.progress
        alpha = int(200 * (1.0 - p))
        center = (int(effect.position[0]), int(effect.position[1]))
        radius = int(24 + p * 68)
        burst = pygame.Surface((radius * 2 + 40, radius * 2 + 40), pygame.SRCALPHA)
        local = burst.get_rect().center

        # Expanding shockwave rings
        pygame.draw.circle(burst, (*effect.attacker_color, max(0, min(255, alpha // 3))), local, radius, 4)
        pygame.draw.circle(burst, (*effect.defender_color, max(0, min(255, alpha // 4))), local, max(6, radius - 14), 3)

        # Radiating energy lines
        for i in range(10):
            angle = i * math.tau / 10 + p * 2.0
            inner = 14 + p * 16
            outer = 28 + p * 52
            s = (int(local[0] + math.cos(angle) * inner), int(local[1] + math.sin(angle) * inner))
            e = (int(local[0] + math.cos(angle) * outer), int(local[1] + math.sin(angle) * outer))
            lc = effect.attacker_color if i % 2 == 0 else effect.defender_color
            pygame.draw.line(burst, (*_brighten(lc, 24), max(0, min(255, alpha))), s, e, 2)

        # Center flash
        pygame.draw.circle(burst, (255, 228, 88, max(0, min(255, alpha))), local, 8 + int(p * 5))

        # Result text
        if p > 0.25:
            text = "VICTORY!" if effect.attacker_won else "DEFENDED"
            tc = (255, 218, 68) if effect.attacker_won else (108, 218, 148)
            text_surf = self._bold_small.render(text, True, tc)
            text_rect = text_surf.get_rect(center=(local[0], local[1] - int(p * 24)))
            burst.blit(text_surf, text_rect)

        self._screen.blit(burst, burst.get_rect(center=center))

    def _draw_player_popup(self, match: Match, player_idx: int, state_info: dict) -> None:
        player = match.players[player_idx]
        home = match.home_territory(player)
        if home is None:
            return

        cx, cy = home.centroid
        cx, cy = int(cx), int(cy)
        keys = KEY_LABELS[player_idx]
        state = state_info["state"]
        color = player.color

        # Popup background
        popup_w, popup_h = 180, 82
        popup_rect = pygame.Rect(cx - popup_w // 2, cy - 50 - popup_h, popup_w, popup_h)
        # Clamp to screen
        popup_rect.clamp_ip(pygame.Rect(5, 5, cfg.WINDOW_WIDTH - 10, cfg.WINDOW_HEIGHT - 10))

        _draw_popup_bg(self._screen, popup_rect, color)

        # Arrow
        arrow = [(cx - 7, popup_rect.bottom), (cx + 7, popup_rect.bottom), (cx, popup_rect.bottom + 8)]
        pygame.draw.polygon(self._screen, (22, 26, 32), arrow)

        x0 = popup_rect.x + 10
        y0 = popup_rect.y + 8

        if state == "summon":
            header = self._tiny.render("SUMMON UNIT", True, cfg.ACCENT_2)
            self._screen.blit(header, (x0, y0))
            cost_s = f"({cfg.SOLDIER_COST}g)"
            cost_w = f"({home.worker_cost()}g)"
            self._draw_key_option(x0, y0 + 16, keys[0], f"Soldier {cost_s}", (218, 128, 68))
            self._draw_key_option(x0, y0 + 34, keys[1], f"Worker {cost_w}", (88, 168, 98))
            self._draw_key_option(x0, y0 + 52, keys[2], "Cancel", cfg.MUTED_TEXT)

        elif state == "attack_target":
            header = self._tiny.render("SELECT TARGET", True, (218, 68, 58))
            self._screen.blit(header, (x0, y0))
            targets = state_info.get("target_territories", [])
            for i, target_id in enumerate(targets[:3]):
                if i < len(keys):
                    target_t = match.territories[target_id]
                    target_p = target_t.owner
                    
                    is_ours = target_p is player
                    action = "Reinforce" if is_ours else "Attack"
                    
                    target_alive = target_p.is_alive and target_t.queen.is_alive
                    label = _fit_text(self._tiny, f"{action} T{target_id+1} ({target_p.name})", 120)
                    label_color = target_p.color if target_alive else (88, 88, 84)
                    status = "" if target_alive else " ✗"
                    self._draw_key_option(x0, y0 + 16 + i * 18, keys[i], label + status, label_color)

        elif state == "attack_amount":
            header = self._tiny.render("HOW MANY?", True, (218, 68, 58))
            self._screen.blit(header, (x0, y0))
            self._draw_key_option(x0, y0 + 16, keys[0], "33%", (108, 198, 138))
            self._draw_key_option(x0 + 60, y0 + 16, keys[1], "66%", (218, 188, 58))
            self._draw_key_option(x0 + 120, y0 + 16, keys[2], "ALL", (218, 68, 48))
            target = state_info.get("target")
            if target:
                action = "Reinforce" if getattr(target, "owner", None) is player else "Attack"
                target_name = f"T{target.id+1} ({getattr(target.owner, 'name', 'Unknown')})"
                tgt_name = _fit_text(self._tiny, target_name, 110)
                tgt_text = self._tiny.render(f"{action} → {tgt_name}", True, cfg.TEXT)
                self._screen.blit(tgt_text, (x0, y0 + 40))
                # Show source soldiers count
                total_soldiers = sum(t.soldiers.count for t in match.territories_of(player) if t is not target)
                src_text = self._tiny.render(f"Available: {total_soldiers} soldiers", True, cfg.MUTED_TEXT)
                self._screen.blit(src_text, (x0, y0 + 56))

    def _draw_key_option(self, x: int, y: int, key: str, label: str, color: tuple) -> None:
        pygame.draw.rect(self._screen, (42, 46, 56), (x, y, 16, 14), border_radius=3)
        pygame.draw.rect(self._screen, (82, 86, 98), (x, y, 16, 14), 1, border_radius=3)
        key_surf = self._tiny.render(key, True, (248, 238, 218))
        self._screen.blit(key_surf, key_surf.get_rect(center=(x + 8, y + 7)))
        label_surf = self._tiny.render(label, True, color)
        self._screen.blit(label_surf, (x + 20, y + 1))

    def _draw_top_bar(self, match: Match) -> None:
        """Minimal top-bar: time + player indicators."""
        bar = pygame.Surface((cfg.WINDOW_WIDTH, 32), pygame.SRCALPHA)
        pygame.draw.rect(bar, (12, 16, 22, 160), bar.get_rect())
        self._screen.blit(bar, (0, 0))

        # Time
        time_text = self._small.render(f"⏱ {_format_time(match.elapsed)}", True, cfg.ACCENT)
        self._screen.blit(time_text, (16, 8))

        # Player dots
        px = 120
        for player in match.players:
            alive = player.is_alive and any(t.owner is player and t.queen.is_alive for t in match.territories)
            c = player.color if alive else (72, 72, 68)
            pygame.draw.circle(self._screen, c, (px, 16), 7)
            if alive:
                pygame.draw.circle(self._screen, (248, 238, 218), (px, 16), 7, 1)
            else:
                # X mark for eliminated
                pygame.draw.line(self._screen, (188, 48, 38), (px - 3, 13), (px + 3, 19), 2)
                pygame.draw.line(self._screen, (188, 48, 38), (px + 3, 13), (px - 3, 19), 2)
            name = _fit_text(self._tiny, player.name, 68)
            name_surf = self._tiny.render(name, True, c)
            self._screen.blit(name_surf, (px + 12, 9))
            # Territory count
            owned = sum(1 for t in match.territories if t.owner is player and t.queen.is_alive)
            if owned > 1:
                count_surf = self._tiny.render(f"×{owned}", True, cfg.ACCENT_2)
                self._screen.blit(count_surf, (px + 12 + name_surf.get_width() + 4, 9))
            px += 140 + name_surf.get_width()


# ─────────────────── Helpers ───────────────────

def _wandering_position(territory: Territory, role: str, index: int, elapsed: float) -> tuple[tuple[int, int], float]:
    polygon = territory.polygon
    cx, cy = territory.centroid
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    # Increase spread significantly so they patrol the whole territory
    spread = max(60.0, min(max(xs) - min(xs), max(ys) - min(ys)) * 0.85)
    role_bias = {"queen": 0.1, "worker": 0.6, "soldier": 0.9}[role]
    seed = (territory.id + 1) * 31 + index * 17 + len(role) * 13
    base_angle = (seed * 2.399963) % math.tau
    speed = {"queen": 0.1, "worker": 0.2, "soldier": 0.22}[role]  # Slower walking
    
    orbit = base_angle + math.sin(elapsed * speed + seed) * 1.5 + elapsed * speed * 0.2
    radius = spread * (role_bias * 0.5 + 0.5 * math.sin(elapsed * speed * 0.3 + seed * 0.7))
    
    # Large wandering paths (Lissajous curves)
    wobble_x = math.cos(elapsed * speed * 0.7 + seed) * spread * 0.4
    wobble_y = math.sin(elapsed * speed * 0.5 + seed * 1.3) * spread * 0.4
    
    x = cx + math.cos(orbit) * radius + wobble_x
    y = cy + math.sin(orbit) * radius + wobble_y

    # Ensure it's inside the polygon
    for factor in (1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.3, 0.1):
        px = cx + (x - cx) * factor
        py = cy + (y - cy) * factor
        if _point_in_polygon((px, py), polygon):
            return (int(px), int(py)), 1.0 if role == "queen" else 0.88 if role == "worker" else 0.82
    return (int(cx), int(cy)), 1.0


def _decor_point(territory: Territory, seed: int, spread_ratio: float) -> tuple[int, int]:
    polygon = territory.polygon
    cx, cy = territory.centroid
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    spread = max(30.0, min(max(xs) - min(xs), max(ys) - min(ys)) * spread_ratio * 0.44)
    angle = ((territory.id + 1) * 59 + seed * 37) * 2.399963
    radius = spread * (0.24 + ((seed * 73) % 100) / 140)
    x = cx + math.cos(angle) * radius + math.sin(seed * 1.7) * 26
    y = cy + math.sin(angle) * radius + math.cos(seed * 1.3) * 22
    for factor in (1.0, 0.82, 0.64, 0.46, 0.28, 0.1):
        px = cx + (x - cx) * factor
        py = cy + (y - cy) * factor
        if _point_in_polygon((px, py), polygon):
            return int(px), int(py)
    return int(cx), int(cy)


def _draw_popup_bg(screen: pygame.Surface, rect: pygame.Rect, color: tuple[int, int, int]) -> None:
    shadow = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, 130), shadow.get_rect(), border_radius=10)
    screen.blit(shadow, rect.move(0, 4))
    panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(panel, (22, 26, 34, 230), panel.get_rect(), border_radius=10)
    screen.blit(panel, rect)
    pygame.draw.rect(screen, _brighten(color, 18), rect, 2, border_radius=10)


def _draw_pill(screen: pygame.Surface, rect: pygame.Rect, fill: tuple, border: tuple) -> None:
    pill = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(pill, fill, pill.get_rect(), border_radius=rect.height // 2)
    screen.blit(pill, rect)
    pygame.draw.rect(screen, border, rect, 1, border_radius=rect.height // 2)


def _draw_star(screen: pygame.Surface, center: tuple[int, int], r: int, color: tuple[int, int, int]) -> None:
    x, y = center
    pts = []
    for i in range(10):
        angle = -math.pi / 2 + i * math.tau / 10
        dist = r if i % 2 == 0 else r * 0.45
        pts.append((int(x + math.cos(angle) * dist), int(y + math.sin(angle) * dist)))
    pygame.draw.polygon(screen, color, pts)


def _shrink_polygon(polygon: list[tuple[float, float]], amount: float) -> list[tuple[float, float]]:
    cx = sum(p[0] for p in polygon) / len(polygon)
    cy = sum(p[1] for p in polygon) / len(polygon)
    result = []
    for px, py in polygon:
        dx, dy = px - cx, py - cy
        dist = max(1.0, math.hypot(dx, dy))
        ratio = max(0.0, (dist - amount) / dist)
        result.append((cx + dx * ratio, cy + dy * ratio))
    return result


def _draw_grass(surface: pygame.Surface, base: tuple[int, int], elapsed: float) -> None:
    x, y = base
    # Draw a clump of 3D-looking grass blades
    for i in range(5):
        h = 6 + (i % 3) * 3
        sway = int(math.sin(elapsed * 2.5 + x * 0.1 + i) * 3)
        ox = (i - 2) * 4
        # Shadow blade
        pygame.draw.line(surface, (30, 60, 20), (x + ox, y + 2), (x + ox + sway - 1, y - h + 2), 2)
        # Highlight blade
        pygame.draw.line(surface, (80, 160, 60), (x + ox, y), (x + ox + sway, y - h), 2)

def _draw_lake(surface: pygame.Surface, base: tuple[int, int], seed: int, elapsed: float) -> None:
    x, y = base
    r_w = 40 + (seed % 20)
    r_h = 25 + (seed % 10)
    lake_rect = pygame.Rect(x - r_w, y - r_h, r_w * 2, r_h * 2)
    
    # Deep water
    pygame.draw.ellipse(surface, (40, 90, 140), lake_rect)
    # Shallow shore (blend)
    pygame.draw.ellipse(surface, (60, 120, 160), lake_rect.inflate(-8, -8))
    # Shoreline border
    pygame.draw.ellipse(surface, (90, 140, 100), lake_rect.inflate(4, 4), 2)

    # Ripples (Animated 3D effect)
    for i in range(3):
        t = (elapsed * 1.5 + i * 2.0 + seed) % 6.0
        if t < 4.0:
            alpha = max(0, int(255 * (1.0 - t/4.0)))
            rip_w = int(r_w * 0.4 * t)
            rip_h = int(r_h * 0.4 * t)
            rip_surf = pygame.Surface((rip_w*2, rip_h*2), pygame.SRCALPHA)
            pygame.draw.ellipse(rip_surf, (200, 240, 255, alpha), rip_surf.get_rect(), 2)
            surface.blit(rip_surf, (x - rip_w, y - rip_h))

def _draw_tree(surface: pygame.Surface, base: tuple[int, int], scale: float) -> None:
    x, y = base
    trunk_w = max(4, int(8 * scale))
    trunk_h = max(15, int(25 * scale))
    # Drop shadow
    pygame.draw.ellipse(surface, (0, 0, 0, 70), (x - 20, y - 5, 40, 15))
    
    # 3D Trunk (cylinder shading)
    trunk_rect = pygame.Rect(x - trunk_w // 2, y - trunk_h + 5, trunk_w, trunk_h)
    pygame.draw.rect(surface, (80, 50, 30), trunk_rect, border_radius=3)
    pygame.draw.rect(surface, (120, 80, 50), (x - trunk_w//2, y - trunk_h + 5, trunk_w//2, trunk_h), border_radius=3) # Highlight
    
    # 3D Leaves (layered spheres)
    colors = [(30, 90, 40), (45, 120, 55), (60, 150, 70)]
    radii = [22, 18, 14]
    offsets = [(0, -25), (-15, -15), (15, -12)]
    
    for color, r, offset in zip(colors, radii, offsets):
        r = int(r * scale)
        cx = x + offset[0]
        cy = y + offset[1]
        # Sphere shading
        pygame.draw.circle(surface, _darken(color, 20), (cx, cy), r) # Base dark
        pygame.draw.circle(surface, color, (cx - r//4, cy - r//4), int(r * 0.8)) # Midtone
        pygame.draw.circle(surface, _brighten(color, 40), (cx - r//2, cy - r//2), int(r * 0.4)) # Specular

def _draw_bush(surface: pygame.Surface, base: tuple[int, int], scale: float) -> None:
    x, y = base
    r = max(8, int(15 * scale))
    # Shadow
    pygame.draw.ellipse(surface, (0, 0, 0, 60), (x - r - 4, y + r // 2 - 2, r * 2 + 8, r))
    # Base dark
    pygame.draw.circle(surface, (25, 60, 25), (x - r//2, y), r)
    pygame.draw.circle(surface, (25, 60, 25), (x + r//2, y), r)
    pygame.draw.circle(surface, (25, 60, 25), (x, y - r//2), r)
    # Highlight
    pygame.draw.circle(surface, (50, 120, 50), (x - r//2 - 2, y - 2), int(r*0.8))
    pygame.draw.circle(surface, (50, 120, 50), (x + r//2 - 2, y - 2), int(r*0.8))
    pygame.draw.circle(surface, (60, 140, 60), (x - 2, y - r//2 - 2), int(r*0.8))

def _draw_flower(surface: pygame.Surface, base: tuple[int, int], color: tuple[int, int, int], elapsed: float) -> None:
    x, y = base
    sway = int(math.sin(elapsed * 1.8 + x * 0.04) * 2)
    pygame.draw.line(surface, (48, 108, 38), (x, y + 5), (x + sway, y - 3), 1)
    petal_c = _brighten(color, 42)
    for i in range(5):
        angle = i * math.tau / 5 + elapsed * 0.25
        px = x + sway + int(math.cos(angle) * 3)
        py = y - 3 + int(math.sin(angle) * 3)
        pygame.draw.circle(surface, petal_c, (px, py), 2)
    pygame.draw.circle(surface, (248, 218, 58), (x + sway, y - 3), 2)

def _draw_rock(surface: pygame.Surface, base: tuple[int, int], scale: float) -> None:
    x, y = base
    w = max(15, int(35 * scale))
    h = max(12, int(22 * scale))
    # Shadow
    pygame.draw.ellipse(surface, (0, 0, 0, 80), (x - w//2 - 2, y + h//4, w + 4, h))
    
    # 3D Rock facets
    pts = [
        (x - w // 2, y + h // 3),
        (x - w // 3, y - h // 2),
        (x + w // 5, y - h // 2 - 2),
        (x + w // 2, y),
        (x + w // 3, y + h // 2),
    ]
    pygame.draw.polygon(surface, (90, 100, 110), pts)
    # Highlight facet (top left)
    pygame.draw.polygon(surface, (150, 160, 170), [pts[0], pts[1], pts[2], (x, y)])
    # Dark facet (bottom right)
    pygame.draw.polygon(surface, (60, 70, 80), [(x, y), pts[2], pts[3], pts[4]])


def _point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if (yi > y) != (yj > y):
            x_int = (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi
            if x < x_int:
                inside = not inside
        j = i
    return inside


def _mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _brighten(color: tuple[int, int, int], amount: int) -> tuple[int, int, int]:
    return tuple(min(255, c + amount) for c in color)


def _darken(color: tuple[int, int, int], amount: int) -> tuple[int, int, int]:
    return tuple(max(0, c - amount) for c in color)


def _format_time(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 60}:{total % 60:02d}"


def _fit_text(font: pygame.font.Font, text: str, max_width: int) -> str:
    if font.size(text)[0] <= max_width:
        return text
    clipped = text
    while clipped and font.size(clipped + "…")[0] > max_width:
        clipped = clipped[:-1]
    return clipped + "…" if clipped else "…"
