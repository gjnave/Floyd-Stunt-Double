"""Optional, app-owned model packs for Floyd Stunt Double.

The customer installer prepares the base runtime. Model weights and the optional
Head Swap runtime are installed later from Settings. Member installations use
the separate customer BAT; manual source clones use model_pack_setup.py.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from headliner_addon import ADDON, WEIGHTS, ready as head_ready
from model_manager import FILES, MODEL_ROOT
from pipeline import APP, busy, engine_root

VIDEO_BYTES = sum(row[4] for row in FILES)
HEAD_BYTES = sum(row[3] for row in WEIGHTS)
_GUARD = threading.Lock()
_GENERATION_GUARD = threading.Lock()
_JOB: dict[str, object] = {"running": False, "pack": "", "status": "", "started": 0.0,
                           "process": None, "cancel": False}


def begin_generation() -> bool:
    with _GUARD:
        return not _JOB["running"] and _GENERATION_GUARD.acquire(blocking=False)


def end_generation() -> None:
    _GENERATION_GUARD.release()


def work_busy() -> bool:
    return _GENERATION_GUARD.locked() or busy()


def video_ready() -> bool:
    if not (engine_root() / "helpers" / "generate_ref.py").is_file():
        return False
    return all((MODEL_ROOT / local).is_file() and (MODEL_ROOT / local).stat().st_size == size
               for _, _, _, local, size, _ in FILES)


def status() -> dict[str, object]:
    with _GUARD:
        state = {key: value for key, value in _JOB.items() if key != "process"}
    state["video_ready"] = video_ready()
    state["head_ready"] = head_ready()
    if state["running"]:
        elapsed = int(time.monotonic() - float(state["started"]))
        state["status"] = f"{state['status']} · {elapsed // 60}m {elapsed % 60:02d}s"
    return state


def _run_install(pack: str) -> None:
    installer = APP.parent / "INSTALL.bat"
    mode = "models-video" if pack == "video" else "models-head"
    last = "Preparing the model download" if pack == "video" else "Preparing the Head Swap runtime and models"
    log = APP / "logs" / f"model-install-{pack}.log"
    try:
        env = {**os.environ, "GGF_UNATTENDED": "1"}
        command = (["cmd.exe", "/d", "/c", str(installer), mode]
                   if installer.is_file() else
                   [sys.executable, str(APP / "model_pack_setup.py"), pack])
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as output:
            output.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} · {mode} ---\n")
            with subprocess.Popen(command,
                                  cwd=str(APP.parent), env=env, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True, errors="replace", bufsize=1,
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)) as process:
                with _GUARD:
                    _JOB["process"] = process
                    cancel_now = bool(_JOB["cancel"])
                if cancel_now:
                    _stop_process(process)
                assert process.stdout is not None
                for line in process.stdout:
                    output.write(line)
                    output.flush()
                    clean = line.strip().replace("\r", "")
                    if clean and clean.startswith(("Downloading", "Verified", "[", "Head Swap", "Video Swap",
                                                    "Setup stopped", "All six", "Could not", "Error", "Installing")):
                        last = clean[-200:]
                        with _GUARD:
                            _JOB["status"] = last
                code = process.wait()
        with _GUARD:
            cancelled = bool(_JOB["cancel"])
        if cancelled:
            last = "Model download stopped. Partial downloads were kept; press Install to resume later."
            return
        if code or not (video_ready() if pack == "video" else head_ready()):
            raise RuntimeError(f"Download incomplete ({last}). Press Install again to resume; existing files are kept. Log: {log}")
        last = ("Video Swap" if pack == "video" else "Head Swap") + " models installed and verified."
    except Exception as error:
        last = f"Model setup stopped: {error}"
    finally:
        with _GUARD:
            _JOB.update(running=False, pack="", status=last, started=0.0, process=None, cancel=False)


def _stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       capture_output=True, check=False)
    else:
        process.terminate()


def stop_install() -> str:
    with _GUARD:
        if not _JOB["running"]:
            return "No model download is running."
        _JOB["cancel"] = True
        _JOB["status"] = "Stopping the download; partial files will be kept."
        process = _JOB["process"]
    if process is not None:
        _stop_process(process)
    return "Stopping the download. You can press Install later to resume."


def start_install(pack: str) -> str:
    if pack not in ("video", "head"):
        return "Unknown model pack."
    if work_busy():
        return "Finish or stop the current generation first."
    if pack == "head" and not video_ready():
        return "Install Video Swap first; Head Swap + Video also needs those video models."
    if (video_ready() if pack == "video" else head_ready()):
        return "Those models are already installed."
    with _GUARD:
        if _JOB["running"] or _GENERATION_GUARD.locked() or busy():
            return "A model download or generation is already running."
        _JOB.update(running=True, pack=pack, status="Preparing the download", started=time.monotonic(),
                    process=None, cancel=False)
    try:
        threading.Thread(target=_run_install, args=(pack,), daemon=True).start()
    except Exception as error:
        with _GUARD:
            _JOB.update(running=False, pack="", status=f"Could not start model download: {error}",
                        started=0.0, process=None, cancel=False)
        return str(_JOB["status"])
    return "Download started. You can leave this phone page open; progress appears here."


def _owned_files(pack: str) -> list[Path]:
    if pack == "video":
        return [path for repo, _, remote, local, _, _ in FILES
                for path in (MODEL_ROOT / local, MODEL_ROOT / "_hf_downloads" / repo.split("/")[-1] / remote)]
    if pack == "head":
        return [path for repo, _, name, _, _, root in WEIGHTS
                for path in (root / name, ADDON / "models" / "_downloads" / repo.split("/")[-1] / name)]
    raise ValueError("Unknown model pack")


def has_files(pack: str) -> bool:
    return any(path.is_file() or path.is_symlink() for path in _owned_files(pack))


def remove_pack(pack: str) -> str:
    """Called only by the second, explicit confirmation button in Settings."""
    if work_busy():
        return "Stop the current generation before removing models."
    with _GUARD:
        if _JOB["running"] or _GENERATION_GUARD.locked() or busy():
            return "Wait until the model download or generation finishes before removing models."
        paths = _owned_files(pack)
        removed = 0
        for path in paths:
            # Exact manifest files only. Never traverse/delete a folder, output,
            # model in a different app, or a symlinked external directory.
            if not path.parent.resolve().is_relative_to(APP.resolve()):
                raise RuntimeError(f"Refusing an external model path: {path}")
            if path.is_file() or path.is_symlink():
                path.unlink()
                removed += 1
        _JOB["status"] = f"Removed {removed} model file links from this app. Outputs and other apps were kept."
        return str(_JOB["status"])
