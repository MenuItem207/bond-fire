"""Local prompt generation for Bondfire installation.

Curated, state-aware prompt dictionaries with rotation to avoid repetition.
Replaces OpenAI dependency with instant, deterministic text selection.
"""

from __future__ import annotations

import random
import time
from collections import deque
from typing import Optional

from .config import get_config
from .state_machine import State


class LocalPromptGenerator:
    """
    Generates installation prompts based on state and context.

    Maintains history to avoid repeating prompts in quick succession.
    Supports dynamic token replacement for personalization.
    Includes cooldown timer to prevent prompts changing too rapidly.
    """

    # Prompt dictionaries by state
    IDLE_PROMPTS = [
        "Social Battery: 0%. I need a spark...",
        "Waiting for brave souls...",
        "The fire sleeps. Wake it up.",
        "Empty space, empty flame.",
        "Come closer. I don't bite.",
        "Lonely fire seeks connection.",
    ]

    FIRE_1_PROMPTS = [
        "One spark. But fires need friends.",
        "Lone flame detected. Battery: 20%",
        "Solo mode: Active. Multiplayer recommended.",
        "One is brave. Two is better.",
        "You started something. Keep going.",
    ]

    FIRE_2_PROMPTS = [
        "Two flames dancing—who's braver, bro?",
        "Pair detected. Battery: 40%",
        "Double trouble! One more?",
        "Two sparks. Getting warmer.",
        "Nice duo. But we can do better.",
    ]

    FIRE_3_PROMPTS = [
        "Three's a fire. One more for a blaze!",
        "Battery 60%. Almost there!",
        "Trio energy! Two more for critical mass.",
        "Three flames strong. Keep recruiting!",
        "Getting hot in here. Literally.",
    ]

    FIRE_4_PROMPTS = [
        "Almost there! Find one more legend.",
        "Four flames roaring. One more for chaos!",
        "SO CLOSE! Where's number five?",
        "Elite squad forming. One slot left!",
        "Battery: 80%. Final push!",
    ]

    PARTY_PROMPTS = [
        "CRITICAL MASS ACHIEVED! 🔥",
        "FIVE FLAMES = PURE ENERGY!",
        "THIS IS WHAT CONNECTION LOOKS LIKE!",
        "LEGENDARY STATUS UNLOCKED!",
        "THE SQUAD IS HERE!",
        "MAXIMUM VIBES ACTIVATED!",
        "FIRE NATION ASSEMBLED!",
        "YOU DID IT! THIS IS EPIC!",
    ]

    PHONE_PROMPTS = [
        "🚫 PHONE DETECTED. PUT IT AWAY!",
        "📱 → 🔥 DISCONNECT TO CONNECT!",
        "📵 FOCUS. THE FIRE WAITS FOR YOU.",
        "☠️ PHONE KILLS THE VIBE. HELP US.",
        "💔 YOU BROKE THE CIRCLE.",
        "⚠️ SIGNAL INTERFERENCE DETECTED!",
        "👀 EYES UP. SCREENS DOWN.",
        "🎯 THIS IS MORE IMPORTANT THAN YOUR FEED!",
        "🔥 > 📱 ALWAYS.",
        "⏰ DISCONNECT NOW. CONNECT WITH US!",
    ]

    PHONE_EXIT_PROMPTS = [
        "🎉 YES! WELCOME BACK TO THE FIRE!",
        "✨ SMART CHOICE! LET'S BURN!",
        "🔥 ATTENTION RESTORED. FIRE APPROVED!",
        "🌟 NOW WE'RE TALKING!",
        "💫 CONNECTION RESTORED. WITH THE FIRE!",
        "🎊 THAT'S WHAT WE NEEDED!",
        "👏 YOU DID IT! THE FIRE CELEBRATES YOU!",
    ]

    # Color-aware prompts (when multiple people have distinct colors)
    COLOR_PROMPTS = [
        "Red meets blue—fusion energy!",
        "Colors clashing—love it! Keep it going.",
        "Rainbow squad detected. Beautiful.",
        "Style mixing activated. Fire approves.",
        "Different vibes, one flame.",
    ]

    def __init__(self, history_size: int = 10, prompt_cooldown: Optional[float] = None) -> None:
        """
        Initialize prompt generator.

        Args:
            history_size: Number of recent prompts to track for deduplication
            prompt_cooldown: Minimum seconds between prompt changes. If None, uses config value (default: 8.0)
        """
        self._history: deque[str] = deque(maxlen=history_size)
        self._color_prompt_enabled = False
        
        # Load cooldown timings from config if not provided
        if prompt_cooldown is None:
            cfg = get_config()
            self._prompt_cooldown = cfg.prompts.normal_cooldown
            self._phone_cooldown = cfg.prompts.phone_cooldown
        else:
            self._prompt_cooldown = prompt_cooldown
            cfg = get_config()
            self._phone_cooldown = cfg.prompts.phone_cooldown
        
        self._current_prompt: Optional[str] = None
        self._last_prompt_time: float = 0.0

    def generate(
        self,
        state: State,
        people_count: int,
        color_count: Optional[int] = None,
        colors_contrasting: bool = False,
    ) -> str:
        """
        Generate a prompt for the current state.

        Args:
            state: Current installation state
            people_count: Number of people detected
            color_count: Number of distinct colors (optional)
            colors_contrasting: Whether colors are visually contrasting (optional)

        Returns:
            Prompt string (max 120 chars)
        """
        # Check cooldown timer
        now = time.monotonic()
        # Use shorter cooldown for PHONE state (2 sec) vs normal (8 sec)
        active_cooldown = self._phone_cooldown if state == State.PHONE else self._prompt_cooldown
        if (self._current_prompt is not None and 
            (now - self._last_prompt_time) < active_cooldown):
            return self._current_prompt
        
        # Select prompt pool based on state
        if state == State.IDLE:
            pool = self.IDLE_PROMPTS
        elif state == State.PHONE:
            pool = self.PHONE_PROMPTS
        elif state == State.PARTY:
            pool = self.PARTY_PROMPTS
        elif state == State.FIRE:
            # Use color-aware prompts if we have contrasting colors
            if colors_contrasting and color_count and color_count >= 2:
                pool = self.COLOR_PROMPTS
            else:
                # Select based on people count
                if people_count == 1:
                    pool = self.FIRE_1_PROMPTS
                elif people_count == 2:
                    pool = self.FIRE_2_PROMPTS
                elif people_count == 3:
                    pool = self.FIRE_3_PROMPTS
                elif people_count >= 4:
                    pool = self.FIRE_4_PROMPTS
                else:
                    pool = self.IDLE_PROMPTS
        else:
            pool = self.IDLE_PROMPTS

        # Filter out recently used prompts
        available = [p for p in pool if p not in self._history]
        if not available:
            # All prompts used recently, reset and use full pool
            available = list(pool)

        # Select random prompt
        prompt = random.choice(available)

        # Add to history
        self._history.append(prompt)
        
        # Update cooldown tracking
        self._current_prompt = prompt
        self._last_prompt_time = now

        return prompt

    def get_entry_prompt(self, person_color_name: Optional[str] = None) -> str:
        """
        Generate a welcome prompt for a new person entering.

        Args:
            person_color_name: Name of the person's shirt color (optional)

        Returns:
            Welcome prompt string
        """
        if person_color_name:
            prompts = [
                f"Welcome, {person_color_name}! Join the fire.",
                f"{person_color_name} enters the flame!",
                f"New spark: {person_color_name}!",
                f"{person_color_name} joined. Fire grows!",
            ]
        else:
            prompts = [
                "New flame detected!",
                "Welcome to the fire!",
                "Another spark joins!",
                "Fresh energy incoming!",
            ]

        return random.choice(prompts)

    def get_phone_exit_prompt(self) -> str:
        """
        Generate a celebratory prompt when phone is put away.

        Returns:
            Celebration prompt string
        """
        return random.choice(self.PHONE_EXIT_PROMPTS)

    def get_pulse_prompt(self, color_names: list[str]) -> str:
        """
        Generate a prompt for the periodic color pulse.

        Args:
            color_names: List of color names in the current group

        Returns:
            Pulse prompt string
        """
        if not color_names:
            return "Unity pulse!"

        if len(color_names) == 1:
            return f"{color_names[0]} energy pulse!"
        elif len(color_names) == 2:
            return f"{color_names[0]} + {color_names[1]} fusion!"
        else:
            # Multiple colors
            return f"Rainbow pulse: {', '.join(color_names[:3])}!"

    def clear_history(self) -> None:
        """Clear prompt history (useful for testing or reset)."""
        self._history.clear()

    def force_regenerate(self) -> None:
        """Force next prompt to regenerate by clearing cooldown timer."""
        self._current_prompt = None
        self._last_prompt_time = 0.0
