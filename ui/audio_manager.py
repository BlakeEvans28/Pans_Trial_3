"""
Generated audio for Pan's Trial.

The game currently has no checked-in sound files, so this creates lightweight
original effects at runtime and fails quietly on machines without audio.
"""

from array import array
import math
import random

import pygame


class AudioManager:
    """Owns generated sound effects, ambient music, and volume control."""

    SAMPLE_RATE = 44100

    def __init__(self) -> None:
        self.enabled = False
        self.volume = 0.5
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.ambient: pygame.mixer.Sound | None = None
        self.ambient_channel: pygame.mixer.Channel | None = None

        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=self.SAMPLE_RATE, size=-16, channels=1, buffer=512)
            self.enabled = True
            self._build_sounds()
            self.set_volume(self.volume)
        except pygame.error:
            self.enabled = False

    def _build_sounds(self) -> None:
        """Create original in-memory sounds for the current session."""
        self.sounds = {
            "clash": self._make_clash(),
            "trap": self._make_trap_hit(),
        }
        self.ambient = self._make_ambient_loop()

    def set_volume(self, volume: float) -> None:
        """Apply user sound-volume setting to all active and future sounds."""
        self.volume = max(0.0, min(1.0, volume))
        if not self.enabled:
            return

        for sound in self.sounds.values():
            sound.set_volume(self.volume)
        if self.ambient is not None:
            self.ambient.set_volume(self.volume * 0.32)
        if self.ambient_channel is not None:
            self.ambient_channel.set_volume(self.volume * 0.32)
            if self.volume <= 0:
                self.ambient_channel.stop()
                self.ambient_channel = None

    def start_ambient(self) -> None:
        """Start calm spooky labyrinth music if audio is available."""
        if not self.enabled or self.volume <= 0 or self.ambient is None:
            return
        if self.ambient_channel is not None and self.ambient_channel.get_busy():
            return
        self.ambient_channel = self.ambient.play(loops=-1, fade_ms=650)
        if self.ambient_channel is not None:
            self.ambient_channel.set_volume(self.volume * 0.32)

    def stop_ambient(self) -> None:
        """Fade out the ambient loop."""
        if self.ambient_channel is not None:
            self.ambient_channel.fadeout(500)
            self.ambient_channel = None

    def play_clash(self) -> None:
        """Play a metallic combat clash."""
        self._play("clash")

    def play_trap(self) -> None:
        """Play an original low trap-hit grunt."""
        self._play("trap")

    def _play(self, sound_name: str) -> None:
        if not self.enabled or self.volume <= 0:
            return
        sound = self.sounds.get(sound_name)
        if sound is not None:
            sound.play()

    def _sound_from_samples(self, samples: list[float]) -> pygame.mixer.Sound:
        clipped = array("h", (max(-32767, min(32767, int(sample * 32767))) for sample in samples))
        return pygame.mixer.Sound(buffer=clipped.tobytes())

    def _make_clash(self) -> pygame.mixer.Sound:
        """Create a short sword-and-shield style impact."""
        rng = random.Random(27)
        total = int(self.SAMPLE_RATE * 0.45)
        samples = []
        for i in range(total):
            t = i / self.SAMPLE_RATE
            envelope = math.exp(-t * 7.5)
            ring = (
                math.sin(2 * math.pi * 1450 * t)
                + 0.55 * math.sin(2 * math.pi * 2320 * t)
                + 0.35 * math.sin(2 * math.pi * 3170 * t)
            )
            hit_noise = rng.uniform(-1.0, 1.0) * math.exp(-t * 22)
            samples.append((0.25 * ring + 0.75 * hit_noise) * envelope * 0.7)
        return self._sound_from_samples(samples)

    def _make_trap_hit(self) -> pygame.mixer.Sound:
        """Create a low original 'oof-like' trap impact without using external audio."""
        total = int(self.SAMPLE_RATE * 0.58)
        samples = []
        for i in range(total):
            t = i / self.SAMPLE_RATE
            progress = i / total
            freq = 170 - 72 * progress
            envelope = min(1.0, t * 28) * math.exp(-t * 4.2)
            voice = math.sin(2 * math.pi * freq * t) + 0.45 * math.sin(2 * math.pi * freq * 2 * t)
            thump = math.sin(2 * math.pi * 58 * t) * math.exp(-t * 13)
            samples.append((0.55 * voice + 0.45 * thump) * envelope * 0.72)
        return self._sound_from_samples(samples)

    def _make_ambient_loop(self) -> pygame.mixer.Sound:
        """Create a calm, spooky drone loop for labyrinth exploration."""
        rng = random.Random(11)
        total = int(self.SAMPLE_RATE * 7.5)
        samples = []
        for i in range(total):
            t = i / self.SAMPLE_RATE
            fade = min(1.0, i / (self.SAMPLE_RATE * 0.8), (total - i) / (self.SAMPLE_RATE * 0.8))
            slow = 0.55 + 0.45 * math.sin(2 * math.pi * 0.08 * t)
            drone = (
                0.48 * math.sin(2 * math.pi * 73 * t)
                + 0.32 * math.sin(2 * math.pi * 109 * t + 0.9)
                + 0.2 * math.sin(2 * math.pi * 146 * t + 1.7)
            )
            air = rng.uniform(-1.0, 1.0) * 0.025
            samples.append((drone * slow + air) * fade * 0.42)
        return self._sound_from_samples(samples)
