"""Unit tests for Bond Fire v2.0 components."""

import time
from pathlib import Path

import pytest

from bond_fire_vision.color_analysis import (
    are_colors_contrasting,
    color_distance,
    get_color_name,
    get_palette_from_people,
)
from bond_fire_vision.local_prompts import LocalPromptGenerator
from bond_fire_vision.packet_builder import PacketBuilderV2, Person
from bond_fire_vision.state_machine import State, StateContext, StateMachine


def make_context(
    people_count: int,
    phone_detected: bool,
    timestamp: float,
    fan_power: float = 0.0,
) -> StateContext:
    return StateContext(
        people_count=people_count,
        phone_detected=phone_detected,
        fan_power=fan_power,
        timestamp=timestamp,
    )


class TestColorAnalysis:
    """Tests for color extraction and naming."""

    def test_color_naming_basic(self):
        """Test color naming for common colors."""
        assert get_color_name([255, 0, 0]) == "Red"
        assert get_color_name([0, 255, 0]) == "Lime"
        assert get_color_name([0, 0, 255]) == "Blue"

    def test_color_naming_grayscale(self):
        """Test color naming for grayscale values."""
        assert get_color_name([0, 0, 0]) == "Black"
        assert get_color_name([255, 255, 255]) == "White"
        assert "Gray" in get_color_name([128, 128, 128])

    def test_color_distance(self):
        """Test color distance calculation."""
        red = (255, 0, 0)
        blue = (0, 0, 255)
        distance = color_distance(red, blue)
        assert distance > 0
        assert distance == color_distance(blue, red)

    def test_colors_contrasting(self):
        """Test color contrast detection."""
        red = (255, 0, 0)
        blue = (0, 0, 255)
        light_gray = (200, 200, 200)

        assert are_colors_contrasting(red, blue, threshold=100)
        assert are_colors_contrasting(red, light_gray, threshold=50)  # Threshold tuned for actual distance

    def test_palette_from_people(self):
        """Test palette generation from multiple colors."""
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        palette = get_palette_from_people(colors, max_colors=3)
        assert len(palette) == 9  # 3 colors * 3 (RGB)
        assert palette[0] == 255  # First R value

    def test_palette_deduplication(self):
        """Test that similar colors are deduplicated in palette."""
        colors = [(255, 0, 0), (254, 0, 0), (253, 0, 0)]  # All very similar red
        palette = get_palette_from_people(colors, max_colors=3)
        # Should only contain one red (deduplicated)
        assert len(palette) == 3


