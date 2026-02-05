"""Command-line interface for the Bond Fire vision module."""

from __future__ import annotations

import argparse
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
    parser = argparse.ArgumentParser(description="Run the Bond Fire vision detector (v2.0).")
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

    vision = BondFireVision(
        model_path=args.model,
        capture_index=args.camera_index,
        roi=roi,
        detection_confidence=args.confidence,
        broadcast_ip=args.broadcast_ip,
        broadcast_port=args.broadcast_port,
        updates_per_second=args.updates_per_second,
        pulse_interval=args.pulse_interval,
        enable_audio=args.enable_audio,
        audio_volume=args.audio_volume,
        narration_enabled=args.narration_enabled,
    )

    try:
        vision.run(display=not args.no_display)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
