#!/usr/bin/env python3
"""Generate a printable storyboard.html from an existing /watch workdir.

Extended mode (fork). Reuses the same plan-boundary derivation as
`reverse_prompt.py` (which itself reuses report.md's frame timestamps and
transcript) -- no re-download, no re-extraction. One card per plan, with the
corresponding frame embedded as a base64 data URI so the file is
self-contained and printable to PDF straight from a browser.

`--no-frames` produces a "production storyboard" variant: the image slot is
left as an empty, hand-drawing box instead of the source frame -- for
handing to a client who will shoot their own version rather than reproducing
the reference footage.
"""
from __future__ import annotations

import argparse
import base64
import datetime as _dt
import html
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from reverse_prompt import build_plans, parse_report, _duration_seconds, _fmt_time  # noqa: E402


def _frame_data_uri(frame_path: str) -> str | None:
    p = Path(frame_path)
    if not p.exists():
        return None
    data = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{data}"


def _card_html(plan: dict, include_frame: bool) -> str:
    t0, t1 = _fmt_time(plan["start_seconds"]), _fmt_time(plan["end_seconds"])
    frame_html = '<div class="frame-slot empty">(cadre à tourner)</div>'
    if include_frame:
        uri = _frame_data_uri(plan["frame_path"])
        if uri:
            frame_html = f'<img class="frame-slot" src="{uri}" alt="Plan {plan["index"]}">'
        else:
            frame_html = '<div class="frame-slot empty">(frame introuvable)</div>'

    return f"""
    <section class="card">
      <header class="card-head">
        <span class="plan-num">PLAN {plan['index']}</span>
        <span class="plan-time">{t0}–{t1} ({plan['duration_seconds']:.1f}s)</span>
      </header>
      {frame_html}
      <dl class="fields">
        <dt>Action</dt><dd class="fillable" contenteditable="true"></dd>
        <dt>Dialogue / VO</dt><dd class="fillable" contenteditable="true"></dd>
        <dt>Mouvement caméra</dt><dd class="fillable" contenteditable="true"></dd>
        <dt>Note d'intention</dt><dd class="fillable" contenteditable="true"></dd>
      </dl>
    </section>
    """


_CSS = """
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
    margin: 0; padding: 24px; background: #f4f4f5; color: #18181b;
  }
  header.page-head { margin-bottom: 24px; }
  header.page-head h1 { margin: 0 0 4px; font-size: 20px; }
  header.page-head p { margin: 2px 0; font-size: 13px; color: #52525b; }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
  }
  .card {
    background: #fff; border: 1px solid #d4d4d8; border-radius: 8px;
    padding: 12px; break-inside: avoid; page-break-inside: avoid;
  }
  .card-head {
    display: flex; justify-content: space-between; align-items: baseline;
    font-size: 12px; font-weight: 600; margin-bottom: 8px;
  }
  .plan-time { font-weight: 400; color: #71717a; }
  .frame-slot {
    width: 100%; aspect-ratio: 9 / 16; object-fit: cover;
    border-radius: 4px; background: #e4e4e7; display: block;
  }
  .frame-slot.empty {
    display: flex; align-items: center; justify-content: center;
    color: #a1a1aa; font-size: 12px; border: 1px dashed #a1a1aa;
  }
  dl.fields { margin: 10px 0 0; font-size: 12px; }
  dl.fields dt { font-weight: 600; margin-top: 6px; color: #3f3f46; }
  dl.fields dd { margin: 2px 0 0; min-height: 1.4em; }
  .fillable {
    border-bottom: 1px solid #d4d4d8; padding: 2px 0;
  }
  .fillable:empty::before { content: "…"; color: #d4d4d8; }
  @media print {
    body { background: #fff; padding: 0; }
    .grid { grid-template-columns: repeat(3, 1fr); }
    .card { border: 1px solid #a1a1aa; }
  }
"""


def write_storyboard(
    out_path: Path,
    workdir: Path,
    report_path: Path,
    include_frames: bool,
    title: str | None,
    source_label: str | None,
) -> Path:
    parsed = parse_report(report_path)
    fm = parsed["frontmatter"]
    frames = parsed["frames"]
    total_duration = _duration_seconds(fm)
    plans = build_plans(frames, total_duration)

    page_title = title or fm.get("title", "Storyboard")
    page_source = source_label or fm.get("source", "(unknown)")
    generated_on = _dt.date.today().isoformat()

    cards = "\n".join(_card_html(p, include_frames) for p in plans)

    doc = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(page_title)} — storyboard</title>
<style>{_CSS}</style>
</head>
<body>
  <header class="page-head">
    <h1>{html.escape(page_title)}</h1>
    <p>Source : {html.escape(page_source)}</p>
    <p>Généré le {generated_on} — {len(plans)} plans — durée {html.escape(fm.get('duration', '?'))}</p>
  </header>
  <div class="grid">
    {cards}
  </div>
</body>
</html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(doc, encoding="utf-8")
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="storyboard",
        description="Generate a printable storyboard.html from an existing /watch workdir.",
    )
    ap.add_argument("workdir", help="Path to a workdir produced by a prior /watch run")
    ap.add_argument("--out", default=None, help="Output path (default: <workdir>/storyboard.html)")
    ap.add_argument(
        "--no-frames", action="store_true",
        help="Production storyboard variant: leave image slots empty for a client to shoot their own version.",
    )
    ap.add_argument("--title", default=None, help="Override the page title (default: report.md title)")
    ap.add_argument("--source-label", default=None, help="Override the displayed source line")
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

    out_path = Path(args.out).expanduser().resolve() if args.out else workdir / "storyboard.html"
    result = write_storyboard(
        out_path, workdir, report_path,
        include_frames=not args.no_frames,
        title=args.title,
        source_label=args.source_label,
    )
    print(str(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
