"""App-local Headliner head transfer for the guided Stunt Double flow.

The installer fetches the pinned Headliner inference core and verified weights
into this app. No separate Headliner app or ComfyUI server is launched.
"""
from __future__ import annotations

import hashlib
import io
import shutil
import time
import urllib.request
import uuid
import zipfile
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageOps

from pipeline import APP, JOBS, OUTPUTS, run_protocol_worker

SOURCE_REVISION = "24b9cfdc0f72d06372eb90b105575991436be643"
SOURCE_URLS = (
    f"https://codeberg.org/Cognibuild/Floyd-Headliner/archive/{SOURCE_REVISION}.zip",
    f"https://github.com/gjnave/Floyd-Headliner/archive/{SOURCE_REVISION}.zip",
)
ADDON = APP / "engine" / "headliner"
CORE = ADDON
WORKER_PYTHON = ADDON / ".venv" / "Scripts" / "python.exe"
MODEL_ROOT = ADDON / "models" / "fast-core"
LORA_ROOT = ADDON / "models" / "loras"

# Pinned upstream paths, exact size, and LFS SHA-256 from Floyd Headliner.
WEIGHTS = (
    ("Comfy-Org/Qwen-Image-2.1", "eee52e917df0f00d910bc1f04f8a4d825dcef255",
     "diffusion_models/qwen_image_2.1_int8_convrot.safetensors", 7256783064,
     "cb74113cb03faecd79611b01fd7fd642f0aa60d6f0b95086abee214d75eaa57d", MODEL_ROOT),
    ("Comfy-Org/Qwen3-VL", "056c1bacea04322faeab9d7c9edb8c3f24460023",
     "text_encoders/qwen3vl_8b_int8_convrot.safetensors", 9350798360,
     "8bfd0f6e12abf2d2d697ecc888e5e90b0d6741d6708f05799f53afa560452e8f", MODEL_ROOT),
    ("Comfy-Org/Qwen-Image-2.1", "eee52e917df0f00d910bc1f04f8a4d825dcef255",
     "vae/qwen_image_2.1_vae_bf16.safetensors", 675509688,
     "bb21f7473051e1ac368515dd3f2e15cd44d7a11748ee8823e1ddca3e4876b7c9", MODEL_ROOT),
    ("Alissonerdx/BFS-Best-Face-Swap", "0ca3913ade4b4ada458d60c232354e8586c4c181",
     "bfs_head_v1.1_alternative_qwen_2.1.safetensors", 318821008,
     "c5332bbc2f826856e7a09bce9740e97d39514b849368212e1f2c3c2c2d81c217", LORA_ROOT),
    ("Viggle/Qwen-Image-2.1-viggle-turbo", "bb26a0f38e5fe6c124aaccc9187a87eed5d9ed13",
     "Qwen-Image-2.1-viggle-turbo-v0.2.1-6step-lora-r256.safetensors", 1359147904,
     "2a0148f5c73abbed5f97da5ea356e439318aadb281d01fce4af39cdf43728803", LORA_ROOT),
)

PROMPT = (
    "head_swap: start with <image1> as the base image, keeping its lighting, "
    "environment, clothing, body, and background. remove the selected head from "
    "<image1> completely and replace it with the head from <image2>, strictly "
    "preserving the hair, eye color, nose structure from <image2>. copy the "
    "direction of the eye, head rotation, micro expressions from <image1>, "
    "high quality, sharp details"
)


