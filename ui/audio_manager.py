"""
Audio for Pan's Trial.

Only the combat clash is generated at runtime; music comes from checked-in
track files and fails quietly on machines without audio.
"""

from array import array
import math
import random
from pathlib import Path

import pygame


class AudioManager:
    """Owns the combat sound effect, title/game music, and volume control."""

    SAMPLE_RATE = 44100
    AUDIO_ROOT = Path(__file__).resolve().parent.parent / "audio"
    MUSIC_TRACKS = {
        "intro": (
            AUDIO_ROOT / "Pan_Intro_Updated.mp3",
            AUDIO_ROOT / "Pan_Intro.mp3",
        ),
        "phase": (
            AUDIO_ROOT / "PanPhase1_Updated.mp3",
            AUDIO_ROOT / "PanPhase1.mp3",
        ),
    }

    def __init__(self, allow_music_files: bool = True) -> None:
        self.enabled = False
        self.allow_music_files = allow_music_files
        self.volume = 0.5
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.current_music: str | None = None
        self.track_paths = {
            name: next((candidate for candidate in candidates if candidate.exists()), None)
            for name, candidates in self.MUSIC_TRACKS.items()
        }

        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=self.SAMPLE_RATE, size=-16, channels=1, buffer=512)
            self.enabled = True
            self._build_sounds()
            self.set_volume(self.volume)
        except pygame.error:
            self.enabled = False

    def _build_sounds(self) -> None:
        """Create the single retained in-memory battle clash sound."""
        self.sounds = {
            "clash": self._make_clash(),
        }

    def set_volume(self, volume: float) -> None:
        """Apply user sound-volume setting to all active and future sounds."""
        self.volume = max(0.0, min(1.0, volume))
        if not self.enabled:
            return

        for sound in self.sounds.values():
            sound.set_volume(self.volume)
        pygame.mixer.music.set_volume(self.volume * 0.55)

    def play_intro_music(self) -> None:
        """Loop the intro/drafting/victory music."""
        self._play_music("intro")

    def play_phase_music(self) -> None:
        """Loop the main phase music."""
        self._play_music("phase")

    def _play_music(self, track_name: str) -> None:
        """Switch to the requested looping music track if possible."""
        if not self.enabled or not self.allow_music_files:
            return
        if self.current_music == track_name and pygame.mixer.music.get_busy():
            return

        path = self.track_paths.get(track_name)
        if path is None:
            return

        try:
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.set_volume(self.volume * 0.55)
            pygame.mixer.music.play(loops=-1, fade_ms=650)
            self.current_music = track_name
        except pygame.error:
            self.current_music = None

    def stop_music(self) -> None:
        """Fade out any active music."""
        if self.enabled:
            pygame.mixer.music.fadeout(500)
        self.current_music = None

    def play_clash(self) -> None:
        """Play a metallic combat clash."""
        self._play("clash")

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
