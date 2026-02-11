"""Packet builder for v2.1 protocol.

Assembles JSON packets with full schema including tracking data, colors,
state machine outputs, and audio context.

"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .audio_manager import AudioState
from .state_machine import State


@dataclass
class Person:
    """Tracked person data."""

    id: int
    bbox: tuple[float, float, float, float]  # Normalized x1,y1,x2,y2
    shirt_rgb: tuple[int, int, int]
    shirt_name: str


class PacketBuilderV2:
    """
    Builds v2.1 protocol packets for ESP32 consumption.

    Schema Version: 2.1
    Max packet size: <1KB for UDP reliability
    """

    PROTOCOL_VERSION = 2

    def __init__(self) -> None:
        """Initialize packet builder."""
        self._packet_count = 0
        self._last_timestamp = 0.0
        self._fps_history: list[float] = []

    def build(
        self,
        state: State,
        people: list[Person],
        dominant_palette: list[int],
        prompt: str,
        mist_pwm: int,
        fan_pwm: int,
        wind: int,
        fire_intensity: float = 0.0,
        pulse_active: bool = False,
        entry_flash_id: Optional[int] = None,
        audio_state: AudioState = AudioState.SILENT,
        party_buildup_progress: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Build a complete v2.1 packet.

        Args:
            state: Current state machine state
            people: List of tracked people
            dominant_palette: Flattened RGB palette [r,g,b,r,g,b,...]
            prompt: Display text (max 120 chars)
            mist_pwm: Mist atomizer PWM (0-255)
            fan_pwm: Fan PWM (0-255)
            wind: Fanning intensity (0-100)
            fire_intensity: Fire intensity (0.0-1.0)
            pulse_active: True during 15s color pulse
            entry_flash_id: Track ID for entry flash (or None)
            audio_state: Current audio state
            party_buildup_progress: Party build-up progress (0.0-1.0)

        Returns:
            JSON-serializable dictionary
        """
        now = time.time()

        # Calculate FPS
        if self._last_timestamp > 0:
            delta = now - self._last_timestamp
            if delta > 0:
                fps = 1.0 / delta
                self._fps_history.append(fps)
                if len(self._fps_history) > 30:
                    self._fps_history.pop(0)
        else:
            fps = 0.0

        avg_fps = sum(self._fps_history) / len(self._fps_history) if self._fps_history else 0.0

        self._last_timestamp = now
        self._packet_count += 1

        # Build people array (max 6)
        people_data = []
        for person in people[:6]:
            people_data.append(
                {
                    "id": person.id,
                    "bbox": [float(v) for v in person.bbox],
                    "color": [int(v) for v in person.shirt_rgb],
                    "shirt_rgb": [int(v) for v in person.shirt_rgb],
                    "shirt_name": person.shirt_name[:24],  # Truncate to 24 chars
                }
            )

        # Truncate palette to max 4 colors (12 values)
        palette = dominant_palette[:12]

        # Truncate prompt to 120 chars
        prompt = prompt[:120]

        # Clamp PWM values
        mist_pwm = max(0, min(255, mist_pwm))
        fan_pwm = max(0, min(255, fan_pwm))
        wind = max(0, min(100, int(wind)))
        wind = int(round(wind / 25.0)) * 25
        wind = max(0, min(100, wind))
        fire_intensity = max(0.0, min(1.0, fire_intensity))

        packet = {
            "version": self.PROTOCOL_VERSION,
            "timestamp": now,
            "fps": round(avg_fps, 1),
            "state": state.value,
            "people": people_data,
            "dominant_palette": palette,
            "prompt": prompt,
            "mist_pwm": mist_pwm,
            "fan_pwm": fan_pwm,
            "wind": wind,
            "fire_intensity": round(fire_intensity, 2),
            "pulse_active": pulse_active,
            "entry_flash_id": entry_flash_id,
            "audio_state": audio_state.value,
            "party_buildup_progress": round(party_buildup_progress, 2),
        }

        return packet

    def get_stats(self) -> Dict[str, Any]:
        """
        Get packet builder statistics.

        Returns:
            Dictionary with packet count, average FPS, etc.
        """
        avg_fps = sum(self._fps_history) / len(self._fps_history) if self._fps_history else 0.0
        return {
            "total_packets": self._packet_count,
            "average_fps": round(avg_fps, 2),
            "fps_min": round(min(self._fps_history), 2) if self._fps_history else 0.0,
            "fps_max": round(max(self._fps_history), 2) if self._fps_history else 0.0,
        }

    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self._packet_count = 0
        self._fps_history.clear()
