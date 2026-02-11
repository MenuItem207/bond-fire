"""Command-line interface for the Bond Fire vision module."""

from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
import json
from typing import Tuple

from .audio_manager import AudioManager, AudioState
from .color_analysis import are_colors_contrasting, get_palette_from_people
from .detector import BondFireVision
from .config import get_config
from .local_prompts import LocalPromptGenerator
from .packet_builder import PacketBuilderV2, Person
from .state_machine import State, StateContext, StateMachine


def _parse_roi(values: list[float]) -> Tuple[float, float, float, float]:
    if len(values) != 4:
        raise argparse.ArgumentTypeError("ROI expects four floats: x_min y_min x_max y_max")
    roi = tuple(values)
    for value in roi:
        if not 0.0 <= value <= 1.0:
            raise argparse.ArgumentTypeError("ROI values must be between 0.0 and 1.0")
    x1, y1, x2, y2 = roi
    if not (x1 < x2 and y1 < y2):
        raise argparse.ArgumentTypeError("ROI must satisfy x_min < x_max and y_min < y_max")
    return (x1, y1, x2, y2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Bond Fire vision detector (v2.0).")
    parser.add_argument("--model", default="yolov8x.pt", help="Path to a YOLOv8 weights file (yolov8x.pt recommended for best phone detection).")
    parser.add_argument("--camera-index", type=int, default=0, help="Index of the camera to open.")
    parser.add_argument("--frame-width", type=int, default=None, help="Camera capture width.")
    parser.add_argument("--frame-height", type=int, default=None, help="Camera capture height.")
    parser.add_argument("--imgsz", type=int, default=None, help="YOLO inference size.")
    parser.add_argument(
        "--roi",
        type=float,
        nargs=4,
        default=(0.0, 0.0, 1.0, 1.0),
        metavar=("X_MIN", "Y_MIN", "X_MAX", "Y_MAX"),
        help="Active zone bounds as normalized floats.",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.35,
        help="Minimum detection confidence between 0 and 1.",
    )
    parser.add_argument(
        "--no-display",
        action="store_true",
        help="Disable the OpenCV preview window (useful on headless devices).",
    )
    parser.add_argument(
        "--manual-state",
        action="store_true",
        help="Run in manual state mode (CLI input instead of camera).",
    )
    parser.add_argument(
        "--broadcast-ip",
        default="255.255.255.255",
        help="UDP broadcast IP address.",
    )
    parser.add_argument(
        "--broadcast-port",
        type=int,
        default=4210,
        help="UDP port the ESP32 listens on.",
    )
    parser.add_argument(
        "--updates-per-second",
        type=float,
        default=60.0,
        help="Target UDP broadcast rate (packets/sec).",
    )
    parser.add_argument(
        "--pulse-interval",
        type=float,
        default=15.0,
        help="Seconds between color pulses in FIRE mode.",
    )
    parser.add_argument(
        "--enable-audio",
        action="store_true",
        help="Enable audio subsystem (SFX, music, TTS).",
    )
    parser.add_argument(
        "--audio-volume",
        type=float,
        default=0.7,
        help="Master audio volume (0.0-1.0).",
    )
    parser.add_argument(
        "--narration-enabled",
        action="store_true",
        help="Enable TTS narration for prompts.",
    )
    parser.add_argument(
        "--tts-voice",
        default=None,
        help="TTS voice selection: 'male' (default deep narrator), 'female', or specific voice name.",
    )
    
    # Legacy OpenAI parameters (kept for backward compatibility, ignored)
    parser.add_argument(
        "--ai-prompts",
        action="store_true",
        help="(Legacy) Ignored in v2. Use local prompts.",
    )
    parser.add_argument(
        "--ai-api-key",
        help="(Legacy) Ignored in v2.",
    )
    parser.add_argument(
        "--ai-interval",
        type=float,
        help="(Legacy) Ignored in v2.",
    )
    parser.add_argument(
        "--ai-model",
        help="(Legacy) Ignored in v2.",
    )

    args = parser.parse_args()

    if not 0.0 < args.confidence <= 1.0:
        parser.error("--confidence must be between 0 and 1")
    if args.broadcast_port <= 0 or args.broadcast_port > 65535:
        parser.error("--broadcast-port must be between 1 and 65535")
    if args.updates_per_second < 0:
        parser.error("--updates-per-second must be non-negative")
    if args.pulse_interval <= 0:
        parser.error("--pulse-interval must be positive")
    if not 0.0 <= args.audio_volume <= 1.0:
        parser.error("--audio-volume must be between 0.0 and 1.0")

    roi = _parse_roi(list(args.roi))

    # Warn about legacy flags
    if args.ai_prompts or args.ai_api_key or args.ai_interval or args.ai_model:
        print("Warning: OpenAI flags are ignored in v2. Using local prompts.", flush=True)

    try:
        if args.manual_state:
            _run_manual_state(
                broadcast_ip=args.broadcast_ip,
                broadcast_port=args.broadcast_port,
                updates_per_second=args.updates_per_second,
                pulse_interval=args.pulse_interval,
                enable_audio=args.enable_audio,
                audio_volume=args.audio_volume,
                narration_enabled=args.narration_enabled,
                tts_voice=args.tts_voice,
            )
        else:
            vision = BondFireVision(
                model_path=args.model,
                capture_index=args.camera_index,
                frame_width=args.frame_width,
                frame_height=args.frame_height,
                imgsz=args.imgsz,
                roi=roi,
                detection_confidence=args.confidence,
                broadcast_ip=args.broadcast_ip,
                broadcast_port=args.broadcast_port,
                updates_per_second=args.updates_per_second,
                pulse_interval=args.pulse_interval,
                enable_audio=args.enable_audio,
                audio_volume=args.audio_volume,
                narration_enabled=args.narration_enabled,
                tts_voice=args.tts_voice,
            )
            vision.run(display=not args.no_display)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def _run_manual_state(
    broadcast_ip: str,
    broadcast_port: int,
    updates_per_second: float,
    pulse_interval: float,
    enable_audio: bool,
    audio_volume: float,
    narration_enabled: bool,
    tts_voice: str | None,
) -> None:
    send_interval = 1.0 / updates_per_second if updates_per_second > 0 else 0.1
    sock = _create_socket(broadcast_ip, broadcast_port)
    packet_builder = PacketBuilderV2()
    state_machine = StateMachine(pulse_interval=pulse_interval)
    prompt_generator = LocalPromptGenerator()
    cfg = get_config()
    same_state_cooldown = cfg.prompts.same_state_cooldown

    audio_manager: AudioManager | None = None
    if enable_audio:
        audio_manager = AudioManager(
            enabled=True,
            master_volume=audio_volume,
            narration_enabled=narration_enabled,
            tts_voice=tts_voice,
        )
        audio_manager.start()

    state_lock = threading.Lock()
    manual_state = {
        "people_count": 0,
        "phone_detected": False,
        "fan_power": 0.0,
    }
    last_entry_id: int | None = None
    celebration_frames_remaining = 0
    celebration_prompt: str | None = None
    last_prompt_state: State | None = None

    def _set_state(people_count: int, phone_detected: bool, fan_power: float = 0.0) -> None:
        with state_lock:
            manual_state["people_count"] = people_count
            manual_state["phone_detected"] = phone_detected
            manual_state["fan_power"] = fan_power

    def _worker() -> None:
        nonlocal last_entry_id
        nonlocal celebration_frames_remaining
        nonlocal celebration_prompt
        nonlocal last_prompt_state
        last_audio_state = AudioState.SILENT
        last_log = 0.0
        colors = [
            (255, 120, 60),
            (200, 80, 40),
            (255, 200, 80),
            (120, 200, 255),
            (180, 120, 255),
        ]
        while True:
            now = time.monotonic()
            with state_lock:
                people_count = manual_state["people_count"]
                phone_detected = manual_state["phone_detected"]
                fan_power = manual_state["fan_power"]

            context = StateContext(
                people_count=people_count,
                phone_detected=phone_detected,
                fan_power=fan_power,
                timestamp=now,
            )
            active_ids = set(range(1, people_count + 1))
            state_output = state_machine.update(context, active_ids)
            state = state_output.state

            people = _make_people(people_count, colors)
            people_colors = [p.shirt_rgb for p in people]
            dominant_palette = get_palette_from_people(people_colors, max_colors=4)
            colors_contrasting = False
            if len(people_colors) >= 2:
                colors_contrasting = are_colors_contrasting(people_colors[0], people_colors[1])

            mist_pwm = state_output.mist_pwm
            fan_pwm = state_output.fan_pwm
            fire_intensity = state_output.fire_intensity
            if state_output.phone_just_exited:
                prompt_generator.force_regenerate()
                celebration_prompt = prompt_generator.get_phone_exit_prompt()
                celebration_frames_remaining = 10
                prompt = celebration_prompt
            elif celebration_frames_remaining > 0:
                celebration_frames_remaining -= 1
                prompt = celebration_prompt or prompt_generator.get_phone_exit_prompt()
            else:
                celebration_prompt = None
                same_state_hold = (
                    last_prompt_state == state
                    and prompt_generator.is_cooldown_active(state, cooldown_override=same_state_cooldown)
                )
                if same_state_hold:
                    prompt = prompt_generator.generate(
                        state_output.state,
                        people_count,
                        len(set(p.shirt_rgb for p in people)),
                        colors_contrasting,
                        cooldown_override=same_state_cooldown,
                    )
                elif state_output.entry_flash_id and state_output.entry_flash_id != last_entry_id:
                    prompt = prompt_generator.get_entry_prompt()
                    last_entry_id = state_output.entry_flash_id
                elif state_output.pulse_active:
                    color_names = [p.shirt_name for p in people if p.shirt_name]
                    prompt = prompt_generator.get_pulse_prompt(color_names)
                else:
                    prompt = prompt_generator.generate(
                        state_output.state,
                        people_count,
                        len(set(p.shirt_rgb for p in people)),
                        colors_contrasting,
                        cooldown_override=same_state_cooldown if last_prompt_state == state else None,
                    )

            last_prompt_state = state

            audio_state = _map_audio_state(state)
            if audio_manager and audio_state != last_audio_state:
                audio_manager.set_state(audio_state)
                last_audio_state = audio_state
            if audio_manager and audio_state in (AudioState.AMBIENT, AudioState.PARTY):
                audio_manager.set_fire_intensity(fire_intensity)

            packet = packet_builder.build(
                state=state,
                people=people,
                phone_detected=phone_detected,
                dominant_palette=dominant_palette,
                prompt=prompt,
                mist_pwm=mist_pwm,
                fan_pwm=fan_pwm,
                wind=int(round(fan_power)),
                fire_intensity=fire_intensity,
                pulse_active=state_output.pulse_active,
                entry_flash_id=state_output.entry_flash_id,
                audio_state=audio_state,
                party_buildup_progress=state_output.party_buildup_progress,
                celebration=state_output.phone_just_exited,
            )

            try:
                message = json.dumps(packet, separators=(",", ":")).encode("utf-8")
                sock.sendto(message, (broadcast_ip, broadcast_port))
            except OSError as exc:
                print(f"Network Error: {exc}", flush=True)

            if now - last_log >= 1.0:
                print(
                    f"[MANUAL] {state.value} | people={people_count} | fire={fire_intensity:.2f} | wind={fan_power:.0f}",
                    flush=True,
                )
                last_log = now

            time.sleep(send_interval)

    worker_thread = threading.Thread(target=_worker, name="manual-state-worker", daemon=True)
    worker_thread.start()
    print("Manual state mode active. Choose a scenario below.", flush=True)

    try:
        while True:
            _print_manual_menu()
            choice = input("Select scenario: ").strip()
            if choice == "1":
                _set_state(0, False, 0.0)
            elif choice == "2":
                _set_state(1, False, 0.0)
            elif choice == "3":
                _set_state(3, False, 0.0)
            elif choice == "4":
                _set_state(4, False, 0.0)
            elif choice == "5":
                _set_state(5, False, 0.0)
            elif choice == "6":
                _set_state(3, True, 20.0)
            elif choice == "7":
                _set_state(3, True, 80.0)
            elif choice == "8":
                _set_state(3, False, 0.0)
            elif choice == "9":
                break
            else:
                print("Invalid selection. Try again.", flush=True)
    finally:
        if audio_manager:
            audio_manager.stop()
        try:
            sock.close()
        except OSError:
            pass


def _print_manual_menu() -> None:
    print("\nManual State Mode", flush=True)
    print("1) IDLE (0 people)", flush=True)
    print("2) FIRE (1 person)", flush=True)
    print("3) FIRE (3 people)", flush=True)
    print("4) FIRE (4 people)", flush=True)
    print("5) PARTY (5 people)", flush=True)
    print("6) PHONE_IDLE (3 people, low wind)", flush=True)
    print("7) FANNING (3 people, high wind)", flush=True)
    print("8) PHONE removed (3 people)", flush=True)
    print("9) Quit", flush=True)


def _create_socket(broadcast_ip: str, broadcast_port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    print(f"Broadcasting to {broadcast_ip}:{broadcast_port}...", flush=True)
    return sock


def _make_people(count: int, colors: list[tuple[int, int, int]]) -> list[Person]:
    people: list[Person] = []
    for idx in range(count):
        color = colors[idx % len(colors)]
        x = 0.2 + 0.15 * (idx % 4)
        y = 0.3 + 0.2 * (idx // 4)
        bbox = (x, y, min(x + 0.1, 0.95), min(y + 0.2, 0.95))
        people.append(
            Person(
                id=idx + 1,
                bbox=bbox,
                shirt_rgb=color,
                shirt_name="",
            )
        )
    return people


def _map_audio_state(state: State) -> AudioState:
    if state == State.IDLE:
        return AudioState.SILENT
    if state == State.FIRE:
        return AudioState.AMBIENT
    if state == State.PARTY:
        return AudioState.PARTY
    if state in (State.PHONE_IDLE, State.FANNING):
        return AudioState.AMBIENT
    return AudioState.SILENT

if __name__ == "__main__":
    main()
