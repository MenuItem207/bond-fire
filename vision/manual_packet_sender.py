"""Manual UDP packet sender for Bond Fire v2.1 protocol testing."""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from types import SimpleNamespace
from typing import Any, Dict

# v2.1 State names
STATE_NAMES = ["IDLE", "FIRE", "PARTY", "PHONE"]

# Preset configurations: (state, people_count, phone_detected, prompt)
PRESETS: Dict[str, tuple[str, int, bool, str]] = {
    "idle": ("IDLE", 0, False, "Waiting for guests..."),
    "spark": ("FIRE", 1, False, "One is a start. Battery: 25%"),
    "kindle": ("FIRE", 2, False, "Ask them about a hidden talent."),
    "flame": ("FIRE", 3, False, "We're getting warmer. Battery: 75%"),
    "blaze": ("FIRE", 4, False, "So close! One more human!"),
    "supernova": ("PARTY", 5, False, "CRITICAL MASS ACHIEVED!"),
    "phone": ("PHONE", 0, True, "SIGNAL INTERFERENCE. DISCONNECT TO CONNECT."),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send manual Bond Fire v2.1 UDP packets to ESP32.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("preset", nargs="?", choices=sorted(PRESETS.keys()), help="Preset configuration to send.")
    parser.add_argument("--state", choices=STATE_NAMES, help="Override state (IDLE/FIRE/PARTY/PHONE).")
    parser.add_argument("--people", type=int, help="Number of people detected (0-6).")
    parser.add_argument("--phone", action="store_true", help="Enable phone detection.")
    parser.add_argument("--no-phone", action="store_true", help="Disable phone detection.")
    parser.add_argument("--prompt", help="Override text prompt.")
    parser.add_argument("--mist", type=int, default=220, help="Mist PWM (0-255).")
    parser.add_argument("--fan", type=int, default=100, help="Fan PWM (0-255).")
    parser.add_argument("--fire-intensity", type=float, default=None, help="Fire intensity (0.0-1.0).")
    parser.add_argument("--palette", nargs="+", type=int, help="Dominant palette as RGB triplets [r g b r g b ...].")
    parser.add_argument("--pulse", action="store_true", help="Activate pulse effect.")
    parser.add_argument("--celebration", action="store_true", help="Trigger celebration effect.")
    parser.add_argument("--ip", default="255.255.255.255", help="Destination IP address.")
    parser.add_argument("--port", type=int, default=4210, help="Destination UDP port.")
    parser.add_argument("--rate", type=float, default=1.0, help="Messages per second when repeating.")
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Number of times to send. Use 0 for continuous until interrupted.",
    )
    parser.add_argument("--interactive", action="store_true", help="Launch interactive prompt mode.")
    return parser.parse_args()


def build_v2_1_payload(args: argparse.Namespace) -> Dict[str, Any]:
    """Build a v2.1 protocol packet."""
    # Start with preset values
    if args.preset:
        state, people, phone, prompt = PRESETS[args.preset]
    else:
        state, people, phone, prompt = "IDLE", 0, False, "Waiting..."

    # Override with command-line args
    if args.state:
        state = args.state
    if args.people is not None:
        people = max(0, min(6, args.people))
    if args.phone:
        phone = True
    if args.no_phone:
        phone = False
    if args.prompt:
        prompt = args.prompt

    # Build people array (empty for manual sender, could be extended)
    people_data = []

    # Build palette
    palette = args.palette if args.palette else [255, 100, 0, 200, 50, 0]  # Default orange tones
    palette = palette[:12]  # Max 12 values (4 colors)

    if args.fire_intensity is None:
        if people <= 0:
            fire_intensity = 0.0
        elif people == 1:
            fire_intensity = 0.35
        elif people == 2:
            fire_intensity = 0.6
        elif people == 3:
            fire_intensity = 0.8
        else:
            fire_intensity = 1.0
    else:
        fire_intensity = args.fire_intensity

    # Build packet
    packet = {
        "version": 2,
        "timestamp": time.time(),
        "fps": 30,
        "state": state,
        "people": people_data,
        "phone_detected": phone,
        "dominant_palette": palette,
        "prompt": prompt,
        "mist_pwm": max(0, min(255, args.mist)),
        "fan_pwm": max(0, min(255, args.fan)),
        "pulse_active": args.pulse,
        "entry_flash_id": None,
        "audio_state": "PARTY" if state == "PARTY" else ("ALERT" if state == "PHONE" else "AMBIENT"),
        "party_buildup_progress": 0.0,
        "celebration": args.celebration,
        "fire_intensity": max(0.0, min(1.0, fire_intensity)),
    }

    return packet


