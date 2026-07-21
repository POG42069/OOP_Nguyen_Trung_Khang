
import math

import pygame

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.battle_arena import (
    DEATH_VISUAL_DURATION,
    BattleArenaType,
    BattleUnitType,
)
from quadrant_wars.core.battlefield import (
    RIVER_BUILDING_CLEARANCE as SHARED_RIVER_BUILDING_CLEARANCE,
    nearest_river_distance as shared_nearest_river_distance,
    river_flow_paths as shared_river_flow_paths,
    specialization_site_position,
)
from quadrant_wars.core.objective import WorldObjective, WorldObjectiveState, WorldObjectiveType
from quadrant_wars.core.territory import Territory, TerritorySpecialization
from quadrant_wars.game.game_manager import Match
from quadrant_wars.ui.art import ArtAssets
from quadrant_wars.ui.map_features import draw_map_features

# Key labels for player HUD popups
KEY_LABELS = [
    ("Q", "W", "E"),
    ("I", "O", "P"),
    ("Z", "X", "C"),
    ("B", "N", "M"),
]

FORTRESS_STYLES = (
    "fortress_western",
    "fortress_northern",
    "fortress_forest",
    "fortress_sun",
)
RIVER_BUILDING_CLEARANCE = SHARED_RIVER_BUILDING_CLEARANCE
WANDERING_RIVER_CLEARANCE = 120.0
WANDERING_RIVER_PATHS = shared_river_flow_paths((cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT))