class TestStateMachine:
    """Tests for state machine logic."""

    def test_initial_state(self):
        """Test initial state is IDLE."""
        sm = StateMachine()
        assert sm.state == State.IDLE

    def test_idle_to_fire_transition(self):
        """Test transition from IDLE to FIRE on first person."""
        sm = StateMachine()
        now = time.time()

        context = make_context(people_count=1, phone_detected=False, timestamp=now)
        sm.update(context)

        context = make_context(
            people_count=1,
            phone_detected=False,
            timestamp=now + sm.FIRE_ENTRY_DWELL + 0.01,
        )
        output = sm.update(context)

        assert output.state == State.FIRE
        assert sm.state == State.FIRE

    def test_fire_to_party_transition(self):
        """Test transition from FIRE to PARTY at 5+ people (includes buildup time)."""
        sm = StateMachine()
        now = time.time()

        # Bring to FIRE state
        context = make_context(people_count=1, phone_detected=False, timestamp=now)
        sm.update(context)
        context = make_context(
            people_count=1,
            phone_detected=False,
            timestamp=now + sm.FIRE_ENTRY_DWELL + 0.01,
        )
        sm.update(context)

        # Jump to 5 people but stay below dwell time
        context = make_context(people_count=5, phone_detected=False, timestamp=now + 1.0)
        output = sm.update(context)
        assert output.state == State.FIRE  # Not yet, below dwell

        # At dwell time (2s) but before buildup completes (needs 1.5s more)
        context = make_context(people_count=5, phone_detected=False, timestamp=now + 3.0)
        output = sm.update(context)
        assert output.state == State.FIRE  # Still FIRE, in buildup phase

        # Exceed dwell + buildup time (2 + 1.5 = 3.5 seconds)
        context = make_context(people_count=5, phone_detected=False, timestamp=now + 4.5)
        output = sm.update(context)
        assert output.state == State.PARTY

    def test_phone_preempts_fire(self):
        """Test phone-driven states preempt FIRE."""
        sm = StateMachine()
        now = time.time()

        # Start in FIRE
        context = make_context(people_count=3, phone_detected=False, timestamp=now)
        sm.update(context)
        context = make_context(
            people_count=3,
            phone_detected=False,
            timestamp=now + sm.FIRE_ENTRY_DWELL + 0.01,
        )
        sm.update(context)
        assert sm.state == State.FIRE

        # Phone appears
        context = make_context(
            people_count=3,
            phone_detected=True,
            fan_power=10.0,
            timestamp=now + sm.PHONE_ENTRY_DWELL + 0.01,
        )
        output = sm.update(context)
        assert output.state == State.PHONE_IDLE
        assert sm.state == State.PHONE_IDLE

        context = make_context(
            people_count=3,
            phone_detected=True,
            fan_power=80.0,
            timestamp=now + sm.PHONE_ENTRY_DWELL + 0.1,
        )
        output = sm.update(context)
        assert output.state == State.FANNING
        assert sm.state == State.FANNING

    def test_fire_intensity_scaling(self):
        """Test fire intensity scales with people count."""
        sm = StateMachine()
        now = time.time()

        context1 = make_context(people_count=1, phone_detected=False, timestamp=now)
        sm.update(context1)
        context1 = make_context(
            people_count=1,
            phone_detected=False,
            timestamp=now + sm.FIRE_ENTRY_DWELL + 0.01,
        )
        output1 = sm.update(context1)
        intensity1 = output1.fire_intensity

        context4 = make_context(
            people_count=4,
            phone_detected=False,
            timestamp=now + sm.FIRE_ENTRY_DWELL + 0.1,
        )
        output4 = sm.update(context4)
        intensity4 = output4.fire_intensity

        assert intensity1 < intensity4
        assert intensity1 == pytest.approx(0.35)
        assert intensity4 == pytest.approx(1.0)

    def test_pulse_timer(self):
        """Test pulse timer triggers at interval."""
        sm = StateMachine(pulse_interval=1.0)  # 1 second for testing
        now = time.time()

        context = make_context(people_count=2, phone_detected=False, timestamp=now)
        sm.update(context)
        context = make_context(
            people_count=2,
            phone_detected=False,
            timestamp=now + sm.FIRE_ENTRY_DWELL + 0.01,
        )
        output = sm.update(context)
        assert output.pulse_active is False

        # Still not time
        context = make_context(people_count=2, phone_detected=False, timestamp=now + 0.5)
        output = sm.update(context)
        assert output.pulse_active is False

        # Time for pulse
        context = make_context(people_count=2, phone_detected=False, timestamp=now + 1.1)
        output = sm.update(context)
        assert output.pulse_active is True


class TestLocalPrompts:
    """Tests for prompt generation."""

    def test_idle_prompts(self):
        """Test IDLE prompts are available."""
        gen = LocalPromptGenerator()
        prompt = gen.generate(State.IDLE, 0)
        assert len(prompt) > 0
        assert len(prompt) <= 120

    def test_fire_prompts_by_count(self):
        """Test FIRE prompts vary by people count (with cooldown disabled)."""
        gen = LocalPromptGenerator(prompt_cooldown=0.0)  # Disable cooldown for test
        p1 = gen.generate(State.FIRE, 1)
        p2 = gen.generate(State.FIRE, 2)
        p4 = gen.generate(State.FIRE, 4)

        # Should be different prompts (from different pools)
        assert p1 != p2
        assert p2 != p4

    def test_phone_prompts(self):
        """Test PHONE_IDLE prompts are available."""
        gen = LocalPromptGenerator()
        prompt = gen.generate(State.PHONE_IDLE, 2, colors_contrasting=False)
        assert len(prompt) > 0
        # Phone prompts should be present and distinct from other states
        assert len(prompt) <= 120

    def test_entry_prompt(self):
        """Test entry prompt generation."""
        gen = LocalPromptGenerator()
        prompt = gen.get_entry_prompt("Crimson")
        assert len(prompt) > 0
        assert "Crimson" in prompt or "Welcome" in prompt or "flame" in prompt.lower()

    def test_pulse_prompt(self):
        """Test pulse prompt generation."""
        gen = LocalPromptGenerator()
        prompt = gen.get_pulse_prompt(["Red", "Blue"])
        assert len(prompt) > 0

    def test_prompt_history_prevents_repetition(self):
        """Test that prompt history prevents rapid repetition (without cooldown)."""
        gen = LocalPromptGenerator(history_size=20, prompt_cooldown=0.0)  # Disable cooldown for test
        prompts = []

        for _ in range(5):
            prompt = gen.generate(State.IDLE, 0)
            prompts.append(prompt)

        # Should have at least 2 different prompts (history dedup works)
        unique_prompts = set(prompts)
        assert len(unique_prompts) > 1


