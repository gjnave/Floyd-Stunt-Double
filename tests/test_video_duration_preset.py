"""Upload duration should populate both workflow tabs without limiting the user."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Floyd-Stunt-Double"))
import app


class VideoDurationPresetTests(unittest.TestCase):
    def test_new_video_sets_full_duration_and_zero_start(self):
        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / "portrait.mp4"
            video.touch()
            with patch("app.video_info", return_value=(72.345, 1080, 1920, True)):
                start, length, note = app.preset_video_length(str(video))
        self.assertEqual(start, 0)
        self.assertEqual(length, 72.34)
        self.assertIn("72.34s", note)

    def test_clearing_video_restores_initial_values(self):
        self.assertEqual(app.preset_video_length(None), (0, 8, ""))

    def test_unreadable_video_explains_error_without_replacing_values(self):
        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / "bad.mp4"
            video.touch()
            with patch("app.video_info", side_effect=ValueError("The uploaded file has no video track.")):
                start, length, note = app.preset_video_length(str(video))
        self.assertIsInstance(start, dict)
        self.assertIsInstance(length, dict)
        self.assertIn("no video track", note)


if __name__ == "__main__":
    unittest.main()
