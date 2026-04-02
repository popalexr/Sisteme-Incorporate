from __future__ import annotations

import argparse
import threading
import time
from collections import Counter
from contextlib import asynccontextmanager
from dataclasses import dataclass

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from camera import CameraConfig, CameraStream
from detector import Detection, YOLOv4TinyDetector


@dataclass
class AppConfig:
    model_dir: str = "models"
    confidence: float = 0.35
    width: int = 1280
    height: int = 720
    backend: str = "picamera2"
    jpeg_quality: int = 80
    detect_every_n_frames: int = 2
    picamera_swap_rb: bool = True


class DetectionService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.camera = CameraStream(
            CameraConfig(
                width=config.width,
                height=config.height,
                prefer_picamera2=True,
                picamera_swap_rb=config.picamera_swap_rb,
            )
        )
        self.detector: YOLOv4TinyDetector | None = None
        self._lock = threading.Lock()
        self._last_frame_time = time.time()
        self._fps_smooth = 0.0
        self._last_counts: dict[str, int] = {}
        self._last_detections: list[Detection] = []
        self._frame_index = 0

    def start(self) -> None:
        self.detector = YOLOv4TinyDetector(self.config.model_dir, self.config.confidence)
        self.camera.start(force_backend=self.config.backend)
        print(f"Camera backend: {self.camera.backend}")
        if self.camera.backend != "picamera2" and self.camera.picamera2_error:
            print(f"Picamera2 unavailable, fallback reason: {self.camera.picamera2_error}")

    def stop(self) -> None:
        self.camera.stop()
        self.detector = None

    def get_jpeg_frame(self) -> bytes:
        with self._lock:
            if self.detector is None:
                raise RuntimeError("Detection service is not started.")
            frame = self.camera.read()

            should_detect = (
                self._frame_index % self.config.detect_every_n_frames == 0
                or not self._last_detections
            )
            if should_detect:
                detections = self.detector.detect(frame)
                self._last_detections = detections
                self._last_counts = count_objects(detections)
            else:
                detections = self._last_detections
            self._frame_index += 1

            now = time.time()
            dt = max(now - self._last_frame_time, 1e-6)
            self._last_frame_time = now
            instant_fps = 1.0 / dt
            self._fps_smooth = (
                instant_fps if self._fps_smooth == 0.0 else (self._fps_smooth * 0.9 + instant_fps * 0.1)
            )

            draw_detections(
                frame,
                detections,
                self._fps_smooth,
                self.camera.backend,
                self._last_counts,
            )
            ok, encoded = cv2.imencode(
                ".jpg",
                frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), self.config.jpeg_quality],
            )
            if not ok:
                raise RuntimeError("Failed to encode frame as JPEG.")
            return encoded.tobytes()

    def status(self) -> dict:
        return {
            "camera_backend": self.camera.backend,
            "picamera2_error": self.camera.picamera2_error,
            "confidence": self.config.confidence,
            "resolution": {"width": self.config.width, "height": self.config.height},
            "jpeg_quality": self.config.jpeg_quality,
            "detect_every_n_frames": self.config.detect_every_n_frames,
            "picamera_swap_rb": self.config.picamera_swap_rb,
            "counts": {
                "total": sum(self._last_counts.values()),
                "by_class": self._last_counts,
            },
        }


def count_objects(detections: list[Detection]) -> dict[str, int]:
    counts = Counter(det.label for det in detections)
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def draw_detections(
    frame: np.ndarray,
    detections: list[Detection],
    fps: float,
    backend: str | None,
    counts: dict[str, int],
) -> None:
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

    info = f"FPS: {fps:.1f} | backend: {backend or 'unknown'} | objects: {len(detections)}"
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

    y = 50
    if counts:
        for label, value in list(counts.items())[:8]:
            line = f"{label}: {value}"
            cv2.putText(
                frame,
                line,
                (10, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (15, 15, 15),
                3,
                cv2.LINE_AA,
            )
            cv2.putText(
                frame,
                line,
                (10, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            y += 24
    else:
        cv2.putText(
            frame,
            "No objects",
            (10, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (15, 15, 15),
            3,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            "No objects",
            (10, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )


def build_app(config: AppConfig) -> FastAPI:
    service = DetectionService(config)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        service.start()
        try:
            yield
        finally:
            service.stop()

    app = FastAPI(title="Raspberry Pi 5 Object Detection", lifespan=lifespan)

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Live Stream</title>
    <style>
      html, body {
        width: 100%;
        height: 100%;
        margin: 0;
      }
      body {
        overflow: hidden;
        background: #000;
      }
      img {
        display: block;
        width: 100vw;
        height: 100vh;
        object-fit: contain;
        background: #000;
      }
    </style>
  </head>
  <body>
    <img src="/video_feed" alt="Live stream" />
  </body>
</html>
"""

    def generate_stream():
        while True:
            frame_bytes = service.get_jpeg_frame()
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Cache-Control: no-cache\r\n\r\n"
                + frame_bytes
                + b"\r\n"
            )

    @app.get("/video_feed")
    async def video_feed() -> StreamingResponse:
        return StreamingResponse(
            generate_stream(),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    @app.get("/status")
    async def status() -> JSONResponse:
        return JSONResponse(service.status())

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FastAPI web UI for live object detection.")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind.")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind.")
    parser.add_argument("--model-dir", default="models", help="Directory with model files.")
    parser.add_argument("--confidence", type=float, default=0.35, help="Detection threshold.")
    parser.add_argument("--width", type=int, default=1280, help="Capture width.")
    parser.add_argument("--height", type=int, default=720, help="Capture height.")
    parser.add_argument(
        "--backend",
        choices=("auto", "picamera2", "opencv"),
        default="picamera2",
        help="Camera backend to use. For Raspberry Pi camera module use picamera2.",
    )
    parser.add_argument("--jpeg-quality", type=int, default=80, help="JPEG quality (1-100).")
    parser.add_argument(
        "--detect-every-n-frames",
        type=int,
        default=2,
        help="Run model inference every N frames and reuse the last detections between runs.",
    )
    parser.add_argument(
        "--picamera-swap-rb",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Swap red/blue channels for Picamera2 frames before OpenCV processing.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = AppConfig(
        model_dir=args.model_dir,
        confidence=args.confidence,
        width=args.width,
        height=args.height,
        backend=args.backend,
        jpeg_quality=max(1, min(100, args.jpeg_quality)),
        detect_every_n_frames=max(1, args.detect_every_n_frames),
        picamera_swap_rb=args.picamera_swap_rb,
    )
    app = build_app(config)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


app = build_app(AppConfig())


if __name__ == "__main__":
    main()
