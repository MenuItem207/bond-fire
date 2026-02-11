import argparse
import time

import cv2


def main() -> int:
    parser = argparse.ArgumentParser(description="Quick camera access test.")
    parser.add_argument("--camera-index", type=int, default=0, help="Camera index to open.")
    parser.add_argument("--backend", choices=["avf", "any", "default"], default="avf")
    parser.add_argument("--frames", type=int, default=10, help="Number of frames to try reading.")
    args = parser.parse_args()

    if args.backend == "avf":
        backend = cv2.CAP_AVFOUNDATION
    elif args.backend == "any":
        backend = cv2.CAP_ANY
    else:
        backend = 0

    if backend == 0:
        cap = cv2.VideoCapture(args.camera_index)
    else:
        cap = cv2.VideoCapture(args.camera_index, backend)

    if not cap.isOpened():
        print("Camera open failed")
        return 2

    print("Camera opened")
    ok = 0
    for _ in range(args.frames):
        ret, frame = cap.read()
        if ret and frame is not None:
            ok += 1
        time.sleep(0.05)

    cap.release()

    if ok == 0:
        print("No frames received")
        return 3

    print(f"Frames received: {ok}/{args.frames}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
