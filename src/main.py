from __future__ import annotations

import argparse
import time

import cv2

from camera import CameraConfig, CameraStream
from detector import MobileNetSSDDetector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Real-time object detection on Raspberry Pi 5 camera."
    )
    parser.add_argument("--model-dir", default="models", help="Directory with model files.")
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.5,
        help="Minimum confidence for detections (0..1).",
    )
    parser.add_argument("--width", type=int, default=1280, help="Capture width.")
    parser.add_argument("--height", type=int, default=720, help="Capture height.")
    parser.add_argument(
        "--no-preview",
        action="store_true",
        help="Disable on-screen preview (for headless mode).",
    )
    return parser.parse_args()


def draw_detections(frame, detections, fps: float, backend: str | None) -> None:
    for det in detections:
        x1, y1, x2, y2 = det.box
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 0), 2)
        caption = f"{det.label} {det.confidence * 100:.1f}%"
        cv2.putText(
            frame,
            caption,
            (x1, max(20, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (20, 20, 20),
            3,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            caption,
            (x1, max(20, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

    info = f"FPS: {fps:.1f} | backend: {backend or 'unknown'} | detections: {len(detections)}"
    cv2.putText(
        frame,
        info,
        (10, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (15, 15, 15),
        3,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        info,
        (10, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 255),
        1,
        cv2.LINE_AA,
    )


def run() -> None:
    args = parse_args()

    camera = CameraStream(
        CameraConfig(width=args.width, height=args.height, prefer_picamera2=True)
    )
    detector = MobileNetSSDDetector(args.model_dir, args.confidence)

    camera.start()
    print(f"Camera backend: {camera.backend}")
    print("Press 'q' or ESC to quit.")

    last_time = time.time()
    fps_smooth = 0.0

    try:
        while True:
            frame = camera.read()
            detections = detector.detect(frame)

            now = time.time()
            dt = max(now - last_time, 1e-6)
            last_time = now
            instant_fps = 1.0 / dt
            fps_smooth = instant_fps if fps_smooth == 0.0 else (fps_smooth * 0.9 + instant_fps * 0.1)

            draw_detections(frame, detections, fps_smooth, camera.backend)

            if args.no_preview:
                continue

            cv2.imshow("Raspberry Pi 5 Object Detection", frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break
    finally:
        camera.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    run()