def send_payload(sock: socket.socket, ip: str, port: int, payload: Dict[str, Any]) -> None:
    """Send packet and print confirmation."""
    message = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sock.sendto(message, (ip, port))
    state = payload.get("state", "???")
    people = len(payload.get("people", []))
    phone = "📱" if payload.get("phone_detected") else ""
    prompt = payload.get("prompt", "")[:40]
    print(f"✓ {state} | {people} people {phone} | '{prompt}' | Size: {len(message)} bytes")


def _send_with_repetition(
    sock: socket.socket,
    ip: str,
    port: int,
    payload: Dict[str, Any],
    repeat: int,
    rate: float,
) -> None:
    """Send payload with optional repetition."""
    if repeat < 0:
        raise ValueError("--repeat must be zero or positive")
    if rate <= 0:
        raise ValueError("--rate must be positive")

    interval = 1.0 / rate if rate > 0 else 0.0
    count = 0

    try:
        while True:
            send_payload(sock, ip, port, payload)
            count += 1
            if repeat and count >= repeat:
                break
            if interval > 0:
                time.sleep(interval)
    except KeyboardInterrupt:
        print(f"\nInterrupted after {count} packet(s).")


def _prompt_int(prompt: str, default: int, minimum: int | None = None) -> int:
    while True:
        raw = input(f"{prompt} [{default}]: ").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            print("Enter a valid integer.")
            continue
        if minimum is not None and value < minimum:
            print(f"Value must be >= {minimum}.")
            continue
        return value


def _prompt_float(prompt: str, default: float, minimum: float | None = None) -> float:
    while True:
        raw = input(f"{prompt} [{default}]: ").strip()
        if not raw:
            return default
        try:
            value = float(raw)
        except ValueError:
            print("Enter a valid number.")
            continue
        if minimum is not None and value < minimum:
            print(f"Value must be >= {minimum}.")
            continue
        return value


def _prompt_bool(prompt: str, default: bool) -> bool:
    default_label = "y" if default else "n"
    raw = input(f"{prompt} (y/n) [{default_label}]: ").strip().lower()
    if not raw:
        return default
    return raw in {"y", "yes", "true", "1"}


def _prompt_ip(current: str) -> str:
    while True:
        raw = input(f"Broadcast IP [{current}]: ").strip()
        if not raw:
            return current
        try:
            socket.inet_aton(raw)
        except OSError:
            print("Invalid IPv4 address. Try again.")
            continue
        return raw


def _prompt_port(current: int) -> int:
    while True:
        raw = input(f"UDP port [{current}]: ").strip()
        if not raw:
            return current
        try:
            value = int(raw)
        except ValueError:
            print("Enter a valid port number.")
            continue
        if not (1 <= value <= 65535):
            print("Port must be between 1 and 65535.")
            continue
        return value


def _cycle_presets(
    sock: socket.socket,
    ip: str,
    port: int,
    repeat: int,
    rate: float,
    loops: int,
    preset_order: list[str],
) -> None:
    if loops < 0:
        raise ValueError("Loop count must be zero or positive")
    iteration = 0
    while loops == 0 or iteration < loops:
        iteration += 1
        for state_name in preset_order:
            temp_args = SimpleNamespace(
                preset=state_name,
                state=None,
                people=None,
                phone=False,
                no_phone=False,
                prompt=None,
                mist=220,
                fan=100,
                fire_intensity=None,
                palette=None,
                pulse=False,
                celebration=False,
            )
            payload = build_v2_1_payload(temp_args)
            _send_with_repetition(sock, ip, port, payload, repeat, rate)


def run_manual_mode(args: argparse.Namespace) -> None:
    """Send a single packet or repeated packets."""
    payload = build_v2_1_payload(args)

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        _send_with_repetition(sock, args.ip, args.port, payload, args.repeat, args.rate)


