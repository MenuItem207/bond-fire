"""Manual UDP packet sender for Bond Fire hardware testing."""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from types import SimpleNamespace
from typing import Dict, Tuple

PROMPTS: Dict[int, str] = {
    0: "Social Battery: 0%. I need a spark...",
    1: "One is a start. Battery: 20%",
    2: "Ask them about a hidden talent.",
    3: "Battery 60%. We need 2 more!",
    4: "So close! Find one more human!",
    5: "CRITICAL MASS ACHIEVED!",
}

PRESETS: Dict[str, Tuple[int, bool, str | None]] = {
    "ghost": (0, False, None),
    "spark": (1, False, None),
    "kindle": (2, False, None),
    "flame": (3, False, None),
    "blaze": (4, False, None),
    "supernova": (5, False, "CRITICAL MASS ACHIEVED!"),
    "penalty": (0, True, "SIGNAL INTERFERENCE. DISCONNECT TO CONNECT."),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send manual Bond Fire UDP packets to the ESP32.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("state", nargs="?", choices=sorted(PRESETS.keys()), help="Preset state to send.")
    parser.add_argument("--count", type=int, help="Override people count (c)")
    parser.add_argument("--phone", action="store_true", help="Force phone detected flag on.")
    parser.add_argument("--no-phone", action="store_true", help="Force phone detected flag off.")
    parser.add_argument("--text", help="Override scrolling text (t)")
    parser.add_argument("--ip", default="255.255.255.255", help="Destination IP address.")
    parser.add_argument("--port", type=int, default=4210, help="Destination UDP port.")
    parser.add_argument("--rate", type=float, default=1.0, help="Messages per second when repeating.")
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Number of times to send the packet. Use 0 for continuous until interrupted.",
    )
    parser.add_argument("--interactive", action="store_true", help="Launch interactive prompt mode.")
    return parser.parse_args()


def build_payload(args: argparse.Namespace) -> Dict[str, object]:
    base = PRESETS.get(args.state) if args.state else (0, False, None)
    count = args.count if args.count is not None else base[0]
    if count < 0:
        raise ValueError("Count must be non-negative")

    phone_flag = base[1]
    if args.phone and args.no_phone:
        raise ValueError("Cannot use --phone and --no-phone together")
    if args.phone:
        phone_flag = True
    if args.no_phone:
        phone_flag = False

    text = args.text or base[2]
    capped = min(count, 5)
    if text is None:
        text = PROMPTS[capped]

    return {"c": capped, "p": phone_flag, "t": text}


def send_payload(sock: socket.socket, ip: str, port: int, payload: Dict[str, object]) -> None:
    message = json.dumps(payload).encode("utf-8")
    sock.sendto(message, (ip, port))
    print(f"Sent -> {message.decode('utf-8')} to {ip}:{port}")


def _send_with_repetition(
    sock: socket.socket,
    ip: str,
    port: int,
    payload: Dict[str, object],
    repeat: int,
    rate: float,
) -> None:
    if repeat < 0:
        raise ValueError("--repeat must be zero or positive")
    if rate < 0:
        raise ValueError("--rate must be zero or positive")

    interval = 1.0 / rate if rate > 0 else 0.0
    count = 0
    while True:
        send_payload(sock, ip, port, payload)
        count += 1
        if repeat and count >= repeat:
            break
        if interval > 0:
            time.sleep(interval)


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
            temp_args = SimpleNamespace(state=state_name, count=None, phone=False, no_phone=False, text=None)
            payload = build_payload(temp_args)
            _send_with_repetition(sock, ip, port, payload, repeat, rate)


def run_manual_mode(args: argparse.Namespace) -> None:
    payload = build_payload(args)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        _send_with_repetition(sock, args.ip, args.port, payload, args.repeat, args.rate)


def run_interactive(args: argparse.Namespace) -> None:
    preset_order = list(PRESETS.keys())
    ip = args.ip
    port = args.port
    repeat = args.repeat if args.repeat >= 0 else 1
    rate = args.rate if args.rate >= 0 else 1.0

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while True:
            print("\n=== Bond Fire Packet CLI ===")
            repeat_label = "∞" if repeat == 0 else str(repeat)
            print(f"Target: {ip}:{port} | Repeat: {repeat_label} | Rate: {rate:.2f} msg/s")
            for idx, name in enumerate(preset_order, start=1):
                count, phone, override_text = PRESETS[name]
                text_sample = override_text or PROMPTS[min(count, 5)]
                phone_flag = "phone" if phone else "no phone"
                print(f"  {idx}) {name.title():<10} c={count} | {phone_flag} | {text_sample}")
            print("  c) Custom payload")
            print("  a) Cycle through presets")
            print("  r) Set repeat count")
            print("  f) Set rate (messages per second)")
            print("  t) Change target (IP/port)")
            print("  q) Quit")

            try:
                choice = input("Select option> ").strip().lower()
            except EOFError:
                print("\nExiting interactive mode.")
                return

            if not choice:
                continue
            if choice in {"q", "quit", "exit"}:
                print("Exiting interactive mode.")
                return

            if choice.isdigit():
                index = int(choice) - 1
                if 0 <= index < len(preset_order):
                    state_name = preset_order[index]
                    temp_args = SimpleNamespace(state=state_name, count=None, phone=False, no_phone=False, text=None)
                    payload = build_payload(temp_args)
                    try:
                        _send_with_repetition(sock, ip, port, payload, repeat, rate)
                    except ValueError as exc:
                        print(f"Error: {exc}")
                else:
                    print("Unknown option. Try again.")
                continue

            if choice in {"c", "custom"}:
                custom_count = _prompt_int("People count (c)", 0, minimum=0)
                custom_phone = _prompt_bool("Phone detected?", False)
                text_input = input("Text override (leave blank for auto): ").strip()
                text_value = text_input if text_input else None
                custom_args = SimpleNamespace(state=None, count=custom_count, phone=custom_phone, no_phone=False, text=text_value)
                if not text_value:
                    custom_args.text = PROMPTS[min(custom_count, 5)]
                payload = build_payload(custom_args)
                try:
                    _send_with_repetition(sock, ip, port, payload, repeat, rate)
                except ValueError as exc:
                    print(f"Error: {exc}")
                continue

            if choice in {"a", "cycle"}:
                loops = _prompt_int("How many times to cycle through presets? (0 = continuous)", 1, minimum=0)
                try:
                    _cycle_presets(sock, ip, port, repeat, rate, loops, preset_order)
                except ValueError as exc:
                    print(f"Error: {exc}")
                except KeyboardInterrupt:
                    print("\nCycle interrupted.")
                continue

            if choice in {"r", "repeat"}:
                repeat = _prompt_int("Repeat count for each send (0 = continuous)", repeat, minimum=0)
                continue

            if choice in {"f", "rate"}:
                rate = _prompt_float("Messages per second", rate, minimum=0.0)
                continue

            if choice in {"t", "target"}:
                ip = _prompt_ip(ip)
                port = _prompt_port(port)
                continue

            print("Unknown option. Try again.")


def main() -> None:
    args = parse_args()
    launch_interactive = args.interactive
    if not launch_interactive:
        no_manual_overrides = (
            args.state is None
            and args.count is None
            and not args.phone
            and not args.no_phone
            and args.text is None
        )
        if no_manual_overrides:
            launch_interactive = True

    if launch_interactive:
        run_interactive(args)
        return

    try:
        run_manual_mode(args)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