def _verified(path: Path, size: int, sha256: str) -> bool:
    if not path.is_file() or path.stat().st_size != size:
        return False
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(16 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest() == sha256


def ready(check_hash: bool = False) -> bool:
    if not WORKER_PYTHON.is_file() or not (CORE / "core_worker.py").is_file() or not (CORE / "vendor/comfy_core/nodes.py").is_file():
        return False
    return all(_verified(root / name, size, sha) if check_hash else
               (root / name).is_file() and (root / name).stat().st_size == size
               for _, _, name, size, sha, root in WEIGHTS)


def install() -> None:
    """Called by the standard INSTALL.bat; verifies this app's own model copies."""
    if not (ADDON / "core_worker.py").is_file():
        errors = []
        for url in SOURCE_URLS:
            try:
                print(f"Downloading pinned Headliner inference code: {url}", flush=True)
                with urllib.request.urlopen(url, timeout=120) as response:
                    raw = response.read()
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    candidates = [p for p in archive.namelist() if p.endswith("/core_worker.py")]
                    if len(candidates) != 1:
                        raise RuntimeError("Headliner archive has an unexpected layout")
                    prefix = candidates[0][:-len("core_worker.py")]
                    for member in archive.infolist():
                        if member.is_dir() or not member.filename.startswith(prefix):
                            continue
                        relative = Path(member.filename[len(prefix):])
                        if not relative.parts or ".." in relative.parts or relative.is_absolute():
                            raise RuntimeError("Unsafe Headliner source path")
                        if relative.as_posix() not in {"core_worker.py", "LICENSE"} and relative.parts[:2] != ("vendor", "comfy_core"):
                            continue
                        target = ADDON / relative
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if not target.exists():
                            with archive.open(member) as source, target.open("wb") as dest:
                                shutil.copyfileobj(source, dest)
                if (ADDON / "core_worker.py").is_file() and (ADDON / "vendor/comfy_core/nodes.py").is_file():
                    break
            except Exception as error:
                errors.append(f"{url}: {error}")
        else:
            raise RuntimeError("Could not install the Headliner inference core: " + " | ".join(errors))
    from huggingface_hub import hf_hub_download
    for index, (repo, revision, name, size, sha, root) in enumerate(WEIGHTS, 1):
        target = root / name
        print(f"[{index}/{len(WEIGHTS)}] Checking {name}", flush=True)
        if _verified(target, size, sha):
            print(f"[{index}/{len(WEIGHTS)}] Verified {name}", flush=True)
            continue
        if target.exists():
            raise RuntimeError(f"Existing file failed verification and was preserved: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        cached = Path(hf_hub_download(repo_id=repo, revision=revision, filename=name,
                                      local_dir=ADDON / "models" / "_downloads" / repo.split("/")[-1]))
        if not _verified(cached, size, sha):
            raise RuntimeError(f"Downloaded file failed SHA-256 validation: {cached}")
        try:
            target.hardlink_to(cached)
        except OSError:
            shutil.copy2(cached, target)
        if not _verified(target, size, sha):
            raise RuntimeError(f"Installed file failed validation: {target}")
        print(f"[{index}/{len(WEIGHTS)}] Verified {name}", flush=True)
    if not ready(check_hash=True):
        raise RuntimeError("Head Swap installation did not verify completely")
    print("Head Swap models and inference core are ready.", flush=True)


def selected_frame(editor: dict, frame_path: str) -> tuple[Image.Image, Image.Image]:
    if not frame_path or not Path(frame_path).is_file():
        raise ValueError("Preview a video frame first.")
    if not isinstance(editor, dict):
        raise ValueError("Paint over the head in the frame preview first.")
    background = editor.get("background")
    if background is None:
        raise ValueError("Preview a video frame first.")
    with Image.open(frame_path) as file:
        original = ImageOps.exif_transpose(file).convert("RGB")
    if abs(background.width / background.height - original.width / original.height) > .02:
        raise ValueError("The preview no longer matches the video frame. Preview it again.")
    # Gradio's brush layers use their alpha channel; do not use the composite
    # because that would add the paint color to the reference image.
    mask = Image.new("L", background.size, 0)
    for layer in editor.get("layers") or []:
        if layer is not None:
            if layer.size != background.size:
                raise ValueError("Paint layer size changed. Preview and repaint the frame.")
            mask = ImageChops.lighter(mask, layer.convert("RGBA").getchannel("A"))
    mask = mask.point(lambda value: 255 if value > 0 else 0)
    if mask.getbbox() is None:
        raise ValueError("Paint over the entire target head, including hair, then press Swap head.")
    if mask.size != original.size:
        mask = mask.resize(original.size, Image.Resampling.NEAREST)
    return original, mask


