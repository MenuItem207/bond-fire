from __future__ import annotations

import json
import socket
import threading
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
from .firebase_shake import FirebaseShakeListener
from .packet_builder import PacketBuilderV2, Person
from .state_machine import State, StateContext, StateMachine


@dataclass(eq=True)
class VisionState:
    """Detection state (for backward compatibility)."""

    people_in_roi: int


class BondFireVision:
    """People detection within a configurable active zone."""

    CLASS_PERSON = 0

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        capture_index: int = 0,
        camera_backend: str | None = None,
        frame_width: int | None = None,
        frame_height: int | None = None,
        imgsz: int | None = None,
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
        self.camera_backend = camera_backend
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
        self._same_state_cooldown = cfg.prompts.same_state_cooldown
        self._min_person_area_ratio = max(0.0, cfg.vision.min_person_area_ratio)
        self._frame_width = frame_width or cfg.vision.frame_width
        self._frame_height = frame_height or cfg.vision.frame_height
        self._imgsz = imgsz or cfg.vision.imgsz
        self._iou_threshold = cfg.vision.iou_threshold

        # RTDB shake listener (lazy init to avoid impacting camera startup)
        self._shake_listener: Optional[FirebaseShakeListener] = None
        self._firebase_cfg = cfg.firebase if cfg.firebase.enabled else None
        self._shake_listener_lock = threading.Lock()
        self._shake_listener_thread_started = False
        self._wind_udp_cfg = cfg.wind_udp
        self._wind_udp_value = 0
        self._wind_udp_last_update = 0.0
        self._wind_udp_lock = threading.Lock()

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
        self._latest_state_output: Optional[Any] = None  # Cache latest state output for packet building
        self._last_narrated_prompt: Optional[str] = None  # Track last narrated prompt to avoid repeats
        self._last_sent_prompt: Optional[str] = None  # Cache prompt to prevent unnecessary resets
        self._last_prompt_state: Optional[State] = None
        self._entry_prompt_id: Optional[int] = None
        self._entry_prompt_until: Optional[float] = None
        self._entry_prompt: Optional[str] = None
        self._pulse_prompt_until: Optional[float] = None
        self._pulse_prompt: Optional[str] = None
        self._pulse_prompt_duration = 2.0
        self._pulse_active_last = False

    def run(self, display: bool = True) -> VisionState:
        """
        Start the capture loop.

        Args:
            display: Whether to show the annotated OpenCV window.
        Returns:
            Last known detection state.
        """
        sock = self._create_socket()
        self.cap = self._open_camera()
        if not self.cap or not self.cap.isOpened():
            raise RuntimeError(
                "Could not open video source. Check camera index and macOS camera permissions for the Python/Terminal app."
            )
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._frame_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._frame_height)

        if display:
            try:
                cv2.namedWindow("Bond Fire Vision", cv2.WINDOW_NORMAL)
            except cv2.error as exc:
                print(f"⚠️  OpenCV display init failed: {exc}")
                print("ℹ️  Continuing without preview window.")
                display = False

        print(
            "Starting vision system. Press 'q' to exit." if display else "Starting vision system. Ctrl+C to exit.",
            flush=True,
        )
        print(f"Bondfire v2.0 - Master/Slave Architecture", flush=True)

        # Start audio manager
        if self.audio_manager:
            self.audio_manager.start()

        # Defer RTDB listener initialization until after the first frame.
        shake_listener_started = False

        previous_state: VisionState | None = None
        state = VisionState(people_in_roi=0)
        last_send = 0.0
        frames_read = 0
        last_heartbeat = time.monotonic()
        heartbeat_interval = 5.0
        last_frame_time = time.monotonic()
        stop_event = threading.Event()
        wind_udp_thread: Optional[threading.Thread] = None

        if self._wind_udp_cfg.enabled:
            wind_udp_thread = threading.Thread(
                target=self._wind_udp_listener,
                args=(stop_event,),
                daemon=True,
            )
            wind_udp_thread.start()

        def camera_watchdog() -> None:
            nonlocal last_frame_time
            while not stop_event.is_set():
                now = time.monotonic()
                if now - last_frame_time > 5.0:
                    print(
                        "⚠️  No camera frames received in 5s. Camera may be in use or permissions blocked.",
                        flush=True,
                    )
                    # Avoid spamming logs if the camera remains blocked
                    last_frame_time = now
                time.sleep(1.0)

        watchdog_thread = threading.Thread(target=camera_watchdog, daemon=True)
        watchdog_thread.start()

        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    raise RuntimeError("Failed to read frame from camera")

                if self._firebase_cfg and not shake_listener_started:
                    self._start_firebase_listener_async()
                    shake_listener_started = True

                frames_read += 1
                last_frame_time = time.monotonic()

                state, processed_frame = self.analyze_frame(frame, annotate=display)
                now = time.monotonic()
                
                if self.send_interval == 0.0 or now - last_send >= self.send_interval:
                    self._send_update(sock, now)
                    last_send = now

                if now - last_heartbeat >= heartbeat_interval:
                    stats = self.packet_builder.get_stats()
                    print(
                        f"Heartbeat: {frames_read} frames, {stats['total_packets']} packets sent",
                        flush=True,
                    )
                    frames_read = 0
                    last_heartbeat = now

                if display:
                    try:
                        cv2.imshow("Bond Fire Vision", processed_frame)
                        if cv2.waitKey(1) & 0xFF == ord("q"):
                            break
                    except cv2.error as exc:
                        print(f"⚠️  OpenCV display error: {exc}")
                        print("ℹ️  Disabling preview window and continuing headless.")
                        display = False
                else:
                    if state != previous_state:
                        wind = self._shake_listener.get_wind_value() if self._shake_listener else 0
                        print(
                            f"Active zone: {state.people_in_roi} people | Wind: {wind:.0f}%",
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
            stop_event.set()
            if self.cap is not None:
                self.cap.release()
                self.cap = None
            if display:
                cv2.destroyAllWindows()
            if self.audio_manager:
                self.audio_manager.stop()
            if self._shake_listener:
                self._shake_listener.stop()

            # Print stats
            stats = self.packet_builder.get_stats()
            print(f"Session stats: {stats['total_packets']} packets, avg {stats['average_fps']:.1f} fps", flush=True)

        return state

    def _start_firebase_listener_async(self) -> None:
        with self._shake_listener_lock:
            if self._shake_listener_thread_started or not self._firebase_cfg:
                return
            self._shake_listener_thread_started = True

        def _worker() -> None:
            listener = FirebaseShakeListener(
                firebase_url=self._firebase_cfg.database_url,
                credentials_path=self._firebase_cfg.credentials_path,
                max_concurrent_shakes=self._firebase_cfg.max_concurrent_shakes,
                shake_timeout=self._firebase_cfg.shake_timeout,
                wind_max=self._firebase_cfg.wind_max,
            )
            listener.start()
            with self._shake_listener_lock:
                self._shake_listener = listener

        threading.Thread(target=_worker, daemon=True).start()

    def _open_camera(self) -> cv2.VideoCapture | None:
        """Open a camera with sensible backend fallbacks on macOS."""
        backend_override = None
        if self.camera_backend == "avf":
            backend_override = cv2.CAP_AVFOUNDATION
        elif self.camera_backend == "any":
            backend_override = cv2.CAP_ANY
        elif self.camera_backend == "default":
            backend_override = None

        backends = []
        if backend_override is not None:
            backends.append(backend_override)
        backends.extend([cv2.CAP_AVFOUNDATION, cv2.CAP_ANY])
        for backend in backends:
            cap = cv2.VideoCapture(self.capture_index, backend)
            if cap.isOpened():
                backend_name = "AVFOUNDATION" if backend == cv2.CAP_AVFOUNDATION else "ANY"
                print(f"📷 Camera opened (index={self.capture_index}, backend={backend_name})", flush=True)
                return cap
            cap.release()

        cap = cv2.VideoCapture(self.capture_index)
        if cap.isOpened():
            print(f"📷 Camera opened (index={self.capture_index}, backend=default)", flush=True)
            return cap
        cap.release()
        return None

    def analyze_frame(self, frame: Any, annotate: bool = True) -> tuple[VisionState, Any]:
        """Analyze a single frame with tracking and color extraction."""
        height, width = frame.shape[:2]
        roi_pixels = self._roi_pixels(width, height)

        person_count = 0
        people_in_roi: list[Person] = []

        if annotate:
            self._draw_roi(frame, roi_pixels)

        # Use track() for people detection only
        results = self.model.track(
            frame,
            persist=True,
            verbose=False,
            conf=self.detection_confidence,
            iou=self._iou_threshold,
            imgsz=self._imgsz,
        )
        
        for result in results:
            if result.boxes is None or result.boxes.id is None:
                continue
                
            for box, track_id in zip(result.boxes, result.boxes.id):
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
                tid = int(track_id)

                if cls == self.CLASS_PERSON:
                    if conf < self.detection_confidence:
                        continue
                    box_area_ratio = ((x2 - x1) * (y2 - y1)) / max(1.0, (width * height))
                    if box_area_ratio < self._min_person_area_ratio:
                        if annotate:
                            # Show filtered-out small people in gray
                            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (128, 128, 128), 1)
                            cv2.putText(frame, f"TOO SMALL ({box_area_ratio:.3f})", (int(x1), max(int(y1) - 10, 0)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (128, 128, 128), 1)
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

        # Phone detection removed - using MQTT shake detection instead

        # Phone detection removed - using MQTT shake detection instead

        # Update state machine (no phone detection)
        context = StateContext(
            people_count=person_count,
            timestamp=time.monotonic(),
        )
        active_ids = {p.id for p in people_in_roi}
        state_output = self.state_machine.update(context, active_ids)
        
        # Cache state output for packet building in _send_update
        self._latest_state_output = state_output

        # Store people for packet building
        self._tracked_people = {p.id: p for p in people_in_roi}

        state = VisionState(people_in_roi=person_count)

        if annotate:
            self._draw_status(frame, state, state_output.state)

        return state, frame

    def _draw_roi(self, frame, roi_pixels: tuple[int, int, int, int]) -> None:
        x1, y1, x2, y2 = roi_pixels
        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 0), 2)
        cv2.putText(frame, "Active Zone", (x1, max(y1 - 10, 0)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

    def _draw_status(self, frame, state: VisionState, current_state: State) -> None:
        """Draw status overlay on frame."""
        wind_value = self._get_wind_value(time.monotonic())
        status_text = f"{current_state.value}: {state.people_in_roi} people | Wind: {wind_value}%"
        color = (0, 255, 0)
        (text_w, _), _ = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
        cv2.rectangle(frame, (5, 5), (15 + text_w, 40), (0, 0, 0), -1)
        cv2.putText(frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        # Wind bar (shows MQTT shake-based wind value if enabled)
        if self._shake_listener is not None:
            wind_value = self._shake_listener.get_wind_value()
            height, width = frame.shape[:2]
            bar_w = int(width * 0.35)
            bar_h = 18
            x1 = 10
            y1 = height - bar_h - 12
            x2 = x1 + bar_w
            y2 = y1 + bar_h
            cv2.rectangle(frame, (x1, y1), (x2, y2), (40, 40, 40), 2)
            fill_w = int(bar_w * (max(0.0, min(100.0, wind_value)) / 100.0))
            if fill_w > 2:
                cv2.rectangle(frame, (x1 + 2, y1 + 2), (x1 + fill_w - 2, y2 - 2), (0, 140, 255), -1)
            cv2.putText(
                frame,
                f"Wind: {wind_value:5.1f}%",
                (x1, y1 - 6),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                2,
            )


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
        # Use cached state output from analyze_frame
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

        # Handle entry flash and prompts
        if state_output.entry_flash_id:
            if (
                self._entry_prompt_id != state_output.entry_flash_id
                or self._entry_prompt_until is None
                or timestamp >= self._entry_prompt_until
            ):
                person = self._tracked_people.get(state_output.entry_flash_id)
                if person:
                    self._entry_prompt = self.prompt_generator.get_entry_prompt(person.shirt_name)
                    if self.audio_manager:
                        self.audio_manager.play_sfx("whoosh", volume=0.65)
                else:
                    self._entry_prompt = self.prompt_generator.generate(
                        state_output.state,
                        len(people),
                        len(set(p.shirt_rgb for p in people)),
                        colors_contrasting,
                    )
                self._entry_prompt_id = state_output.entry_flash_id
                self._entry_prompt_until = timestamp + self.state_machine.ENTRY_FLASH_DURATION
            prompt = self._entry_prompt or ""
            self._last_entry_id = state_output.entry_flash_id
        elif state_output.pulse_active:
            if not self._pulse_active_last:
                color_names = sorted(p.shirt_name for p in people if p.shirt_name)
                self._pulse_prompt = self.prompt_generator.get_pulse_prompt(color_names)
                self._pulse_prompt_until = timestamp + self._pulse_prompt_duration
                if self.audio_manager:
                    self.audio_manager.play_sfx("chime", volume=0.3)
            prompt = self._pulse_prompt or ""
        else:
            self._entry_prompt_id = None
            self._entry_prompt_until = None
            self._entry_prompt = None
            self._pulse_prompt_until = None
            self._pulse_prompt = None
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

        self._pulse_active_last = state_output.pulse_active
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
        wind_value = self._get_wind_value(timestamp)
        packet = self.packet_builder.build(
            state=state_output.state,
            people=people,
            dominant_palette=dominant_palette,
            prompt=prompt,
            mist_pwm=state_output.mist_pwm,
            fan_pwm=state_output.fan_pwm,
            wind=wind_value,
            fire_intensity=state_output.fire_intensity,
            pulse_active=state_output.pulse_active,
            entry_flash_id=state_output.entry_flash_id,
            audio_state=audio_state,
            party_buildup_progress=state_output.party_buildup_progress,
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
        return AudioState.SILENT

    def _get_wind_value(self, now: float) -> int:
        if self._wind_udp_cfg.enabled:
            with self._wind_udp_lock:
                if now - self._wind_udp_last_update <= self._wind_udp_cfg.timeout:
                    return self._wind_udp_value
                if self._wind_udp_value > 0 and now - self._wind_udp_last_update <= 0.5:
                    return self._wind_udp_value
        return self._shake_listener.get_wind_value() if self._shake_listener else 0

    def _wind_udp_listener(self, stop_event: threading.Event) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self._wind_udp_cfg.listen_host, self._wind_udp_cfg.listen_port))
        sock.settimeout(0.5)
        print(
            f"Listening for wind UDP on {self._wind_udp_cfg.listen_host}:{self._wind_udp_cfg.listen_port}",
            flush=True,
        )

        while not stop_event.is_set():
            try:
                data, _addr = sock.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break

            wind_value = None
            try:
                payload = json.loads(data.decode("utf-8"))
                if isinstance(payload, dict):
                    wind_value = payload.get("wind")
                else:
                    wind_value = payload
            except (json.JSONDecodeError, UnicodeDecodeError):
                try:
                    wind_value = int(data.decode("utf-8").strip())
                except (ValueError, UnicodeDecodeError):
                    wind_value = None

            if wind_value is None:
                continue

            try:
                wind_value = int(float(wind_value))
            except (TypeError, ValueError):
                continue

            wind_value = max(0, min(100, wind_value))
            with self._wind_udp_lock:
                self._wind_udp_value = wind_value
                self._wind_udp_last_update = time.monotonic()
            print(f"Received wind={wind_value}", flush=True)

        sock.close()
