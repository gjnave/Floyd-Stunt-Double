"""Check and apply source updates from Codeberg with GitHub fallback."""
from __future__ import annotations

import argparse
import hashlib
import io
import shutil
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PACKAGE = ROOT.parent
APP_FILES = (
    "app.py", "pipeline.py", "model_manager.py", "model_packs.py", "model_pack_setup.py", "engine_manager.py",
    "headliner_addon.py", "headliner-requirements.txt",
    "access.py", "ui.css", "README.md", ".gitignore", "update_source.py",
)
ROOT_FILES = ("RUN.bat",)
SOURCES = tuple(f"Floyd-Stunt-Double/{name}" for name in APP_FILES) + ROOT_FILES
MIRRORS = (
    "https://codeberg.org/Cognibuild/Floyd-Stunt-Double/archive/main.zip",
    "https://github.com/gjnave/Floyd-Stunt-Double/archive/refs/heads/main.zip",
)


def fetch() -> tuple[str, dict[str, bytes]]:
    errors = []
    for url in MIRRORS:
        try:
            with urllib.request.urlopen(url, timeout=45) as response:
                raw = response.read()
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                members = {Path(*Path(name).parts[1:]).as_posix(): name
                           for name in archive.namelist() if len(Path(name).parts) >= 2}
                if not all(name in members for name in SOURCES):
                    raise ValueError("Repository archive is missing required app files")
                files = {}
                for name in SOURCES:
                    inner = members[name]
                    if ".." in Path(inner).parts or Path(inner).is_absolute():
                        raise ValueError("Unsafe repository archive entry")
                    files[name] = archive.read(inner)
            return url, files
        except Exception as error:
            errors.append(f"{url}: {error}")
    raise RuntimeError("Both source mirrors failed. " + " | ".join(errors))


def changes(files: dict[str, bytes]) -> list[str]:
    return [name for name in SOURCES if not (PACKAGE / name).is_file()
            or hashlib.sha256((PACKAGE / name).read_bytes()).digest() != hashlib.sha256(files[name]).digest()]


def check() -> tuple[str, list[str]]:
    url, files = fetch()
    return url, changes(files)


def apply() -> tuple[str, list[str]]:
    url, files = fetch()
    changed = changes(files)
    if not changed:
        return url, []
    backup = ROOT / "backups" / ("source-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    backup.mkdir(parents=True, exist_ok=False)
    for name in changed:
        dest = PACKAGE / name
        if dest.exists():
            saved = backup / name
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dest, saved)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(files[name])
    return url, changed


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    mirror, modified = check() if args.check else apply()
    print("Source: " + mirror)
    print("Changed: " + (", ".join(modified) if modified else "none"))
