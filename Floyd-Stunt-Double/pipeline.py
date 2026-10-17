"""App-owned character swap orchestration around the pinned H3 Ref2VA worker."""
from __future__ import annotations

import os
import json
import math
import re
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock

import av

APP = Path(__file__).resolve().parent
OUTPUTS = APP / "outputs"
JOBS = APP / "jobs"
_guard = Lock()
_active: subprocess.Popen | None = None
_cancel = Event()


def engine_root() -> Path:
    override = os.getenv("GGF_STUNT_ENGINE")
    return Path(override).resolve() if override else APP / "engine"


def model_paths() -> dict[str, Path]:
    base = engine_root() / "models" / "minimax_h3"
    return {
        "diffusion": Path(os.environ["GGF_STUNT_REF2VA_MODEL"]).resolve() if os.environ.get("GGF_STUNT_REF2VA_MODEL") else base / "diffusion_models/minimax_h3_ref2va_pruned-w4a8_convrot_pruned.safetensors",
        "text": base / "text_encoders/qwen3vl_32b_minimax_h3-w4a8_convrot.safetensors",
        "video_vae": base / "video_vae/MiniMax-H3-video_vae_fp16.safetensors",
        "audio_vae": base / "audio_vae/MiniMax-H3-audio_vae_fp32.safetensors",
        "character": base / "loras/h3_character_swap_v1.5.safetensors",
        "turbo": base / "loras/minimax_h3_fl2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors",
    }


def missing_models() -> list[str]:
    return [name for name, path in model_paths().items() if not path.is_file()]


def ffmpeg_path() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except (ImportError, RuntimeError) as error:
        raise RuntimeError("FFmpeg is unavailable. Run INSTALL.bat again.") from error


def video_info(path: Path) -> tuple[float, int, int, bool]:
    with av.open(str(path)) as container:
        video = next((s for s in container.streams if s.type == "video"), None)
        if video is None:
            raise ValueError("The uploaded file has no video track.")
        duration = float(container.duration or 0) / 1_000_000
        if not duration and video.duration and video.time_base:
            duration = float(video.duration * video.time_base)
        if duration <= 0:
            raise ValueError("Could not read the video duration.")
        has_audio = any(s.type == "audio" for s in container.streams)
        width, height = int(video.width), int(video.height)
        if video.metadata.get("rotate") in {"90", "270", "-90", "-270"}:
            width, height = height, width
        return duration, width, height, has_audio


def output_shape(width: int, height: int, megapixels: float) -> tuple[int, int]:
    if width < 1 or height < 1:
        raise ValueError("Invalid video dimensions")
    factor = (float(megapixels) * 1_000_000 / (width * height)) ** 0.5
    out_w = max(256, round(width * factor / 32) * 32)
    out_h = max(256, round(height * factor / 32) * 32)
    return out_w, out_h


