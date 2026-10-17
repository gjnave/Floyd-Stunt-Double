"""No-download checks for optional packs and the automatic head-swap path."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Floyd-Stunt-Double"))
import app
import headliner_addon
import model_packs


class OptionalModelTests(unittest.TestCase):
    def test_manifest_targets_stay_inside_this_app(self):
        self.assertEqual(len(model_packs._owned_files("video")), 12)
        self.assertEqual(len(model_packs._owned_files("head")), 10)
        for pack in ("video", "head"):
            for path in model_packs._owned_files(pack):
                self.assertTrue(path.is_relative_to(model_packs.APP))

    def test_model_removal_refuses_an_external_path_without_unlinking(self):
        outside = model_packs.APP.parent / "another-app" / "weights.safetensors"
        with patch("model_packs._owned_files", return_value=[outside]), \
                patch("model_packs.work_busy", return_value=False), \
                patch("model_packs.busy", return_value=False), \
                patch.object(Path, "unlink") as unlink:
            with self.assertRaisesRegex(RuntimeError, "Refusing an external model path"):
                model_packs.remove_pack("video")
        unlink.assert_not_called()

    def test_missing_models_show_install_choices(self):
        state = {"video_ready": False, "head_ready": False,
                 "running": False, "status": "", "started": 0.0}
        with patch("app.pack_status", return_value=state), patch("app.work_busy", return_value=False), \
                patch("app.has_files", return_value=False):
            updates = app.model_panel_state((False, False))
        self.assertEqual(len(updates), 22)
        self.assertTrue(updates[0]["visible"])
        self.assertIn("36.2 GB", updates[5])
        self.assertIn("19.0 GB", updates[6])
        self.assertFalse(updates[9]["interactive"])
        self.assertFalse(updates[18]["visible"])
        self.assertFalse(updates[19]["visible"])

    def test_video_install_enables_create_without_resetting_other_tabs(self):
        state = {"video_ready": True, "head_ready": False,
                 "running": False, "status": "Video Swap models installed and verified.", "started": 0.0}
        with patch("app.pack_status", return_value=state), patch("app.work_busy", return_value=False), \
                patch("app.has_files", return_value=True):
            updates = app.model_panel_state((False, False))
        self.assertFalse(updates[0]["visible"])
        self.assertTrue(updates[9]["interactive"])
        self.assertTrue(updates[13]["interactive"])
        self.assertEqual(updates[17], (True, False))
        self.assertTrue(updates[18]["visible"])
        self.assertFalse(updates[19]["visible"])
        self.assertTrue(updates[20]["interactive"])

    def test_completed_head_download_shows_both_installed_badges(self):
        state = {"video_ready": True, "head_ready": True,
                 "running": False, "status": "Head Swap models installed and verified.", "started": 0.0}
        with patch("app.pack_status", return_value=state), patch("app.work_busy", return_value=False), \
                patch("app.has_files", return_value=True):
            updates = app.model_panel_state((True, False))
        self.assertTrue(updates[18]["visible"])
        self.assertTrue(updates[19]["visible"])

    def test_automatic_swap_uses_whole_frame_without_paint_upload(self):
        source = MagicMock()
        source.__enter__.return_value = Image.new("RGB", (80, 50), "blue")
        with patch.object(Path, "is_file", return_value=True), \
                patch("headliner_addon.Image.open", return_value=source), \
                patch("headliner_addon._render_swap", return_value=Path("result.png")) as worker:
            result = headliner_addon.automatic("preview.png", Path("head.png"))
        self.assertEqual(result, Path("result.png"))
        self.assertEqual(worker.call_args.args[1].getbbox(), (0, 0, 80, 50))
        self.assertFalse(worker.call_args.kwargs.get("protect_painted", False))


if __name__ == "__main__":
    unittest.main()