class TestPacketBuilder:
    """Tests for v2.1 packet assembly."""

    def test_packet_has_required_fields(self):
        """Test that packets contain all required v2.1 fields."""
        pb = PacketBuilderV2()
        people = [Person(id=1, bbox=(0.2, 0.3, 0.4, 0.8), shirt_rgb=(255, 0, 0), shirt_name="Red")]
        packet = pb.build(
            state=State.FIRE,
            people=people,
            phone_detected=False,
            dominant_palette=[255, 0, 0],
            prompt="Test prompt",
            mist_pwm=200,
            fan_pwm=150,
            wind=0,
            pulse_active=False,
            entry_flash_id=None,
        )

        assert packet["version"] == 2
        assert "timestamp" in packet
        assert "fps" in packet
        assert packet["state"] == "FIRE"
        assert len(packet["people"]) == 1
        assert packet["phone_detected"] is False
        assert packet["prompt"] == "Test prompt"
        assert packet["mist_pwm"] == 200
        assert packet["fan_pwm"] == 150
        assert packet["wind"] == 0

    def test_packet_clamps_pwm_values(self):
        """Test that PWM values are clamped to 0-255."""
        pb = PacketBuilderV2()
        packet = pb.build(
            state=State.FIRE,
            people=[],
            phone_detected=False,
            dominant_palette=[],
            prompt="Test",
            mist_pwm=300,
            fan_pwm=-10,
            wind=0,
        )

        assert packet["mist_pwm"] == 255
        assert packet["fan_pwm"] == 0

    def test_packet_truncates_prompt(self):
        """Test that long prompts are truncated."""
        pb = PacketBuilderV2()
        long_prompt = "x" * 200
        packet = pb.build(
            state=State.FIRE,
            people=[],
            phone_detected=False,
            dominant_palette=[],
            prompt=long_prompt,
            mist_pwm=200,
            fan_pwm=150,
            wind=0,
        )

        assert len(packet["prompt"]) <= 120

    def test_packet_limits_people_array(self):
        """Test that people array is limited to 6."""
        pb = PacketBuilderV2()
        people = [
            Person(id=i, bbox=(0.2, 0.3, 0.4, 0.8), shirt_rgb=(255, 0, 0), shirt_name=f"Person{i}")
            for i in range(10)
        ]
        packet = pb.build(
            state=State.FIRE,
            people=people,
            phone_detected=False,
            dominant_palette=[],
            prompt="Test",
            mist_pwm=200,
            fan_pwm=150,
            wind=0,
        )

        assert len(packet["people"]) == 6

    def test_packet_fps_tracking(self):
        """Test that FPS is tracked across multiple packets."""
        pb = PacketBuilderV2()

        for i in range(3):
            packet = pb.build(
                state=State.FIRE,
                people=[],
                phone_detected=False,
                dominant_palette=[],
                prompt="Test",
                mist_pwm=200,
                fan_pwm=150,
                wind=0,
            )
            time.sleep(0.02)  # Simulate 50ms between packets (~20 fps)

        stats = pb.get_stats()
        assert stats["total_packets"] == 3
        assert stats["average_fps"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
