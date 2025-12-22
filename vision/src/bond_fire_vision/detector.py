from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Tuple

import cv2
from ultralytics import YOLO


@dataclass(eq=True)
class VisionState:
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
        roi: Tuple[float, float, float, float] = (0.2, 0.2, 0.8, 0.8),
        detection_confidence: float = 0.5,
    ) -> None:
        self._validate_roi(roi)
        self._validate_confidence(detection_confidence)

        self.model = YOLO(model_path)
        self.capture_index = capture_index
        self.roi = roi
        self.detection_confidence = detection_confidence
        self.cap: cv2.VideoCapture | None = None

    def run(self, display: bool = True) -> VisionState:
        """
        Start the capture loop.

        Args:
            display: Whether to show the annotated OpenCV window.
        Returns:
            Last known detection state.
        """
        self.cap = cv2.VideoCapture(self.capture_index)
        if not self.cap.isOpened():
            raise RuntimeError("Could not open video source")

        print(
            "Starting vision system. Press 'q' to exit." if display else "Starting vision system. Ctrl+C to exit.",
            flush=True,
        )

        previous_state: VisionState | None = None
        state = VisionState(people_in_roi=0, phone_detected=False)

        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    raise RuntimeError("Failed to read frame from camera")

                state, processed_frame = self.analyze_frame(frame, annotate=display)

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
            if self.cap is not None:
                self.cap.release()
                self.cap = None
            if display:
                cv2.destroyAllWindows()

        return state

    def analyze_frame(self, frame: Any, annotate: bool = True) -> tuple[VisionState, Any]:
        """Analyze a single frame and optionally draw annotations."""
        height, width = frame.shape[:2]
        roi_pixels = self._roi_pixels(width, height)

        person_count = 0
        phone_detected = False

        if annotate:
            self._draw_roi(frame, roi_pixels)

        results = self.model(frame, stream=True, verbose=False)
        for result in results:
            for box in result.boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                if conf < self.detection_confidence:
                    continue

                x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]

                if cls == self.CLASS_PERSON:
                    inside = self._is_inside_roi((x1, y1, x2, y2), roi_pixels)
                    if inside:
                        person_count += 1
                    if annotate:
                        color = (0, 255, 0) if inside else (0, 0, 255)
                        thickness = 2 if inside else 1
                        cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color, thickness)
                        if inside:
                            label = f"Person {conf:.2f}"
                            cv2.putText(frame, label, (int(x1), max(int(y1) - 10, 0)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                elif cls == self.CLASS_PHONE:
                    phone_detected = True
                    if annotate:
                        cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), 2)
                        cv2.putText(frame, "PHONE", (int(x1), max(int(y1) - 10, 0)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        state = VisionState(people_in_roi=person_count, phone_detected=phone_detected)

        if annotate:
            self._draw_status(frame, state)

        return state, frame

    def _draw_roi(self, frame, roi_pixels: tuple[int, int, int, int]) -> None:
        x1, y1, x2, y2 = roi_pixels
        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 0), 2)
        cv2.putText(frame, "Active Zone", (x1, max(y1 - 10, 0)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

    def _draw_status(self, frame, state: VisionState) -> None:
        status_text = f"People in Zone: {state.people_in_roi} | Phone Detected: {'YES' if state.phone_detected else 'NO'}"
        color = (0, 0, 255) if state.phone_detected else (0, 255, 0)
        (text_w, _), _ = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
        cv2.rectangle(frame, (5, 5), (15 + text_w, 40), (0, 0, 0), -1)
        cv2.putText(frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    def _is_inside_roi(self, box: tuple[float, float, float, float], roi_pixels: tuple[int, int, int, int]) -> bool:
        x1, y1, x2, y2 = box
        roi_x1, roi_y1, roi_x2, roi_y2 = roi_pixels
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        return roi_x1 < cx < roi_x2 and roi_y1 < cy < roi_y2

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