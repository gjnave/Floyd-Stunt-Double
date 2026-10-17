"""Small non-GPU checks for the guided frame-to-video handoff."""
from __future__ import annotations

import sys
import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Floyd-Stunt-Double"))
from headliner_addon import selected_frame, reswap
from pipeline import run_protocol_worker
from app import latest_saved_video


class GuidedFrameTests(unittest.TestCase):
    def test_painted_mask_scales_to_full_frame(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "frame.png"
            Image.new("RGB", (400, 200), "blue").save(path)
            background = Image.new("RGB", (200, 100), "blue")
            layer = Image.new("RGBA", background.size, (0, 0, 0, 0))
            ImageDraw.Draw(layer).ellipse((40, 10, 80, 50), fill=(255, 180, 0, 255))
            original, mask = selected_frame({"background": background, "layers": [layer]}, str(path))
            self.assertEqual(original.size, (400, 200))
            self.assertEqual(mask.size, (400, 200))
            self.assertEqual(mask.getpixel((120, 60)), 255)
            self.assertEqual(mask.getpixel((300, 100)), 0)

    def test_paint_is_required(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "frame.png"
            image = Image.new("RGB", (200, 100), "blue")
            image.save(path)
            with self.assertRaisesRegex(ValueError, "Paint over"):
                selected_frame({"background": image, "layers": []}, str(path))

    def test_retry_uses_saved_mask_without_editor_upload(self):
        with tempfile.TemporaryDirectory() as folder:
            frame = Path(folder) / "frame.png"
            mask = Path(folder) / "mask.png"
            head = Path(folder) / "head.png"
            Image.new("RGB", (200, 100), "blue").save(frame)
            painted = Image.new("L", (200, 100), 0)
            ImageDraw.Draw(painted).rectangle((40, 20, 90, 70), fill=255)
            painted.save(mask)
            Image.new("RGB", (100, 100), "red").save(head)
            with patch("headliner_addon._render_swap", return_value=Path(folder) / "result.png") as worker:
                reswap(str(frame), str(mask), head)
                self.assertEqual(worker.call_args.args[1].getbbox(), (40, 20, 91, 71))

    def test_latest_saved_video_can_be_recovered(self):
        with tempfile.TemporaryDirectory() as folder:
            first = Path(folder) / "Floyd-Stunt-Double-first.mp4"
            second = Path(folder) / "Floyd-Stunt-Double-second.mp4"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            os.utime(first, ns=(1_000_000_000, 1_000_000_000))
            os.utime(second, ns=(2_000_000_000, 2_000_000_000))
            with patch("app.OUTPUTS", Path(folder)):
                video, note = latest_saved_video()
            self.assertEqual(video, str(second))
            self.assertIn("second.mp4", note)

    def test_one_shot_worker_protocol(self):
        code = ("import json,sys; "
                "print(json.dumps({'ready':True}),flush=True); "
                "request=json.loads(sys.stdin.readline()); "
                "print(json.dumps({'ok':True,'received':request['value']}),flush=True)")
        with tempfile.TemporaryDirectory() as folder:
            answer = run_protocol_worker([sys.executable, "-u", "-c", code],
                                         Path(folder), {"value": "head"},
                                         Path(folder) / "worker.log")
            self.assertEqual(answer["received"], "head")


if __name__ == "__main__":
    unittest.main()
