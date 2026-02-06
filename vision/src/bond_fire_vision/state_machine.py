"""State machine for Bondfire installation.

Manages transitions between IDLE, FIRE, PARTY, and PHONE states with
event-driven timers and thresholds.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class State(Enum):
    """Installation states."""

    IDLE = "IDLE"
    FIRE = "FIRE"
    PARTY = "PARTY"
    PHONE = "PHONE"


@dataclass
class StateContext:
    """Input context for state evaluation."""

    people_count: int
    phone_detected: bool
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
    pulse_active: bool
    entry_flash_id: Optional[int]


class StateMachine:
    """
    Event-driven state machine for Bondfire installation.

    State Transitions:
    - IDLE → FIRE: First person detected
    - FIRE → PARTY: ≥5 people for ≥2 seconds
    - FIRE → PHONE: Phone detected (preempts)
    - PARTY → FIRE: <4 people for ≥3 seconds
    - PHONE → previous: Phone absent for ≥2 seconds
    """

    # Timing constants
    IDLE_TIMEOUT = 5.0  # Seconds with 0 people to enter IDLE (hysteresis)
    PARTY_DWELL = 2.0  # Seconds with ≥5 people to enter PARTY
    PARTY_EXIT_DWELL = 3.0  # Seconds with <4 people to exit PARTY
    PHONE_ENTRY_DWELL = 0.0  # Seconds to detect phone (instant, no hysteresis)
    PHONE_EXIT_DWELL = 2.0  # Seconds without phone to exit PHONE
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
        self.previous_state = State.IDLE  # For PHONE exit
        self.PULSE_INTERVAL = pulse_interval

        # Timers
        self._state_enter_time = time.monotonic()
        self._idle_start: Optional[float] = None
        self._party_dwell_start: Optional[float] = None
        self._party_exit_start: Optional[float] = None
        self._phone_exit_start: Optional[float] = None
        self._last_pulse_time: Optional[float] = None
        self._entry_flash_until: Optional[float] = None
        self._entry_flash_id: Optional[int] = None

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
        phone = context.phone_detected

        # Track new person entries for flash effect
        if active_ids is not None:
            new_ids = active_ids - self._known_ids
            if new_ids and self.state == State.FIRE:
                # Flash the first new person
                self._entry_flash_id = next(iter(new_ids))
                self._entry_flash_until = now + self.ENTRY_FLASH_DURATION
            self._known_ids = active_ids.copy()

        # PHONE state has highest priority (preempts everything)
        if phone:
            if self.state != State.PHONE:
                self.previous_state = self.state
                self._change_state(State.PHONE, now)
            self._phone_exit_start = None
        elif self.state == State.PHONE:
            # Phone just disappeared, start exit timer
            if self._phone_exit_start is None:
                self._phone_exit_start = now
            elif now - self._phone_exit_start >= self.PHONE_EXIT_DWELL:
                # Exit PHONE, return to previous state
                self._change_state(self.previous_state, now)
                self._phone_exit_start = None

        # Evaluate non-PHONE states
        if self.state != State.PHONE:
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
                self._change_state(State.FIRE, now)

            elif self.state == State.FIRE:
                # Check for PARTY entry
                if people_count >= 5:
                    if self._party_dwell_start is None:
                        self._party_dwell_start = now
                    elif now - self._party_dwell_start >= self.PARTY_DWELL:
                        # Start party buildup for light show effect
                        if self._party_buildup_start is None:
                            self._party_buildup_start = now
                        elif now - self._party_buildup_start >= self.PARTY_ENTRY_BUILDUP:
                            self._change_state(State.PARTY, now)
                            self._party_buildup_start = None  # Reset for next time
                else:
                    self._party_dwell_start = None
                    self._party_buildup_start = None  # Reset if count drops

                # Drop to IDLE if no people
                if people_count == 0 and self._idle_start is not None:
                    if now - self._idle_start >= self.IDLE_TIMEOUT:
                        self._change_state(State.IDLE, now)

            elif self.state == State.PARTY:
                # Check for PARTY exit
                if people_count < 4:
                    if self._party_exit_start is None:
                        self._party_exit_start = now
                    elif now - self._party_exit_start >= self.PARTY_EXIT_DWELL:
                        self._change_state(State.FIRE, now)
                else:
                    self._party_exit_start = None

                # Emergency drop to IDLE
                if people_count == 0 and self._idle_start is not None:
                    if now - self._idle_start >= self.IDLE_TIMEOUT:
                        self._change_state(State.IDLE, now)

        # Update pulse timer for FIRE mode
        pulse_active = False
        if self.state == State.FIRE and people_count > 0:
            if self._last_pulse_time is None:
                self._last_pulse_time = now
            elif now - self._last_pulse_time >= self.PULSE_INTERVAL:
                pulse_active = True
                # Pulse lasts ~2 seconds, then reset timer
                if now - self._last_pulse_time >= self.PULSE_INTERVAL + 2.0:
                    self._last_pulse_time = now

        # Check if entry flash is still active
        entry_flash_id = None
        if self._entry_flash_until is not None and now < self._entry_flash_until:
            entry_flash_id = self._entry_flash_id
        elif self._entry_flash_until is not None and now >= self._entry_flash_until:
            # Flash expired
            self._entry_flash_id = None
            self._entry_flash_until = None

        # Calculate hardware outputs based on state
        party_buildup_progress = 0.0
        if self._party_buildup_start is not None and self.state == State.FIRE and people_count >= 5:
            # Calculate buildup progress (0.0 to 1.0 over PARTY_ENTRY_BUILDUP seconds)
            elapsed = now - self._party_buildup_start
            party_buildup_progress = min(1.0, elapsed / self.PARTY_ENTRY_BUILDUP)
        
        output = self._calculate_output(people_count, pulse_active, entry_flash_id, party_buildup_progress)

        self._last_people_count = people_count
        return output

    def _change_state(self, new_state: State, timestamp: float) -> None:
        """Internal state transition handler."""
        self.state = new_state
        self._state_enter_time = timestamp

        # Reset state-specific timers
        self._party_dwell_start = None
        self._party_exit_start = None
        self._phone_exit_start = None

        # Reset pulse timer on state entry
        if new_state == State.FIRE:
            self._last_pulse_time = timestamp
        else:
            self._last_pulse_time = None

    def _calculate_output(
        self,
        people_count: int,
        pulse_active: bool,
        entry_flash_id: Optional[int],
        party_buildup_progress: float = 0.0,
    ) -> StateOutput:
        """Calculate hardware outputs for current state."""
        if self.state == State.IDLE:
            return StateOutput(
                state=State.IDLE,
                mist_pwm=self.MIST_IDLE,
                fan_pwm=self.FAN_IDLE,
                fire_intensity=0.0,
                pulse_active=False,
                entry_flash_id=None,
                party_buildup_progress=0.0,
            )

        elif self.state == State.FIRE:
            # Scale intensity linearly: 1 person = 25%, 4 people = 100%
            fire_intensity = min(0.25 + (people_count - 1) * 0.25, 1.0)

            # Fan: 100 + (count * 30), capped at 255
            fan_pwm = min(self.FAN_MIN + people_count * 30, self.FAN_MAX)

            # Mist: 180 + (count * 15), capped at 255
            mist_pwm = min(180 + people_count * 15, self.MIST_MAX)

            return StateOutput(
                state=State.FIRE,
                mist_pwm=mist_pwm,
                fan_pwm=fan_pwm,
                fire_intensity=fire_intensity,
                pulse_active=pulse_active,
                entry_flash_id=entry_flash_id,
                party_buildup_progress=party_buildup_progress,
            )

        elif self.state == State.PARTY:
            return StateOutput(
                state=State.PARTY,
                mist_pwm=self.MIST_MAX,
                fan_pwm=self.FAN_MAX,
                fire_intensity=1.0,
                pulse_active=False,  # Party has its own rainbow effect
                entry_flash_id=None,
                party_buildup_progress=0.0,
            )

        elif self.state == State.PHONE:
            return StateOutput(
                state=State.PHONE,
                mist_pwm=self.MIST_MIN,
                fan_pwm=0,
                fire_intensity=0.0,
                pulse_active=False,
                entry_flash_id=None,
                party_buildup_progress=0.0,
            )

        # Fallback (should never reach)
        return StateOutput(
            state=State.IDLE,
            mist_pwm=self.MIST_IDLE,
            fan_pwm=self.FAN_IDLE,
            fire_intensity=0.0,
            pulse_active=False,
            entry_flash_id=None,
            party_buildup_progress=0.0,
        )

    def get_time_in_state(self, now: float) -> float:
        """Get seconds elapsed in current state."""
        return now - self._state_enter_time

    def reset(self) -> None:
        """Reset state machine to initial state."""
        self.state = State.IDLE
        self.previous_state = State.IDLE
        self._state_enter_time = time.monotonic()
        self._idle_start = None
        self._party_dwell_start = None
        self._party_exit_start = None
        self._phone_exit_start = None
        self._last_pulse_time = None
        self._entry_flash_until = None
        self._entry_flash_id = None
        self._last_people_count = 0
        self._known_ids.clear()
