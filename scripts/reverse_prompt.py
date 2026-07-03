#!/usr/bin/env python3
"""Reverse-engineer a video-gen prompt sheet from an existing /watch workdir.

Extended mode (fork). Consumes the `report.md` a prior `/watch` run already
produced -- same frames, same transcript, same per-frame timestamps -- and
re-derives plan (shot) boundaries from it. No re-download, no re-extraction:
this only reads files already on disk in the workdir.

Like `report.py`, narrative fields (global style, per-plan visual
description, transitions, on-screen text) are emitted as
`<!-- pending Claude fill: <hint> -->` markers. This script only structures
`prompts.md`; Claude fills the markers in by reading the frames, same as it
already does for `report.md` at /watch Step 4.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


def _pending(hint: str) -> str:
    return f"<!-- pending Claude fill: {hint} -->"


def _fmt_time(seconds: float) -> str:
    total = int(round(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _parse_time(value: str) -> float:
    parts = value.strip().split(":")
    try:
        if len(parts) == 1:
            return float(parts[0])
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    except ValueError:
        pass
    raise SystemExit(f"Cannot parse timestamp: {value!r}")


_FRAME_LINE_RE = re.compile(r"^\s*\*?\s*`([^`]+)`\s*\(t=([0-9:]+)\)\s*$", re.MULTILINE)
_TRANSCRIPT_BLOCK_RE = re.compile(r"## Transcript\n.*?```\n(.*?)\n```", re.DOTALL)
_TRANSCRIPT_LINE_RE = re.compile(r"^\[([0-9:]+)\]\s?(.*)$")
_FRONTMATTER_LINE_RE = re.compile(r"^([A-Za-z_]+):\s*(.*)$")


def parse_report(report_path: Path) -> dict:
    """Read report.md and pull out the structures the new modes reuse.

    Returns: {frontmatter: dict, frames: [{path, timestamp_seconds}],
              transcript: [{timestamp_seconds, text}]}
    """
    text = report_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    frontmatter: dict[str, str] = {}
    body_start = 0
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                body_start = i + 1
                break
            m = _FRONTMATTER_LINE_RE.match(line)
            if m:
                frontmatter[m.group(1)] = m.group(2)

    body = "\n".join(lines[body_start:])

    frames: list[dict] = []
    seen_paths: set[str] = set()
    for m in _FRAME_LINE_RE.finditer(body):
        path, t = m.group(1), m.group(2)
        if path in seen_paths:
            continue
        seen_paths.add(path)
        frames.append({"path": path, "timestamp_seconds": _parse_time(t)})
    frames.sort(key=lambda f: f["timestamp_seconds"])

    transcript: list[dict] = []
    tmatch = _TRANSCRIPT_BLOCK_RE.search(body)
    if tmatch:
        for line in tmatch.group(1).splitlines():
            lm = _TRANSCRIPT_LINE_RE.match(line.strip())
            if lm:
                transcript.append({
                    "timestamp_seconds": _parse_time(lm.group(1)),
                    "text": lm.group(2),
                })

    return {"frontmatter": frontmatter, "frames": frames, "transcript": transcript}


def _duration_seconds(frontmatter: dict) -> float:
    raw = frontmatter.get("duration", "")
    if not raw:
        return 0.0
    try:
        return _parse_time(raw)
    except SystemExit:
        return 0.0


def detect_aspect_ratio(workdir: Path) -> str | None:
    """Best-effort probe of the downloaded video's resolution via ffprobe.

    Returns a string like '1080x1920 (9:16 vertical)' or None if unavailable
    (local-file runs, deleted download/, or ffprobe missing) -- callers should
    fall back to a pending marker in that case.
    """
    if shutil.which("ffprobe") is None:
        return None
    video_dir = workdir / "download"
    if not video_dir.is_dir():
        return None
    candidates = sorted(video_dir.glob("video.*"))
    video_path = next(
        (p for p in candidates if p.suffix.lower() in
         {".mp4", ".mkv", ".webm", ".mov", ".m4v"}),
        None,
    )
    if video_path is None:
        return None

    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(video_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return None
    stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if not stream or not stream.get("width") or not stream.get("height"):
        return None
    w, h = stream["width"], stream["height"]
    orientation = "vertical" if h > w else ("horizontal" if w > h else "square")
    from math import gcd
    g = gcd(w, h) or 1
    return f"{w}x{h} ({w // g}:{h // g} {orientation})"


def build_plans(frames: list[dict], total_duration: float) -> list[dict]:
    plans: list[dict] = []
    for i, frame in enumerate(frames):
        start = frame["timestamp_seconds"]
        end = frames[i + 1]["timestamp_seconds"] if i + 1 < len(frames) else total_duration
        plans.append({
            "index": i + 1,
            "start_seconds": start,
            "end_seconds": max(start, end),
            "duration_seconds": max(0.0, end - start),
            "frame_path": frame["path"],
        })
    return plans


def write_prompts(out_path: Path, workdir: Path, report_path: Path) -> Path:
    parsed = parse_report(report_path)
    fm = parsed["frontmatter"]
    frames = parsed["frames"]
    transcript = parsed["transcript"]
    total_duration = _duration_seconds(fm)
    plans = build_plans(frames, total_duration)
    aspect = detect_aspect_ratio(workdir)

    lines: list[str] = []
    lines.append("---")
    lines.append(f"source: {fm.get('source', '(unknown)')}")
    lines.append(f"title: {fm.get('title', '(unknown)')}")
    lines.append(f"generated_from: {report_path}")
    lines.append(f"workdir: {workdir}")
    lines.append(f"plan_count: {len(plans)}")
    lines.append("---")
    lines.append("")

    lines.append(f"# Reverse-engineered prompt sheet — {fm.get('title', '(unknown)')}")
    lines.append("")

    lines.append("## STYLE GLOBAL")
    lines.append("")
    lines.append(f"- Duration: {fm.get('duration', '(unknown)')}")
    lines.append(f"- Shot count: {len(plans)}")
    lines.append(f"- Aspect ratio: {aspect or _pending('detect from frames — width:height + orientation')}")
    lines.append(_pending(
        "2-4 lines in English, optimized for video generators: color palette, "
        "lighting, overall energy/pacing. Base it on the hero frames + pacing "
        "data already in report.md."
    ))
    lines.append("")

    lines.append("## Plans")
    lines.append("")
    for plan in plans:
        t0, t1 = _fmt_time(plan["start_seconds"]), _fmt_time(plan["end_seconds"])
        lines.append(f"### PLAN {plan['index']} — {t0}–{t1} ({plan['duration_seconds']:.1f}s)")
        lines.append("")
        lines.append(f"_Frame: `{plan['frame_path']}`_")
        lines.append("")
        lines.append(_pending(
            "English, video-generator-optimized shot description: subject, "
            "action, framing/shot size, camera movement, lighting. One dense "
            "paragraph, no filler words."
        ))
        lines.append("")
        is_last = plan is plans[-1]
        if not is_last:
            lines.append(f"**Transition → PLAN {plan['index'] + 1}:** " + _pending(
                "cut type: hard cut, whip pan, match cut, etc."
            ))
        else:
            lines.append("**End of sequence.**")
        lines.append("")

    lines.append("## Script voix off (horodaté)")
    lines.append("")
    if transcript:
        lines.append("```")
        for seg in transcript:
            lines.append(f"[{_fmt_time(seg['timestamp_seconds'])}] {seg['text']}")
        lines.append("```")
    else:
        lines.append("_No transcript available in report.md._")
    lines.append("")

    lines.append("## Textes incrustés")
    lines.append("")
    lines.append(_pending(
        "List every on-screen text/graphic overlay you can see in the frames, "
        "one bullet per occurrence, timestamped: `- [MM:SS] <exact text>`. "
        "Omit this section's content if the video has no on-screen text."
    ))
    lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="reverse_prompt",
        description="Generate a video-gen prompt sheet (prompts.md) from an existing /watch workdir.",
    )
    ap.add_argument("workdir", help="Path to a workdir produced by a prior /watch run")
    ap.add_argument("--out", default=None, help="Output path (default: <workdir>/prompts.md)")
    args = ap.parse_args()

    workdir = Path(args.workdir).expanduser().resolve()
    if not workdir.is_dir():
        raise SystemExit(f"Not a directory: {workdir}")
    report_path = workdir / "report.md"
    if not report_path.exists():
        raise SystemExit(
            f"No report.md found at {report_path} — run this against a workdir "
            "a /watch invocation already produced."
        )

    out_path = Path(args.out).expanduser().resolve() if args.out else workdir / "prompts.md"
    result = write_prompts(out_path, workdir, report_path)
    print(str(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
