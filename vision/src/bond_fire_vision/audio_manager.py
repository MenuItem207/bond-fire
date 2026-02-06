"""Audio manager for Bondfire installation.

Non-blocking audio playback for SFX, music, and optional TTS narration.
"""

from __future__ import annotations

import os
import queue
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

try:
    import pygame.mixer as mixer

    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    mixer = None

try:
    import pyttsx3

    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    pyttsx3 = None


class AudioChannel(Enum):
    """Audio playback channels."""

    MUSIC = "music"
    SFX_PRIMARY = "sfx_primary"
    SFX_SECONDARY = "sfx_secondary"
    NARRATION = "narration"


class AudioState(Enum):
    """High-level audio states."""

    SILENT = "SILENT"
    AMBIENT = "AMBIENT"
    PARTY = "PARTY"
    ALERT = "ALERT"


@dataclass
class AudioCommand:
    """Command for audio worker thread."""

    action: str  # "play", "stop", "set_volume", "set_state"
    channel: Optional[AudioChannel] = None
    asset_name: Optional[str] = None
    loop: bool = False
    volume: float = 1.0
    state: Optional[AudioState] = None


class AudioManager:
    """
    Manages audio playback for the installation.

    Uses pygame.mixer for sound effects and music, with optional pyttsx3
    for text-to-speech narration. Runs in a background thread to avoid
    blocking the main vision loop.
    """

    # Default asset paths (relative to vision/assets/)
    ASSETS_DIR = Path(__file__).parent.parent / "assets"
    SFX_DIR = ASSETS_DIR / "sfx"
    MUSIC_DIR = ASSETS_DIR / "music"

    # Asset mappings
    ASSET_MAP = {
        "fire_crackle": "sfx/fire_crackle_loop.mp3",
        "whoosh": "sfx/whoosh_entry.mp3",
        "buzzer": "sfx/buzzer_alert.mp3",
        "party_horn": "sfx/party_horn.mp3",
        "chime": "sfx/soft_chime.mp3",
        "buildup_start": "sfx/buildup_start.mp3",  # Low tone to signal build-up beginning
        "buildup_pulse": "sfx/buildup_pulse.mp3",  # Pulsing tone during build-up
        "supernova": "sfx/supernova_burst.mp3",  # Explosion sound when party starts
        "ambient_music": "music/ambient_chill.mp3",
        "party_music": "music/party_upbeat.mp3",
    }

    def __init__(
        self,
        enabled: bool = True,
        master_volume: float = 0.7,
        narration_enabled: bool = False,
        assets_dir: Optional[Path] = None,
    ) -> None:
        """
        Initialize audio manager.

        Args:
            enabled: Enable audio subsystem
            master_volume: Master volume (0.0-1.0)
            narration_enabled: Enable TTS narration
            assets_dir: Override default assets directory
        """
        self.enabled = enabled and PYGAME_AVAILABLE
        self.master_volume = max(0.0, min(1.0, master_volume))
        self.narration_enabled = narration_enabled and TTS_AVAILABLE

        if assets_dir:
            self.assets_dir = Path(assets_dir)
        else:
            self.assets_dir = self.ASSETS_DIR

        self._queue: queue.Queue[AudioCommand] = queue.Queue(maxsize=20)
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._started = False

        # State tracking
        self._current_state = AudioState.SILENT
        self._loaded_sounds: dict[str, any] = {}
        self._music_channel: Optional[any] = None
        self._sfx_channels: dict[AudioChannel, any] = {}

        # TTS engine
        self._tts_engine: Optional[any] = None

        if not self.enabled:
            print("Audio disabled: pygame.mixer not available.", flush=True)

    def start(self) -> None:
        """Start the audio worker thread."""
        if not self.enabled or self._started:
            return

        try:
            # Initialize pygame mixer
            mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            mixer.set_num_channels(8)  # Ensure enough channels

            # Initialize TTS if enabled
            if self.narration_enabled and TTS_AVAILABLE:
                self._tts_engine = pyttsx3.init()
                self._tts_engine.setProperty("rate", 150)  # Speed
                self._tts_engine.setProperty("volume", self.master_volume)

            # Start worker thread
            self._thread = threading.Thread(target=self._worker, name="audio-worker", daemon=True)
            self._thread.start()
            self._started = True

            print(f"Audio system started (volume={self.master_volume:.1f}).", flush=True)
            if self.narration_enabled:
                print("TTS narration enabled.", flush=True)

        except Exception as exc:
            print(f"Audio initialization failed: {exc}", flush=True)
            self.enabled = False

    def stop(self) -> None:
        """Stop the audio worker thread and cleanup."""
        if not self._started:
            return

        self._stop_event.set()
        if self._thread is not None:
            try:
                self._queue.put_nowait(AudioCommand(action="stop"))
            except queue.Full:
                pass
            self._thread.join(timeout=2.0)

        if self.enabled and mixer:
            mixer.quit()

        self._started = False

    def play_sfx(self, asset_name: str, volume: float = 1.0) -> None:
        """
        Play a sound effect (non-blocking).

        Args:
            asset_name: Name of the SFX asset (e.g., "whoosh", "buzzer")
            volume: Volume override (0.0-1.0)
        """
        if not self.enabled:
            return

        try:
            self._queue.put_nowait(
                AudioCommand(
                    action="play",
                    channel=AudioChannel.SFX_PRIMARY,
                    asset_name=asset_name,
                    volume=volume,
                )
            )
        except queue.Full:
            pass  # Drop if queue full

    def play_music(self, asset_name: str, loop: bool = True, volume: float = 0.7) -> None:
        """
        Play background music (non-blocking).

        Args:
            asset_name: Name of the music asset (e.g., "ambient_music")
            loop: Loop the music track
            volume: Volume override (0.0-1.0)
        """
        if not self.enabled:
            return

        try:
            self._queue.put_nowait(
                AudioCommand(
                    action="play",
                    channel=AudioChannel.MUSIC,
                    asset_name=asset_name,
                    loop=loop,
                    volume=volume,
                )
            )
        except queue.Full:
            pass

    def stop_music(self) -> None:
        """Stop currently playing music."""
        if not self.enabled:
            return

        try:
            self._queue.put_nowait(AudioCommand(action="stop", channel=AudioChannel.MUSIC))
        except queue.Full:
            pass

    def speak(self, text: str) -> None:
        """
        Speak text using TTS (non-blocking).

        Args:
            text: Text to speak
        """
        if not self.enabled or not self.narration_enabled:
            return

        try:
            self._queue.put_nowait(
                AudioCommand(action="play", channel=AudioChannel.NARRATION, asset_name=text)
            )
        except queue.Full:
            pass

    def set_state(self, state: AudioState) -> None:
        """
        Set the high-level audio state, triggering appropriate music/SFX.

        Args:
            state: Target audio state
        """
        if not self.enabled:
            return

        try:
            self._queue.put_nowait(AudioCommand(action="set_state", state=state))
        except queue.Full:
            pass

    def _worker(self) -> None:
        """Background worker thread for audio playback."""
        while not self._stop_event.is_set():
            try:
                cmd = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                if cmd.action == "play":
                    self._handle_play(cmd)
                elif cmd.action == "stop":
                    self._handle_stop(cmd)
                elif cmd.action == "set_state":
                    self._handle_state_change(cmd)
            except Exception as exc:
                print(f"Audio worker error: {exc}", flush=True)
            finally:
                self._queue.task_done()

    def _handle_play(self, cmd: AudioCommand) -> None:
        """Handle play command."""
        if cmd.channel == AudioChannel.NARRATION and self._tts_engine:
            # TTS narration
            try:
                self._tts_engine.say(cmd.asset_name)
                self._tts_engine.runAndWait()
            except Exception as exc:
                print(f"TTS error: {exc}", flush=True)
            return

        # Load sound if not cached
        if cmd.asset_name not in self._loaded_sounds:
            asset_path = self.assets_dir / self.ASSET_MAP.get(cmd.asset_name, cmd.asset_name)
            if not asset_path.exists():
                print(f"Audio asset not found: {asset_path}", flush=True)
                return

            try:
                self._loaded_sounds[cmd.asset_name] = mixer.Sound(str(asset_path))
            except Exception as exc:
                print(f"Failed to load {asset_path}: {exc}", flush=True)
                return

        sound = self._loaded_sounds[cmd.asset_name]
        volume = cmd.volume * self.master_volume

        if cmd.channel == AudioChannel.MUSIC:
            # Use mixer.music for background tracks
            asset_path = self.assets_dir / self.ASSET_MAP.get(cmd.asset_name, cmd.asset_name)
            try:
                mixer.music.load(str(asset_path))
                mixer.music.set_volume(volume)
                mixer.music.play(loops=-1 if cmd.loop else 0)
            except Exception as exc:
                print(f"Music playback error: {exc}", flush=True)
        else:
            # Use channels for SFX
            sound.set_volume(volume)
            if cmd.loop:
                sound.play(loops=-1)
            else:
                sound.play()

    def _handle_stop(self, cmd: AudioCommand) -> None:
        """Handle stop command."""
        if cmd.channel == AudioChannel.MUSIC:
            mixer.music.stop()
        elif cmd.channel in self._sfx_channels:
            channel = self._sfx_channels[cmd.channel]
            if channel:
                channel.stop()

    def _handle_state_change(self, cmd: AudioCommand) -> None:
        """Handle high-level state change."""
        if cmd.state == self._current_state:
            return

        self._current_state = cmd.state

        if cmd.state == AudioState.SILENT:
            mixer.music.stop()
        elif cmd.state == AudioState.AMBIENT:
            self.play_music("ambient_music", loop=True, volume=0.5)
            self.play_sfx("fire_crackle", volume=0.3)
        elif cmd.state == AudioState.PARTY:
            self.play_music("party_music", loop=True, volume=0.8)
            self.play_sfx("party_horn", volume=1.0)
        elif cmd.state == AudioState.ALERT:
            mixer.music.stop()
            self.play_sfx("buzzer", volume=0.8)


