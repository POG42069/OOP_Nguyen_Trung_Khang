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

    def animation_count(self, name: str, action: str) -> int:
        return len(self._animations.get((name, action), ()))

    def animation_frame(
        self,
        name: str,
        action: str,
        frame_index: int,
        target_height: int,
    ) -> pygame.Surface | None:
        frames = self._animations.get((name, action))
        if not frames:
            return self.sprite(name, target_height)
        frame_index %= len(frames)
        target_height = max(8, int(target_height))
        key = ("animation", name, action, frame_index, target_height)
        if key not in self._scaled_cache:
            source = frames[frame_index]
            width = max(1, round(source.get_width() * target_height / source.get_height()))
            self._scaled_cache[key] = pygame.transform.smoothscale(source, (width, target_height))
        return self._scaled_cache[key]

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
