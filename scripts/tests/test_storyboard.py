"""Tests for the storyboard extended mode (fork)."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

from report import write_report  # noqa: E402
from storyboard import write_storyboard  # noqa: E402


class TestStoryboard(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="watch-storyboard-test-"))
        self.frames_dir = self.tmp / "frames"
        self.frames_dir.mkdir()
        # A tiny real JPEG so the embed path is exercised end-to-end.
        jpeg_bytes = bytes.fromhex(
            "ffd8ffe000104a46494600010100000100010000ffdb004300"
            + "01" * 63
            + "ffc9000b0800010001010011ffcc0006001001010101ffda0008010100003f00d2cf20ffd9"
        )
        self.frame1 = self.frames_dir / "frame_0001.jpg"
        self.frame2 = self.frames_dir / "frame_0002.jpg"
        self.frame1.write_bytes(jpeg_bytes)
        self.frame2.write_bytes(jpeg_bytes)

        self.report_path = write_report(
            out_path=self.tmp / "report.md",
            source="https://example.com/ad.mp4",
            title="Test Ad",
            duration_seconds=10.0,
            intent="storyboard test",
            transcript_segments=[{"start": 0.0, "text": "Line one."}],
            transcript_source="captions",
            all_frames=[
                {"index": 0, "timestamp_seconds": 0.0, "path": str(self.frame1)},
                {"index": 1, "timestamp_seconds": 5.0, "path": str(self.frame2)},
            ],
            hero_frames=[{"index": 0, "timestamp_seconds": 0.0, "path": str(self.frame1)}],
            pacing={
                "shot_count": 2, "cuts_per_minute": 12.0,
                "mean_shot_length": 5.0, "median_shot_length": 5.0, "shots": [],
            },
            hook={"frames": [], "words": [], "ran": False, "skipped_reason": "video <30s"},
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_default_mode_embeds_frames(self):
        out = write_storyboard(
            self.tmp / "storyboard.html", self.tmp, self.report_path,
            include_frames=True, title=None, source_label=None,
        )
        html = out.read_text(encoding="utf-8")
        self.assertEqual(html.count('class="card"'), 2)
        self.assertIn("data:image/jpeg;base64,", html)
        self.assertIn("Test Ad", html)
        self.assertIn("PLAN 1", html)
        self.assertIn("PLAN 2", html)

    def test_no_frames_mode_leaves_empty_slots(self):
        out = write_storyboard(
            self.tmp / "storyboard-production.html", self.tmp, self.report_path,
            include_frames=False, title="Client Reshoot", source_label="internal ref",
        )
        html = out.read_text(encoding="utf-8")
        self.assertNotIn("data:image/jpeg;base64,", html)
        self.assertIn("frame-slot empty", html)
        self.assertIn("Client Reshoot", html)
        self.assertIn("internal ref", html)


if __name__ == "__main__":
    unittest.main()
