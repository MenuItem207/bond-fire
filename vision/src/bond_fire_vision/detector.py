from __future__ import annotations

import json
import socket
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import cv2
from ultralytics import YOLO

from .audio_manager import AudioManager, AudioState
from .config import get_config
from .color_analysis import (
    are_colors_contrasting,
    extract_dominant_color,
    get_color_name,
    get_palette_from_people,
)
from .local_prompts import LocalPromptGenerator
from .packet_builder import PacketBuilderV2, Person
from .state_machine import State, StateContext, StateMachine


@dataclass(eq=True)
class VisionState:
    """Detection state (for backward compatibility)."""

    people_in_roi: int
    phone_detected: bool


class BondFireVision:
    """People and phone detection within a configurable active zone."""

    CLASS_PERSON = 0
    CLASS_PHONE = 67

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        capture_index: int = 0,
        roi: Tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0),
        detection_confidence: float = 0.5,
        person_confidence: float = 0.6,
        broadcast_ip: str = "255.255.255.255",
        broadcast_port: int = 4210,
        updates_per_second: float = 60.0,
        pulse_interval: float = 15.0,
        enable_audio: bool = False,
        audio_volume: float = 0.7,
        narration_enabled: bool = False,
        tts_voice: Optional[str] = None,
        # Legacy parameters (ignored, kept for compatibility)
        ai_enabled: bool = False,
        ai_interval: float = 5.0,
        ai_model: str = "gpt-4o-mini",
        ai_temperature: float = 0.9,
        ai_max_output_tokens: int = 120,
        ai_prompt_ttl: float = 30.0,
        openai_api_key: str | None = None,
    ) -> None:
        """
        Initialize BondFireVision v2.

        Args:
            model_path: Path to YOLOv8 weights
            capture_index: Camera index
            roi: Active zone (x_min, y_min, x_max, y_max) normalized 0-1
            detection_confidence: Minimum detection confidence
            person_confidence: Minimum detection confidence for people
            broadcast_ip: UDP broadcast IP
            broadcast_port: UDP port
            updates_per_second: Target packet rate
            pulse_interval: Seconds between color pulses
            enable_audio: Enable audio subsystem
            audio_volume: Master audio volume (0.0-1.0)
            narration_enabled: Enable TTS prompts
        """
        self._validate_roi(roi)
        self._validate_confidence(detection_confidence)
        self._validate_confidence(person_confidence)

        self.model = YOLO(model_path)
        self.capture_index = capture_index
        self.roi = roi
        self.detection_confidence = detection_confidence
        self.person_confidence = max(detection_confidence, person_confidence)
        self.cap: cv2.VideoCapture | None = None
        self.broadcast_ip = broadcast_ip
        self.broadcast_port = broadcast_port
        self.send_interval = 1.0 / updates_per_second if updates_per_second > 0 else 0.0

        # New v2 components
        self.state_machine = StateMachine(pulse_interval=pulse_interval)
        self.prompt_generator = LocalPromptGenerator()
        self.packet_builder = PacketBuilderV2()
        self.audio_manager: Optional[AudioManager] = None

        cfg = get_config()
        frame_rate = max(1, cfg.state_machine.frame_rate)
        self._celebration_duration = cfg.celebration.duration_frames / frame_rate
        self._celebration_until: Optional[float] = None
        self._same_state_cooldown = cfg.prompts.same_state_cooldown
        self._min_person_area_ratio = max(0.0, cfg.vision.min_person_area_ratio)

        if enable_audio:
            self.audio_manager = AudioManager(
                enabled=True,
                master_volume=audio_volume,
                narration_enabled=narration_enabled,
                tts_voice=tts_voice,
            )

        # Tracking state
        self._tracked_people: Dict[int, Person] = {}
        self._last_audio_state = AudioState.SILENT
        self._last_entry_id: Optional[int] = None
        self._party_buildup_started = False
        self._last_buildup_step = 0
        self._celebration_frames_remaining = 0  # Deprecated: time-based celebration is used instead
        self._celebration_prompt: Optional[str] = None  # Store celebration prompt to avoid toggling
        self._latest_state_output: Optional[Any] = None  # Cache latest state output for packet building
        self._last_narrated_prompt: Optional[str] = None  # Track last narrated prompt to avoid repeats
        self._last_sent_prompt: Optional[str] = None  # Cache prompt to prevent unnecessary resets
        self._last_prompt_state: Optional[State] = None

    def run(self, display: bool = True) -> VisionState:
        """
        Start the capture loop.

        Args:
            display: Whether to show the annotated OpenCV window.
        Returns:
            Last known detection state.
        """
        sock = self._create_socket()
        self.cap = cv2.VideoCapture(self.capture_index)
        if not self.cap.isOpened():
            raise RuntimeError("Could not open video source")

        print(
            "Starting vision system. Press 'q' to exit." if display else "Starting vision system. Ctrl+C to exit.",
            flush=True,
        )
        print(f"Bondfire v2.0 - Master/Slave Architecture", flush=True)

        # Start audio manager
        if self.audio_manager:
            self.audio_manager.start()

        previous_state: VisionState | None = None
        state = VisionState(people_in_roi=0, phone_detected=False)
        last_send = 0.0

        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    raise RuntimeError("Failed to read frame from camera")

                state, processed_frame = self.analyze_frame(frame, annotate=display)
                now = time.monotonic()
                
                if self.send_interval == 0.0 or now - last_send >= self.send_interval:
                    self._send_update(sock, now)
                    last_send = now

                if display:
                    cv2.imshow("Bond Fire Vision", processed_frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
                else:
                    if state != previous_state:
                        print(
                            f"Active zone: {state.people_in_roi} people | Phone detected: {'YES' if state.phone_detected else 'NO'}",
                            flush=True,
                        )
                        previous_state = state
        except KeyboardInterrupt:
            print("Stopping vision loop.", flush=True)
        finally:
            try:
                sock.close()
            except OSError:
                pass
            if self.cap is not None:
                self.cap.release()
                self.cap = None
            if display:
                cv2.destroyAllWindows()
            if self.audio_manager:
                self.audio_manager.stop()

            # Print stats
            stats = self.packet_builder.get_stats()
            print(f"Session stats: {stats['total_packets']} packets, avg {stats['average_fps']:.1f} fps", flush=True)

        return state

    def analyze_frame(self, frame: Any, annotate: bool = True) -> tuple[VisionState, Any]:
        """Analyze a single frame with tracking and color extraction."""
        height, width = frame.shape[:2]
        roi_pixels = self._roi_pixels(width, height)

        person_count = 0
        phone_detected = False
        people_in_roi: list[Person] = []

        if annotate:
            self._draw_roi(frame, roi_pixels)

        # Use track() instead of model() for persistent IDs
        results = self.model.track(frame, persist=True, verbose=False, conf=self.detection_confidence)
        
        for result in results:
            if result.boxes is None or result.boxes.id is None:
                continue
                
            for box, track_id in zip(result.boxes, result.boxes.id):
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
                tid = int(track_id)

                if cls == self.CLASS_PERSON:
                    if conf < self.person_confidence:
                        continue
                    box_area_ratio = ((x2 - x1) * (y2 - y1)) / max(1.0, (width * height))
                    if box_area_ratio < self._min_person_area_ratio:
                        continue
                    inside = self._is_inside_roi((x1, y1, x2, y2), roi_pixels)
                    if inside:
                        person_count += 1
                        
                        # Extract shirt color
                        shirt_rgb = extract_dominant_color(frame, (x1, y1, x2, y2))
                        shirt_name = get_color_name(shirt_rgb)
                        
                        # Normalize bbox
                        bbox_norm = (x1 / width, y1 / height, x2 / width, y2 / height)
                        
                        person = Person(
                            id=tid,
                            bbox=bbox_norm,
                            shirt_rgb=shirt_rgb,
                            shirt_name=shirt_name,
                        )
                        people_in_roi.append(person)
                        self._tracked_people[tid] = person
                        
                    if annotate:
                        color = (0, 255, 0) if inside else (0, 0, 255)
                        thickness = 2 if inside else 1
                        cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color, thickness)
                        if inside:
                            label = f"ID:{tid} {self._tracked_people.get(tid, person).shirt_name if tid in self._tracked_people or inside else ''}"
                            cv2.putText(frame, label, (int(x1), max(int(y1) - 10, 0)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                            
                elif cls == self.CLASS_PHONE:
                    if conf < self.detection_confidence:
                        continue
                    inside = self._is_inside_roi((x1, y1, x2, y2), roi_pixels)
                    if inside:
                        phone_detected = True
                    if annotate:
                        color = (0, 0, 255) if inside else (160, 160, 255)
                        thickness = 2 if inside else 1
                        cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color, thickness)
                        label = "PHONE" if inside else "PHONE (out)"
                        cv2.putText(frame, label, (int(x1), max(int(y1) - 10, 0)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # Update state machine
        context = StateContext(
            people_count=person_count,
            phone_detected=phone_detected,
            timestamp=time.monotonic(),
        )
        active_ids = {p.id for p in people_in_roi}
        state_output = self.state_machine.update(context, active_ids)
        
        # Cache state output for packet building in _send_update
        self._latest_state_output = state_output

        # Store people for packet building
        self._tracked_people = {p.id: p for p in people_in_roi}

        state = VisionState(people_in_roi=person_count, phone_detected=phone_detected)

        if annotate:
            self._draw_status(frame, state, state_output.state)

        return state, frame

    def _draw_roi(self, frame, roi_pixels: tuple[int, int, int, int]) -> None:
        x1, y1, x2, y2 = roi_pixels
        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 0), 2)
        cv2.putText(frame, "Active Zone", (x1, max(y1 - 10, 0)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

    def _draw_status(self, frame, state: VisionState, current_state: State) -> None:
        """Draw status overlay on frame."""
        status_text = f"{current_state.value}: {state.people_in_roi} people | Phone: {'YES' if state.phone_detected else 'NO'}"
        color = (0, 0, 255) if state.phone_detected else (0, 255, 0)
        (text_w, _), _ = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
        cv2.rectangle(frame, (5, 5), (15 + text_w, 40), (0, 0, 0), -1)
        cv2.putText(frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    def _is_inside_roi(self, box: tuple[float, float, float, float], roi_pixels: tuple[int, int, int, int]) -> bool:
        """Check if bounding box center is in ROI with expanded tolerance."""
        x1, y1, x2, y2 = box
        roi_x1, roi_y1, roi_x2, roi_y2 = roi_pixels
        # Use bbox center with expanded tolerance (25px margin) for edge cases
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        margin = 25  # pixels, for detecting people at ROI edges
        return (roi_x1 - margin) < cx < (roi_x2 + margin) and (roi_y1 - margin) < cy < (roi_y2 + margin)

    def _roi_pixels(self, width: int, height: int) -> tuple[int, int, int, int]:
        rx1, ry1, rx2, ry2 = self.roi
        return (
            int(rx1 * width),
            int(ry1 * height),
            int(rx2 * width),
            int(ry2 * height),
        )

    def _validate_roi(self, roi: Tuple[float, float, float, float]) -> None:
        if len(roi) != 4:
            raise ValueError("ROI must be a tuple of four floats: (x_min, y_min, x_max, y_max)")
        x1, y1, x2, y2 = roi
        for value in roi:
            if not 0.0 <= value <= 1.0:
                raise ValueError("ROI values must be between 0.0 and 1.0")
        if not (x1 < x2 and y1 < y2):
            raise ValueError("ROI must have x_min < x_max and y_min < y_max")

    def _validate_confidence(self, confidence: float) -> None:
        if not 0.0 < confidence <= 1.0:
            raise ValueError("detection_confidence must be between 0 and 1")

    def _create_socket(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        print(f"Broadcasting to {self.broadcast_ip}:{self.broadcast_port}...", flush=True)
        return sock

    def _send_update(self, sock: socket.socket, timestamp: float) -> None:
        """Build and send v2.1 packet."""
        # Use cached state output from analyze_frame (preserves phone_just_exited flag)
        if self._latest_state_output is None:
            return  # No frame analyzed yet
        
        state_output = self._latest_state_output

        # Get people list
        people = list(self._tracked_people.values())

        # Generate palette from people colors
        people_colors = [p.shirt_rgb for p in people]
        dominant_palette = get_palette_from_people(people_colors, max_colors=4)

        # Check for color contrasts
        colors_contrasting = False
        if len(people_colors) >= 2:
            colors_contrasting = are_colors_contrasting(people_colors[0], people_colors[1])

        # Generate prompt
        phone_flag = len(people) > 0 and any(p for p in people)  # Simplified
        context = StateContext(
            people_count=len(people),
            phone_detected=self.state_machine.state == State.PHONE,
            timestamp=timestamp,
        )
        
        # Debug: Log state output flags
        if state_output.phone_just_exited:
            print(f"📥 Detector received phone_just_exited=True", flush=True)
        
        # Handle phone exit celebration (time-based)
        celebration_prompt = None
        if state_output.phone_just_exited:
            # Phone was just removed - celebrate for configured duration
            # Clear any cached prompts so we don't show stale PHONE prompts after celebration
            self.prompt_generator.force_regenerate()
            self._celebration_prompt = self.prompt_generator.get_phone_exit_prompt()
            celebration_prompt = self._celebration_prompt
            self._celebration_until = timestamp + self._celebration_duration
            print(f"🎉 CELEBRATION! Phone removed: '{celebration_prompt}'", flush=True)
            if self.audio_manager:
                self.audio_manager.play_sfx("party_horn", volume=0.7)
        elif self._celebration_until is not None and timestamp < self._celebration_until:
            celebration_prompt = self._celebration_prompt
        else:
            # Celebration ended, clear stored prompt
            self._celebration_prompt = None
            self._celebration_until = None
        
        # Use celebration prompt if in celebration mode, otherwise normal logic
        if celebration_prompt is not None:
            prompt = celebration_prompt
        # Handle entry flash and prompts
        elif state_output.entry_flash_id and state_output.entry_flash_id != self._last_entry_id:
            # New person entry
            person = self._tracked_people.get(state_output.entry_flash_id)
            if person:
                prompt = self.prompt_generator.get_entry_prompt(person.shirt_name)
                if self.audio_manager:
                    self.audio_manager.play_sfx("whoosh", volume=0.65)
            else:
                prompt = self.prompt_generator.generate(
                    state_output.state,
                    len(people),
                    len(set(p.shirt_rgb for p in people)),
                    colors_contrasting,
                )
            self._last_entry_id = state_output.entry_flash_id
        elif state_output.pulse_active:
            # Color pulse
            color_names = [p.shirt_name for p in people]
            prompt = self.prompt_generator.get_pulse_prompt(color_names)
            if self.audio_manager:
                self.audio_manager.play_sfx("chime", volume=0.3)
        else:
            # Normal prompt
            cooldown_override = None
            if self._last_prompt_state == state_output.state:
                cooldown_override = self._same_state_cooldown
            prompt = self.prompt_generator.generate(
                state_output.state,
                len(people),
                len(set(p.shirt_rgb for p in people)),
                colors_contrasting,
                cooldown_override=cooldown_override,
            )

        self._last_prompt_state = state_output.state

        # Narrate prompts when they change
        if self.audio_manager and self.audio_manager.narration_enabled:
            if prompt != self._last_narrated_prompt:
                self.audio_manager.speak(prompt)
                self._last_narrated_prompt = prompt
        
        # Update last sent prompt only if it actually changed
        # This prevents ESP32 from seeing redundant updates and resetting the scroll
        if prompt != self._last_sent_prompt:
            self._last_sent_prompt = prompt

        # Determine audio state
        audio_state = self._map_audio_state(state_output.state)
        
        # Trigger audio changes and build-up effects
        if audio_state != self._last_audio_state and self.audio_manager:
            self.audio_manager.set_state(audio_state)
            self._last_audio_state = audio_state
        
        # Update fire crackle volume with fire intensity in AMBIENT state
        if audio_state == AudioState.AMBIENT and self.audio_manager:
            self.audio_manager.set_fire_intensity(state_output.fire_intensity)
        
        # Trigger build-up audio when party buildup starts
        if state_output.party_buildup_progress > 0.0 and not self._party_buildup_started:
            if self.audio_manager:
                self.audio_manager.play_sfx("buildup_start", volume=0.75)
            self._party_buildup_started = True
        elif state_output.party_buildup_progress == 0.0:
            self._party_buildup_started = False
        
        # Trigger intermediate buildup SFX at key points (33%, 66%)
        buildup_step = int(state_output.party_buildup_progress * 3)
        if buildup_step > self._last_buildup_step:
            if self.audio_manager and buildup_step in (1, 2):
                self.audio_manager.play_sfx("buildup_pulse", volume=0.55)
            self._last_buildup_step = buildup_step

        # Build packet
        is_celebrating = self._celebration_until is not None and timestamp < self._celebration_until
        packet = self.packet_builder.build(
            state=state_output.state,
            people=people,
            phone_detected=context.phone_detected,
            dominant_palette=dominant_palette,
            prompt=prompt,
            mist_pwm=state_output.mist_pwm,
            fan_pwm=state_output.fan_pwm,
            fire_intensity=state_output.fire_intensity,
            pulse_active=state_output.pulse_active,
            entry_flash_id=state_output.entry_flash_id,
            audio_state=audio_state,
            party_buildup_progress=state_output.party_buildup_progress,
            celebration=is_celebrating,
        )

        # Send packet
        try:
            message = json.dumps(packet, separators=(",", ":")).encode("utf-8")
            sock.sendto(message, (self.broadcast_ip, self.broadcast_port))
        except OSError as exc:
            print(f"Network Error: {exc}", flush=True)

    def _map_audio_state(self, state: State) -> AudioState:
        """Map state machine state to audio state."""
        if state == State.IDLE:
            return AudioState.SILENT
        elif state == State.FIRE:
            return AudioState.AMBIENT
        elif state == State.PARTY:
            return AudioState.PARTY
        elif state == State.PHONE:
            return AudioState.ALERT
        return AudioState.SILENT