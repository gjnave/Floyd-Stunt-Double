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
import app
from headliner_addon import selected_frame, reswap, _model_crop
from pipeline import run_protocol_worker
from app import latest_saved_video


class GuidedFrameTests(unittest.TestCase):
    def test_video_can_start_before_head_swap_frame(self):
        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / "video.mp4"
            head = Path(folder) / "head.png"
            result = Path(folder) / "swapped.png"
            for file in (video, head, result):
                file.touch()
            state = {"video": str(video.resolve()), "head": str(head.resolve()),
                     "frame_time": 3.0, "result": str(result)}
            captured = []

            def fake_generate(plan):
                captured.append(plan)
                yield "Generation complete · saved to result.mp4", "result.mp4"

            with patch("app.begin_generation", return_value=True), patch("app.end_generation"), \
                    patch("app.generate", side_effect=fake_generate):
                updates = list(app.guided_generate(video, head, state, 3, "left person", 0, 5,
                                                   .4, True, True, "", 3))
                stale_frame = list(app.guided_generate(video, head, state, 4, "left person", 0, 5,
                                                       .4, True, True, "", 3))
            self.assertEqual(len(captured), 1)
            self.assertEqual(captured[0].start, 0)
            self.assertEqual(captured[0].duration, 5)
            self.assertEqual(captured[0].character, result)
            self.assertEqual(updates[-1][1], "result.mp4")
            self.assertEqual(len(captured), 1)
            self.assertIn("selected frame changed", stale_frame[-1][0])

    def test_video_start_does_not_reset_selected_frame(self):
        config = app.build_ui().get_config_file()
        labels = {item["id"]: item.get("props", {}).get("label", "") for item in config["components"]}
        frame_id = next(key for key, label in labels.items() if label.startswith("Frame to swap at"))
        start_id = next(key for key, label in labels.items() if label == "Video start at (seconds)")
        length_id = next(key for key, label in labels.items() if label.startswith("Video length (seconds"))
        reset_targets = {target[0] for event in config["dependencies"]
                         if (event.get("api_name") or "").startswith("reset_guided")
                         for target in event["targets"]}
        self.assertIn(frame_id, reset_targets)
        self.assertNotIn(start_id, reset_targets)
        self.assertNotIn(length_id, reset_targets)
        preview_inputs = next(event["inputs"] for event in config["dependencies"]
                              if event.get("api_name") == "guided_preview")
        self.assertIn(frame_id, preview_inputs)
        self.assertNotIn(start_id, preview_inputs)
        generate_inputs = next(event["inputs"] for event in config["dependencies"]
                               if event.get("api_name") == "guided_generate")
        self.assertIn(frame_id, generate_inputs)
        self.assertIn(start_id, generate_inputs)
        self.assertIn(length_id, generate_inputs)

    def test_painted_crop_focuses_on_one_person(self):
        original = Image.new("RGB", (1920, 1080))
        mask = Image.new("L", original.size, 0)
        ImageDraw.Draw(mask).rectangle((444, 2, 1244, 959), fill=255)
        crop = _model_crop(original, mask)
        self.assertGreaterEqual(crop[0], 350)
        self.assertLessEqual(crop[2], 1350)
        self.assertEqual(crop[1], 0)

    def test_unpainted_auto_swap_keeps_full_frame(self):
        original = Image.new("RGB", (1920, 1080))
        mask = Image.new("L", original.size, 255)
        self.assertEqual(_model_crop(original, mask), (0, 0, 1920, 1080))

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
