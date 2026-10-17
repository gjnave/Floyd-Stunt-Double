"""Install an optional app-owned model pack from a manual source checkout.

The separate member installer remains outside the public source repository.
This helper supports the existing Settings model-download buttons for people
who installed the application manually.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from headliner_addon import ADDON, install as install_head, ready as head_ready
from model_manager import run as run_video

APP = Path(__file__).resolve().parent


def install_video() -> None:
    if run_video(verify_only=False, adapters_only=False):
        raise RuntimeError("Video model download did not complete")
    if run_video(verify_only=True, adapters_only=False):
        raise RuntimeError("Video model verification failed")
    print("Video Swap models installed and verified.", flush=True)


def install_head() -> None:
    uv = APP / "runtime" / "uv.exe"
    if not uv.is_file():
        found = shutil.which("uv")
        if not found:
            raise RuntimeError("Install uv from https://docs.astral.sh/uv/ before adding Head Swap models")
        uv = Path(found)
    venv = ADDON / ".venv"
    python = venv / "Scripts" / "python.exe"
    if not python.is_file():
        subprocess.run([str(uv), "venv", "--managed-python", "--python", "3.11", str(venv)], check=True)
    subprocess.run([
        str(uv), "pip", "install", "--python", str(python),
        "--index-url", "https://download.pytorch.org/whl/cu130",
        "torch==2.10.0+cu130", "torchvision==0.25.0+cu130", "torchaudio==2.10.0+cu130",
    ], check=True)
    subprocess.run([
        str(uv), "pip", "install", "--python", str(python),
        "-r", str(APP / "headliner-requirements.txt"),
    ], check=True)
    install_head()
    if not head_ready():
        raise RuntimeError("Head Swap model verification failed")
    print("Head Swap models installed and verified.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pack", choices=("video", "head"))
    args = parser.parse_args()
    (install_video if args.pack == "video" else install_head)()