def _model_crop(original: Image.Image, mask: Image.Image) -> tuple[int, int, int, int]:
    """Focus model inference on the painted head, not nearby people.

    The Headliner head-transfer worker does not accept a mask. The painted area
    selects its input crop, while the same mask limits compositing afterward.
    """
    left, top, right, bottom = mask.getbbox()
    if (left, top, right, bottom) == (0, 0, original.width, original.height):
        return 0, 0, original.width, original.height
    pad = max(24, round(max(right - left, bottom - top) * .08))
    return (max(0, left - pad), max(0, top - pad),
            min(original.width, right + pad), min(original.height, bottom + pad))


def _render_swap(original: Image.Image, mask: Image.Image, head_path: Path, feather: int = 8) -> Path:
    if not ready():
        raise RuntimeError("Head Swap models are not installed. Open Settings to add them.")
    if not head_path.is_file():
        raise ValueError("Upload a head reference image.")
    if mask.size != original.size or mask.getbbox() is None:
        raise ValueError("The saved head selection is invalid. Preview the frame and try again.")
    crop = _model_crop(original, mask)
    job = JOBS / ("head-" + time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8])
    job.mkdir(parents=True, exist_ok=False)
    body = job / "body.png"
    original.crop(crop).save(body)
    with Image.open(head_path) as file:
        head = ImageOps.exif_transpose(file).convert("RGB")
    reference = job / "head.png"
    head.save(reference)
    log = job / "headliner.log"
    command = [str(WORKER_PYTHON), "-u", str(CORE / "core_worker.py"),
               "--core-root", str(CORE / "vendor/comfy_core"),
               "--model-root", str(MODEL_ROOT), "--lora-root", str(LORA_ROOT)]
    payload = {"body_path": str(body), "head_path": str(reference), "prompt": PROMPT,
               "seed": -1, "steps": 6, "resolution": 768, "upscale": 1,
               "bfs_strength": 1.0, "turbo_strength": 1.0, "output_dir": str(job)}
    answer = run_protocol_worker(command, CORE, payload, log)
    if not answer.get("ok"):
        raise RuntimeError(answer.get("error", f"Head transfer failed. See {log}"))
    with Image.open(answer["output"]) as file:
        generated = file.convert("RGB")
    generated = generated.resize((crop[2] - crop[0], crop[3] - crop[1]), Image.Resampling.LANCZOS)
    blend = ImageChops.multiply(mask, mask.filter(ImageFilter.GaussianBlur(float(feather))))
    edited = original.copy()
    edited.paste(generated, crop[:2], blend.crop(crop))
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    result = OUTPUTS / f"Floyd-Stunt-Double-Head-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}.png"
    edited.save(result)
    mask.save(result.with_suffix(".mask.png"))
    return result


def swap(editor: dict, frame_path: str, head_path: Path, feather: int = 8) -> Path:
    original, mask = selected_frame(editor, frame_path)
    return _render_swap(original, mask, head_path, feather)


def automatic(frame_path: str, head_path: Path) -> Path:
    """Follow Headliner's unpainted, single-visible-person head-swap path."""
    if not frame_path or not Path(frame_path).is_file():
        raise ValueError("Preview a frame before swapping the head.")
    with Image.open(frame_path) as source:
        original = ImageOps.exif_transpose(source).convert("RGB")
    full_frame = Image.new("L", original.size, 255)
    return _render_swap(original, full_frame, head_path)


def reswap(frame_path: str, mask_path: str, head_path: Path, feather: int = 8) -> Path:
    """Retry with the saved selection, without re-uploading the phone's editor canvas."""
    if not frame_path or not Path(frame_path).is_file() or not mask_path or not Path(mask_path).is_file():
        raise ValueError("Preview and paint a frame before trying another head swap.")
    with Image.open(frame_path) as source:
        original = ImageOps.exif_transpose(source).convert("RGB")
    with Image.open(mask_path) as source:
        mask = source.convert("L")
    return _render_swap(original, mask, head_path, feather)


if __name__ == "__main__":
    install()
