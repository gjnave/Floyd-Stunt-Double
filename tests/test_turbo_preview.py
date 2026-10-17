"""No-GPU checks for the short, lower-resolution preview path."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Floyd-Stunt-Double"))
import app
import pipeline


class FakeWorker:
    stdout = ["Loading models\n", "Saved\n"]
    returncode = 0

    def wait(self):
        return 0


class TurboPreviewTests(unittest.TestCase):
    def test_half_size_obeys_worker_alignment_and_minimum(self):
        full = pipeline.output_shape(1920, 1080, 0.4)
        preview = pipeline.output_shape(1920, 1080, 0.4, half_size=True)
        self.assertTrue(all(x >= 256 and x % 32 == 0 for x in preview))
        self.assertTrue(all(a <= b for a, b in zip(preview, full)))
        self.assertNotEqual(preview, full)

    def test_turbo_button_sets_preview_only_for_that_job(self):
        with tempfile.TemporaryDirectory() as folder:
            video, character = Path(folder) / "video.mp4", Path(folder) / "character.png"
            video.touch()
            character.touch()
            captured = []

            def fake_generate(plan):
                captured.append(plan)
                yield "Turbo preview complete · saved to PREVIEW.mp4", "PREVIEW.mp4"

            with patch("app.begin_generation", return_value=True), patch("app.end_generation"), \
                    patch("app.generate", side_effect=fake_generate):
                updates = list(app.run_turbo_preview(str(video), str(character), "the person", 1, 12,
                                                     0.4, False, True, "", 3))
                list(app.run_generation(str(video), str(character), "the person", 1, 12,
                                        0.4, False, True, "", 3))
            self.assertEqual(captured[0].preview_seconds, 3)
            self.assertEqual(captured[0].duration, 12)
            self.assertFalse(captured[0].turbo)  # The pipeline forces eight steps for preview.
            self.assertIsNone(captured[1].preview_seconds)
            self.assertTrue(updates[-1][2]["interactive"])
            self.assertTrue(updates[-1][3]["interactive"])

    def test_preview_clips_before_worker_and_forces_fast_adapter(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            video, character = root / "video.mp4", root / "character.png"
            video.touch()
            character.touch()
            engine = root / "engine"
            (engine / "helpers").mkdir(parents=True)
            (engine / "helpers" / "generate_ref.py").touch()
            ffmpeg_calls = []
            worker_calls = []

            def fake_ffmpeg(args):
                ffmpeg_calls.append(args)
                Path(args[-1]).write_bytes(b"test video")

            def fake_worker(command, _engine):
                worker_calls.append(command)
                Path(command[command.index("--output") + 1]).write_bytes(b"test render")
                return FakeWorker()

            paths = {key: root / key for key in ("diffusion", "text", "video_vae", "audio_vae", "character", "turbo")}
            with patch("pipeline.missing_models", return_value=[]), \
                    patch("pipeline.engine_root", return_value=engine), \
                    patch("pipeline.video_info", return_value=(12, 1920, 1080, False)), \
                    patch("pipeline.model_paths", return_value=paths), \
                    patch("pipeline._run_ffmpeg", side_effect=fake_ffmpeg), \
                    patch("pipeline._start_worker", side_effect=fake_worker), \
                    patch("pipeline.JOBS", root / "jobs"), patch("pipeline.OUTPUTS", root / "outputs"):
                preview = list(pipeline.generate(pipeline.JobPlan(video, character, "the person", 2, 8,
                                                                 0.4, "", False, False, 3)))
                selected = ffmpeg_calls[0]
                command = worker_calls[0]
                self.assertEqual(selected[selected.index("-t") + 1], "3.000")
                self.assertEqual(command[command.index("--steps") + 1], "8")
                self.assertIn(str(paths["turbo"]), command)
                self.assertIn("PREVIEW", Path(preview[-1][1]).name)
                preview_width = int(command[command.index("--width") + 1])
                self.assertLess(preview_width, pipeline.output_shape(1920, 1080, 0.4)[0])

                ffmpeg_calls.clear()
                worker_calls.clear()
                full = list(pipeline.generate(pipeline.JobPlan(video, character, "the person", 2, 8,
                                                              0.4, "", False, False)))
                selected = ffmpeg_calls[0]
                command = worker_calls[0]
                self.assertEqual(selected[selected.index("-t") + 1], "8.000")
                self.assertEqual(command[command.index("--steps") + 1], "20")
                self.assertNotIn(str(paths["turbo"]), command)
                self.assertNotIn("PREVIEW", Path(full[-1][1]).name)

                ffmpeg_calls.clear()
                worker_calls.clear()
                list(pipeline.generate(pipeline.JobPlan(video, character, "the person", 2, 8,
                                                        0.4, "", False, False, 0)))
                self.assertEqual(ffmpeg_calls[0][ffmpeg_calls[0].index("-t") + 1], "8.000")


if __name__ == "__main__":
    unittest.main()
