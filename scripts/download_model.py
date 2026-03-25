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
    "deploy.prototxt": {
        "url": "https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/deploy.prototxt",
        "sha256": "2d180f723b3109e21f8287f6b3c691390d07b60eed998327cd3259ffa0e50608",
    },
    "mobilenet_iter_73000.caffemodel": {
        "url": "https://github.com/chuanqi305/MobileNet-SSD/raw/master/mobilenet_iter_73000.caffemodel",
        "sha256": "52eed8be80522c152a17fb56740de705b79881bde1a167e0e747310523685fc7",
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
    parser = argparse.ArgumentParser(description="Download MobileNet-SSD model files.")
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
