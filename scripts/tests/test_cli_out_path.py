"""Regression test: relative --out must resolve against workdir, not cwd.

Covers the bug where `reverse_prompt.py <workdir> --out prompts.md` (and the
storyboard equivalent) wrote the output file into the shell's current working
directory instead of the workdir passed on the command line.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

from report import write_report  # noqa: E402


class TestRelativeOutResolvesAgainstWorkdir(unittest.TestCase):

    def setUp(self):
        self.workdir = Path(tempfile.mkdtemp(prefix="watch-cli-out-test-workdir-"))
        self.other_cwd = Path(tempfile.mkdtemp(prefix="watch-cli-out-test-cwd-"))
        write_report(
            out_path=self.workdir / "report.md",
            source="https://example.com/ad.mp4",
            title="Test Ad",
            duration_seconds=20.0,
            intent="cli --out regression test",
            transcript_segments=[{"start": 0.0, "text": "Hook line."}],
            transcript_source="captions",
            all_frames=[
                {"index": 0, "timestamp_seconds": 0.0, "path": str(self.workdir / "frames/frame_0001.jpg")},
                {"index": 1, "timestamp_seconds": 8.0, "path": str(self.workdir / "frames/frame_0002.jpg")},
            ],
            hero_frames=[{"index": 0, "timestamp_seconds": 0.0, "path": str(self.workdir / "frames/frame_0001.jpg")}],
            pacing={
                "shot_count": 2, "cuts_per_minute": 6.0,
                "mean_shot_length": 10.0, "median_shot_length": 10.0, "shots": [],
            },
            hook={"frames": [], "words": [], "ran": False, "skipped_reason": "video <30s"},
        )

    def tearDown(self):
        shutil.rmtree(self.workdir, ignore_errors=True)
        shutil.rmtree(self.other_cwd, ignore_errors=True)

    def test_reverse_prompt_relative_out_lands_in_workdir(self):
        subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "reverse_prompt.py"), str(self.workdir), "--out", "prompts.md"],
            cwd=str(self.other_cwd), check=True, capture_output=True, text=True,
        )
        self.assertTrue((self.workdir / "prompts.md").exists())
        self.assertFalse((self.other_cwd / "prompts.md").exists())

    def test_storyboard_relative_out_lands_in_workdir(self):
        subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "storyboard.py"), str(self.workdir), "--out", "storyboard.html"],
            cwd=str(self.other_cwd), check=True, capture_output=True, text=True,
        )
        self.assertTrue((self.workdir / "storyboard.html").exists())
        self.assertFalse((self.other_cwd / "storyboard.html").exists())

    def test_absolute_out_is_respected_as_is(self):
        forced = self.other_cwd / "forced-name.md"
        subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "reverse_prompt.py"), str(self.workdir), "--out", str(forced)],
            cwd=str(self.other_cwd), check=True, capture_output=True, text=True,
        )
        self.assertTrue(forced.exists())


if __name__ == "__main__":
    unittest.main()
