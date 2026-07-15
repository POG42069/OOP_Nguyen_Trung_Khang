from __future__ import annotations

from pathlib import Path

import pygame


IMAGE_DIR = Path(__file__).resolve().parents[1] / "assets" / "images"


class ArtAssets:
    """Loads generated artwork once and serves screen-sized/cropped variants."""

    def __init__(self, viewport: tuple[int, int]) -> None:
        self._viewport = viewport
        self._scaled_cache: dict[tuple[object, ...], pygame.Surface] = {}
        self._sources: dict[str, pygame.Surface] = {}
        self._animations: dict[tuple[str, str], list[pygame.Surface]] = {}
        self.battlefield = _load_cover(IMAGE_DIR / "battlefield.png", viewport)
        self.river_mask = _load_cover_alpha(IMAGE_DIR / "river_mask.png", viewport)

        for name in (
            "soldier",
            "defender",
            "worker",
            "queen",
            "fortress",
            "fortress_western",
            "fortress_northern",
            "fortress_forest",
            "fortress_sun",
        ):
            source = _load_alpha(IMAGE_DIR / f"{name}.png")
            if source is not None:
                bounds = source.get_bounding_rect(min_alpha=8)
                if bounds.width and bounds.height:
                    source = source.subsurface(bounds).copy()
                self._sources[name] = source

        action_names = {"soldier": "attack", "worker": "work", "queen": "attack"}
        for name, action in action_names.items():
            sheet = _load_alpha(IMAGE_DIR / f"{name}_animation.png")
            if sheet is None:
                continue
            frames = _extract_animation_frames(sheet)
            if len(frames) != 8:
                continue
            self._animations[(name, "idle")] = [frames[0]]
            self._animations[(name, "walk")] = frames[:4]
            self._animations[(name, action)] = frames[4:]

        for view_name, filename in (
            ("soldier", "soldier_combat_v2.png"),
            ("soldier_back", "soldier_combat_back_v2.png"),
            ("defender", "defender_combat_v1.png"),
            ("defender_back", "defender_combat_back_v1.png"),
        ):
            atlas = _load_alpha(IMAGE_DIR / filename)
            if atlas is None:
                continue
            actions = _extract_combat_atlas(atlas)
            required = {"idle": 4, "walk": 8, "attack": 8, "hit": 4, "death": 6}
            if any(len(actions.get(action, ())) != count for action, count in required.items()):
                continue
            for action, frames in actions.items():
                self._animations[(view_name, action)] = frames

    def sprite(self, name: str, target_height: int) -> pygame.Surface | None:
        source = self._sources.get(name)
        if source is None:
            return None
        target_height = max(8, int(target_height))
        key = (name, target_height)
        if key not in self._scaled_cache:
            width = max(1, round(source.get_width() * target_height / source.get_height()))
            self._scaled_cache[key] = pygame.transform.smoothscale(source, (width, target_height))
        return self._scaled_cache[key]

    def animation_count(
        self,
        name: str,
        action: str,
        direction: tuple[float, float] | None = None,
    ) -> int:
        resolved_name = self._directional_name(name, direction)
        return len(self._animations.get((resolved_name, action), ()))

    def animation_frame(
        self,
        name: str,
        action: str,
        frame_index: int,
        target_height: int,
        direction: tuple[float, float] | None = None,
    ) -> pygame.Surface | None:
        resolved_name = self._directional_name(name, direction)
        frames = self._animations.get((resolved_name, action))
        if not frames:
            return self.sprite(name, target_height)
        frame_index %= len(frames)
        target_height = max(8, int(target_height))
        key = ("animation", resolved_name, action, frame_index, target_height)
        if key not in self._scaled_cache:
            source = frames[frame_index]
            width = max(1, round(source.get_width() * target_height / source.get_height()))
            self._scaled_cache[key] = pygame.transform.smoothscale(source, (width, target_height))
        return self._scaled_cache[key]

    def _directional_name(
        self,
        name: str,
        direction: tuple[float, float] | None,
    ) -> str:
        if (
            name in ("soldier", "defender")
            and direction is not None
            and direction[1] < -0.18
            and (f"{name}_back", "idle") in self._animations
        ):
            return f"{name}_back"
        return name

    def building(self, name: str, target_width: int) -> pygame.Surface | None:
        source = self._sources.get(name)
        if source is None:
            return None
        target_width = max(16, int(target_width))
        target_height = max(1, round(source.get_height() * target_width / source.get_width()))
        key = (f"building:{name}", target_width)
        if key not in self._scaled_cache:
            self._scaled_cache[key] = pygame.transform.smoothscale(source, (target_width, target_height))
        return self._scaled_cache[key]


_MENU_CACHE: dict[tuple[int, int], pygame.Surface] = {}