def create_placeholder_assets(assets_dir: Path) -> None:
    """
    Create placeholder audio asset structure.

    This is a helper for development when actual audio files are not available.
    Creates empty directories and a README explaining the required assets.
    """
    sfx_dir = assets_dir / "sfx"
    music_dir = assets_dir / "music"

    sfx_dir.mkdir(parents=True, exist_ok=True)
    music_dir.mkdir(parents=True, exist_ok=True)

    readme = assets_dir / "README.md"
    if not readme.exists():
        readme.write_text(
            """# Bondfire Audio Assets

## Required Files

### SFX (vision/assets/sfx/)
- `fire_crackle_loop.mp3` - 30s looping fire crackle (volume scales 0.2-1.0)
- `whoosh_entry.mp3` - 1s whoosh sound for person entry
- `buzzer_alert.mp3` - 0.5s buzzer for phone detection
- `party_horn.mp3` - 2s party horn for party mode entry
- `soft_chime.mp3` - Short chime for 15s color pulse

### Music (vision/assets/music/)
- `ambient_chill.mp3` - 3min looping ambient track for FIRE mode
- `party_upbeat.mp3` - 3min looping upbeat track for PARTY mode

## Sources
- Free SFX: freesound.org, zapsplat.com
- Free Music: incompetech.com, bensound.com
- TTS: Built-in (pyttsx3)

## Testing Without Assets
The audio manager will gracefully degrade if files are missing.
"""
        )

    print(f"Created audio asset structure at {assets_dir}", flush=True)
