"""Command-line interface for the Bond Fire vision module."""

from __future__ import annotations

import argparse
import socket
import sys
import threading
from pynput import keyboard
import time
import json
import random
from typing import Tuple

from .audio_manager import AudioManager, AudioState
from .detector import BondFireVision
from .config import get_config
from .firebase_shake import FirebaseShakeListener
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
    parser.add_argument("--model", default="yolov8n.pt", help="Path to a YOLOv8 weights file (yolov8n.pt for fastest performance).")
    parser.add_argument("--camera-index", type=int, default=0, help="Index of the camera to open.")
    parser.add_argument(
        "--camera-backend",
        choices=["avf", "any", "default"],
        default=None,
        help="Camera backend override (macOS: 'avf' often works best).",
    )
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
        help="Seconds between pulses (unused).",
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
                camera_backend=args.camera_backend,
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
    wind_udp_cfg = cfg.wind_udp
    shake_listener: FirebaseShakeListener | None = None

    if cfg.firebase.enabled:
        shake_listener = FirebaseShakeListener(
            firebase_url=cfg.firebase.database_url,
            credentials_path=cfg.firebase.credentials_path,
            max_concurrent_shakes=cfg.firebase.max_concurrent_shakes,
            shake_timeout=cfg.firebase.shake_timeout,
            wind_max=cfg.firebase.wind_max,
        )
        shake_listener.start()

    audio_manager: AudioManager | None = None
    if enable_audio:
        audio_manager = AudioManager(
            enabled=True,
            master_volume=audio_volume,
            narration_enabled=narration_enabled,
            tts_voice=tts_voice,
        )
        audio_manager.start()

    stop_event = threading.Event()
    state_lock = threading.Lock()
    manual_state = {
        "people_count": 0,
        "wind_value": 0,
        "wind_last_update": 0.0,
        "wind_colors": [],
    }
    last_entry_id: int | None = None
    last_prompt_state: State | None = None

    def _set_state(people_count: int) -> None:
        with state_lock:
            manual_state["people_count"] = people_count

    def _wind_udp_listener() -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((wind_udp_cfg.listen_host, wind_udp_cfg.listen_port))
        sock.settimeout(0.5)
        print(
            f"Listening for wind UDP on {wind_udp_cfg.listen_host}:{wind_udp_cfg.listen_port}",
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
            colors_value = None
            try:
                payload = json.loads(data.decode("utf-8"))
                if isinstance(payload, dict):
                    wind_value = payload.get("wind")
                    colors_value = payload.get("colors")
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
            colors: list[tuple[int, int, int]] = []
            if isinstance(colors_value, list):
                for item in colors_value:
                    if isinstance(item, list) and len(item) >= 3:
                        try:
                            colors.append((int(item[0]), int(item[1]), int(item[2])))
                        except (TypeError, ValueError):
                            continue
            with state_lock:
                manual_state["wind_value"] = wind_value
                manual_state["wind_last_update"] = time.monotonic()
                manual_state["wind_colors"] = colors

        sock.close()

    fan_pulse_min_wind = max(0, int(cfg.fanning_pulse.min_wind))
    fan_pulse_duration = max(0.1, float(cfg.fanning_pulse.pulse_duration))
    fan_pulse_interval = max(0.1, float(cfg.fanning_pulse.pulse_interval))
    fan_pulse_value = 0.0
    fan_pulse_color: tuple[int, int, int] = (255, 120, 60)
    fan_pulse_start = 0.0
    fan_pulse_last_trigger = 0.0
    fan_pulse_active = False

    def _update_fan_pulse(
        now: float,
        wind_value: int,
        colors: list[tuple[int, int, int]],
    ) -> None:
        nonlocal fan_pulse_value
        nonlocal fan_pulse_color
        nonlocal fan_pulse_start
        nonlocal fan_pulse_last_trigger
        nonlocal fan_pulse_active

        if wind_value < fan_pulse_min_wind or not colors:
            fan_pulse_value = 0.0
            fan_pulse_active = False
            return

        if not fan_pulse_active and now - fan_pulse_last_trigger >= fan_pulse_interval:
            fan_pulse_active = True
            fan_pulse_start = now
            fan_pulse_color = random.choice(colors)

        if not fan_pulse_active:
            fan_pulse_value = 0.0
            return

        progress = (now - fan_pulse_start) / fan_pulse_duration
        if progress >= 1.0:
            fan_pulse_active = False
            fan_pulse_value = 0.0
            fan_pulse_last_trigger = now
            return

        fan_pulse_value = min(1.0, max(0.0, progress))

    def _worker() -> None:
        nonlocal last_entry_id
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
                wind_value = manual_state["wind_value"]
                wind_last_update = manual_state["wind_last_update"]
                wind_colors = list(manual_state["wind_colors"])

            context = StateContext(
                people_count=people_count,
                timestamp=now,
            )
            active_ids = set(range(1, people_count + 1))
            state_output = state_machine.update(context, active_ids)
            state = state_output.state

            people = _make_people(people_count, colors)
            dominant_palette: list[int] = []

            mist_pwm = state_output.mist_pwm
            fan_pwm = state_output.fan_pwm
            fire_intensity = state_output.fire_intensity
            same_state_hold = (
                last_prompt_state == state
                and prompt_generator.is_cooldown_active(state, cooldown_override=same_state_cooldown)
            )
            if same_state_hold:
                prompt = prompt_generator.generate(
                    state_output.state,
                    people_count,
                    None,
                    False,
                    cooldown_override=same_state_cooldown,
                )
            elif state_output.entry_flash_id and state_output.entry_flash_id != last_entry_id:
                prompt = prompt_generator.get_entry_prompt()
                last_entry_id = state_output.entry_flash_id
            else:
                prompt = prompt_generator.generate(
                    state_output.state,
                    people_count,
                    None,
                    False,
                    cooldown_override=same_state_cooldown if last_prompt_state == state else None,
                )

            last_prompt_state = state

            audio_state = _map_audio_state(state)
            if audio_manager and audio_state != last_audio_state:
                audio_manager.set_state(audio_state)
                last_audio_state = audio_state
            if audio_manager and audio_state in (AudioState.AMBIENT, AudioState.PARTY):
                audio_manager.set_fire_intensity(fire_intensity)

            if wind_udp_cfg.enabled and now - wind_last_update <= wind_udp_cfg.timeout:
                pass
            elif shake_listener:
                wind_value = shake_listener.get_wind_value()
                wind_colors = []
            else:
                wind_value = 0
                wind_colors = []

            _update_fan_pulse(now, wind_value, wind_colors)
            packet = packet_builder.build(
                state=state,
                people=people,
                dominant_palette=dominant_palette,
                prompt=prompt,
                mist_pwm=mist_pwm,
                fan_pwm=fan_pwm,
                wind=wind_value,
                fan_pulse=fan_pulse_value,
                fan_pulse_color=fan_pulse_color,
                fire_intensity=fire_intensity,
                pulse_active=state_output.pulse_active,
                entry_flash_id=state_output.entry_flash_id,
                audio_state=audio_state,
                party_buildup_progress=state_output.party_buildup_progress,
            )

            try:
                message = json.dumps(packet, separators=(",", ":")).encode("utf-8")
                sock.sendto(message, (broadcast_ip, broadcast_port))
            except OSError as exc:
                print(f"Network Error: {exc}", flush=True)

            if now - last_log >= 1.0:
                print(
                    f"[MANUAL] {state.value} | people={people_count} | fire={fire_intensity:.2f} | wind={wind_value:.0f}",
                    flush=True,
                )
                last_log = now

            time.sleep(send_interval)

    worker_thread = threading.Thread(target=_worker, name="manual-state-worker", daemon=True)
    worker_thread.start()
    wind_udp_thread: threading.Thread | None = None
    if wind_udp_cfg.enabled:
        wind_udp_thread = threading.Thread(target=_wind_udp_listener, name="manual-wind-udp", daemon=True)
        wind_udp_thread.start()
    print("Manual state mode active. Choose a scenario below.", flush=True)

    print("Manual state mode active. Press 0-5 to set people count, or 'q' to quit.", flush=True)
    def on_press(key):
        try:
            if hasattr(key, 'char'):
                if key.char in ('0','1','2','3','4','5'):
                    _set_state(int(key.char))
                    print(f"[KEY] Set people count to {key.char}", flush=True)
                elif key.char in ('q', 'Q'):
                    print("[KEY] Quit signal received.", flush=True)
                    stop_event.set()
                    return False
        except Exception as e:
            print(f"[KEY] Error: {e}", flush=True)
    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    try:
        while not stop_event.is_set():
            time.sleep(0.1)
    finally:
        stop_event.set()
        listener.stop()
        if audio_manager:
            audio_manager.stop()
        if shake_listener:
            shake_listener.stop()
        try:
            sock.close()
        except OSError:
            pass


def _print_manual_menu() -> None:
    print("\nManual State Mode", flush=True)
    print("1) IDLE (0 people)", flush=True)
    print("2) FIRE (1 person)", flush=True)
    print("3) FIRE (2 people)", flush=True)
    print("4) FIRE (3 people)", flush=True)
    print("5) FIRE (4 people)", flush=True)
    print("6) PARTY (5 people)", flush=True)
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
    return AudioState.SILENT

if __name__ == "__main__":
    main()