def menu_background(viewport: tuple[int, int]) -> pygame.Surface | None:
    if viewport not in _MENU_CACHE:
        loaded = _load_cover(IMAGE_DIR / "menu_battlefield.png", viewport)
        if loaded is None:
            return None
        _MENU_CACHE[viewport] = loaded
    return _MENU_CACHE[viewport]


def _load_alpha(path: Path) -> pygame.Surface | None:
    try:
        return pygame.image.load(str(path)).convert_alpha()
    except (FileNotFoundError, pygame.error):
        return None


def _load_cover(path: Path, viewport: tuple[int, int]) -> pygame.Surface | None:
    try:
        source = pygame.image.load(str(path)).convert()
    except (FileNotFoundError, pygame.error):
        return None

    target_w, target_h = viewport
    scale = max(target_w / source.get_width(), target_h / source.get_height())
    scaled_size = (
        max(target_w, round(source.get_width() * scale)),
        max(target_h, round(source.get_height() * scale)),
    )
    scaled = pygame.transform.smoothscale(source, scaled_size)
    x = (scaled.get_width() - target_w) // 2
    y = (scaled.get_height() - target_h) // 2
    return scaled.subsurface((x, y, target_w, target_h)).copy()


def _load_cover_alpha(path: Path, viewport: tuple[int, int]) -> pygame.Surface | None:
    try:
        source = pygame.image.load(str(path)).convert_alpha()
    except (FileNotFoundError, pygame.error):
        return None

    target_w, target_h = viewport
    scale = max(target_w / source.get_width(), target_h / source.get_height())
    scaled_size = (
        max(target_w, round(source.get_width() * scale)),
        max(target_h, round(source.get_height() * scale)),
    )
    scaled = pygame.transform.smoothscale(source, scaled_size)
    x = (scaled.get_width() - target_w) // 2
    y = (scaled.get_height() - target_h) // 2
    return scaled.subsurface((x, y, target_w, target_h)).copy()


def _extract_animation_frames(sheet: pygame.Surface) -> list[pygame.Surface]:
    """Extract eight isolated poses and normalize them to a shared foot anchor."""
    mask = pygame.mask.from_surface(sheet, 16)
    components = mask.connected_components(500)
    poses: list[tuple[pygame.Rect, pygame.Surface]] = []
    for component in components:
        rects = component.get_bounding_rects()
        if not rects:
            continue
        rect = max(rects, key=lambda item: item.width * item.height)
        if rect.width * rect.height < 8_000:
            continue
        padded = rect.inflate(8, 8).clip(sheet.get_rect())
        poses.append((rect, sheet.subsurface(padded).copy()))

    if len(poses) != 8:
        return []
    half = sheet.get_height() / 2
    poses.sort(key=lambda item: (0 if item[0].centery < half else 1, item[0].centerx))

    max_width = max(frame.get_width() for _, frame in poses) + 12
    max_height = max(frame.get_height() for _, frame in poses) + 12
    normalized: list[pygame.Surface] = []
    for _, frame in poses:
        canvas = pygame.Surface((max_width, max_height), pygame.SRCALPHA)
        destination = frame.get_rect(midbottom=(max_width // 2, max_height - 4))
        canvas.blit(frame, destination)
        normalized.append(canvas)
    return normalized


def _extract_combat_atlas(sheet: pygame.Surface) -> dict[str, list[pygame.Surface]]:
    """Extract the fixed 8x4 v2 atlas into foot-anchored action frames."""
    columns = 8
    rows = 4
    if sheet.get_width() % columns or sheet.get_height() % rows:
        return {}
    cell_width = sheet.get_width() // columns
    cell_height = sheet.get_height() // rows

    layout = {
        "idle": (0, range(0, 4)),
        "hit": (0, range(4, 8)),
        "walk": (1, range(0, 8)),
        "attack": (2, range(0, 8)),
        "death": (3, range(0, 6)),
    }
    actions: dict[str, list[pygame.Surface]] = {}
    for action, (row, columns_for_action) in layout.items():
        cropped: list[pygame.Surface] = []
        for column in columns_for_action:
            cell_rect = pygame.Rect(
                column * cell_width,
                row * cell_height,
                cell_width,
                cell_height,
            )
            cell = sheet.subsurface(cell_rect)
            bounds = cell.get_bounding_rect(min_alpha=8)
            if not bounds.width or not bounds.height:
                return {}
            bounds = bounds.inflate(8, 8).clip(cell.get_rect())
            cropped.append(cell.subsurface(bounds).copy())

        max_width = max(frame.get_width() for frame in cropped) + 10
        max_height = max(frame.get_height() for frame in cropped) + 10
        normalized: list[pygame.Surface] = []
        for frame in cropped:
            canvas = pygame.Surface((max_width, max_height), pygame.SRCALPHA)
            canvas.blit(frame, frame.get_rect(midbottom=(max_width // 2, max_height - 4)))
            normalized.append(canvas)
        actions[action] = normalized
    return actions