def run_interactive(args: argparse.Namespace) -> None:
    """Interactive mode with menu."""
    ip = args.ip
    port = args.port
    repeat = args.repeat if args.repeat >= 0 else 1
    rate = args.rate if args.rate >= 0 else 1.0

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        while True:
            print("\n" + "=" * 50)
            print("Bond Fire v2.1 Packet Sender")
            print("=" * 50)
            print(f"Target: {ip}:{port} | Repeat: {repeat if repeat else '∞'} | Rate: {rate:.1f} msg/s\n")

            # Show presets
            for idx, (name, (state, people, phone, prompt)) in enumerate(PRESETS.items(), 1):
                phone_str = "📱" if phone else ""
                print(f"  {idx}) {name.title():<12} [{state:<6}] {people} people {phone_str} | {prompt[:35]}")

            print("\n  c) Custom payload")
            print("  a) Auto-cycle presets")
            print("  r) Set repeat count")
            print("  f) Set rate (msg/sec)")
            print("  t) Change target IP/port")
            print("  q) Quit\n")

            try:
                choice = input("Select option> ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                return

            if not choice:
                continue

            if choice in {"q", "quit", "exit"}:
                return

            # Preset selection
            if choice.isdigit():
                idx = int(choice) - 1
                preset_list = list(PRESETS.keys())
                if 0 <= idx < len(preset_list):
                    preset_name = preset_list[idx]
                    temp_args = SimpleNamespace(
                        preset=preset_name,
                        state=None,
                        people=None,
                        phone=False,
                        no_phone=False,
                        prompt=None,
                        mist=220,
                        fan=100,
                        fire_intensity=0.5,
                        palette=None,
                        pulse=False,
                        celebration=False,
                    )
                    payload = build_v2_1_payload(temp_args)
                    try:
                        _send_with_repetition(sock, ip, port, payload, repeat, rate)
                    except ValueError as e:
                        print(f"Error: {e}")
                else:
                    print("Invalid selection.")

            elif choice == "c":
                # Custom payload
                print("\nCustom Payload Builder:")
                try:
                    state = input(f"State [{STATE_NAMES[1]}]: ").strip() or STATE_NAMES[1]
                    if state not in STATE_NAMES:
                        print(f"Invalid state. Must be one of {STATE_NAMES}")
                        continue

                    people_input = input("People count [0]: ").strip()
                    people = int(people_input) if people_input else 0
                    people = max(0, min(6, people))

                    phone = input("Phone detected? (y/n) [n]: ").strip().lower() in {"y", "yes"}

                    prompt = input("Prompt text [Custom message]: ").strip() or "Custom message"

                    temp_args = SimpleNamespace(
                        preset=None,
                        state=state,
                        people=people,
                        phone=phone,
                        no_phone=False,
                        prompt=prompt,
                        mist=220,
                        fan=100,
                        fire_intensity=0.5,
                        palette=None,
                        pulse=False,
                        celebration=False,
                    )
                    payload = build_v2_1_payload(temp_args)
                    _send_with_repetition(sock, ip, port, payload, repeat, rate)
                except (ValueError, KeyboardInterrupt) as e:
                    print(f"Error: {e}")

            elif choice == "a":
                # Auto-cycle presets
                try:
                    loops = int(input("Number of loops (0=infinite) [1]: ").strip() or "1")
                    preset_list = list(PRESETS.keys())
                    iteration = 0
                    while loops == 0 or iteration < loops:
                        iteration += 1
                        for preset_name in preset_list:
                            temp_args = SimpleNamespace(
                                preset=preset_name,
                                state=None,
                                people=None,
                                phone=False,
                                no_phone=False,
                                prompt=None,
                                mist=220,
                                fan=100,
                                fire_intensity=0.5,
                                palette=None,
                                pulse=False,
                                celebration=False,
                            )
                            payload = build_v2_1_payload(temp_args)
                            send_payload(sock, ip, port, payload)
                            time.sleep(1.0 / rate if rate > 0 else 1.0)
                except KeyboardInterrupt:
                    print("Interrupted.")

            elif choice == "r":
                try:
                    repeat = int(input("Repeat count (0=infinite) [1]: ").strip() or "1")
                except ValueError:
                    print("Invalid number.")

            elif choice == "f":
                try:
                    rate = float(input("Rate (msg/sec) [1.0]: ").strip() or "1.0")
                    if rate <= 0:
                        print("Rate must be positive.")
                        rate = 1.0
                except ValueError:
                    print("Invalid number.")

            elif choice == "t":
                try:
                    new_ip = input(f"IP address [{ip}]: ").strip() or ip
                    socket.inet_aton(new_ip)
                    ip = new_ip
                    new_port = input(f"Port [{port}]: ").strip()
                    if new_port:
                        port = int(new_port)
                    print(f"Target updated: {ip}:{port}")
                except (OSError, ValueError) as e:
                    print(f"Invalid: {e}")


def main() -> None:
    args = parse_args()

    if args.interactive:
        run_interactive(args)
    else:
        if not args.preset and not args.state:
            print("Error: Must specify either a preset or --state")
            sys.exit(1)
        run_manual_mode(args)


if __name__ == "__main__":
    main()
