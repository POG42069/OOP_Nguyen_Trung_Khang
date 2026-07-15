from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

import pygame


class SoundManager:
    def __init__(self) -> None:
        self._enabled = False
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        sound_dir = Path(__file__).resolve().parents[1] / "assets" / "sounds"
        sound_dir.mkdir(parents=True, exist_ok=True)
        specs = {
            "click": (420, 0.055, "square", 0.22),
            "recruit": (660, 0.12, "bell", 0.28),
            "attack": (190, 0.20, "drop", 0.35),
            "combat_defend": (115, 0.36, "noise", 0.44),
            "combat_win": (260, 0.42, "rise", 0.48),
            "develop": (520, 0.19, "bell", 0.30),
            "objective_warning": (310, 0.46, "rise", 0.38),
            "objective_ready": (430, 0.30, "bell", 0.42),
            "objective_contest": (145, 0.25, "drop", 0.38),
            "objective_clash": (125, 0.34, "clang", 0.44),
            "objective_claim": (590, 0.58, "fanfare", 0.48),
            "battle_reinforce": (330, 0.18, "rise", 0.28),
            "fortress_alarm": (176, 0.42, "fanfare", 0.34),
            "spear_thrust": (325, 0.11, "sweep", 0.22),
            "defender_down": (82, 0.22, "drop", 0.21),
            "page_turn": (470, 0.07, "sweep", 0.16),
            "countdown": (540, 0.09, "bell", 0.20),
            "battle_start": (310, 0.28, "fanfare", 0.36),
            "footstep_1": (72, 0.075, "thud", 0.22),
            "footstep_2": (84, 0.068, "thud", 0.19),
            "footstep_3": (64, 0.083, "thud", 0.20),
            "sword_swing_1": (420, 0.095, "sweep", 0.23),
            "sword_swing_2": (510, 0.082, "sweep", 0.20),
            "sword_swing_3": (360, 0.105, "sweep", 0.22),
            "metal_hit_1": (680, 0.105, "clang", 0.26),
            "metal_hit_2": (790, 0.092, "clang", 0.23),
            "shield_hit": (215, 0.13, "clang", 0.28),
            "stone_hit_1": (92, 0.16, "thud", 0.30),
            "stone_hit_2": (115, 0.14, "thud", 0.26),
            "soldier_down_1": (108, 0.17, "drop", 0.20),
            "soldier_down_2": (94, 0.19, "drop", 0.18),
            "win": (520, 0.72, "fanfare", 0.50),
        }
        self._variants = {
            "footstep": ("footstep_1", "footstep_2", "footstep_3"),
            "sword_swing": ("sword_swing_1", "sword_swing_2", "sword_swing_3"),
            "metal_hit": ("metal_hit_1", "metal_hit_2"),
            "stone_hit": ("stone_hit_1", "stone_hit_2"),
            "soldier_down": ("soldier_down_1", "soldier_down_2"),
        }
        self._variant_index: dict[str, int] = {}
        self._last_played: dict[str, int] = {}
        self._cooldowns_ms = {
            "footstep": 85,
            "sword_swing": 55,
            "metal_hit": 55,
            "shield_hit": 90,
            "stone_hit": 75,
            "soldier_down": 105,
            "spear_thrust": 65,
            "defender_down": 120,
            "fortress_alarm": 500,
            "objective_clash": 220,
        }
        for name, spec in specs.items():
            path = sound_dir / f"{name}.wav"
            if not path.exists():
                _write_sound(path, *spec)

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.set_num_channels(24)
            self._enabled = True
        except pygame.error:
            self._enabled = False
            return

        for name in specs:
            path = sound_dir / f"{name}.wav"
            self._sounds[name] = pygame.mixer.Sound(str(path))

    def play(self, name: str) -> None:
        if not self._enabled:
            return
        now = pygame.time.get_ticks()
        cooldown = self._cooldowns_ms.get(name, 0)
        if now - self._last_played.get(name, -100000) < cooldown:
            return
        self._last_played[name] = now
        variants = self._variants.get(name)
        sound_name = name
        if variants:
            index = self._variant_index.get(name, 0)
            sound_name = variants[index % len(variants)]
            self._variant_index[name] = index + 1
        sound = self._sounds.get(sound_name)
        if sound is not None:
            sound.play()

    def play_many(self, names: list[str]) -> None:
        for name in names:
            self.play(name)


def _write_sound(path: Path, frequency: int, duration: float, wave_type: str, volume: float) -> None:
    sample_rate = 44100
    samples = int(sample_rate * duration)
    with wave.open(str(path), "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        for i in range(samples):
            t = i / sample_rate
            envelope = max(0.0, 1.0 - i / samples)
            if wave_type == "square":
                value = 1.0 if math.sin(math.tau * frequency * t) >= 0 else -1.0
            elif wave_type == "bell":
                value = (
                    math.sin(math.tau * frequency * t)
                    + 0.45 * math.sin(math.tau * frequency * 1.5 * t)
                ) * envelope
            elif wave_type == "drop":
                f = frequency + 260 * envelope
                value = math.sin(math.tau * f * t) * envelope
            elif wave_type == "rise":
                f = frequency + 280 * (1.0 - envelope)
                value = math.sin(math.tau * f * t) * envelope
            elif wave_type == "fanfare":
                f = frequency * (1.0 if t < duration * 0.33 else 1.25 if t < duration * 0.66 else 1.5)
                value = math.sin(math.tau * f * t) * envelope
            elif wave_type == "thud":
                value = (
                    math.sin(math.tau * frequency * t) * 0.72
                    + math.sin(i * 0.731) * 0.28
                ) * envelope * envelope
            elif wave_type == "sweep":
                f = frequency * (1.8 - 1.15 * (i / max(1, samples)))
                value = math.sin(math.tau * f * t) * envelope
            elif wave_type == "clang":
                value = (
                    math.sin(math.tau * frequency * t)
                    + 0.55 * math.sin(math.tau * frequency * 2.13 * t)
                    + 0.24 * math.sin(math.tau * frequency * 3.91 * t)
                ) * envelope
            else:
                value = math.sin(i * 12.9898) * math.sin(i * 78.233) * envelope
            packed = int(max(-1.0, min(1.0, value * volume)) * 32767)
            wav.writeframes(struct.pack("<h", packed))
