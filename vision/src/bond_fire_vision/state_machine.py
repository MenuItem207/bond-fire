"""Simplified state machine for Bondfire installation.

Manages transitions between IDLE, FIRE, and PARTY states only.
Shake detection handled via MQTT integration.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .config import get_config


class State(Enum):
    """Installation states."""

    IDLE = "IDLE"
    FIRE = "FIRE"
    PARTY = "PARTY"


@dataclass
class StateContext:
    """Input context for state evaluation."""

    people_count: int
    timestamp: float


@dataclass
class StateOutput:
    """Output from state machine."""

    state: State
    mist_pwm: int
    fan_pwm: int
    fire_intensity: float  # 0.0-1.0
    pulse_active: bool
    entry_flash_id: Optional[int]
    party_buildup_progress: float = 0.0  # 0.0-1.0, progress towards full party


class StateMachine:
    """
    Event-driven state machine for Bondfire installation.

    State Transitions:
    - IDLE → FIRE: First person detected
    - FIRE → PARTY: ≥5 people for ≥2 seconds
    - PARTY → FIRE: <4 people for ≥3 seconds
    - FIRE → IDLE: 0 people for ≥5 seconds
    """

    # Timing constants
    IDLE_TIMEOUT = 5.0  # Seconds with 0 people to enter IDLE (hysteresis)
    PARTY_DWELL = 2.0  # Seconds with ≥5 people to enter PARTY
    PARTY_EXIT_DWELL = 3.0  # Seconds with <4 people to exit PARTY
    PARTY_ENTRY_BUILDUP = 1.5  # Seconds of light show build-up before full party
    PULSE_INTERVAL = 15.0  # Seconds between color pulses
    ENTRY_FLASH_DURATION = 3.0  # Seconds to flash new person's color

    # Hardware limits
    MIST_MIN = 150
    MIST_IDLE = 220
    MIST_MAX = 255
    FAN_IDLE = 60
    FAN_MIN = 100
    FAN_MAX = 255

    def __init__(self, pulse_interval: float = 15.0) -> None:
        """
        Initialize state machine.

        Args:
            pulse_interval: Seconds between color pulses in FIRE mode
        """
        self.state = State.IDLE
        self.PULSE_INTERVAL = pulse_interval

        # Load config
        cfg = get_config()
        self.FIRE_ENTRY_DWELL = cfg.state_machine.fire_entry_dwell

        # Timers
        self._state_enter_time = time.monotonic()
        self._idle_start: Optional[float] = None
        self._party_dwell_start: Optional[float] = None
        self._party_exit_start: Optional[float] = None
        self._last_pulse_time: Optional[float] = None
        self._entry_flash_until: Optional[float] = None
        self._entry_flash_id: Optional[int] = None
        self._fire_entry_start: Optional[float] = None

        # Tracking
        self._last_people_count = 0
        self._known_ids: set[int] = set()
        self._party_buildup_start: Optional[float] = None  # For supernova build-up effect

    def update(self, context: StateContext, active_ids: Optional[set[int]] = None) -> StateOutput:
        """
        Update state machine with current context.

        Args:
            context: Current detection state
            active_ids: Set of currently tracked person IDs (optional)

        Returns:
            Current state output with hardware settings
        """
        now = context.timestamp
        people_count = context.people_count

        # Track new person entries for flash effect
        if active_ids is not None:
            new_ids = active_ids - self._known_ids
            if new_ids and self.state == State.FIRE:
                # Flash the first new person
                self._entry_flash_id = next(iter(new_ids))
                self._entry_flash_until = now + self.ENTRY_FLASH_DURATION
            self._known_ids = active_ids.copy()

        # IDLE logic
        if people_count == 0:
            if self._idle_start is None:
                self._idle_start = now
            elif now - self._idle_start >= self.IDLE_TIMEOUT and self.state != State.IDLE:
                self._change_state(State.IDLE, now)
        else:
            self._idle_start = None

        # FIRE/PARTY transitions
        if self.state == State.IDLE and people_count > 0:
            if self.FIRE_ENTRY_DWELL <= 0:
                self._change_state(State.FIRE, now)
                self._fire_entry_start = None
            elif self._fire_entry_start is None:
                self._fire_entry_start = now
            elif now - self._fire_entry_start >= self.FIRE_ENTRY_DWELL:
                self._change_state(State.FIRE, now)
                self._fire_entry_start = None

        elif self.state == State.FIRE:
            if people_count >= 5:
                if self._party_dwell_start is None:
                    self._party_dwell_start = now
                elif now - self._party_dwell_start >= self.PARTY_DWELL:
                    if self._party_buildup_start is None:
                        self._party_buildup_start = now
                    buildup_elapsed = now - self._party_buildup_start
                    if buildup_elapsed >= self.PARTY_ENTRY_BUILDUP:
                        self._change_state(State.PARTY, now)
                        self._party_dwell_start = None
                        self._party_buildup_start = None
            else:
                self._party_dwell_start = None
                self._party_buildup_start = None

        elif self.state == State.PARTY:
            if people_count < 4:
                if self._party_exit_start is None:
                    self._party_exit_start = now
                elif now - self._party_exit_start >= self.PARTY_EXIT_DWELL:
                    self._change_state(State.FIRE, now)
                    self._party_exit_start = None
            else:
                self._party_exit_start = None

        self._last_people_count = people_count

        # Generate output
        return self._get_output(context, now)

    def _change_state(self, new_state: State, timestamp: float) -> None:
        """Change active state."""
        print(f"[STATE] {self.state.value} → {new_state.value}", flush=True)
        self.state = new_state
        self._state_enter_time = timestamp
        # Reset pulse timer on state change
        self._last_pulse_time = None

    def _get_output(self, context: StateContext, now: float) -> StateOutput:
        """Build state output based on current state."""
        people = context.people_count

        # Entry flash (overrides pulse)
        entry_flash_id = None
        if self._entry_flash_until is not None and now < self._entry_flash_until:
            entry_flash_id = self._entry_flash_id

        # Pulse logic (every PULSE_INTERVAL seconds, not during entry flash)
        pulse_active = False
        if entry_flash_id is None:
            if self._last_pulse_time is None:
                self._last_pulse_time = now
            elif now - self._last_pulse_time >= self.PULSE_INTERVAL:
                pulse_active = True
                self._last_pulse_time = now

        # Party buildup progress
        party_buildup_progress = 0.0
        if self._party_buildup_start is not None:
            elapsed = now - self._party_buildup_start
            party_buildup_progress = min(1.0, elapsed / self.PARTY_ENTRY_BUILDUP)

        # State-specific outputs
        if self.state == State.IDLE:
            return StateOutput(
                state=State.IDLE,
                mist_pwm=self.MIST_IDLE,
                fan_pwm=self.FAN_IDLE,
                fire_intensity=0.35,
                pulse_active=False,
                entry_flash_id=None,
                party_buildup_progress=0.0,
            )

        elif self.state == State.FIRE:
            intensity = min(1.0, 0.4 + (people * 0.12))
            mist = int(self.MIST_MIN + (self.MIST_MAX - self.MIST_MIN) * intensity)
            fan = int(self.FAN_MIN + (self.FAN_MAX - self.FAN_MIN) * intensity)
            return StateOutput(
                state=State.FIRE,
                mist_pwm=min(self.MIST_MAX, mist),
                fan_pwm=min(self.FAN_MAX, fan),
                fire_intensity=intensity,
                pulse_active=pulse_active,
                entry_flash_id=entry_flash_id,
                party_buildup_progress=party_buildup_progress,
            )

        else:  # PARTY
            return StateOutput(
                state=State.PARTY,
                mist_pwm=self.MIST_MAX,
                fan_pwm=self.FAN_MAX,
                fire_intensity=1.0,
                pulse_active=False,
                entry_flash_id=None,
                party_buildup_progress=1.0,
            )
