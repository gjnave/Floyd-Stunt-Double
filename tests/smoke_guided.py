"""Manual end-to-end guided smoke; requires installed models and test media.

Example: python tests/smoke_guided.py --video clip.mp4 --head portrait.jpg
         --head-box 160,90,310,270 --seconds 1
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Floyd-Stunt-Double"))
from app import guided_generate, guided_preview, guided_swap


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--head", type=Path, required=True)
    parser.add_argument("--head-box", required=True, help="x1,y1,x2,y2 in preview pixels")
    parser.add_argument("--seconds", type=float, default=1.0)
    args = parser.parse_args()
    preview = guided_preview(str(args.video.resolve()), 0)
    editor, frame_path = preview[0], preview[2]
    box = tuple(int(value) for value in args.head_box.split(","))
    layer = Image.new("RGBA", editor["background"].size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse(box, fill=(245, 185, 66, 255))
    editor["layers"] = [layer]
    edited, state, message, _, _ = guided_swap(editor, frame_path, str(args.head.resolve()),
                                               str(args.video.resolve()), 0)
    print(message, flush=True)
    if not edited or not state:
        return 1
    final = None
    for status, result, _ in guided_generate(str(args.video.resolve()), str(args.head.resolve()), state,
                                              "the drummer", 0, args.seconds, .3, True, True, ""):
        if status:
            print(status[-220:], flush=True)
        if result:
            final = result
    print(f"Edited still: {edited}\nVideo: {final}", flush=True)
    return 0 if final and Path(final).is_file() else 1


if __name__ == "__main__":
    raise SystemExit(main())
