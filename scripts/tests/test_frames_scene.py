"""Smoke tests for scene-change frame extraction."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

from frames import extract_scene_change, extract  # noqa: E402


def _make_test_video(out: Path, seconds: int = 6) -> Path:
    """Generate a synthetic test video with 3 distinct scenes (color changes)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"color=c=red:size=320x240:duration=2",
        "-f", "lavfi", "-i", f"color=c=green:size=320x240:duration=2",
        "-f", "lavfi", "-i", f"color=c=blue:size=320x240:duration=2",
        "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
        "-map", "[v]",
        "-pix_fmt", "yuv420p",
        str(out),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out


class TestSceneChange(unittest.TestCase):

    def setUp(self):
        if shutil.which("ffmpeg") is None:
            self.skipTest("ffmpeg not available")
        self.tmp = Path(tempfile.mkdtemp(prefix="watch-test-"))
        self.video = _make_test_video(self.tmp / "input.mp4", seconds=6)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_detects_scene_boundaries(self):
        out_dir = self.tmp / "frames"
        frames = extract_scene_change(
            str(self.video), out_dir,
            scene_threshold=0.3, resolution=128, max_frames=10,
        )
        self.assertGreaterEqual(len(frames), 2, "expected >=2 scene frames")
        self.assertLessEqual(len(frames), 10, "respect max_frames cap")
        for f in frames:
            self.assertTrue(Path(f["path"]).exists())
            self.assertIn("timestamp_seconds", f)

    def test_short_fast_cut_video_keeps_scene_change(self):
        """Regression test: a short clip with real cuts must not fall back to
        uniform sampling just because it has fewer than the (formerly fixed)
        absolute floor of 10 detected scene changes.

        Mirrors the 7-Eleven Thailand ad case: a short, fast-cut video used to
        trip `len(frames) < uniform_fallback_min=10` and silently discard real
        scene-change data in favor of a uniform sample, even though the cuts
        were genuine. On this 8s / 4-color clip, ffmpeg's scene filter detects
        3 real transitions; the duration-scaled floor
        (`max(3, min(10, 8 // 3)) == 3`) must accept that as real data instead
        of forcing a uniform fallback.
        """
        fast_cuts = self.tmp / "fast_cuts.mp4"
        colors = ["red", "green", "blue", "yellow"]
        inputs: list[str] = []
        for c in colors:
            inputs += ["-f", "lavfi", "-i", f"color=c={c}:size=320x240:duration=2"]
        filter_inputs = "".join(f"[{i}:v]" for i in range(len(colors)))
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            *inputs,
            "-filter_complex", f"{filter_inputs}concat=n={len(colors)}:v=1:a=0[v]",
            "-map", "[v]",
            "-pix_fmt", "yuv420p",
            str(fast_cuts),
        ]
        subprocess.run(cmd, check=True, capture_output=True)

        out_dir = self.tmp / "fast_cuts_frames"
        frames = extract_scene_change(
            str(fast_cuts), out_dir,
            scene_threshold=0.3, resolution=128, max_frames=100,
        )
        sources = {f.get("source") for f in frames}
        self.assertEqual(
            sources, {"scene-change"},
            "short fast-cut video must not silently fall back to uniform sampling",
        )
        self.assertGreaterEqual(len(frames), 3, "expected the real cuts to survive")

    def test_falls_back_to_uniform_when_no_scenes(self):
        static = self.tmp / "static.mp4"
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "color=c=red:size=320x240:duration=4",
            "-pix_fmt", "yuv420p",
            str(static),
        ], check=True, capture_output=True)

        out_dir = self.tmp / "static_frames"
        frames = extract_scene_change(
            str(static), out_dir,
            scene_threshold=0.3, resolution=128,
            max_frames=10, uniform_fallback_min=5,
        )
        self.assertGreaterEqual(len(frames), 5, "fallback should produce >=5 frames")


if __name__ == "__main__":
    unittest.main()
