"""Command-line interface for the Bond Fire vision module."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Tuple

from .detector import BondFireVision


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
    parser = argparse.ArgumentParser(description="Run the Bond Fire vision detector.")
    parser.add_argument("--model", default="yolov8n.pt", help="Path to a YOLOv8 weights file.")
    parser.add_argument("--camera-index", type=int, default=0, help="Index of the camera to open.")
    parser.add_argument(
        "--roi",
        type=float,
        nargs=4,
        default=(0.2, 0.2, 0.8, 0.8),
        metavar=("X_MIN", "Y_MIN", "X_MAX", "Y_MAX"),
        help="Active zone bounds as normalized floats.",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.5,
        help="Minimum detection confidence between 0 and 1.",
    )
    parser.add_argument(
        "--no-display",
        action="store_true",
        help="Disable the OpenCV preview window (useful on headless devices).",
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
        default=30.0,
        help="Target UDP broadcast rate.",
    )
    parser.add_argument(
        "--ai-prompts",
        action="store_true",
        help="Enable OpenAI-generated prompt text.",
    )
    parser.add_argument(
        "--ai-api-key",
        help="OpenAI API key override (otherwise use environment variables).",
    )
    parser.add_argument(
        "--ai-interval",
        type=float,
        help="Seconds between OpenAI prompt refreshes (default 5).",
    )
    parser.add_argument(
        "--ai-model",
        help="OpenAI model to use for prompt generation (default gpt-4o-mini).",
    )

    args = parser.parse_args()

    if not 0.0 < args.confidence <= 1.0:
        parser.error("--confidence must be between 0 and 1")
    if args.broadcast_port <= 0 or args.broadcast_port > 65535:
        parser.error("--broadcast-port must be between 1 and 65535")
    if args.updates_per_second < 0:
        parser.error("--updates-per-second must be non-negative")

    roi = _parse_roi(list(args.roi))

    env_ai_enabled = os.getenv("BOND_FIRE_AI_PROMPTS", "").lower() in {"1", "true", "yes"}
    ai_enabled = args.ai_prompts or env_ai_enabled

    env_interval = os.getenv("BOND_FIRE_AI_INTERVAL")
    if args.ai_interval is not None:
        ai_interval = args.ai_interval
    elif env_interval:
        try:
            ai_interval = float(env_interval)
        except ValueError:
            parser.error("BOND_FIRE_AI_INTERVAL must be a number")
    else:
        ai_interval = 5.0

    env_model = os.getenv("BOND_FIRE_OPENAI_MODEL")
    ai_model = args.ai_model or env_model or "gpt-4o-mini"

    env_temperature = os.getenv("BOND_FIRE_AI_TEMPERATURE")
    if env_temperature:
        try:
            ai_temperature = float(env_temperature)
        except ValueError:
            parser.error("BOND_FIRE_AI_TEMPERATURE must be a number")
    else:
        ai_temperature = 0.9

    env_ttl = os.getenv("BOND_FIRE_AI_PROMPT_TTL")
    if env_ttl:
        try:
            ai_prompt_ttl = float(env_ttl)
        except ValueError:
            parser.error("BOND_FIRE_AI_PROMPT_TTL must be a number")
    else:
        ai_prompt_ttl = 30.0

    env_max_tokens = os.getenv("BOND_FIRE_AI_MAX_TOKENS")
    if env_max_tokens:
        try:
            ai_max_tokens = int(env_max_tokens)
        except ValueError:
            parser.error("BOND_FIRE_AI_MAX_TOKENS must be an integer")
    else:
        ai_max_tokens = 120

    if ai_enabled and ai_interval <= 0:
        parser.error("--ai-interval must be greater than 0 when AI prompts are enabled")

    vision = BondFireVision(
        model_path=args.model,
        capture_index=args.camera_index,
        roi=roi,
        detection_confidence=args.confidence,
        broadcast_ip=args.broadcast_ip,
        broadcast_port=args.broadcast_port,
        updates_per_second=args.updates_per_second,
        ai_enabled=ai_enabled,
        ai_interval=ai_interval,
        ai_model=ai_model,
        ai_temperature=ai_temperature,
        ai_max_output_tokens=ai_max_tokens,
        ai_prompt_ttl=ai_prompt_ttl,
        openai_api_key=args.ai_api_key,
    )

    try:
        vision.run(display=not args.no_display)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
