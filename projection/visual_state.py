from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class VisualState:
    state_name: str = "IDLE"
    people_count: int = 0
    dominant_palette: List[int] = field(default_factory=list)
    prompt: str = ""
    fire_intensity: float = 0.0
    pulse_active: bool = False
    party_buildup_progress: float = 0.0
    wind: int = 0
    fan_pulse: float = 0.0
    fan_pulse_color: List[int] = field(default_factory=list)

    def update_from_packet(self, packet: dict) -> None:
        self.state_name = str(packet.get("state", self.state_name))
        self.people_count = int(len(packet.get("people", [])))
        self.dominant_palette = list(packet.get("dominant_palette", self.dominant_palette))
        self.prompt = str(packet.get("prompt", self.prompt))
        self.fire_intensity = float(packet.get("fire_intensity", self.fire_intensity))
        self.pulse_active = bool(packet.get("pulse_active", self.pulse_active))
        self.party_buildup_progress = float(
            packet.get("party_buildup_progress", self.party_buildup_progress)
        )
        self.wind = int(packet.get("wind", self.wind))
        self.fan_pulse = float(packet.get("fan_pulse", self.fan_pulse))
        self.fan_pulse_color = list(packet.get("fan_pulse_color", self.fan_pulse_color))
