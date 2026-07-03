"""Tests for the reverse-prompt extended mode (fork)."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

from report import write_report  # noqa: E402
from reverse_prompt import build_plans, parse_report, write_prompts  # noqa: E402


class TestReversePrompt(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="watch-reverse-prompt-test-"))
        # Build a report.md the same way watch.py would, so parse_report is
        # exercised against the real emitter's output shape.
        self.report_path = write_report(
            out_path=self.tmp / "report.md",
            source="https://example.com/ad.mp4",
            title="Test Ad",
            duration_seconds=20.0,
            intent="reverse-engineer the cuts",
            transcript_segments=[
                {"start": 0.0, "text": "Hook line."},
                {"start": 9.0, "text": "Offer reveal."},
            ],
            transcript_source="whisper (groq)",
            all_frames=[
                {"index": 0, "timestamp_seconds": 0.0, "path": str(self.tmp / "frames/frame_0001.jpg")},
                {"index": 1, "timestamp_seconds": 3.0, "path": str(self.tmp / "frames/frame_0002.jpg")},
                {"index": 2, "timestamp_seconds": 8.0, "path": str(self.tmp / "frames/frame_0003.jpg")},
            ],
            hero_frames=[
                {"index": 0, "timestamp_seconds": 0.0, "path": str(self.tmp / "frames/frame_0001.jpg")},
            ],
            pacing={
                "shot_count": 3, "cuts_per_minute": 9.0,
                "mean_shot_length": 6.67, "median_shot_length": 5.0, "shots": [],
            },
            hook={"frames": [], "words": [], "ran": False, "skipped_reason": "video <30s"},
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_parse_report_extracts_frames_and_transcript(self):
        parsed = parse_report(self.report_path)
        self.assertEqual(parsed["frontmatter"]["source"], "https://example.com/ad.mp4")
        self.assertEqual(parsed["frontmatter"]["title"], "Test Ad")
        self.assertEqual(len(parsed["frames"]), 3)
        self.assertEqual([f["timestamp_seconds"] for f in parsed["frames"]], [0.0, 3.0, 8.0])
        self.assertEqual(len(parsed["transcript"]), 2)
        self.assertEqual(parsed["transcript"][0]["text"], "Hook line.")

    def test_build_plans_uses_next_frame_as_boundary(self):
        frames = [
            {"path": "a.jpg", "timestamp_seconds": 0.0},
            {"path": "b.jpg", "timestamp_seconds": 3.0},
            {"path": "c.jpg", "timestamp_seconds": 8.0},
        ]
        plans = build_plans(frames, total_duration=20.0)
        self.assertEqual(len(plans), 3)
        self.assertEqual(plans[0]["start_seconds"], 0.0)
        self.assertEqual(plans[0]["end_seconds"], 3.0)
        self.assertEqual(plans[1]["end_seconds"], 8.0)
        # Last plan's end is clamped to total duration, not left open-ended.
        self.assertEqual(plans[2]["end_seconds"], 20.0)

    def test_write_prompts_emits_pending_markers_and_plan_blocks(self):
        out = write_prompts(self.tmp / "prompts.md", self.tmp, self.report_path)
        text = out.read_text(encoding="utf-8")

        self.assertIn("## STYLE GLOBAL", text)
        self.assertIn("## Plans", text)
        self.assertIn("## Script voix off (horodaté)", text)
        self.assertIn("## Textes incrustés", text)
        self.assertIn("### PLAN 1", text)
        self.assertIn("### PLAN 3", text)
        self.assertIn("<!-- pending Claude fill", text)
        self.assertIn("Hook line.", text)
        self.assertIn("**End of sequence.**", text)
        # Ensures the script only structures the file -- it must not have
        # invented a visual description on its own.
        self.assertNotIn("PLAN 4", text)


if __name__ == "__main__":
    unittest.main()
