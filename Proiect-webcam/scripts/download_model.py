from __future__ import annotations

import argparse
import hashlib
import shutil
import ssl
import urllib.error
import urllib.request
from pathlib import Path

MODEL_DIR = Path("models")

FILES = {
    "yolov4-tiny.cfg": {
        "url": "https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4-tiny.cfg",
        "sha256": "f858e3724962eedf3ac44e3b6cb3f0c3d9ed067c306bb831f539c578b924c90e",
    },
    "yolov4-tiny.weights": {
        "url": "https://github.com/AlexeyAB/darknet/releases/download/yolov4/yolov4-tiny.weights",
        "sha256": "cf9fbfd0f6d4869b35762f56100f50ed05268084078805f0e7989efe5bb8ca87",
    },
    "coco.names": {
        "url": "https://raw.githubusercontent.com/pjreddie/darknet/master/data/coco.names",
        "sha256": "634a1132eb33f8091d60f2c346ababe8b905ae08387037aed883953b7329af84",
    },
}


def sha256sum(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def download(url: str, destination: Path, insecure: bool = False) -> None:
    print(f"Downloading {destination.name}...")
    context = ssl._create_unverified_context() if insecure else ssl.create_default_context()
    with urllib.request.urlopen(url, context=context) as response, destination.open("wb") as out:
        shutil.copyfileobj(response, out)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download YOLOv4-tiny model files.")
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Skip TLS certificate verification if your environment has broken certs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    for filename, meta in FILES.items():
        out_path = MODEL_DIR / filename

        if out_path.exists():
            current_hash = sha256sum(out_path)
            if current_hash == meta["sha256"]:
                print(f"{filename}: already present and verified.")
                continue
            print(f"{filename}: hash mismatch, re-downloading.")

        try:
            download(meta["url"], out_path, insecure=args.insecure)
        except urllib.error.URLError as exc:
            out_path.unlink(missing_ok=True)
            raise RuntimeError(
                "Download failed because TLS certificates could not be validated. "
                "Install CA certificates or retry with: python scripts/download_model.py --insecure"
            ) from exc
        downloaded_hash = sha256sum(out_path)
        if downloaded_hash != meta["sha256"]:
            out_path.unlink(missing_ok=True)
            raise RuntimeError(
                f"Checksum mismatch for {filename}. Expected {meta['sha256']}, got {downloaded_hash}."
            )
        print(f"{filename}: downloaded and verified.")

    print("Model files are ready in ./models")


if __name__ == "__main__":
    main()
