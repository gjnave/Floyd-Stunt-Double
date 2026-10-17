"""Download and verify the exact MiniMax H3 files Stunt Double needs."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from huggingface_hub import hf_hub_download


ROOT = Path(__file__).resolve().parent
ENGINE = ROOT / "engine"
MODEL_ROOT = ENGINE / "models" / "minimax_h3"

# repo, commit, remote path, local path, byte size, LFS SHA-256
FILES = (
    ("koongrizzly/MiniMax_H3_int4_W4A8_ConvRot_Pruned", "483eee468874f1fd12dd2159666b7a72f0504cbc",
     "diffusion_models/minimax_h3_ref2va_pruned-w4a8_convrot_pruned.safetensors",
     "diffusion_models/minimax_h3_ref2va_pruned-w4a8_convrot_pruned.safetensors",
     12540857840, "16be87247dff1f49c7141d6bcde4c0465fc254128e2de60e34aebc744a8177df"),
    ("koongrizzly/MiniMax_H3_int4_W4A8_ConvRot_Pruned", "483eee468874f1fd12dd2159666b7a72f0504cbc",
     "text_encoders/qwen3vl_32b_minimax_h3-w4a8_convrot.safetensors",
     "text_encoders/qwen3vl_32b_minimax_h3-w4a8_convrot.safetensors",
     15697532972, "808e3b351e71e3dd2444e2cdd6accc701e5b40254ede13d481936e6332c7a0e2"),
    ("koongrizzly/MiniMax_H3_int4_W4A8_ConvRot_Pruned", "483eee468874f1fd12dd2159666b7a72f0504cbc",
     "video_vae/Minimax_h3_video_vae_fp16.safetensors",
     "video_vae/MiniMax-H3-video_vae_fp16.safetensors",
     5210400696, "be4968ac83726a7435c0ff33da67fe88507f4888a69e01543de84260ca3930a6"),
    ("koongrizzly/MiniMax_H3_int4_W4A8_ConvRot_Pruned", "483eee468874f1fd12dd2159666b7a72f0504cbc",
     "audio_vae/Minimax_H3_fp32_audio_vae.safetensors",
     "audio_vae/MiniMax-H3-audio_vae_fp32.safetensors",
     605429308, "37dddc2f3e6d5d5139d823d5ea283bbf304dadcb885b1ccda818aa13dade5ea2"),
    ("akatz-ai/MiniMax-H3-Character-Swap-LoRA", "d06323b7c8e70e97cdab48b78a1e05f786c8cba9",
     "h3_character_swap_v1.5.safetensors", "loras/h3_character_swap_v1.5.safetensors",
     155110792, "8f2c3c3eba161df8d0c6099598b4730f641f5ce01e04cd16d2427cff8a35218f"),
    ("lightx2v/Minimax-h3-Turbo", "a29e57d195f80ead07c89f89e55ecf2911e893c5",
     "minimax_h3_fl2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors",
     "loras/minimax_h3_fl2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors",
     1956193000, "08cfe946033af7d27719b964b6e0a0e50c32138daabbd6ce4137e23df6bf9980"),
)


def verify(path: Path, expected_size: int, expected_hash: str) -> bool:
    if not path.is_file() or path.stat().st_size != expected_size:
        return False
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower() == expected_hash


def run(verify_only: bool = False, adapters_only: bool = False) -> int:
    for repo, revision, remote, local, size, sha in FILES:
        if adapters_only and not local.startswith("loras/"):
            continue
        target = MODEL_ROOT / local
        if verify(target, size, sha):
            print(f"Verified: {target.name}", flush=True)
            continue
        if verify_only:
            print(f"Missing or damaged: {target}", flush=True)
            return 1
        target.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {target.name} from {repo} ({size / 1e9:.1f} GB)", flush=True)
        downloaded = Path(hf_hub_download(
            repo_id=repo, revision=revision, filename=remote,
            local_dir=MODEL_ROOT / "_hf_downloads" / repo.split("/")[-1],
        ))
        if not verify(downloaded, size, sha):
            raise RuntimeError(f"Download verification failed: {downloaded}")
        # Keep the verified HF cache file for resumable re-installs; hardlink when
        # possible so the required runtime path does not duplicate model bytes.
        if not target.exists():
            try:
                target.hardlink_to(downloaded)
            except OSError:
                import shutil
                shutil.copy2(downloaded, target)
        else:
            import shutil
            shutil.copy2(downloaded, target)
        if not verify(target, size, sha):
            raise RuntimeError(f"Installed model verification failed: {target}")
        print(f"Verified: {target.name}", flush=True)
    print("All six required model files are verified.", flush=True)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--adapters-only", action="store_true", help="Development check; customer installer always downloads all files")
    args = parser.parse_args()
    raise SystemExit(run(args.verify_only, args.adapters_only))
