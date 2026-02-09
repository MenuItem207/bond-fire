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

from .config import get_config

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
    SFX_AMBIENT = "sfx_ambient"
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
    ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets"
    SFX_DIR = ASSETS_DIR / "sfx"
    MUSIC_DIR = ASSETS_DIR / "music"

    # Asset mappings
    ASSET_MAP = {
        "fire_crackle": "sfx/fire_crackle_loop.wav",
        "whoosh": "sfx/whoosh_entry.wav",
        "buzzer": "sfx/buzzer_alert.wav",
        "party_horn": "sfx/party_horn.wav",
        "chime": "sfx/soft_chime.wav",
        "buildup_start": "sfx/buildup_start.wav",  # Low tone to signal build-up beginning
        "buildup_pulse": "sfx/buildup_pulse.wav",  # Pulsing tone during build-up
        "supernova": "sfx/supernova_burst.wav",  # Explosion sound when party starts
        "party_music": "music/party_upbeat.wav",
        "party_layer": "music/party_layer.wav",
    }

    def __init__(
        self,
        enabled: bool = True,
        master_volume: Optional[float] = None,
        narration_enabled: bool = False,
        assets_dir: Optional[Path] = None,
        tts_voice: Optional[str] = None,
    ) -> None:
        """
        Initialize audio manager.

        Args:
            enabled: Enable audio subsystem
            master_volume: Master volume (0.0-1.0). If None, uses config value
            narration_enabled: Enable TTS narration
            assets_dir: Override default assets directory
            tts_voice: TTS voice to use ("male", "female", or specific voice name)
                      Default: Auto-selects deep male voice
        """
        # Load config
        cfg = get_config()
        
        self.enabled = enabled and PYGAME_AVAILABLE
        # Use provided master_volume or fall back to config
        if master_volume is None:
            master_volume = cfg.audio.master_volume
        self.master_volume = max(0.0, min(1.0, master_volume))
        self.sfx_volume = max(0.0, min(1.0, cfg.audio.sfx_volume))
        self.music_volume = max(0.0, min(1.0, cfg.audio.music_volume))
        self.narration_enabled = narration_enabled and TTS_AVAILABLE
        self.tts_voice = tts_voice

        if assets_dir:
            self.assets_dir = Path(assets_dir)
        else:
            self.assets_dir = self.ASSETS_DIR

        self._queue: queue.Queue[AudioCommand] = queue.Queue(maxsize=cfg.audio.audio_queue_size)
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._started = False

        # State tracking
        self._current_state = AudioState.SILENT
        self._fire_intensity = 0.0  # 0.0-1.0, scales background fire crackle volume
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

            # Reserve channels for consistent mixing
            self._sfx_channels = {
                AudioChannel.SFX_AMBIENT: mixer.Channel(0),
                AudioChannel.SFX_PRIMARY: mixer.Channel(1),
                AudioChannel.SFX_SECONDARY: mixer.Channel(2),
            }

            # Initialize TTS if enabled
            if self.narration_enabled and TTS_AVAILABLE:
                cfg = get_config()
                self._tts_engine = pyttsx3.init()
                self._tts_engine.setProperty("rate", cfg.audio.tts.speech_rate)  # Speech speed from config
                self._tts_engine.setProperty("volume", self.master_volume)
                self._configure_tts_voice()

            # Create placeholder assets directory if missing
            if not self.assets_dir.exists():
                create_placeholder_assets(self.assets_dir)

            # Start worker thread
            self._thread = threading.Thread(target=self._worker, name="audio-worker", daemon=True)
            self._thread.start()
            self._started = True

            # Validate assets and warn about missing files
            self._validate_assets()

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

    def _validate_assets(self) -> None:
        """Check for missing audio assets and print warnings."""
        missing_assets = []
        for asset_name, relative_path in self.ASSET_MAP.items():
            asset_path = self.assets_dir / relative_path
            if not asset_path.exists():
                missing_assets.append((asset_name, asset_path))
        
        if missing_assets:
            print("\n⚠️  WARNING: Missing audio assets:", flush=True)
            for asset_name, path in missing_assets:
                print(f"  - {asset_name}: {path}", flush=True)
            print(f"\nExpected assets directory: {self.assets_dir}", flush=True)
            print("See AUDIO_ASSETS.md for complete asset list and setup instructions.\n", flush=True)

    def get_available_voices(self) -> list[str]:
        """Get list of available TTS voices."""
        if not TTS_AVAILABLE:
            return []
        try:
            engine = pyttsx3.init()
            voices = engine.getProperty("voices")
            return [voice.name for voice in voices]
        except Exception:
            return []

    def _configure_tts_voice(self) -> None:
        """Configure TTS voice with preference for deep narrator voice."""
        if not self._tts_engine:
            return
        
        try:
            voices = self._tts_engine.getProperty("voices")
            if not voices:
                print("⚠️  Warning: No TTS voices available", flush=True)
                return
            
            selected_voice = None
            
            # If user specified a voice, try to find it
            if self.tts_voice:
                if self.tts_voice.lower() == "male":
                    # Find best male voice
                    preferred = ["david", "alex", "john", "james", "google uk english male"]
                    for pref in preferred:
                        for voice in voices:
                            if pref in voice.name.lower():
                                selected_voice = voice
                                break
                        if selected_voice:
                            break
                elif self.tts_voice.lower() == "female":
                    # Find best female voice
                    preferred = ["victoria", "samantha", "moira", "fiona", "google uk english female"]
                    for pref in preferred:
                        for voice in voices:
                            if pref in voice.name.lower():
                                selected_voice = voice
                                break
                        if selected_voice:
                            break
                else:
                    # Try to find voice by ID or name substring
                    for voice in voices:
                        if self.tts_voice.lower() in voice.id.lower() or self.tts_voice.lower() in voice.name.lower():
                            selected_voice = voice
                            break
            
            # Default: Auto-select best deep male narrator voice (avoid "Albert")
            if not selected_voice:
                # Tier 1: Preferred professional/deep narrator voices
                preferred_names = [
                    "daniel",  # Professional British English (best narrator voice)
                    "grandpa",  # Deeper/mature tone
                    "rocko",   # High-quality eloquence
                    "reed",    # Eloquence line
                    "david", "alex", "john", "james", "google uk english male", "microsoft"
                ]
                for pref in preferred_names:
                    for voice in voices:
                        voice_name = voice.name.lower()
                        if pref in voice_name and "albert" not in voice_name:
                            selected_voice = voice
                            break
                    if selected_voice:
                        break
                
                # Tier 2: Any male voice
                if not selected_voice:
                    for voice in voices:
                        if "male" in voice.name.lower() and "albert" not in voice.name.lower():
                            selected_voice = voice
                            break
                
                # Tier 3: First available voice
                if not selected_voice:
                    selected_voice = voices[0]
            
            if selected_voice:
                self._tts_engine.setProperty("voice", selected_voice.id)
                print(f"TTS voice: {selected_voice.name}", flush=True)
        
        except Exception as exc:
            print(f"TTS voice configuration error: {exc}", flush=True)

    def play_sfx(
        self,
        asset_name: str,
        volume: float = 1.0,
        loop: bool = False,
        channel: AudioChannel = AudioChannel.SFX_PRIMARY,
    ) -> None:
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
                    channel=channel,
                    asset_name=asset_name,
                    loop=loop,
                    volume=volume,
                )
            )
        except queue.Full:
            print(f"⚠️  Audio queue full, dropping SFX: {asset_name}", flush=True)

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
            print(f"⚠️  Audio queue full, dropping narration", flush=True)

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

    def set_fire_intensity(self, intensity: float) -> None:
        """Set fire intensity for AMBIENT state background audio scaling.

        Args:
            intensity: Fire intensity 0.0-1.0, scales crackle volume
        """
        if not self.enabled:
            return

        intensity = max(0.0, min(1.0, intensity))
        self._fire_intensity = intensity
        
        # If in AMBIENT state, update the fire crackle volume immediately
        if self._current_state == AudioState.AMBIENT:
            volume = 0.18 + (intensity * 0.42)  # Maps 0.0-1.0 to 0.18-0.6 volume
            try:
                # Queue a volume update for the fire crackle SFX
                self._queue.put_nowait(
                    AudioCommand(
                        action="set_volume",
                        channel=AudioChannel.SFX_AMBIENT,
                        volume=volume,
                    )
                )
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
                elif cmd.action == "set_volume":
                    self._handle_set_volume(cmd)
            except Exception as exc:
                print(f"Audio worker error: {exc}", flush=True)
            finally:
                self._queue.task_done()

    def _handle_play(self, cmd: AudioCommand) -> None:
        """Handle play command."""
        if cmd.channel == AudioChannel.NARRATION:
            # TTS narration - use fresh engine instance for each utterance to avoid blocking
            if not TTS_AVAILABLE:
                return
            
            try:
                # Create a fresh TTS engine for this utterance
                # This prevents the engine from getting stuck after multiple calls
                tts = pyttsx3.init()
                tts.setProperty("rate", 150)  # Speech speed
                tts.setProperty("volume", self.master_volume)
                
                # Apply saved voice preference if available
                if self._tts_engine:
                    try:
                        current_voice = self._tts_engine.getProperty("voice")
                        tts.setProperty("voice", current_voice)
                    except Exception:
                        pass  # Voice not available in fresh instance
                
                # Speak and wait for completion
                tts.say(cmd.asset_name)
                tts.runAndWait()
                
                # Clean up engine
                try:
                    del tts
                except Exception:
                    pass
            except Exception as exc:
                print(f"TTS error: {exc}", flush=True)
            return

        # Load sound if not cached
        if cmd.asset_name not in self._loaded_sounds:
            relative_path = self.ASSET_MAP.get(cmd.asset_name, cmd.asset_name)
            asset_path = self.assets_dir / relative_path
            if not asset_path.exists():
                # Only warn once per missing asset
                if cmd.asset_name not in self._loaded_sounds:
                    print(f"⚠️  Audio asset missing: '{cmd.asset_name}' at {asset_path}", flush=True)
                    self._loaded_sounds[cmd.asset_name] = None  # Mark as attempted
                return

            try:
                self._loaded_sounds[cmd.asset_name] = mixer.Sound(str(asset_path))
            except Exception as exc:
                print(f"❌ Failed to load audio '{cmd.asset_name}': {exc}", flush=True)
                self._loaded_sounds[cmd.asset_name] = None  # Mark as failed
                return

        sound = self._loaded_sounds.get(cmd.asset_name)
        if sound is None:
            return  # Asset failed to load previously
        volume = cmd.volume

        if cmd.channel == AudioChannel.MUSIC:
            # Use mixer.music for background tracks
            relative_path = self.ASSET_MAP.get(cmd.asset_name, cmd.asset_name)
            asset_path = self.assets_dir / relative_path
            if not asset_path.exists():
                print(f"⚠️  Music asset missing: '{cmd.asset_name}' at {asset_path}", flush=True)
                return
            try:
                mixer.music.load(str(asset_path))
                mixer.music.set_volume(self._apply_music_mix(volume))
                mixer.music.play(loops=-1 if cmd.loop else 0)
            except Exception as exc:
                print(f"❌ Music playback error for '{cmd.asset_name}': {exc}", flush=True)
        else:
            # Use channels for SFX
            channel = self._sfx_channels.get(cmd.channel)
            effective_volume = self._apply_sfx_mix(volume)
            if channel:
                channel.set_volume(effective_volume)
                channel.play(sound, loops=-1 if cmd.loop else 0)
            else:
                sound.set_volume(effective_volume)
                sound.play(loops=-1 if cmd.loop else 0)

    def _handle_stop(self, cmd: AudioCommand) -> None:
        """Handle stop command."""
        if cmd.channel == AudioChannel.MUSIC:
            mixer.music.stop()
        else:
            channel = self._sfx_channels.get(cmd.channel)
            if channel:
                channel.stop()

    def _handle_set_volume(self, cmd: AudioCommand) -> None:
        """Handle volume adjustment on a channel."""
        if cmd.channel == AudioChannel.MUSIC:
            mixer.music.set_volume(self._apply_music_mix(cmd.volume))
            return

        channel = self._sfx_channels.get(cmd.channel)
        if channel:
            channel.set_volume(self._apply_sfx_mix(cmd.volume))

    def _handle_state_change(self, cmd: AudioCommand) -> None:
        """Handle high-level state change."""
        if cmd.state == self._current_state:
            return

        self._current_state = cmd.state

        if cmd.state == AudioState.SILENT:
            mixer.music.stop()
            self._stop_channel(AudioChannel.SFX_AMBIENT)
            self._stop_channel(AudioChannel.SFX_SECONDARY)
        elif cmd.state == AudioState.AMBIENT:
            # Play fire crackle as background loop, scaled by fire_intensity
            volume = 0.25 + (self._fire_intensity * 0.45)  # Maps 0.0-1.0 to 0.25-0.7 volume
            self.play_sfx(
                "fire_crackle",
                volume=volume,
                loop=True,
                channel=AudioChannel.SFX_AMBIENT,
            )
            self._stop_channel(AudioChannel.SFX_SECONDARY)
            self.play_music("party_music", loop=True, volume=0.55)
        elif cmd.state == AudioState.PARTY:
            # Keep the fire crackle as a warm bed under party music
            volume = 0.25 + (self._fire_intensity * 0.45)
            self.play_sfx(
                "fire_crackle",
                volume=min(volume, 0.5),
                loop=True,
                channel=AudioChannel.SFX_AMBIENT,
            )
            self.play_music("party_music", loop=True, volume=0.65)
            self.play_sfx(
                "party_layer",
                volume=0.6,
                loop=True,
                channel=AudioChannel.SFX_SECONDARY,
            )
            self.play_sfx("party_horn", volume=0.9)
        elif cmd.state == AudioState.ALERT:
            mixer.music.stop()
            self._stop_channel(AudioChannel.SFX_AMBIENT)
            self._stop_channel(AudioChannel.SFX_SECONDARY)
            self.play_sfx("buzzer", volume=0.45)

    def _apply_sfx_mix(self, volume: float) -> float:
        return max(0.0, min(1.0, volume * self.master_volume * self.sfx_volume))

    def _apply_music_mix(self, volume: float) -> float:
        return max(0.0, min(1.0, volume * self.master_volume * self.music_volume))

    def _stop_channel(self, channel: AudioChannel) -> None:
        sfx_channel = self._sfx_channels.get(channel)
        if sfx_channel:
            sfx_channel.stop()


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
