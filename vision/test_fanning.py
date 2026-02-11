#!/usr/bin/env python3
"""Proof-of-tech fanning detector using YOLOv8 phone tracking."""

from __future__ import annotations

import argparse
import time
from collections import deque

import cv2
import numpy as np
from ultralytics import YOLO


CLASS_PHONE = 67


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test phone fanning detection.")
    parser.add_argument("--model", default="yolov8s.pt", help="Path to YOLOv8 weights")
    parser.add_argument("--camera-index", type=int, default=0, help="Camera index")
    parser.add_argument("--frame-width", type=int, default=1280, help="Camera capture width")
    parser.add_argument("--frame-height", type=int, default=720, help="Camera capture height")
    parser.add_argument("--imgsz", type=int, default=960, help="YOLO inference size (larger helps distant phones)")
    parser.add_argument("--confidence", type=float, default=0.35, help="Detection confidence threshold")
    parser.add_argument("--history", type=int, default=30, help="Number of x-positions to keep")
    parser.add_argument("--threshold", type=float, default=40.0, help="Movement threshold to trigger fanning")
    parser.add_argument("--metric", choices=("std", "distance"), default="distance", help="Movement metric")
    parser.add_argument("--decay", type=float, default=0.95, help="Fan power decay rate per frame")
    parser.add_argument("--increase-step", type=float, default=6.0, help="Fan power increase per frame")
    parser.add_argument("--reset-missing", type=int, default=10, help="Frames until history reset when phone is missing")
    return parser.parse_args()


def compute_movement_metric(x_positions: deque[float], metric: str) -> float:
    if len(x_positions) < 2:
        return 0.0
    values = np.array(x_positions, dtype=np.float32)
    if metric == "std":
        return float(np.std(values))
    return float(np.sum(np.abs(np.diff(values))))


def draw_fan_bar(frame: np.ndarray, power: float) -> None:
    height, width = frame.shape[:2]
    bar_w = int(width * 0.4)
    bar_h = 22
    x1 = 20
    y1 = height - bar_h - 20
    x2 = x1 + bar_w
    y2 = y1 + bar_h

    cv2.rectangle(frame, (x1, y1), (x2, y2), (40, 40, 40), 2)
    fill_w = int(bar_w * (max(0.0, min(100.0, power)) / 100.0))
    cv2.rectangle(frame, (x1 + 2, y1 + 2), (x1 + fill_w - 2, y2 - 2), (0, 140, 255), -1)
    cv2.putText(
        frame,
        f"Fan Power: {power:5.1f}%",
        (x1, y1 - 8),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2,
    )


def main() -> None:
    args = parse_args()

    model = YOLO(args.model)
    cap = cv2.VideoCapture(args.camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera index {args.camera_index}")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.frame_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.frame_height)

    x_history: deque[float] = deque(maxlen=args.history)
    fan_power = 0.0
    missing_frames = 0
    last_fps_report = time.monotonic()
    frame_count = 0

    print("Press 'q' to quit.", flush=True)

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                raise RuntimeError("Failed to read frame from camera")

            results = model(frame, verbose=False, conf=args.confidence, imgsz=args.imgsz)
            best_phone = None

            for result in results:
                if result.boxes is None:
                    continue
                for box in result.boxes:
                    cls = int(box.cls[0])
                    if cls != CLASS_PHONE:
                        continue
                    conf = float(box.conf[0])
                    if best_phone is None or conf > best_phone[0]:
                        x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
                        best_phone = (conf, x1, y1, x2, y2)

            if best_phone is not None:
                _, x1, y1, x2, y2 = best_phone
                cx = (x1 + x2) * 0.5
                cy = (y1 + y2) * 0.5
                x_history.append(cx)
                missing_frames = 0

                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), 2)
                cv2.circle(frame, (int(cx), int(cy)), 6, (0, 255, 255), -1)
                cv2.putText(
                    frame,
                    "PHONE",
                    (int(x1), max(int(y1) - 10, 0)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 0, 255),
                    2,
                )
            else:
                missing_frames += 1
                if missing_frames >= args.reset_missing:
                    x_history.clear()

            movement = compute_movement_metric(x_history, args.metric)
            if movement > args.threshold:
                fan_power = min(100.0, fan_power + args.increase_step)
            else:
                fan_power *= args.decay

            draw_fan_bar(frame, fan_power)
            cv2.putText(
                frame,
                f"Movement: {movement:6.2f}  Threshold: {args.threshold:6.2f}",
                (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )
            cv2.imshow("Bond Fire - Fanning Test", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

            frame_count += 1
            now = time.monotonic()
            if now - last_fps_report >= 2.0:
                fps = frame_count / (now - last_fps_report)
                print(f"FPS: {fps:.1f} | Fan Power: {fan_power:.1f}%", flush=True)
                last_fps_report = now
                frame_count = 0
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
