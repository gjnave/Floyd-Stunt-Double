"""Fetch the pinned app-local MiniMax inference runtime without a Git dependency."""
from __future__ import annotations

import io
import shutil
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENGINE = ROOT / "engine"
REVISION = "fc86444383a8888de8036356a5febd5141010c41"
URL = f"https://github.com/Koongrizzly/MiniMax_H3_Standalone_app/archive/{REVISION}.zip"
REQUIRED = ("helpers/generate_ref.py", "runtime/sample_worker_ref.py", "vendor/comfy/model_management.py")


def ready() -> bool:
    return all((ENGINE / name).is_file() for name in REQUIRED)


def install() -> None:
    if ready():
        print("Inference runtime is already installed.", flush=True)
        return
    print("Downloading pinned MiniMax inference runtime...", flush=True)
    with urllib.request.urlopen(URL, timeout=90) as response:
        raw = response.read()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        roots = {item.filename.split("/")[0] for item in members if item.filename}
        if len(roots) != 1:
            raise RuntimeError("Unexpected inference runtime archive layout")
        prefix = next(iter(roots)) + "/"
        for item in members:
            name = item.filename
            if not name.startswith(prefix) or item.is_dir():
                continue
            relative = Path(name[len(prefix):])
            if not relative.parts or ".." in relative.parts or relative.is_absolute():
                raise RuntimeError(f"Unsafe runtime archive path: {name}")
            # The wrapper uses the backend modules, not its desktop UI/assets.
            if relative.parts[0] not in {"helpers", "runtime", "vendor", "presets"}:
                continue
            target = ENGINE / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.is_file():
                with archive.open(item) as source, target.open("wb") as dest:
                    shutil.copyfileobj(source, dest)
    if not ready():
        raise RuntimeError("Inference runtime download is incomplete")
    print("Inference runtime ready.", flush=True)


if __name__ == "__main__":
    install()
