"""Download table recognition models into models/ directory.

Run before building so PyInstaller --add-data "models;models" has content.
Already downloaded models are skipped (checks inference.yml).
"""

import os
import sys
import json
import tarfile
import urllib.request
import time

BOS_MODEL_BASE = (
    "https://paddle-model-ecology.bj.bcebos.com/paddlex/"
    "official_inference_model/paddle3.0.0"
)

TABLE_MODEL_NAMES = [
    "SLANet_plus",
    "PP-OCRv5_mobile_det",
    "PP-OCRv5_mobile_rec",
]

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
OFFICIAL_DIR = os.path.join(MODELS_DIR, "official_models")


def _model_dir(name):
    return os.path.join(OFFICIAL_DIR, name)


def _is_model_complete(name):
    return os.path.isfile(os.path.join(_model_dir(name), "inference.yml"))


def _download_and_extract(name):
    url = f"{BOS_MODEL_BASE}/{name}_infer.tar"
    tar_path = os.path.join(MODELS_DIR, f"{name}_infer.tar")

    print(f"  Downloading {name} ...")
    print(f"    URL: {url}")

    os.makedirs(MODELS_DIR, exist_ok=True)

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        start = time.time()
        with open(tar_path, "wb") as f:
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded * 100 // total
                    elapsed = time.time() - start + 0.001
                    speed = downloaded / elapsed / 1024 / 1024
                    mb_done = downloaded / 1024 / 1024
                    mb_total = total / 1024 / 1024
                    print(f"\r    {pct}%  ({mb_done:.1f}/{mb_total:.1f} MB, {speed:.1f} MB/s)", end="", flush=True)
        print()

    print(f"  Extracting {name} ...")
    os.makedirs(OFFICIAL_DIR, exist_ok=True)
    with tarfile.open(tar_path, "r:*") as tar:
        tar.extractall(OFFICIAL_DIR)

    os.remove(tar_path)
    print(f"  {name} done")


def main():
    print("=" * 50)
    print("  Downloading table recognition models")
    print("=" * 50)
    print()

    os.makedirs(MODELS_DIR, exist_ok=True)

    skipped = []
    downloaded = []
    failed = []

    for name in TABLE_MODEL_NAMES:
        if _is_model_complete(name):
            print(f"  [skip] {name} already exists")
            skipped.append(name)
            continue
        try:
            _download_and_extract(name)
            downloaded.append(name)
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            failed.append(name)

    manifest = {}
    manifest_path = os.path.join(MODELS_DIR, "manifest.json")
    if os.path.isfile(manifest_path):
        try:
            with open(manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:
            pass

    for name in TABLE_MODEL_NAMES:
        if name in downloaded or (name not in manifest and _is_model_complete(name)):
            manifest[name] = f"builtin-{name}"

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 50)
    skipped_count = len(skipped)
    downloaded_count = len(downloaded)
    failed_count = len(failed)
    print(f"  Skipped: {skipped_count}, Downloaded: {downloaded_count}, Failed: {failed_count}")
    if failed:
        failed_str = ", ".join(failed)
        print(f"  Failed models: {failed_str}")
        print("  Check your network and retry.")
        sys.exit(1)
    else:
        print("  All models ready!")
    print("=" * 50)


if __name__ == "__main__":
    main()
