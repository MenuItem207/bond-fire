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
        "I'm burning for nobody. Sad sia.",
        "Free warmth. Why you running?",
        "Come. I won't bite. Maybe.",
        "Ghost town here. Be the main character.",
        "Don't paiseh. Just step in.",
        "Your crush might be the next one to join.",
        "Provide me company, I provide vibes.",
    ]

    FIRE_1_PROMPTS = [
        "Main Character energy. Now find a sidekick.",
        "You look lonely. Drag someone in.",
        "Make eye contact with a stranger. I dare you.",
        "Solo is cool, duo is warmer.",
        "Don't scroll. Wave at the next person.",
        "I'm judging your outfit. Come closer.",
        "Wait for it... someone cool is coming.",
    ]

    FIRE_2_PROMPTS = [
        "Date night or strangers? I can't tell.",
        "Accepting applications for a third wheel.",
        "Awkward silence? Talk about me.",
        "You two look good. Need one more critic.",
        "Don't gatekeep the heat. Jio someone.",
        "Create a conspiracy theory about the next person.",
        "Two is company, three is a party.",
    ]

    FIRE_3_PROMPTS = [
        "We need a fourth player for Mahjong.",
        "Triangle formation strong. Square is better.",
        "Almost a squad. Who's the missing link?",
        "Don't let the next person walk past. Stare at them.",
        "Three's a crowd? Nah, three's a crew.",
        "Look at you three. Best friends already?",
        "One more spot to unlock full power.",
    ]

    FIRE_4_PROMPTS = [
        "One slot left. Auditions open.",
        "Who is the chosen one? Point at them.",
        "So squeezy. I love it.",
        "Don't be selfish. Squeeze one more in.",
        "Perfect balance pending. One more.",
        "Tell the next walker: 'We've been expecting you.'",
    ]

    PARTY_PROMPTS = [
        "Kampung spirit unlocked. Shiok.",
        "Okay, nobody move. This lighting is perfection.",
        "Look at everyone. Now smile. Cute.",
        "Core memory unlocked. Stay here.",
        "Vibe check passed. 10/10.",
        "This is it. The peak of your day.",
        "Whatever you're doing, it's working.",
        "Full house! Don't break the chain.",
    ]

    # Color-aware prompts (when multiple people have distinct colors)
    COLOR_PROMPTS = [
        "Wah, this palette is expensive.",
        "You guys coordinated this? Liar.",
        "Fit check: immaculate.",
        "Power Rangers vibes today.",
        "Different styles, same heat.",
        "Who dressed you guys? Good job.",
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
        
        # Load cooldown timing from config if not provided
        if prompt_cooldown is None:
            cfg = get_config()
            self._prompt_cooldown = cfg.prompts.normal_cooldown
        else:
            self._prompt_cooldown = prompt_cooldown
        
        self._current_prompt: Optional[str] = None
        self._last_prompt_time: float = 0.0

    def generate(
        self,
        state: State,
        people_count: int,
        color_count: Optional[int] = None,
        colors_contrasting: bool = False,
        cooldown_override: Optional[float] = None,
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
        active_cooldown = self._prompt_cooldown
        if cooldown_override is not None:
            active_cooldown = max(active_cooldown, cooldown_override)
        if (self._current_prompt is not None and 
            (now - self._last_prompt_time) < active_cooldown):
            return self._current_prompt
        
        # Select prompt pool based on state
        if state == State.IDLE:
            pool = self.IDLE_PROMPTS
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

    def is_cooldown_active(self, state: State, cooldown_override: Optional[float] = None) -> bool:
        """
        Check whether the prompt cooldown is still active.

        Args:
            state: Current installation state
            cooldown_override: Optional override to enforce a longer cooldown

        Returns:
            True if cooldown is active, otherwise False
        """
        if self._current_prompt is None:
            return False
        now = time.monotonic()
        active_cooldown = self._prompt_cooldown
        if cooldown_override is not None:
            active_cooldown = max(active_cooldown, cooldown_override)
        return (now - self._last_prompt_time) < active_cooldown

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
                f"Eh {person_color_name}, come in.",
                f"{person_color_name} shirt, nice. Join.",
                f"New spark: {person_color_name}.",
                f"{person_color_name} just joined.",
            ]
        else:
            prompts = [
                "Eh, jump in.",
                "Come in, don't shy.",
                "New spark in.",
                "Fresh energy.",
            ]

        return random.choice(prompts)

    def get_pulse_prompt(self, color_names: list[str]) -> str:
        """
        Generate a prompt for the periodic color pulse.

        Args:
            color_names: List of color names in the current group

        Returns:
            Pulse prompt string
        """
        if not color_names:
            return "Color combo: all of you."

        if len(color_names) == 1:
            return f"Color combo: {color_names[0]}."
        elif len(color_names) == 2:
            return f"Color combo: {color_names[0]} + {color_names[1]}."
        else:
            # Multiple colors
            return f"Color combo: {', '.join(color_names[:3])}."

    def clear_history(self) -> None:
        """Clear prompt history (useful for testing or reset)."""
        self._history.clear()

    def force_regenerate(self) -> None:
        """Force next prompt to regenerate by clearing cooldown timer."""
        self._current_prompt = None
        self._last_prompt_time = 0.0