def valid_frames(seconds: float) -> int:
    # H3 uses an AV frame grid of 17n+5. Round upward, then trim export to time.
    wanted = max(22, int(seconds * 24 + 0.999))
    return 5 + 17 * ((wanted - 5 + 16) // 17)


def prompt_for(target: str, extra: str = "") -> str:
    subject = (target or "").strip() or "the main person"
    if len(subject) > 160:
        raise ValueError("Person description is too long.")
    prompt = (
        f"Replace {subject} in <Video 1> with the character in <Picture 1>. "
        "Keep the reference character's face, hair and clothing. Follow the source "
        "performance's pose, gaze, facial expressions and movement. Keep the camera, "
        "scene and other people consistent with <Video 1>."
    )
    return prompt + (" " + extra.strip() if extra and extra.strip() else "")


def _run_ffmpeg(args: list[str]) -> None:
    proc = subprocess.run([ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y", *args],
                          capture_output=True, text=True, timeout=3600)
    if proc.returncode:
        raise RuntimeError((proc.stderr or "FFmpeg failed.")[-1200:])


@dataclass
class JobPlan:
    video: Path
    character: Path
    target: str
    start: float
    duration: float
    megapixels: float = 0.4
    extra_prompt: str = ""
    turbo: bool = True
    preserve_audio: bool = True


def _start_worker(command: list[str], cwd: Path, stderr=None) -> subprocess.Popen:
    global _active
    with _guard:
        if _active and _active.poll() is None:
            raise RuntimeError("A generation is already running.")
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        _active = subprocess.Popen(command, cwd=str(cwd), stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT if stderr is None else stderr, text=True,
                                   bufsize=1, creationflags=flags)
        return _active


def run_protocol_worker(command: list[str], cwd: Path, payload: dict, log: Path) -> dict:
    """Run one app-owned JSON-line inference request, then release its VRAM."""
    global _active
    _cancel.clear()
    with log.open("w", encoding="utf-8") as diagnostics:
        proc = _start_worker(command, cwd, stderr=diagnostics)
        try:
            output, _ = proc.communicate(json.dumps(payload) + "\n", timeout=900)
        except subprocess.TimeoutExpired as error:
            cancel_active()
            proc.communicate()
            raise RuntimeError(f"Head transfer timed out. See {log}") from error
        finally:
            with _guard:
                if _active is proc:
                    _active = None
    if _cancel.is_set():
        raise RuntimeError("Head transfer stopped.")
    try:
        messages = [json.loads(line) for line in output.splitlines() if line.strip()]
    except (ValueError, TypeError) as error:
        raise RuntimeError(f"Head transfer returned invalid output. See {log}") from error
    if not messages or not messages[0].get("ready"):
        detail = messages[0].get("error") if messages else "Headliner worker did not start"
        raise RuntimeError(f"{detail}. See {log}")
    if proc.returncode or len(messages) < 2:
        raise RuntimeError(f"Head transfer stopped unexpectedly. See {log}")
    return messages[-1]


def cancel_active() -> bool:
    with _guard:
        _cancel.set()
        proc = _active
    if proc and proc.poll() is None:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True, check=False)
        else:
            proc.terminate()
        return True
    return False


def busy() -> bool:
    with _guard:
        return _active is not None and _active.poll() is None


def generate(plan: JobPlan):
    """Yield status and optional finished path. Only the app-owned worker runs on GPU."""
    if busy():
        raise RuntimeError("A generation is already running. Wait or press Stop.")
    missing = missing_models()
    if missing:
        raise RuntimeError("Required models are missing: " + ", ".join(missing) + ". Run INSTALL.bat.")
    engine = engine_root()
    if not (engine / "helpers/generate_ref.py").is_file():
        raise RuntimeError("Inference runtime is missing. Run INSTALL.bat.")
    if not plan.video.is_file() or not plan.character.is_file():
        raise ValueError("Add both a source video and a character image.")
    total, width, height, has_audio = video_info(plan.video)
    start = max(0.0, float(plan.start))
    if start >= total:
        raise ValueError("Start is past the end of the video.")
    duration = (total - start) if plan.duration <= 0 else min(float(plan.duration), total - start)
    if duration < 0.9:
        raise ValueError("Choose at least one second of video.")
    out_w, out_h = output_shape(width, height, plan.megapixels)
    job_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    work = JOBS / job_id
    work.mkdir(parents=True, exist_ok=False)
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    # Retain only the requested interval. Uploads may be hours long; copying
    # the whole file would delay the job and needlessly use the user's disk.
    source = work / "selected-source.mp4"
    yield "Preparing the selected part of your video…", None
    _run_ffmpeg(["-ss", f"{start:.3f}", "-i", str(plan.video),
                 "-t", f"{duration:.3f}", "-map", "0:v:0", "-map", "0:a:0?",
                 "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
                 "-c:a", "aac", str(source)])
    start = 0.0
    image = work / "character" / ("reference" + plan.character.suffix.lower())
    image.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(plan.character, image)
    result = OUTPUTS / f"Floyd-Stunt-Double-{job_id}.mp4"
    parts: list[Path] = []
    # Native H3 supports up to 99 seconds. Short segments keep memory and
    # quality manageable, while allowing arbitrary total input duration.
    segment_seconds = 8.0
    count = math.ceil(duration / segment_seconds)
    segment_lengths = [segment_seconds] * (count - 1) + [duration - segment_seconds * (count - 1)]
    if len(segment_lengths) > 1 and segment_lengths[-1] < 0.9:
        segment_lengths[-2] += segment_lengths.pop()
    count = len(segment_lengths)
    _cancel.clear()
    offset = 0.0
    for index, clip_seconds in enumerate(segment_lengths):
        if _cancel.is_set():
            raise RuntimeError("Generation stopped.")
        clip = work / f"clip-{index + 1:03d}.mp4"
        keep_audio = plan.preserve_audio and has_audio
        inputs = ["-ss", f"{start + offset:.3f}", "-i", str(source)]
        if not keep_audio:
            # Ref2VA decodes audio from every reference video. Supply silence
            # when the upload has no audio or the user disables source audio.
            inputs += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
        _run_ffmpeg([*inputs, "-t", f"{clip_seconds:.3f}", "-map", "0:v:0",
                     "-map", "0:a:0" if keep_audio else "1:a:0", "-vf",
                     f"fps=24,scale={out_w}:{out_h}:force_original_aspect_ratio=decrease,"
                     f"pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2",
                     "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(clip)])
        offset += clip_seconds
        wav = work / f"audio-{index + 1:03d}.wav"
        use_audio = keep_audio
        if use_audio:
            _run_ffmpeg(["-i", str(clip), "-vn", "-ac", "2", "-ar", "48000", str(wav)])
        rendered = work / f"render-{index + 1:03d}.mp4"
        models = model_paths()
        command = [sys.executable, str(engine / "helpers/generate_ref.py"),
                   "--prompt", prompt_for(plan.target, plan.extra_prompt),
                   "--width", str(out_w), "--height", str(out_h),
                   "--frames", str(valid_frames(clip_seconds)),
                   "--steps", "8" if plan.turbo else "20",
                   "--cfg", "1", "--sampler", "er_sde" if plan.turbo else "euler",
                   "--scheduler", "normal" if plan.turbo else "beta",
                   "--vram-manager-auto", "--ref-image", str(image),
                   "--ref-video", str(clip), "--ref2va-checkpoint", str(models["diffusion"]),
                   "--text-encoder", str(models["text"]),
                   "--video-vae", str(models["video_vae"]),
                   "--audio-vae", str(models["audio_vae"]),
                   "--lora", str(models["character"]), "--lora-strength", "1.0",
                   "--output", str(rendered)]
        if plan.turbo:
            command += ["--lora", str(models["turbo"]), "--lora-strength", "1.0"]
        if use_audio:
            command += ["--ref-audio", str(wav), "--lock-source-audio-index", "1"]
        log = work / f"segment-{index + 1:03d}.log"
        yield f"Preparing part {index + 1} of {count} · {out_w} × {out_h}", None
        proc = _start_worker(command, engine)
        stage = "Loading models"
        started = time.monotonic()
        with log.open("w", encoding="utf-8") as output:
            assert proc.stdout is not None
            for line in proc.stdout:
                output.write(line)
                output.flush()
                clean = re.sub(r"\x1b\[[0-9;]*m", "", line).strip()
                if clean and ("Loading" in clean or "Sampling" in clean or "VAE" in clean or "Saved" in clean):
                    stage = clean[:180]
                if _cancel.is_set():
                    break
                yield f"Part {index + 1}/{count} · {stage} · {int(time.monotonic() - started)}s", None
        code = proc.wait()
        with _guard:
            global _active
            if _active is proc:
                _active = None
        if _cancel.is_set():
            raise RuntimeError("Generation stopped.")
        if code or not rendered.is_file():
            raise RuntimeError(f"Part {index + 1} failed. See {log}. Last stage: {stage}")
        part = work / f"part-{index + 1:03d}.mp4"
        _run_ffmpeg(["-i", str(rendered), "-t", f"{clip_seconds:.3f}",
                     "-c:v", "libx264", "-crf", "18",
                     "-c:a", "aac" if use_audio else "copy",
                     *([] if use_audio else ["-an"]), str(part)])
        parts.append(part)
        yield f"Finished part {index + 1} of {count}", None
    if len(parts) == 1:
        shutil.copy2(parts[0], result)
    else:
        manifest = work / "parts.txt"
        manifest.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
        _run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(manifest),
                     "-c", "copy", str(result)])
    if not result.is_file() or result.stat().st_size == 0:
        raise RuntimeError("The output video was not created.")
    yield f"Complete · saved to {result}", str(result)
