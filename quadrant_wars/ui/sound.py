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
            "objective_claim": (590, 0.58, "fanfare", 0.48),
            "objective_expire": (120, 0.34, "noise", 0.24),
            "win": (520, 0.72, "fanfare", 0.50),
        }
        for name, spec in specs.items():
            path = sound_dir / f"{name}.wav"
            if not path.exists():
                _write_sound(path, *spec)

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
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
        sound = self._sounds.get(name)
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
            else:
                value = math.sin(i * 12.9898) * math.sin(i * 78.233) * envelope
            packed = int(max(-1.0, min(1.0, value * volume)) * 32767)
            wav.writeframes(struct.pack("<h", packed))
