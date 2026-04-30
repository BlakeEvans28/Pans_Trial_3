"""
Audio for Pan's Trial.

Desktop builds use pygame's mixer. Web builds use browser-native HTML5 audio
so music playback does not depend on pygame's wasm codec support.
"""

from array import array
import math
import random
import sys
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
    WEB_MUSIC_TRACKS = {
        "intro": (
            "audio/Pan_Intro_Updated.mp3",
            "audio/Pan_Intro.mp3",
        ),
        "phase": (
            "audio/PanPhase1_Updated.mp3",
            "audio/PanPhase1.mp3",
        ),
    }
    WEB_SOUND_TRACKS = {
        "clash": "audio/clash.wav",
    }

    def __init__(self, allow_music_files: bool = True) -> None:
        self.is_web = sys.platform == "emscripten"
        self.enabled = False
        self.allow_music_files = allow_music_files
        self.volume = 0.5
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.current_music: str | None = None
        self.track_paths: dict[str, tuple[Path, ...]] = {}
        self.track_urls: dict[str, tuple[str, ...]] = {}
        self.last_error: str | None = None

        if self.is_web:
            self.track_urls = {
                name: tuple(candidates)
                for name, candidates in self.WEB_MUSIC_TRACKS.items()
            }
            self._ensure_web_ready()
        else:
            self._refresh_track_paths()
            self._ensure_desktop_ready()

    def _refresh_track_paths(self) -> None:
        """Re-scan disk so desktop audio can find the checked-in music files."""
        self.track_paths = {
            name: tuple(candidate for candidate in candidates if candidate.exists())
            for name, candidates in self.MUSIC_TRACKS.items()
        }

    def _get_web_audio_bridge(self):
        """Return the browser audio helper injected by the web loader."""
        try:
            import platform

            return getattr(platform.window, "panTrialAudio", None)
        except Exception:
            return None

    def _ensure_web_ready(self) -> bool:
        """Bind to the browser audio helper when running under wasm."""
        bridge = self._get_web_audio_bridge()
        if bridge is None:
            self.enabled = False
            return False

        try:
            bridge.setVolume(self.volume)
            self.enabled = True
            return True
        except Exception as exc:
            self.enabled = False
            self.last_error = f"Browser audio unavailable: {exc}"
            return False

    def _apply_desktop_volume(self) -> None:
        """Push the current volume level into loaded desktop sounds and music."""
        if not self.enabled:
            return

        for sound in self.sounds.values():
            sound.set_volume(self.volume)
        pygame.mixer.music.set_volume(self.volume * 0.55)

    def _ensure_desktop_ready(self) -> bool:
        """Initialize mixer-backed desktop audio, retrying later if needed."""
        if self.enabled and pygame.mixer.get_init() is not None:
            return True

        try:
            mixer_was_uninitialized = pygame.mixer.get_init() is None
            if mixer_was_uninitialized:
                pygame.mixer.init(frequency=self.SAMPLE_RATE, size=-16, channels=1, buffer=512)
            if mixer_was_uninitialized or not self.sounds:
                self._build_sounds()
            self._refresh_track_paths()
            self.enabled = True
            self._apply_desktop_volume()
            return True
        except pygame.error as exc:
            self.enabled = False
            self.last_error = f"Desktop audio unavailable: {exc}"
            return False

    def _build_sounds(self) -> None:
        """Create the single retained in-memory battle clash sound."""
        self.sounds = {
            "clash": self._make_clash(),
        }

    def set_volume(self, volume: float) -> None:
        """Apply user sound-volume setting to all active and future sounds."""
        self.volume = max(0.0, min(1.0, volume))
        if self.is_web:
            if not self._ensure_web_ready():
                return
            bridge = self._get_web_audio_bridge()
            if bridge is None:
                return
            try:
                bridge.setVolume(self.volume)
            except Exception as exc:
                self.enabled = False
                self.last_error = f"Browser audio volume update failed: {exc}"
            return

        if not self._ensure_desktop_ready():
            return
        self._apply_desktop_volume()

    def play_intro_music(self) -> None:
        """Loop the intro/drafting/victory music."""
        self._play_music("intro")

    def play_phase_music(self) -> None:
        """Loop the main phase music."""
        self._play_music("phase")

    def _play_music(self, track_name: str) -> None:
        """Switch to the requested looping music track if possible."""
        if not self.allow_music_files:
            return

        if self.is_web:
            self._play_web_music(track_name)
            return

        if not self._ensure_desktop_ready():
            return
        if self.current_music == track_name and pygame.mixer.music.get_busy():
            return

        paths = self.track_paths.get(track_name, ())
        if not paths:
            self._refresh_track_paths()
            paths = self.track_paths.get(track_name, ())
        if not paths:
            self.last_error = f"No audio files found for music track: {track_name}"
            return

        errors = []
        for path in paths:
            try:
                pygame.mixer.music.load(str(path))
                self._apply_desktop_volume()
                pygame.mixer.music.play(loops=-1, fade_ms=650)
                self.current_music = track_name
                self.last_error = None
                return
            except pygame.error as exc:
                errors.append(f"{path.name}: {exc}")

        self.current_music = None
        self.last_error = f"Unable to play {track_name} music. Tried " + "; ".join(errors)

    def _play_web_music(self, track_name: str) -> None:
        """Ask the browser helper to play one of the streamed music tracks."""
        if not self._ensure_web_ready():
            return
        if self.current_music == track_name:
            return

        urls = self.track_urls.get(track_name, ())
        bridge = self._get_web_audio_bridge()
        if not urls or bridge is None:
            return

        try:
            bridge.playMusic("\n".join(urls), self.volume)
            self.current_music = track_name
            self.last_error = None
        except Exception as exc:
            self.current_music = None
            self.enabled = False
            self.last_error = f"Browser music playback failed: {exc}"

    def stop_music(self) -> None:
        """Fade out any active music."""
        if self.is_web:
            bridge = self._get_web_audio_bridge()
            if bridge is not None:
                try:
                    bridge.stopMusic()
                except Exception as exc:
                    self.enabled = False
                    self.last_error = f"Browser music stop failed: {exc}"
            self.current_music = None
            return

        if self.enabled and pygame.mixer.get_init() is not None:
            pygame.mixer.music.fadeout(500)
        self.current_music = None

    def play_clash(self) -> None:
        """Play a metallic combat clash."""
        self._play("clash")

    def _play(self, sound_name: str) -> None:
        if self.volume <= 0:
            return

        if self.is_web:
            if not self._ensure_web_ready():
                return
            url = self.WEB_SOUND_TRACKS.get(sound_name)
            bridge = self._get_web_audio_bridge()
            if url is None or bridge is None:
                return
            try:
                bridge.playOneShot(url, self.volume)
            except Exception as exc:
                self.enabled = False
                self.last_error = f"Browser sound playback failed: {exc}"
            return

        if not self._ensure_desktop_ready():
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