class Renderer:
    def __init__(self, screen):
        self._screen = screen
        self._font = pygame.font.SysFont("segoeui", 18)
        self._small = pygame.font.SysFont("segoeui", 14)
        self._tiny = pygame.font.SysFont("segoeui", 11)
        self._title = pygame.font.SysFont("georgia", 28, bold=True)
        self._subtitle = pygame.font.SysFont("segoeui", 20, bold=True)
        self._bold_small = pygame.font.SysFont("segoeui", 13, bold=True)
        self._art = ArtAssets(screen.get_size())
        self._background = self._build_background()
        self._cloud_shadow = self._build_cloud_shadow()
        self._water_layer = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        self._river_paths = _river_flow_paths(screen.get_size())
        self._unit_positions = {}
        self._unit_targets = {}
        self._unit_facing = {}
        self._sprite_cache = {}
        self._territory_layer_cache = {}
        self._territory_decor_cache = {}
        self._last_elapsed = None
        self._frame_dt = 1.0 / max(30, cfg.FPS)

    @property
    def target_surface(self):
        return self._screen

    def bind_surface(self, screen):
        if screen is self._screen:
            return
        if screen.get_size() != self._screen.get_size():
            self._art = ArtAssets(screen.get_size())
            self._background = self._build_background()
            self._cloud_shadow = self._build_cloud_shadow()
            self._water_layer = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            self._river_paths = _river_flow_paths(screen.get_size())
            self._sprite_cache.clear()
            self._territory_layer_cache.clear()
            self._territory_decor_cache.clear()
        self._screen = screen

    def draw_match(self, match, player_states):
        elapsed = float(getattr(match, "elapsed", 0.0))
        if self._last_elapsed is None or elapsed < self._last_elapsed:
            self._frame_dt = 1.0 / max(30, cfg.FPS)
            if self._last_elapsed is not None:
                self._unit_positions.clear()
                self._unit_targets.clear()
                self._unit_facing.clear()
        else:
            self._frame_dt = min(0.05, max(0.0, elapsed - self._last_elapsed))
        self._last_elapsed = elapsed
        self._screen.blit(self._background, (0, 0))
        self._draw_animated_rivers(elapsed)

        # Broad, soft cloud shadows keep the battlefield alive without obscuring it.
        for i in range(4):
            fx = (int(match.elapsed * (8 + i * 1.8)) + i * 360) % (cfg.WINDOW_WIDTH + 420) - 210
            fy = 80 + i * 175 + int(math.sin(match.elapsed * 0.18 + i) * 34)
            self._screen.blit(self._cloud_shadow, self._cloud_shadow.get_rect(center=(fx, fy)))

        # Draw all ground layers before any structures.  This keeps grass,
        # flowers, and rocks visually behind castles and specialization sites.
        for territory in match.territories:
            self._draw_territory(territory, match.elapsed)

        for territory in match.territories:
            self._draw_territory_decor(territory, match.elapsed)

        draw_map_features(self._screen, match.terrain, match.elapsed)

        for territory in match.territories:
            self._draw_specialization_building(territory, match.elapsed)
            self._draw_base_building(territory, match.elapsed)

        objective = getattr(match, "world_objective", None)
        if objective is not None:
            self._draw_world_objective(objective, match.elapsed, match.objective_countdown)

        # Wandering units
        for territory in match.territories:
            self._draw_wandering_units(match, territory, match.elapsed)

        # Spawn effects
        for territory in match.territories:
            self._draw_spawn_effects(territory)

        # Moving armies
        for army in match.armies:
            self._draw_army(army)

        # Every visible combatant is a persistent BattleAgent.
        for arena in match.battles:
            self._draw_battle_arena(arena)

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
        self._draw_command_dock(match, player_states)

    def _build_background(self):
        if self._art.battlefield is not None:
            surface = self._art.battlefield.copy()
            grade = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            grade.fill((18, 30, 16, 18))
            surface.blit(grade, (0, 0))

            vignette = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            for i in range(22):
                alpha = max(2, 18 - i // 2)
                rect = vignette.get_rect().inflate(-i * 14, -i * 10)
                pygame.draw.rect(vignette, (3, 8, 4, alpha), rect, 9, border_radius=18)
            surface.blit(vignette, (0, 0))
            return surface

        surface = pygame.Surface((cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT))
        for y in range(cfg.WINDOW_HEIGHT):
            t = y / cfg.WINDOW_HEIGHT
            pygame.draw.line(surface, (int(40 + 22 * t), int(88 + 42 * t), int(38 + 18 * t)), (0, y), (cfg.WINDOW_WIDTH, y))
        return surface

    def _build_cloud_shadow(self):
        small = pygame.Surface((120, 58), pygame.SRCALPHA)
        for rect in ((4, 22, 70, 28), (34, 7, 78, 43), (62, 18, 54, 30)):
            pygame.draw.ellipse(small, (3, 12, 5, 19), rect)
        return pygame.transform.smoothscale(small, (420, 210))

    def _draw_animated_rivers(self, elapsed):
        river_mask = self._art.river_mask
        if river_mask is None:
            return

        layer = self._water_layer
        layer.fill((0, 0, 0, 0))
        for path_index, path in enumerate(self._river_paths):
            particle_count = 26
            speed = 0.072 + path_index * 0.006
            for i in range(particle_count):
                progress = (i / particle_count + elapsed * speed + path_index * 0.11) % 1.0
                x, y, tx, ty = _sample_path(path, progress)
                lateral = math.sin(elapsed * 1.8 + i * 2.17 + path_index) * (5 + i % 3 * 2)
                x += -ty * lateral
                y += tx * lateral

                glint = 0.5 + 0.5 * math.sin(elapsed * 3.4 + i * 1.73)
                length = 7 + i % 4 * 2
                start = (round(x - tx * length), round(y - ty * length))
                end = (round(x + tx * length), round(y + ty * length))
                pygame.draw.line(layer, (45, 178, 236, 35 + int(glint * 28)), start, end, 5)
                pygame.draw.line(layer, (190, 239, 255, 75 + int(glint * 90)), start, end, 2)

                if i % 8 == 0:
                    ripple = pygame.Rect(0, 0, 16 + int(glint * 9), 6 + int(glint * 3))
                    ripple.center = (round(x), round(y))
                    pygame.draw.arc(layer, (226, 248, 255, 95), ripple, 0.15, math.pi - 0.15, 1)

        layer.blit(river_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        self._screen.blit(layer, (0, 0))

    def _draw_territory(self, territory, elapsed):
        alive = getattr(territory.owner, "is_alive", False)
        base = territory.owner.color if alive else (72, 72, 68)
        cache_key = (
            territory.id,
            getattr(territory.owner, "id", id(territory.owner)),
            alive,
            base,
        )
        cached = self._territory_layer_cache.get(cache_key)
        if cached is not None:
            layer, bounds = cached
            self._screen.blit(layer, bounds)
            return

        xs = [int(p[0]) for p in territory.polygon]
        ys = [int(p[1]) for p in territory.polygon]
        bounds = pygame.Rect(min(xs) - 14, min(ys) - 14, max(xs) - min(xs) + 29, max(ys) - min(ys) + 29)
        local = [(int(x - bounds.x), int(y - bounds.y)) for x, y in territory.polygon]
        layer = pygame.Surface(bounds.size, pygame.SRCALPHA)

        # Preserve the painted ground while making ownership immediately readable.
        tint_alpha = 58 if alive else 100
        pygame.draw.polygon(layer, (*base, tint_alpha), local)

        self._territory_layer_cache[cache_key] = (layer, bounds)
        self._screen.blit(layer, bounds)

    def _draw_territory_hud(self, territory):
        """Small ownership/resource marker; unit strength stays visual on the map."""
        cx, cy = territory.centroid
        cx, cy = int(cx), int(cy)
        owner_color = territory.owner.color
        alive = getattr(territory.owner, "is_alive", False)

        name = _fit_text(self._bold_small, territory.owner.name.upper(), 110)
        name_surf = self._bold_small.render(name, True, (255, 249, 229))
        badge_w = max(112, name_surf.get_width() + 36)
        badge = pygame.Rect(cx - badge_w // 2, cy - 102, badge_w, 24)
        _draw_popup_bg(self._screen, badge, owner_color if alive else (82, 82, 78), radius=5)
        pygame.draw.rect(self._screen, owner_color if alive else (82, 82, 78), (badge.x, badge.y, 6, badge.height), border_radius=3)
        self._screen.blit(name_surf, name_surf.get_rect(center=(badge.centerx - 2, badge.centery)))

        if territory.is_capital and alive:
            _draw_star(self._screen, (badge.right - 13, badge.centery), 6, (255, 210, 62))

        if territory.specialization is not TerritorySpecialization.NONE:
            branch = {
                TerritorySpecialization.ECONOMY: "E",
                TerritorySpecialization.BARRACKS: "B",
                TerritorySpecialization.FORTRESS: "F",
            }[territory.specialization]
            level = territory.specialization_level
            label = f"{branch} {level if level else 'RUIN'}"
            if (
                territory.specialization is TerritorySpecialization.FORTRESS
                and level > 0
            ):
                label += f"  {territory.defenders.count}/{territory.defender_capacity}"
                if territory.next_defender_respawn is not None:
                    label += f"  {math.ceil(territory.next_defender_respawn)}s"
            chip_w = 116 if len(label) > 8 else 68
            chip = pygame.Rect(cx - chip_w // 2, badge.bottom + 4, chip_w, 15)
            fill = (35, 43, 37, 220) if level else (62, 47, 38, 220)
            _draw_pill(self._screen, chip, fill, _brighten(owner_color, 22))
            chip_text = self._tiny.render(label, True, (242, 232, 195))
            self._screen.blit(chip_text, chip_text.get_rect(center=chip.center))

        # Gold remains numeric because it is a spendable resource, not a unit counter.
        food_label = f"{int(territory.food)}  +{territory.income_per_second:.1f}/s"
        food_text = self._tiny.render(food_label, True, (255, 241, 196))
        food = pygame.Rect(cx - 47, cy + 76, 94, 20)
        _draw_pill(self._screen, food, (15, 20, 18, 210), (211, 163, 53))
        pygame.draw.circle(self._screen, (242, 193, 66), (food.x + 12, food.centery), 5)
        pygame.draw.circle(self._screen, (255, 230, 128), (food.x + 11, food.centery - 1), 2)
        self._screen.blit(food_text, food_text.get_rect(center=(food.centerx + 8, food.centery)))

        if territory.spawn_queue_size > 0:
            for i in range(min(4, territory.spawn_queue_size)):
                phase = pygame.time.get_ticks() * 0.006 + i * 1.1
                r = 2 + int((math.sin(phase) + 1) * 0.5)
                pygame.draw.circle(self._screen, (255, 202, 83), (food.right + 8 + i * 7, food.centery), r)

        # Queen HP bar
        if territory.queen.is_alive:
            q_hp = territory.queen.front_hp
            q_max = territory.queen.max_hp
            if q_hp < q_max:
                bar_w = 72
                bar_h = 7
                bar_rect = pygame.Rect(cx - bar_w // 2, food.bottom + 5, bar_w, bar_h)
                pygame.draw.rect(self._screen, (24, 10, 9), bar_rect, border_radius=3)
                fill_w = max(1, int(bar_w * q_hp / q_max))
                hp_ratio = q_hp / q_max
                bar_color = (68, 198, 82) if hp_ratio > 0.5 else (228, 178, 48) if hp_ratio > 0.25 else (218, 52, 42)
                pygame.draw.rect(self._screen, bar_color, (bar_rect.x, bar_rect.y, fill_w, bar_h), border_radius=3)
                pygame.draw.rect(self._screen, (235, 224, 190), bar_rect, 1, border_radius=3)

    def _draw_territory_decor(self, territory, elapsed):
        # The painted map already carries the biome. These accents add motion only.
        points = self._territory_decor_cache.get(territory.id)
        if points is None:
            points = (
                tuple(_decor_point(territory, 150 + i, 0.9) for i in range(7)),
                tuple(_decor_point(territory, 80 + i, 0.75) for i in range(2)),
                tuple(_decor_point(territory, 100 + i, 0.82) for i in range(4)),
            )
            self._territory_decor_cache[territory.id] = points
        grass_points, rock_points, flower_points = points
        for i, (x, y) in enumerate(grass_points):
            _draw_grass(self._screen, (x, y), elapsed + i)

        for i, (x, y) in enumerate(rock_points):
            _draw_rock(self._screen, (x, y), 0.34 + i * 0.08)

        for i, (x, y) in enumerate(flower_points):
            _draw_flower(self._screen, (x, y), territory.owner.color, elapsed + i * 1.3)

    def _draw_base_building(self, territory, elapsed):
        x, y = map(int, territory.battle_position)
        color = territory.owner.color
        alive = getattr(territory.owner, "is_alive", False)
        width = 122 if territory.is_capital else 108
        owner_id = int(getattr(territory.owner, "id", territory.id))
        building_name = FORTRESS_STYLES[owner_id % len(FORTRESS_STYLES)]
        building = self._art.building(building_name, width)
        if building is None:
            building = self._art.building("fortress", width)

        shadow = pygame.Surface((width + 28, 36), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (2, 7, 3, 105), shadow.get_rect())
        self._screen.blit(shadow, shadow.get_rect(center=(x, y + 20)))

        ring = pygame.Surface((width + 20, 34), pygame.SRCALPHA)
        pygame.draw.ellipse(ring, (*_darken(color, 25), 85 if alive else 45), ring.get_rect())
        pygame.draw.ellipse(ring, (*_brighten(color, 28), 175 if alive else 80), ring.get_rect(), 2)
        self._screen.blit(ring, ring.get_rect(center=(x, y + 14)))

        if building is None:
            pygame.draw.rect(self._screen, (135, 128, 110), (x - 42, y - 42, 84, 62), border_radius=5)
            return

        sprite = building
        if not alive:
            sprite = building.copy()
            sprite.fill((92, 86, 76, 190), special_flags=pygame.BLEND_RGBA_MULT)
        rect = sprite.get_rect(midbottom=(x, y + 30))

        is_spawning = alive and bool(territory.visual_spawns or territory.spawn_queue_size > 0)
        if alive:
            glow = pygame.Surface((70, 52), pygame.SRCALPHA)
            glow_alpha = int(82 + math.sin(elapsed * (7.5 if is_spawning else 2.4) + territory.id) * 32)
            pygame.draw.ellipse(glow, (255, 176 if is_spawning else 210, 74, max(25, glow_alpha)), glow.get_rect())
            self._screen.blit(glow, glow.get_rect(center=(x, y + 4)))

        self._screen.blit(sprite, rect)

        if alive:
            # A live cloth flag supplies the faction color without recoloring the artwork.
            pole_x = x + 2
            pole_top = rect.top - 19
            pygame.draw.line(self._screen, (65, 52, 35), (pole_x, rect.top + 18), (pole_x, pole_top), 3)
            wave = int(math.sin(elapsed * 3.2 + territory.id * 1.7) * 4)
            flag = [(pole_x, pole_top), (pole_x + 29, pole_top + 6 + wave), (pole_x, pole_top + 17)]
            pygame.draw.polygon(self._screen, _brighten(color, 24), flag)
            pygame.draw.lines(self._screen, _darken(color, 28), True, flag, 2)
            pygame.draw.circle(self._screen, (255, 232, 155), (pole_x + 12, pole_top + 8 + wave // 2), 3)
        else:
            for i in range(3):
                phase = (elapsed * 0.18 + i * 0.3) % 1.0
                sx = x - 14 + i * 13 + int(math.sin(elapsed + i) * 5)
                sy = rect.top + 20 - int(phase * 42)
                smoke = pygame.Surface((26, 26), pygame.SRCALPHA)
                pygame.draw.circle(smoke, (48, 45, 40, int(70 * (1.0 - phase))), (13, 13), 5 + int(phase * 8))
                self._screen.blit(smoke, (sx - 13, sy - 13))

    def _draw_specialization_building(self, territory, elapsed):
        specialization = territory.specialization
        if specialization is TerritorySpecialization.NONE:
            return
        if specialization is TerritorySpecialization.FORTRESS:
            return

        x, y = self._specialization_site_position(territory)
        x, y = int(x), int(y)
        level = territory.specialization_level
        alive = getattr(territory.owner, "is_alive", False)
        faction = territory.owner.color if alive else (92, 88, 78)

        shadow = pygame.Surface((90, 34), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (5, 8, 5, 105), shadow.get_rect())
        self._screen.blit(shadow, shadow.get_rect(center=(x, y + 17)))

        if level == 0:
            for i, offset in enumerate((-22, -8, 8, 23)):
                height = 7 + (i % 2) * 6
                pygame.draw.polygon(
                    self._screen,
                    (101, 92, 74),
                    [(x + offset - 7, y + 12), (x + offset + 7, y + 12), (x + offset + 2, y + 12 - height)],
                )
            for i in range(2):
                phase = (elapsed * 0.26 + i * 0.41) % 1.0
                smoke = pygame.Surface((28, 30), pygame.SRCALPHA)
                pygame.draw.circle(smoke, (59, 55, 49, int(80 * (1.0 - phase))), (14, 15), 5 + int(phase * 7))
                self._screen.blit(smoke, (x - 17 + i * 16, y - 17 - int(phase * 20)))
            return

        if specialization is TerritorySpecialization.ECONOMY:
            self._draw_economy_site((x, y), faction, level, elapsed)
        elif specialization is TerritorySpecialization.BARRACKS:
            self._draw_barracks_site((x, y), faction, level, elapsed)

    def _specialization_site_position(self, territory):
        point = specialization_site_position(territory)
        return int(point[0]), int(point[1])

    def _draw_economy_site(
        self,
        position,
        faction,
        level,
        elapsed,
    ):
        x, y = position
        soil = (111, 79, 39)
        for row in range(3 + level):
            yy = y + 7 + row * 5
            pygame.draw.line(self._screen, _darken(soil, 18), (x - 39, yy), (x + 38, yy - 2), 2)
            for col in range(5):
                px = x - 30 + col * 15 + (row % 2) * 4
                sway = int(math.sin(elapsed * 2.2 + row + col) * 2)
                pygame.draw.line(self._screen, (85, 153, 67), (px, yy), (px + sway, yy - 7), 2)
        roof = _brighten(faction, 12)
        pygame.draw.rect(self._screen, (143, 104, 56), (x - 17, y - 23, 34, 28), border_radius=2)
        pygame.draw.polygon(self._screen, roof, [(x - 23, y - 23), (x, y - 38), (x + 23, y - 23)])
        pygame.draw.polygon(self._screen, _darken(roof, 28), [(x - 23, y - 23), (x, y - 38), (x + 23, y - 23)], 2)
        pygame.draw.rect(self._screen, (69, 51, 34), (x - 4, y - 8, 8, 13))
        for i in range(level):
            coin_x = x + 26 + i * 8
            coin_y = y - 11 - i * 3
            pygame.draw.circle(self._screen, (243, 195, 67), (coin_x, coin_y), 4)
            pygame.draw.circle(self._screen, (255, 231, 132), (coin_x - 1, coin_y - 1), 1)

    def _draw_barracks_site(
        self,
        position,
        faction,
        level,
        elapsed,
    ):
        x, y = position
        tent_color = _brighten(faction, 6)
        for i in range(1 + level):
            tx = x - 25 + i * 25
            pygame.draw.polygon(self._screen, (74, 64, 48), [(tx - 12, y + 12), (tx + 12, y + 12), (tx, y - 18)])
            pygame.draw.polygon(self._screen, tent_color, [(tx - 12, y + 12), (tx, y - 18), (tx, y + 12)])
            pygame.draw.line(self._screen, _darken(tent_color, 30), (tx, y - 18), (tx, y + 13), 1)
        for i in range(2 + level):
            px = x - 32 + i * 18
            pygame.draw.line(self._screen, (154, 151, 139), (px, y + 13), (px + 8, y - 11), 2)
            pygame.draw.line(self._screen, (154, 151, 139), (px + 8, y + 13), (px, y - 11), 2)
        pole_x = x + 31
        pygame.draw.line(self._screen, (74, 54, 33), (pole_x, y + 13), (pole_x, y - 35), 3)
        wave = int(math.sin(elapsed * 4.0) * 4)
        flag = [(pole_x, y - 34), (pole_x + 23, y - 28 + wave), (pole_x, y - 20)]
        pygame.draw.polygon(self._screen, _brighten(faction, 25), flag)
        pygame.draw.lines(self._screen, _darken(faction, 32), True, flag, 1)

    def _draw_spawn_effects(self, territory):
        """Draw birth animation when units spawn from queen."""
        cx, cy = territory.battle_position
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

    def _draw_wandering_units(self, match, territory, elapsed):
        color = territory.owner.color
        alive = getattr(territory.owner, "is_alive", False)
        if not alive:
            return
            
        vs_soldiers = [vs for vs in territory.visual_spawns if vs["role"] == "soldier"]
        vs_workers = [vs for vs in territory.visual_spawns if vs["role"] == "worker"]
        vs_defenders = [vs for vs in territory.visual_spawns if vs["role"] == "defender"]
        
        active_arena = next(
            (
                arena
                for arena in getattr(match, "battles", [])
                if arena.arena_type is BattleArenaType.TERRITORY
                and arena.target is territory
            ),
            None,
        )

        sprites = []
        if territory.queen.is_alive:
            sprites.append(("queen", 0))
            
        w_drawn = min(territory.workers.count - len(vs_workers), 6 - len(vs_workers))
        for i in range(w_drawn):
            sprites.append(("worker", i))
            
        s_drawn = min(
            territory.soldiers.count - len(vs_soldiers),
            18 - len(vs_soldiers),
        )
        for i in range(s_drawn):
            sprites.append(("soldier", i))

        d_drawn = max(0, territory.defenders.count - len(vs_defenders))
        for i in range(d_drawn):
            sprites.append(("defender", i))

        for role, index in sprites:
            key = f"{territory.id}:{role}:{index}"

            animation = "walk"
            animation_phase = elapsed + index * 0.17 + territory.id * 0.31
            impact = 0.0
            hit_flash = 0.0
            if active_arena is not None and role == "queen":
                gate_x, gate_y = territory.battle_position
                target_pos = (gate_x, gate_y + 13)
                scale = 0.95
                animation = "attack" if active_arena.damage_flash > 0.2 else "idle"
                animation_phase = active_arena.elapsed + territory.id * 0.07
                hit_flash = active_arena.damage_flash * 0.42
            elif active_arena is not None and role == "worker":
                gate_x, gate_y = territory.battle_position
                shelter_angle = index * math.tau / max(1, territory.workers.count)
                target_pos = (
                    gate_x + math.cos(shelter_angle) * 17,
                    gate_y + 17 + math.sin(shelter_angle) * 7,
                )
                scale = 0.66
                animation = "idle"
            else:
                if role == "defender":
                    target_pos, scale = _defender_patrol_position(
                        territory,
                        index,
                        elapsed,
                    )
                else:
                    target_pos, scale = _wandering_position(territory, role, index, elapsed)

                if role == "worker":
                    work_time = (elapsed + index * 1.13 + territory.id * 0.47) % 5.4
                    if work_time < 1.08:
                        animation = "work"
                        animation_phase = work_time
                        target_pos = self._unit_positions.get(key, target_pos)
                    else:
                        self._unit_targets[key] = target_pos

            max_speed = {
                "queen": 36.0,
                "worker": 44.0,
                "soldier": 52.0,
                "defender": 40.0,
            }[role]
            (nx, ny), speed, facing = self._smooth_unit_position(
                key,
                target_pos,
                3.2,
                max_speed=max_speed,
            )
            draw_x, draw_y = nx, ny
            if animation == "attack" and active_arena is not None:
                lunge, impact = _attack_motion(animation_phase)
                to_enemy_x = active_arena.position[0] - nx
                to_enemy_y = active_arena.position[1] - ny
                distance = max(1.0, math.hypot(to_enemy_x, to_enemy_y))
                draw_x += to_enemy_x / distance * lunge
                draw_y += to_enemy_y / distance * lunge * 0.55
                if abs(to_enemy_x) > 0.5:
                    facing = 1 if to_enemy_x > 0 else -1
            elif animation != "work" and speed < 2.0:
                animation = "idle"

            self._draw_unit_sprite(
                (int(draw_x), int(draw_y)),
                color,
                scale,
                role,
                animation_phase,
                facing,
                animation=animation,
                hit_flash=hit_flash,
                impact=impact,
            )

        # Draw spawning units emerging from base building
        base_pos = territory.battle_position
        base_pos = (base_pos[0] + 3, base_pos[1] + 12) # Door position
        
        for vs in territory.visual_spawns:
            role = vs["role"]
            index = vs["index"]
            if role == "defender":
                target_pos, scale = _defender_patrol_position(
                    territory,
                    index,
                    elapsed,
                )
            else:
                target_pos, scale = _wandering_position(territory, role, index, elapsed)
            unit_key = f"{territory.id}:{role}:{index}"
            spawn_key = f"{unit_key}:spawn:{id(vs)}"
            stable_target = self._unit_targets.setdefault(spawn_key, target_pos)
            self._unit_positions.setdefault(spawn_key, (float(base_pos[0]), float(base_pos[1])))
            max_speed = 44.0 if role == "worker" else 40.0 if role == "defender" else 52.0
            (nx, ny), _, facing = self._smooth_unit_position(
                spawn_key,
                stable_target,
                3.4,
                max_speed=max_speed,
            )
            self._unit_positions[unit_key] = (nx, ny)
            self._unit_facing[unit_key] = facing

            self._draw_unit_sprite(
                (int(nx), int(ny)),
                color,
                scale,
                role,
                elapsed + index * 0.17,
                facing,
                animation="walk",
            )

    def _smooth_unit_position(
        self,
        key,
        target,
        responsiveness,
        *,
        max_speed = None,
    ):
        current = self._unit_positions.get(key)
        if current is None:
            self._unit_positions[key] = target
            facing = self._unit_facing.setdefault(key, 1)
            return target, 0.0, facing

        alpha = 1.0 - math.exp(-responsiveness * self._frame_dt)
        step_x = (target[0] - current[0]) * alpha
        step_y = (target[1] - current[1]) * alpha
        step_distance = math.hypot(step_x, step_y)
        if max_speed is not None and self._frame_dt > 0.0:
            max_step = max(0.0, max_speed) * self._frame_dt
            if step_distance > max_step:
                if max_step <= 0.0:
                    step_x = 0.0
                    step_y = 0.0
                else:
                    scale = max_step / step_distance
                    step_x *= scale
                    step_y *= scale
        nx = current[0] + step_x
        ny = current[1] + step_y
        self._unit_positions[key] = (nx, ny)

        dx = nx - current[0]
        dy = ny - current[1]
        speed = math.hypot(dx, dy) / max(self._frame_dt, 1e-6) if self._frame_dt > 0 else 0.0
        facing = self._unit_facing.get(key, 1)
        if abs(dx) > 0.04:
            facing = 1 if dx > 0 else -1
            self._unit_facing[key] = facing
        return (nx, ny), speed, facing

    def _draw_army(self, army):
        pos = army.position
        current = (int(pos[0]), int(pos[1]))
        ux, uy = army.heading
        nx, ny = -uy, ux
        color = army.attacker.color

        # Dust follows the formation only; the route itself is never drawn.
        for i in range(min(12, max(5, army.soldiers // 2))):
            back = 14 + i * 8
            spread = math.sin(army.elapsed * 5 + i * 2.1) * 10
            dot = (int(current[0] - ux * back + nx * spread), int(current[1] - uy * back + ny * spread))
            dot_r = 3 + (i % 3)
            dust = pygame.Surface((dot_r * 4, dot_r * 4), pygame.SRCALPHA)
            alpha = max(12, 68 - i * 7)
            pygame.draw.circle(dust, (198, 174, 123, alpha), (dot_r * 2, dot_r * 2), dot_r)
            self._screen.blit(dust, dust.get_rect(center=dot))

        facing = 1 if ux >= 0 else -1
        count = max(0, int(army.soldiers))
        scale = _formation_scale(count, marching=True)
        positions = army.unit_positions
        indexed = list(enumerate(zip(army.units, positions)))
        for i, (unit, sprite_pos) in sorted(indexed, key=lambda item: item[1][1][1]):
            wave = math.sin(army.elapsed * 10.5 + unit.unit_id * 0.37) * max(0.7, scale * 1.7)
            self._draw_unit_sprite(
                (round(sprite_pos[0]), round(sprite_pos[1] + wave)),
                color,
                scale,
                "soldier",
                army.elapsed + unit.unit_id * 0.031,
                facing,
                animation="walk",
                direction=(ux, uy),
            )

    def _draw_battle_arena(self, arena):
        cx, cy = map(int, arena.position)
        visible_agents = arena.visible_agents
        living_count = len(arena.living_agents)
        scale = max(0.52, _formation_scale(max(1, len(visible_agents))))

        ground = pygame.Surface((190, 118), pygame.SRCALPHA)
        pygame.draw.ellipse(ground, (34, 27, 18, 54), ground.get_rect().inflate(-14, -30))
        pygame.draw.ellipse(ground, (113, 78, 35, 38), ground.get_rect().inflate(-34, -47), 2)
        self._screen.blit(ground, ground.get_rect(center=(cx, cy + 15)))

        # Smoke is intentionally sparse and behind units. Density drops as the
        # arena gets crowded, while every Soldier remains visible.
        smoke_count = max(2, min(8, 10 - living_count // 24))
        smoke = pygame.Surface((186, 132), pygame.SRCALPHA)
        local_x, local_y = smoke.get_rect().center
        for index in range(smoke_count):
            life = (arena.elapsed * (0.26 + index * 0.017) + index * 0.173) % 1.0
            angle = index * 2.399 + arena.elapsed * 0.12
            distance = 16 + (index % 4) * 13
            px = local_x + int(math.cos(angle) * distance)
            py = local_y + int(math.sin(angle) * distance * 0.45 - life * 28)
            radius = 6 + int(life * 10)
            alpha = int(56 * (1.0 - life))
            pygame.draw.circle(smoke, (56, 58, 52, alpha), (px, py), radius)
        self._screen.blit(smoke, smoke.get_rect(center=(cx, cy - 3)))

        ordered = sorted(visible_agents, key=lambda agent: (agent.position[1], agent.unit_id))
        fx_stride = max(1, math.ceil(max(1, living_count) / 6))
        for agent in ordered:
            if not agent.alive:
                self._draw_fallen_agent(agent, scale)
                continue

            animation = {
                "run": "walk",
                "attack": "attack",
                "hit": "hit",
                "idle": "idle",
            }.get(agent.animation, "idle")
            facing = 1 if agent.facing[0] >= 0.0 else -1
            impact = 0.0
            if animation == "attack":
                impact = math.exp(
                    -((agent.animation_time - agent.impact_delay) / 0.045) ** 2
                )
                if agent.unit_id % fx_stride:
                    impact = 0.0
            position = (round(agent.position[0]), round(agent.position[1]))
            animation_phase = agent.animation_time
            if animation in ("idle", "walk"):
                animation_phase += agent.unit_id * 0.031
            role = (
                "defender"
                if agent.unit_type is BattleUnitType.DEFENDER
                else "soldier"
            )
            self._draw_unit_sprite(
                position,
                agent.color,
                scale,
                role,
                animation_phase,
                facing,
                animation=animation,
                hit_flash=agent.hit_flash,
                impact=impact,
                direction=agent.facing,
                show_crest=living_count <= 120,
            )
            if agent.health_ratio < 0.995:
                self._draw_agent_health(position, agent.health_ratio, scale)

        impact_budget = max(3, 7 - living_count // 14)
        for impact in arena.impacts[-impact_budget:]:
            self._draw_arena_impact(impact, arena.elapsed)

        if arena.damage_flash > 0.0:
            radius = 18 + int(arena.damage_flash * 18)
            flash = pygame.Surface((radius * 2 + 8, radius * 2 + 8), pygame.SRCALPHA)
            pygame.draw.circle(
                flash,
                (255, 219, 119, int(arena.damage_flash * 105)),
                flash.get_rect().center,
                radius,
                2,
            )
            self._screen.blit(flash, flash.get_rect(center=(cx, cy)))

    def _draw_fallen_agent(self, agent, scale):
        progress = min(1.0, agent.death_elapsed / DEATH_VISUAL_DURATION)
        role = (
            "defender"
            if agent.unit_type is BattleUnitType.DEFENDER
            else "soldier"
        )
        target_height = max(8, round((60 if role == "defender" else 56) * scale))
        frame_count = self._art.animation_count(role, "death", agent.facing)
        frame_index = min(
            max(0, frame_count - 1),
            int(progress * max(1, frame_count)),
        )
        sprite = self._art.animation_frame(
            role,
            "death",
            frame_index,
            target_height,
            agent.facing,
        )
        if sprite is None:
            sprite = self._get_cached_sprite(role, agent.color, scale)
        if agent.facing[0] >= 0.0:
            sprite = pygame.transform.flip(sprite, True, False)
        if frame_count <= 1:
            angle = (-1 if agent.facing[0] >= 0.0 else 1) * (8 + 70 * _smoothstep(progress))
            sprite = pygame.transform.rotate(sprite, angle)
        sprite = sprite.copy()
        sprite.set_alpha(max(0, int(255 * (1.0 - progress ** 1.8))))
        x, y = map(int, agent.position)
        shadow = pygame.Surface((32, 12), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (4, 5, 3, int(75 * (1.0 - progress))), shadow.get_rect())
        self._screen.blit(shadow, shadow.get_rect(center=(x, y + 7)))
        self._screen.blit(sprite, sprite.get_rect(midbottom=(x, y + 9)))
        if progress < 0.42:
            for index in range(3):
                angle = agent.unit_id * 0.73 + index * math.tau / 3
                distance = 5 + progress * 22
                pygame.draw.circle(
                    self._screen,
                    (186, 158, 102),
                    (
                        x + int(math.cos(angle) * distance),
                        y + 6 + int(math.sin(angle) * distance * 0.35),
                    ),
                    2,
                )

    def _draw_agent_health(
        self,
        position,
        ratio,
        scale,
    ):
        width = max(15, int(24 * scale))
        rect = pygame.Rect(0, 0, width, 4)
        rect.midbottom = (position[0], position[1] - max(24, int(44 * scale)))
        pygame.draw.rect(self._screen, (16, 20, 18), rect, border_radius=2)
        fill = rect.copy()
        fill.width = max(1, int(rect.width * max(0.0, min(1.0, ratio))))
        color = (92, 207, 102) if ratio > 0.5 else (238, 176, 70) if ratio > 0.25 else (218, 72, 62)
        pygame.draw.rect(self._screen, color, fill, border_radius=2)

    def _draw_arena_impact(self, impact, elapsed):
        x, y = map(int, impact.position)
        life = max(0.0, min(1.0, impact.ttl / 0.42))
        if impact.kind == "stone":
            for index in range(6):
                angle = index * math.tau / 6 + elapsed
                distance = 5 + (1.0 - life) * 18
                point = (
                    x + int(math.cos(angle) * distance),
                    y + int(math.sin(angle) * distance * 0.55),
                )
                pygame.draw.rect(self._screen, (128, 117, 97), (*point, 3, 3))
            return
        if impact.kind == "magic":
            radius = 5 + int((1.0 - life) * 12)
            pygame.draw.circle(self._screen, (*impact.color, 255), (x, y), radius, 2)
            pygame.draw.circle(self._screen, (238, 247, 255), (x, y), 2)
            return

        radius = 4 + int((1.0 - life) * 9)
        pygame.draw.circle(self._screen, (225, 235, 238), (x, y), radius, 2)
        for index in range(5):
            angle = index * math.tau / 5 + elapsed * 4.0
            end = (
                x + int(math.cos(angle) * (radius + 7)),
                y + int(math.sin(angle) * (radius + 7)),
            )
            pygame.draw.line(self._screen, (255, 190, 66), (x, y), end, 1)

    def _get_cached_sprite(self, role, color, scale):
        key = f"humanoid_{role}_{color[0]}_{color[1]}_{color[2]}_{scale:.2f}"
        if key in self._sprite_cache:
            return self._sprite_cache[key]

        base_height = {
            "queen": 76,
            "worker": 58,
            "soldier": 56,
            "defender": 60,
        }.get(role, 56)
        painted = self._art.sprite(role, round(base_height * scale))
        if painted is not None:
            self._sprite_cache[key] = painted
            return painted

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

        elif role in ("soldier", "defender"):
            # Legs (Armor)
            pygame.draw.rect(surf, _darken(armor_color, 20), (cx - base_r//2, cy + base_r, base_r//2, base_r))
            pygame.draw.rect(surf, _darken(armor_color, 20), (cx + 1, cy + base_r, base_r//2, base_r))
            # Torso (Armor over color)
            pygame.draw.rect(surf, body_color, (cx - base_r, cy, base_r*2, base_r*1.2))
            pygame.draw.rect(surf, armor_color, (cx - base_r//1.2, cy, base_r*1.6, base_r))
            # Right arm and weapon.
            pygame.draw.rect(surf, armor_color, (cx + base_r, cy + 1, base_r//2, base_r))
            sw_x, sw_y = cx + base_r + base_r//4, cy + base_r
            if role == "defender":
                pygame.draw.line(surf, (116, 78, 42), (sw_x, sw_y + base_r), (sw_x, sw_y - base_r * 3), max(2, int(scale*2)))
                pygame.draw.polygon(
                    surf,
                    (222, 222, 204),
                    [(sw_x, sw_y - base_r * 3 - 7), (sw_x - 4, sw_y - base_r * 3 + 2), (sw_x + 4, sw_y - base_r * 3 + 2)],
                )
            else:
                pygame.draw.line(surf, (192, 192, 192), (sw_x, sw_y), (sw_x, sw_y - base_r * 2), max(2, int(scale*3)))
                pygame.draw.line(surf, (255, 255, 255), (sw_x - 1, sw_y), (sw_x - 1, sw_y - base_r * 2 + 2), 1)
                pygame.draw.line(surf, (100, 50, 20), (sw_x - 4, sw_y - 2), (sw_x + 4, sw_y - 2), max(2, int(scale*2)))
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

    def _draw_world_objective(
        self,
        objective,
        elapsed,
        countdown,
    ):
        cx, cy = map(int, objective.centroid)
        state = objective.state
        pulse = 0.5 + 0.5 * math.sin(elapsed * 4.2)

        ring = pygame.Surface((180, 180), pygame.SRCALPHA)
        ring_center = ring.get_rect().center
        ring_color = (244, 197, 81) if state is WorldObjectiveState.TELEGRAPHING else (111, 211, 171)
        radius = 46 + int(pulse * 8)
        pygame.draw.circle(ring, (*ring_color, 28), ring_center, radius + 16)
        pygame.draw.circle(ring, (*ring_color, 150), ring_center, radius, 2)
        for i in range(12):
            angle = elapsed * 0.7 + i * math.tau / 12
            px = ring_center[0] + int(math.cos(angle) * (radius + 8))
            py = ring_center[1] + int(math.sin(angle) * (radius + 8))
            pygame.draw.circle(ring, (*ring_color, 170), (px, py), 2)
        self._screen.blit(ring, ring.get_rect(center=(cx, cy)))

        shadow = pygame.Surface((116, 42), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (4, 7, 5, 115), shadow.get_rect())
        self._screen.blit(shadow, shadow.get_rect(center=(cx, cy + 23)))

        alpha = 115 if state is WorldObjectiveState.TELEGRAPHING else 255
        landmark = pygame.Surface((120, 105), pygame.SRCALPHA)
        local = landmark.get_rect().center
        if objective.objective_type is WorldObjectiveType.CARAVAN:
            self._draw_caravan_objective(landmark, local, alpha, elapsed)
        elif objective.objective_type is WorldObjectiveType.WAR_BANNER:
            self._draw_banner_objective(landmark, local, alpha, elapsed)
        else:
            self._draw_shrine_objective(landmark, local, alpha, elapsed)
        self._screen.blit(landmark, landmark.get_rect(center=(cx, cy - 6)))

        if objective.state is WorldObjectiveState.ACTIVE:
            guard_count = objective.soldiers.count
            for i in range(guard_count):
                angle = elapsed * 0.5 + i * math.tau / max(1, guard_count)
                gx = cx + int(math.cos(angle) * 42)
                gy = cy + int(math.sin(angle) * 19) + 10
                self._draw_unit_sprite(
                    (gx, gy),
                    (136, 126, 105),
                    0.54,
                    "soldier",
                    elapsed + i * 0.3,
                    1 if math.cos(angle) >= 0 else -1,
                    animation="idle",
                )

        if objective.active and objective.queen.is_alive:
            hp_w = 56
            hp = max(0.0, objective.core_hp)
            fill = max(1, int(hp_w * hp / objective.core_max_hp))
            hp_y = cy + (104 if state is WorldObjectiveState.CONTESTED else 49)
            hp_rect = pygame.Rect(cx - hp_w // 2, hp_y, hp_w, 5)
            pygame.draw.rect(self._screen, (39, 24, 20), hp_rect, border_radius=2)
            pygame.draw.rect(self._screen, (226, 157, 61), (hp_rect.x, hp_rect.y, fill, hp_rect.height), border_radius=2)
            pygame.draw.rect(self._screen, (247, 225, 171), hp_rect, 1, border_radius=2)

        if state is WorldObjectiveState.TELEGRAPHING:
            status = f"{objective.display_name.upper()} IN {math.ceil(countdown)}"
            status_color = (255, 214, 105)
        elif state is WorldObjectiveState.CONTESTED:
            status = f"{objective.display_name.upper()} CONTESTED"
            status_color = (255, 179, 86)
        elif state is WorldObjectiveState.ACTIVE:
            status = f"{objective.display_name.upper()} READY"
            status_color = (222, 244, 201)
        else:
            status = "OBJECTIVE CLAIMED"
            status_color = (255, 218, 101)
        text = self._bold_small.render(status, True, status_color)
        label_y = cy - (126 if state is WorldObjectiveState.CONTESTED else 82)
        label = pygame.Rect(
            cx - max(66, text.get_width() // 2 + 10),
            label_y,
            max(132, text.get_width() + 20),
            21,
        )
        _draw_popup_bg(self._screen, label, ring_color, radius=5)
        self._screen.blit(text, text.get_rect(center=label.center))

    def _draw_caravan_objective(
        self,
        surface,
        center,
        alpha,
        elapsed,
    ):
        x, y = center
        wood = (145, 89, 42, alpha)
        pygame.draw.rect(surface, wood, (x - 34, y - 4, 56, 26), border_radius=3)
        pygame.draw.polygon(surface, (184, 118, 56, alpha), [(x - 39, y - 4), (x - 7, y - 29), (x + 28, y - 4)])
        pygame.draw.rect(surface, (247, 201, 73, alpha), (x - 5, y - 22, 17, 17), border_radius=2)
        for wx in (x - 22, x + 13):
            pygame.draw.circle(surface, (54, 43, 31, alpha), (wx, y + 24), 10)
            pygame.draw.circle(surface, (190, 149, 83, alpha), (wx, y + 24), 4)
        sparkle = int(math.sin(elapsed * 6) * 2)
        pygame.draw.circle(surface, (255, 237, 146, alpha), (x + 26, y - 20 + sparkle), 3)

    def _draw_banner_objective(
        self,
        surface,
        center,
        alpha,
        elapsed,
    ):
        x, y = center
        pygame.draw.line(surface, (93, 63, 36, alpha), (x - 3, y + 29), (x - 3, y - 44), 4)
        wave = int(math.sin(elapsed * 5.0) * 7)
        flag = [(x - 1, y - 41), (x + 39, y - 30 + wave), (x - 1, y - 12)]
        pygame.draw.polygon(surface, (195, 73, 59, alpha), flag)
        pygame.draw.lines(surface, (255, 210, 119, alpha), True, flag, 2)
        pygame.draw.circle(surface, (255, 213, 99, alpha), (x - 3, y - 48), 4)
        for i in range(4):
            phase = (elapsed * 0.9 + i * 0.24) % 1.0
            sx = x - 25 + i * 16
            sy = y + 27 - int(phase * 18)
            pygame.draw.circle(surface, (247, 159, 55, int(alpha * (1.0 - phase))), (sx, sy), 2 + i % 2)

    def _draw_shrine_objective(
        self,
        surface,
        center,
        alpha,
        elapsed,
    ):
        x, y = center
        glow = pygame.Surface((80, 80), pygame.SRCALPHA)
        pygame.draw.circle(glow, (104, 202, 212, int(alpha * 0.18)), glow.get_rect().center, 28 + int(math.sin(elapsed * 3) * 4))
        surface.blit(glow, glow.get_rect(center=(x, y - 3)))
        for ox, height in ((-24, 34), (0, 48), (24, 34)):
            pygame.draw.polygon(surface, (108, 121, 126, alpha), [(x + ox - 8, y + 25), (x + ox + 8, y + 25), (x + ox + 5, y + 25 - height), (x + ox - 4, y + 22 - height)])
            pygame.draw.line(surface, (173, 209, 202, alpha), (x + ox - 1, y + 16), (x + ox + 3, y + 5), 2)
        pygame.draw.circle(surface, (116, 232, 221, alpha), (x, y - 4), 8)
        pygame.draw.circle(surface, (235, 255, 217, alpha), (x - 2, y - 6), 2)

    def _draw_unit_sprite(
        self,
        center,
        color,
        scale,
        role,
        phase,
        facing = 1,
        *,
        animation = "idle",
        hit_flash = 0.0,
        impact = 0.0,
        direction = None,
        show_crest = True,
    ):
        base_height = {
            "queen": 76,
            "worker": 58,
            "soldier": 56,
            "defender": 60,
        }.get(role, 56)
        target_height = max(8, round(base_height * scale))
        frame_count = self._art.animation_count(role, animation, direction)
        frame_index = _animation_frame_index(role, animation, phase, frame_count)
        surf = self._art.animation_frame(
            role,
            animation,
            frame_index,
            target_height,
            direction,
        )
        if surf is None:
            surf = self._get_cached_sprite(role, color, scale)
            frame_index = 0

        x, y = center
        if animation == "work" and impact <= 0.0:
            impact = _work_impact(phase)

        if animation == "walk":
            stride = phase * math.tau / 0.48
            bob = -abs(math.sin(stride)) * (1.3 if role == "queen" else 2.1)
            lean = math.sin(stride) * 1.4 * facing
        elif animation == "attack":
            bob = -impact * 2.2
            lean = (-2.0 + impact * 6.5) * facing
        elif animation == "work":
            bob = -impact * 1.2
            lean = (1.0 - impact * 5.0) * facing
        else:
            bob = math.sin(phase * 2.4 + len(role)) * (0.8 if role == "queen" else 0.55)
            lean = math.sin(phase * 1.7 + len(role)) * 0.45

        base_w = max(18, int((32 if role == "queen" else 26) * scale))
        base_h = max(7, int(base_w * 0.38))
        marker_key = f"marker_{role}_{color}_{scale:.2f}"
        marker = self._sprite_cache.get(marker_key)
        if marker is None:
            marker = pygame.Surface((base_w + 12, base_h + 8), pygame.SRCALPHA)
            pygame.draw.ellipse(marker, (2, 6, 3, 115), marker.get_rect())
            inner = marker.get_rect().inflate(-6, -4)
            pygame.draw.ellipse(marker, (*_darken(color, 28), 190), inner)
            pygame.draw.ellipse(marker, (*_brighten(color, 54), 235), inner, 2)
            self._sprite_cache[marker_key] = marker
        self._screen.blit(marker, marker.get_rect(center=(x, y + 10)))

        self._draw_unit_action_fx((x, y), role, animation, facing, impact, phase, foreground=False)

        if facing > 0:
            flip_key = f"flip_{role}_{animation}_{frame_index}_{color}_{target_height}"
            flipped = self._sprite_cache.get(flip_key)
            if flipped is None:
                flipped = pygame.transform.flip(surf, True, False)
                self._sprite_cache[flip_key] = flipped
            surf = flipped

        lean_step = int(round(lean))
        if lean_step:
            lean_key = f"lean_{role}_{animation}_{frame_index}_{color}_{target_height}_{facing}_{lean_step}"
            leaned = self._sprite_cache.get(lean_key)
            if leaned is None:
                leaned = pygame.transform.rotate(surf, lean_step)
                self._sprite_cache[lean_key] = leaned
            surf = leaned

        render_surf = surf
        if hit_flash > 0.02:
            render_surf = surf.copy()
            flash = max(0, min(180, int(hit_flash * 180)))
            render_surf.fill((flash, flash, flash, 0), special_flags=pygame.BLEND_RGB_ADD)

        rect = render_surf.get_rect(midbottom=(x, round(y + 12 + bob)))
        self._screen.blit(render_surf, rect)
        self._draw_unit_action_fx((x, y), role, animation, facing, impact, phase, foreground=True)

        # Tiny heraldic marker makes team ownership legible in crowded fights.
        if show_crest:
            marker_y = rect.top + 3
            crest_radius = max(2, int(round(4.5 * scale)))
            crest_height = max(5, int(round(10.0 * scale)))
            crest = [
                (x, marker_y),
                (x + crest_radius, marker_y + crest_height // 2),
                (x, marker_y + crest_height),
                (x - crest_radius, marker_y + crest_height // 2),
            ]
            pygame.draw.polygon(self._screen, _brighten(color, 36), crest)
            pygame.draw.lines(self._screen, (255, 241, 199), True, crest, 1)

    def _draw_unit_action_fx(
        self,
        center,
        role,
        animation,
        facing,
        impact,
        phase,
        *,
        foreground,
    ):
        if impact < 0.025:
            return
        x, y = center
        alpha = max(0, min(255, int(impact * 255)))

        if role == "queen" and animation == "attack":
            if not foreground:
                aura = pygame.Surface((72, 62), pygame.SRCALPHA)
                radius = 20 + int(impact * 10)
                pygame.draw.circle(aura, (72, 194, 255, alpha // 4), (36, 35), radius)
                pygame.draw.circle(aura, (242, 220, 120, alpha), (36, 35), radius, 2)
                pygame.draw.circle(aura, (122, 224, 255, alpha), (36, 35), max(5, radius - 8), 1)
                self._screen.blit(aura, aura.get_rect(center=(x, y - 18)))
            else:
                orb_x = x + facing * 18
                orb_y = y - 38
                pygame.draw.circle(self._screen, (255, 247, 190), (orb_x, orb_y), 2 + int(impact * 3))
                for i in range(4):
                    angle = phase * 8.0 + i * math.tau / 4
                    end = (
                        orb_x + int(math.cos(angle) * (6 + impact * 7)),
                        orb_y + int(math.sin(angle) * (6 + impact * 7)),
                    )
                    pygame.draw.line(self._screen, (112, 216, 255), (orb_x, orb_y), end, 1)
            return

        if role == "worker" and animation == "work":
            if foreground:
                return
            dust = pygame.Surface((54, 30), pygame.SRCALPHA)
            for i in range(6):
                px = 11 + i * 7 + int(math.sin(phase * 11 + i) * 3)
                py = 18 - (i % 3) * 3
                radius = 2 + i % 2
                pygame.draw.circle(dust, (204, 174, 112, alpha // (2 + i % 2)), (px, py), radius)
            self._screen.blit(dust, dust.get_rect(center=(x + facing * 9, y + 8)))
            return

        if role in ("soldier", "defender") and animation == "attack" and foreground:
            slash = pygame.Surface((54, 48), pygame.SRCALPHA)
            if role == "defender":
                start = (12, 27) if facing > 0 else (42, 27)
                end = (48, 19) if facing > 0 else (6, 19)
                pygame.draw.line(slash, (255, 239, 183, alpha // 2), start, end, 5)
                pygame.draw.line(slash, (255, 249, 220, alpha), start, end, 2)
                points = [start, end]
            elif facing > 0:
                points = [(12, 10), (32, 15), (44, 32)]
            else:
                points = [(42, 10), (22, 15), (10, 32)]
            if role != "defender":
                pygame.draw.lines(slash, (255, 244, 205, alpha // 3), False, points, 6)
                pygame.draw.lines(slash, (255, 226, 132, alpha), False, points, 2)
            impact_point = points[-1]
            for i in range(5):
                angle = -1.2 + i * 0.6
                spark_end = (
                    impact_point[0] + int(math.cos(angle) * (4 + impact * 8)),
                    impact_point[1] + int(math.sin(angle) * (4 + impact * 8)),
                )
                pygame.draw.line(slash, (255, 188, 62, alpha), impact_point, spark_end, 1)
            self._screen.blit(slash, slash.get_rect(center=(x + facing * 10, y - 16)))

    def _draw_combat_effect(self, effect):
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

    def _draw_player_popup(self, match, player_idx, state_info):
        player = match.players[player_idx]
        home = match.home_territory(player)
        if home is None:
            return
        keys = KEY_LABELS[player_idx]
        state = state_info["state"]
        color = player.color

        anchor = home
        army_anchor = None
        if state == "summon":
            territory_ids = state_info.get("summon_territories", [])
            selected = state_info.get("summon_index", 0)
            if territory_ids:
                territory_id = territory_ids[min(selected, len(territory_ids) - 1)]
                if 0 <= territory_id < len(match.territories):
                    anchor = match.territories[territory_id]
        elif state == "development":
            territory_ids = state_info.get("development_territories", [])
            selected = state_info.get("development_index", 0)
            if territory_ids:
                territory_id = territory_ids[min(selected, len(territory_ids) - 1)]
                if 0 <= territory_id < len(match.territories):
                    anchor = match.territories[territory_id]
        elif state == "retreat":
            armies = match.cancellable_armies(player)
            selected = state_info.get("march_index", 0)
            if armies:
                army_anchor = armies[min(selected, len(armies) - 1)].position
        cx, cy = army_anchor if army_anchor is not None else anchor.centroid
        cx, cy = int(cx), int(cy)

        # Popup background
        popup_w = 228 if state in ("summon", "strategy", "development", "military", "retreat") else 180
        popup_h = 116 if state == "development" else 104 if state == "summon" else 96 if state in ("military", "retreat") else 90 if state == "strategy" else 82
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
            territory_ids = state_info.get("summon_territories", [])
            selected = state_info.get("summon_index", 0)
            territory = home
            if territory_ids:
                territory_id = territory_ids[min(selected, len(territory_ids) - 1)]
                if 0 <= territory_id < len(match.territories):
                    territory = match.territories[territory_id]

            choices = ("soldier", "worker", None)
            choice_index = state_info.get("summon_choice", 0)
            choice = choices[min(max(0, choice_index), len(choices) - 1)]
            header = self._tiny.render(
                f"RECRUIT T{territory.id + 1}  {int(territory.food)}g  +{territory.income_per_second:.1f}/s",
                True,
                cfg.ACCENT_2,
            )
            self._screen.blit(header, (x0, y0))
            self._draw_key_option(x0, y0 + 18, keys[0], f"Region T{territory.id + 1}", (161, 203, 231))
            if choice == "soldier":
                self._draw_key_option(x0, y0 + 37, keys[1], f"Soldier ({territory.soldier_cost}g)", (218, 128, 68))
                self._draw_key_option(x0, y0 + 56, keys[2], "Confirm", (244, 205, 98))
            elif choice == "worker":
                self._draw_key_option(x0, y0 + 37, keys[1], f"Worker ({territory.worker_cost()}g)", (88, 168, 98))
                self._draw_key_option(x0, y0 + 56, keys[2], "Confirm", (244, 205, 98))
            else:
                self._draw_key_option(x0, y0 + 37, keys[1], "Cancel", cfg.MUTED_TEXT)
                self._draw_key_option(x0, y0 + 56, keys[2], "Back", cfg.MUTED_TEXT)
            message = state_info.get("message", "")
            if message:
                message_surf = self._tiny.render(_fit_text(self._tiny, message, popup_w - 20), True, (238, 137, 97))
                self._screen.blit(message_surf, (x0, y0 + 75))

        elif state == "military":
            armies = match.cancellable_armies(player)
            header = self._tiny.render("MILITARY ORDERS", True, (224, 173, 102))
            self._screen.blit(header, (x0, y0))
            self._draw_key_option(x0, y0 + 18, keys[0], "Launch attack", (222, 113, 88))
            recall_color = (106, 190, 218) if armies else cfg.MUTED_TEXT
            self._draw_key_option(x0, y0 + 38, keys[1], f"Recall army ({len(armies)})", recall_color)
            self._draw_key_option(x0, y0 + 58, keys[2], "Back", cfg.MUTED_TEXT)
            message = state_info.get("message", "")
            if message:
                message_surf = self._tiny.render(_fit_text(self._tiny, message, popup_w - 20), True, (238, 137, 97))
                self._screen.blit(message_surf, (x0, y0 + 77))

        elif state == "retreat":
            armies = match.cancellable_armies(player)
            if not armies:
                return
            selected = state_info.get("march_index", 0) % len(armies)
            army = armies[selected]
            target = "objective" if not army.targets_territory else f"T{army.target_id + 1}"
            header = self._tiny.render("RECALL BEFORE BATTLE", True, (106, 190, 218))
            self._screen.blit(header, (x0, y0))
            self._draw_key_option(x0, y0 + 18, keys[0], f"Army {selected + 1}/{len(armies)}: {army.soldiers} -> {target}", (203, 216, 219))
            self._draw_key_option(x0, y0 + 38, keys[1], "Recall now", (111, 201, 224))
            self._draw_key_option(x0, y0 + 58, keys[2], "Back", cfg.MUTED_TEXT)

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
            self._draw_key_option(x0, y0 + 16, keys[0], "0%", cfg.MUTED_TEXT)
            self._draw_key_option(x0 + 60, y0 + 16, keys[1], "33%", (108, 198, 138))
            self._draw_key_option(x0 + 120, y0 + 16, keys[2], "66%", (218, 188, 58))
            target = state_info.get("target")
            if target:
                if isinstance(target, WorldObjective):
                    action = "Claim"
                    target_name = target.display_name
                else:
                    action = "Reinforce" if getattr(target, "owner", None) is player else "Attack"
                    target_name = f"T{target.id+1} ({getattr(target.owner, 'name', 'Unknown')})"
                tgt_name = _fit_text(self._tiny, target_name, 110)
                tgt_text = self._tiny.render(f"{action} → {tgt_name}", True, cfg.TEXT)
                self._screen.blit(tgt_text, (x0, y0 + 40))
                total_soldiers = sum(t.soldiers.count for t in match.territories_of(player) if t is not target)
                for i in range(min(12, total_soldiers)):
                    dot_x = x0 + 5 + (i % 12) * 11
                    dot_y = y0 + 62
                    pygame.draw.circle(self._screen, _darken(player.color, 25), (dot_x, dot_y), 4)
                    pygame.draw.circle(self._screen, _brighten(player.color, 42), (dot_x, dot_y), 4, 1)

        elif state == "strategy":
            header = self._tiny.render("STRATEGY", True, (163, 223, 190))
            self._screen.blit(header, (x0, y0))
            objective = match.world_objective
            if objective is not None and objective.active:
                objective_label = f"Claim {objective.display_name.title()}"
                objective_color = (244, 205, 99)
            elif objective is not None and objective.state is WorldObjectiveState.TELEGRAPHING:
                objective_label = f"Objective in {math.ceil(match.objective_countdown)}s"
                objective_color = cfg.MUTED_TEXT
            else:
                objective_label = "No objective active"
                objective_color = cfg.MUTED_TEXT
            self._draw_key_option(x0, y0 + 18, keys[0], "Development", (118, 208, 149))
            self._draw_key_option(x0, y0 + 37, keys[1], objective_label, objective_color)
            self._draw_key_option(x0, y0 + 56, keys[2], "Cancel", cfg.MUTED_TEXT)
            message = state_info.get("message", "")
            if message:
                message_surf = self._tiny.render(_fit_text(self._tiny, message, popup_w - 20), True, (238, 137, 97))
                self._screen.blit(message_surf, (x0, y0 + 73))

        elif state == "development":
            territory_ids = state_info.get("development_territories", [])
            selected = state_info.get("development_index", 0)
            choice_index = state_info.get("development_choice", 0)
            choices = (
                TerritorySpecialization.ECONOMY,
                TerritorySpecialization.BARRACKS,
                TerritorySpecialization.FORTRESS,
                None,
            )
            choice = choices[min(max(0, choice_index), len(choices) - 1)]
            if not territory_ids:
                return
            territory_id = territory_ids[min(selected, len(territory_ids) - 1)]
            territory = match.territories[territory_id]
            header = self._tiny.render(
                f"DEVELOP T{territory.id + 1}  {int(territory.food)}g  +{territory.income_per_second:.1f}/s",
                True,
                (163, 223, 190),
            )
            self._screen.blit(header, (x0, y0))
            current_branch = territory.specialization.name.title()
            current = f"Current: {current_branch} {territory.specialization_level or 'Ruin' if territory.specialization is not TerritorySpecialization.NONE else '-'}"
            self._draw_key_option(x0, y0 + 17, keys[0], f"Region T{territory.id + 1}", (161, 203, 231))
            if choice is None:
                self._draw_key_option(x0, y0 + 36, keys[1], "Cancel", cfg.MUTED_TEXT)
                self._draw_key_option(x0, y0 + 55, keys[2], "Back", cfg.MUTED_TEXT)
            else:
                quote = territory.development_quote(choice)
                label = f"{quote.action.title()} {choice.name.title()} ({quote.cost}g)"
                label_color = (112, 213, 147) if quote.allowed else (232, 142, 96)
                self._draw_key_option(x0, y0 + 36, keys[1], _fit_text(self._tiny, label, 172), label_color)
                self._draw_key_option(x0, y0 + 55, keys[2], "Confirm", (244, 205, 98))
            current_surf = self._tiny.render(_fit_text(self._tiny, current, popup_w - 20), True, cfg.MUTED_TEXT)
            self._screen.blit(current_surf, (x0, y0 + 73))
            message = state_info.get("message", "")
            if message:
                message_surf = self._tiny.render(_fit_text(self._tiny, message, popup_w - 20), True, (238, 137, 97))
                self._screen.blit(message_surf, (x0, y0 + 90))

    def _draw_key_option(self, x, y, key, label, color):
        pygame.draw.rect(self._screen, (42, 46, 56), (x, y, 16, 14), border_radius=3)
        pygame.draw.rect(self._screen, (82, 86, 98), (x, y, 16, 14), 1, border_radius=3)
        key_surf = self._tiny.render(key, True, (248, 238, 218))
        self._screen.blit(key_surf, key_surf.get_rect(center=(x + 8, y + 7)))
        label_surf = self._tiny.render(label, True, color)
        self._screen.blit(label_surf, (x + 20, y + 1))

    def _draw_command_dock(self, match, player_states):
        for order, (player_idx, state_info) in enumerate(sorted(player_states.items())):
            player = match.players[player_idx]
            panel = pygame.Rect(12 + order * 178, cfg.WINDOW_HEIGHT - 46, 168, 36)
            layer = pygame.Surface(panel.size, pygame.SRCALPHA)
            pygame.draw.rect(layer, (12, 17, 18, 226), layer.get_rect(), border_radius=5)
            pygame.draw.rect(layer, (*player.color, 225), (0, 0, 5, panel.height), border_radius=3)
            pygame.draw.rect(layer, (*_brighten(player.color, 28), 150), layer.get_rect(), 1, border_radius=5)
            self._screen.blit(layer, panel)

            p_label = self._bold_small.render(f"P{player_idx + 1}", True, (247, 241, 220))
            self._screen.blit(p_label, p_label.get_rect(center=(panel.x + 19, panel.centery)))

            keys = KEY_LABELS[player_idx]
            for i, label in enumerate(keys):
                cell_x = panel.x + 36 + i * 43
                enabled = True
                key_rect = pygame.Rect(cell_x, panel.y + 7, 23, 22)
                fill = (42, 49, 49) if enabled else (29, 33, 33)
                stroke = _brighten(player.color, 42) if enabled else (71, 76, 74)
                pygame.draw.rect(self._screen, fill, key_rect, border_radius=4)
                pygame.draw.rect(self._screen, stroke, key_rect, 1, border_radius=4)
                key_surf = self._tiny.render(label, True, (251, 245, 224) if enabled else (102, 107, 104))
                self._screen.blit(key_surf, key_surf.get_rect(center=key_rect.center))

                icon_x = cell_x + 31
                icon_y = panel.centery
                icon_c = stroke if enabled else (71, 76, 74)
                if i == 0:
                    pygame.draw.line(self._screen, icon_c, (icon_x - 4, icon_y), (icon_x + 4, icon_y), 2)
                    pygame.draw.line(self._screen, icon_c, (icon_x, icon_y - 4), (icon_x, icon_y + 4), 2)
                elif i == 1:
                    pygame.draw.line(self._screen, icon_c, (icon_x - 4, icon_y - 4), (icon_x + 4, icon_y + 4), 2)
                    pygame.draw.line(self._screen, icon_c, (icon_x + 4, icon_y - 4), (icon_x - 4, icon_y + 4), 2)
                else:
                    pygame.draw.rect(self._screen, icon_c, (icon_x - 4, icon_y - 4, 8, 8), 1)
                    pygame.draw.line(self._screen, icon_c, (icon_x, icon_y - 3), (icon_x, icon_y + 3), 1)
                    pygame.draw.line(self._screen, icon_c, (icon_x - 3, icon_y), (icon_x + 3, icon_y), 1)

    def _draw_top_bar(self, match):
        """Compact per-player economy and army overview."""
        bar_h = 48
        bar = pygame.Surface((cfg.WINDOW_WIDTH, bar_h), pygame.SRCALPHA)
        pygame.draw.rect(bar, (8, 13, 13, 232), bar.get_rect())
        pygame.draw.line(bar, (118, 101, 64, 195), (0, bar_h - 1), (cfg.WINDOW_WIDTH, bar_h - 1), 1)
        self._screen.blit(bar, (0, 0))

        pygame.draw.circle(self._screen, (211, 170, 78), (18, 24), 7, 1)
        pygame.draw.line(self._screen, (235, 213, 160), (18, 24), (18, 20), 1)
        pygame.draw.line(self._screen, (235, 213, 160), (18, 24), (22, 26), 1)
        time_text = self._bold_small.render(_format_time(match.elapsed), True, (244, 232, 201))
        self._screen.blit(time_text, (30, 17))

        slot_x = 72
        available = cfg.WINDOW_WIDTH - slot_x - 8
        slot_w = available // max(1, len(match.players))
        for i, player in enumerate(match.players):
            rect = pygame.Rect(slot_x + i * slot_w + 3, 6, slot_w - 6, 36)
            owned = [territory for territory in match.territories if territory.owner is player]
            alive = player.is_alive and any(t.queen.is_alive for t in owned)
            c = player.color if alive else (72, 72, 68)
            panel = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(panel, (20, 27, 26, 215), panel.get_rect(), border_radius=5)
            pygame.draw.rect(panel, (*c, 230), (0, 0, 4, panel.get_height()), border_radius=2)
            pygame.draw.rect(panel, (*_brighten(c, 28), 105), panel.get_rect(), 1, border_radius=5)
            self._screen.blit(panel, rect)

            pygame.draw.circle(self._screen, c, (rect.x + 15, rect.centery), 7)
            pygame.draw.circle(self._screen, (247, 238, 211), (rect.x + 15, rect.centery), 7, 1)
            if not alive:
                pygame.draw.line(self._screen, (212, 71, 57), (rect.x + 10, rect.centery - 5), (rect.x + 20, rect.centery + 5), 2)
                pygame.draw.line(self._screen, (212, 71, 57), (rect.x + 20, rect.centery - 5), (rect.x + 10, rect.centery + 5), 2)
            player_label = self._tiny.render(f"P{i + 1}", True, (247, 241, 220))
            self._screen.blit(player_label, (rect.x + 27, rect.y + 12))

            if player.war_banner_time > 0:
                flag_x = rect.x + 49
                pygame.draw.line(self._screen, (205, 177, 105), (flag_x, rect.y + 10), (flag_x, rect.bottom - 9), 1)
                pygame.draw.polygon(
                    self._screen,
                    (237, 119, 77),
                    [(flag_x + 1, rect.y + 10), (flag_x + 8, rect.y + 13), (flag_x + 1, rect.y + 17)],
                )
                buff_surf = self._tiny.render(str(math.ceil(player.war_banner_time)), True, (255, 225, 139))
                self._screen.blit(buff_surf, (flag_x + 9, rect.y + 11))

            pygame.draw.line(self._screen, (103, 110, 102), (rect.x + 61, rect.y + 8), (rect.x + 61, rect.bottom - 8), 1)

            gold = int(sum(territory.food for territory in owned))
            soldiers = sum(territory.soldiers.count for territory in owned)
            workers = sum(territory.workers.count for territory in owned)
            soldiers += sum(army.soldiers for army in match.armies if army.attacker is player)
            soldiers += sum(
                arena.commitment_count(player)
                for arena in match.battles
            )
            stats = (
                ("gold", gold, (240, 190, 59)),
                ("soldier", soldiers, (198, 214, 224)),
                ("worker", workers, (207, 157, 93)),
            )
            metrics_x = rect.x + 66
            metric_w = max(38, (rect.width - 69) // 3)
            text_color = (242, 239, 220) if alive else (119, 122, 116)
            for stat_index, (kind, value, icon_color) in enumerate(stats):
                cell_x = metrics_x + stat_index * metric_w
                if stat_index:
                    pygame.draw.line(
                        self._screen,
                        (62, 72, 68),
                        (cell_x - 3, rect.y + 10),
                        (cell_x - 3, rect.bottom - 10),
                        1,
                    )
                value_surf = self._bold_small.render(_compact_stat(value), True, text_color)
                group_width = 19 + value_surf.get_width()
                group_x = cell_x + max(0, (metric_w - group_width) // 2)
                _draw_resource_icon(
                    self._screen,
                    kind,
                    (group_x + 7, rect.centery),
                    icon_color if alive else (94, 98, 94),
                )
                self._screen.blit(value_surf, (group_x + 18, rect.y + 10))


# ─────────────────── Helpers ───────────────────

def _river_flow_paths(viewport):
    width, height = viewport
    normalized = (
        ((0.24, -0.04), (0.22, 0.06), (0.17, 0.15), (0.08, 0.24), (-0.03, 0.37)),
        ((-0.03, 0.53), (0.01, 0.64), (0.07, 0.71), (0.11, 0.78), (0.14, 0.88), (0.16, 1.04)),
        ((0.80, -0.04), (0.82, 0.06), (0.87, 0.12), (0.94, 0.19), (1.02, 0.28), (1.03, 0.47)),
        ((1.04, 0.60), (0.99, 0.68), (0.93, 0.75), (0.86, 0.82), (0.82, 0.90), (0.79, 1.04)),
    )
    return [[(x * width, y * height) for x, y in path] for path in normalized]


def _sample_path(path, progress):
    lengths = [math.dist(path[i], path[i + 1]) for i in range(len(path) - 1)]
    total = max(1.0, sum(lengths))
    remaining = (progress % 1.0) * total
    for i, segment_length in enumerate(lengths):
        if remaining <= segment_length or i == len(lengths) - 1:
            ratio = remaining / max(1.0, segment_length)
            x0, y0 = path[i]
            x1, y1 = path[i + 1]
            dx = x1 - x0
            dy = y1 - y0
            return x0 + dx * ratio, y0 + dy * ratio, dx / segment_length, dy / segment_length
        remaining -= segment_length
    x0, y0 = path[-2]
    x1, y1 = path[-1]
    length = max(1.0, math.hypot(x1 - x0, y1 - y0))
    return x1, y1, (x1 - x0) / length, (y1 - y0) / length


def _nearest_river_distance(
    point,
    river_paths,
):
    distances = [
        _point_to_segment_distance(point, start, end)
        for path in river_paths
        for start, end in zip(path, path[1:])
    ]
    return min(distances, default=math.inf)


def _point_to_segment_distance(
    point,
    start,
    end,
):
    px, py = point
    sx, sy = start
    ex, ey = end
    dx = ex - sx
    dy = ey - sy
    length_squared = dx * dx + dy * dy
    if length_squared <= 0.0:
        return math.hypot(px - sx, py - sy)
    ratio = max(0.0, min(1.0, ((px - sx) * dx + (py - sy) * dy) / length_squared))
    closest_x = sx + dx * ratio
    closest_y = sy + dy * ratio
    return math.hypot(px - closest_x, py - closest_y)


def _sample_closed_path(
    path,
    spacing,
    offset = 0.0,
):
    if len(path) < 2:
        return []
    segments = [
        (path[index], path[(index + 1) % len(path)])
        for index in range(len(path))
    ]
    lengths = [math.dist(start, end) for start, end in segments]
    total = sum(lengths)
    distance = offset % spacing
    samples = []
    while distance < total:
        remaining = distance
        for (start, end), length in zip(segments, lengths):
            if remaining <= length:
                ratio = remaining / max(1.0, length)
                dx = end[0] - start[0]
                dy = end[1] - start[1]
                samples.append(
                    (
                        start[0] + dx * ratio,
                        start[1] + dy * ratio,
                        dx / max(1.0, length),
                        dy / max(1.0, length),
                    )
                )
                break
            remaining -= length
        distance += spacing
    return samples


def _draw_resource_icon(
    surface,
    kind,
    center,
    color,
):
    x, y = center
    if kind == "gold":
        pygame.draw.circle(surface, _darken(color, 48), center, 7)
        pygame.draw.circle(surface, color, center, 6)
        pygame.draw.circle(surface, _brighten(color, 28), (x - 2, y - 2), 2)
        pygame.draw.circle(surface, (255, 236, 159), center, 6, 1)
    elif kind == "soldier":
        shield = [(x, y - 7), (x + 6, y - 4), (x + 5, y + 3), (x, y + 8), (x - 5, y + 3), (x - 6, y - 4)]
        pygame.draw.polygon(surface, _darken(color, 56), shield)
        pygame.draw.lines(surface, color, True, shield, 1)
        pygame.draw.line(surface, _brighten(color, 32), (x - 4, y + 5), (x + 5, y - 5), 2)
        pygame.draw.line(surface, color, (x - 5, y), (x + 1, y + 6), 1)
    else:
        pygame.draw.line(surface, (126, 82, 44), (x - 4, y + 7), (x + 3, y - 5), 3)
        pygame.draw.line(surface, color, (x - 4, y - 6), (x + 7, y - 3), 3)
        pygame.draw.line(surface, _brighten(color, 32), (x - 3, y - 7), (x + 6, y - 4), 1)


def _compact_stat(value):
    if value >= 10_000:
        return f"{value / 1000:.0f}k"
    if value >= 1_000:
        return f"{value / 1000:.1f}k"
    return str(value)


def _animation_frame_index(role, animation, phase, frame_count):
    if frame_count <= 1:
        return 0
    if animation == "walk":
        return int(phase * (8.5 if role == "queen" else 10.5)) % frame_count
    if role in ("soldier", "defender") and animation == "idle":
        return int(phase * 4.0) % frame_count
    if role in ("soldier", "defender") and animation == "attack":
        duration = 0.68 if role == "defender" else 0.58
        return min(frame_count - 1, int(max(0.0, phase) / duration * frame_count))
    if role in ("soldier", "defender") and animation == "hit":
        return min(frame_count - 1, int(max(0.0, phase) / 0.16 * frame_count))

    duration = 1.08 if animation == "work" else 0.72
    cycle = (phase % duration) / duration
    if cycle < 0.2:
        frame = 0
    elif cycle < 0.42:
        frame = 1
    elif cycle < 0.57:
        frame = 2
    elif cycle < 0.84:
        frame = 3
    else:
        frame = 0
    return min(frame, frame_count - 1)


def _formation_scale(count, marching = False):
    """Keep every unit legible while allowing large armies to remain compact."""
    if count <= 8:
        return 0.84 if marching else 0.78
    if count <= 20:
        return 0.72 if marching else 0.68
    if count <= 40:
        return 0.61 if marching else 0.58
    if count <= 80:
        return 0.52 if marching else 0.50
    return 0.44


def _formation_slots(
    front_center,
    count,
    forward,
    scale,
    *,
    rearward,
):
    if count <= 0:
        return []
    length = max(0.01, math.hypot(*forward))
    ux, uy = forward[0] / length, forward[1] / length
    nx, ny = -uy, ux
    columns = min(14, max(1, math.ceil(math.sqrt(count * 1.45))))
    lateral_spacing = max(10.0, 22.0 * scale)
    rank_spacing = max(9.0, 18.0 * scale)
    direction = -1.0 if rearward else 1.0
    slots = []
    for index in range(count):
        rank = index // columns
        column = index % columns
        rank_count = min(columns, count - rank * columns)
        lateral = (column - (rank_count - 1) / 2.0) * lateral_spacing
        depth = rank * rank_spacing * direction
        slots.append(
            (
                front_center[0] + nx * lateral + ux * depth,
                front_center[1] + ny * lateral + uy * depth,
            )
        )
    return slots


def _attack_motion(phase):
    cycle = (phase % 0.72) / 0.72
    if cycle < 0.2:
        lunge = -2.0 * _smoothstep(cycle / 0.2)
    elif cycle < 0.45:
        lunge = -2.0 + 11.0 * _ease_out_cubic((cycle - 0.2) / 0.25)
    elif cycle < 0.58:
        lunge = 9.0 - 2.0 * _smoothstep((cycle - 0.45) / 0.13)
    else:
        lunge = 7.0 * (1.0 - _smoothstep((cycle - 0.58) / 0.42))
    impact = math.exp(-((cycle - 0.46) / 0.055) ** 2)
    return lunge, impact


def _work_impact(phase):
    cycle = (phase % 1.08) / 1.08
    return math.exp(-((cycle - 0.56) / 0.07) ** 2)


def _smoothstep(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def _ease_out_cubic(value):
    value = max(0.0, min(1.0, value))
    return 1.0 - (1.0 - value) ** 3


def _defender_patrol_position(
    territory,
    index,
    elapsed,
):
    gate_x, gate_y = territory.battle_position
    slot_angle = -math.pi * 0.82 + index * math.pi * 0.55
    patrol = math.sin(elapsed * 0.72 + index * 1.9) * 0.22
    angle = slot_angle + patrol
    radius = 38.0 + (index % 2) * 9.0
    return (
        (
            int(gate_x + math.cos(angle) * radius),
            int(gate_y + 12 + math.sin(angle) * radius * 0.48),
        ),
        0.86,
    )


def _wandering_position(territory, role, index, elapsed):
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

    # Keep patrols on dry ground and out of the castle footprint.
    castle = territory.battle_position
    castle_clearance = 48.0 if role == "queen" else 68.0
    for factor in (1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.3, 0.1):
        px = cx + (x - cx) * factor
        py = cy + (y - cy) * factor
        if (
            _point_in_polygon((px, py), polygon)
            and shared_nearest_river_distance((px, py), WANDERING_RIVER_PATHS)
            >= WANDERING_RIVER_CLEARANCE
            and math.dist((px, py), castle) >= castle_clearance
        ):
            return (int(px), int(py)), 1.0 if role == "queen" else 0.88 if role == "worker" else 0.82
    fallback_x = cx + (castle[0] - cx) * 0.35
    fallback_y = cy + (castle[1] - cy) * 0.35
    return (int(fallback_x), int(fallback_y)), 1.0


def _decor_point(territory, seed, spread_ratio):
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


def _specialization_site_candidates(territory):
    """Return stable interior building sites, ordered independently of rivers."""
    cx, cy = territory.centroid
    candidates = []

    # Walking partway toward multiple vertices keeps each site inside even for
    # irregular territories, while giving the renderer enough alternatives to
    # avoid riverbeds and the capital.
    for vx, vy in territory.polygon:
        for factor in (0.34, 0.48):
            px = cx + (vx - cx) * factor
            py = cy + (vy - cy) * factor
            if (
                48 <= px <= cfg.WINDOW_WIDTH - 48
                and 42 <= py <= cfg.WINDOW_HEIGHT - 42
                and _point_in_polygon((px, py), territory.polygon)
            ):
                candidates.append((px, py))
    return candidates


def _draw_popup_bg(
    screen,
    rect,
    color,
    radius = 6,
):
    shadow = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, 130), shadow.get_rect(), border_radius=radius)
    screen.blit(shadow, rect.move(0, 4))
    panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(panel, (22, 26, 31, 236), panel.get_rect(), border_radius=radius)
    screen.blit(panel, rect)
    pygame.draw.rect(screen, _brighten(color, 18), rect, 2, border_radius=radius)


def _draw_pill(screen, rect, fill, border):
    pill = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(pill, fill, pill.get_rect(), border_radius=rect.height // 2)
    screen.blit(pill, rect)
    pygame.draw.rect(screen, border, rect, 1, border_radius=rect.height // 2)


def _draw_star(screen, center, r, color):
    x, y = center
    pts = []
    for i in range(10):
        angle = -math.pi / 2 + i * math.tau / 10
        dist = r if i % 2 == 0 else r * 0.45
        pts.append((int(x + math.cos(angle) * dist), int(y + math.sin(angle) * dist)))
    pygame.draw.polygon(screen, color, pts)


def _shrink_polygon(polygon, amount):
    cx = sum(p[0] for p in polygon) / len(polygon)
    cy = sum(p[1] for p in polygon) / len(polygon)
    result = []
    for px, py in polygon:
        dx, dy = px - cx, py - cy
        dist = max(1.0, math.hypot(dx, dy))
        ratio = max(0.0, (dist - amount) / dist)
        result.append((cx + dx * ratio, cy + dy * ratio))
    return result


def _draw_grass(surface, base, elapsed):
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

def _draw_lake(surface, base, seed, elapsed):
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

def _draw_tree(surface, base, scale):
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

def _draw_bush(surface, base, scale):
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

def _draw_flower(surface, base, color, elapsed):
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

def _draw_rock(surface, base, scale):
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


def _point_in_polygon(point, polygon):
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


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _brighten(color, amount):
    return tuple(min(255, c + amount) for c in color)


def _darken(color, amount):
    return tuple(max(0, c - amount) for c in color)


def _format_time(seconds):
    total = int(seconds)
    return f"{total // 60}:{total % 60:02d}"


def _fit_text(font, text, max_width):
    if font.size(text)[0] <= max_width:
        return text
    clipped = text
    while clipped and font.size(clipped + "…")[0] > max_width:
        clipped = clipped[:-1]
    return clipped + "…" if clipped else "…"
