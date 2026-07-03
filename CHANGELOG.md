# Changelog

All notable changes to `/watch` are documented here.

## [0.3.1] — 2026-07-03

### Fixed
- `reverse_prompt.py` and `storyboard.py` resolved a relative `--out` path against the shell's current working directory instead of the `<workdir>` argument, so `--out prompts.md` (or `--out storyboard.html`) landed the file wherever the caller's shell happened to be — including polluting an unrelated git repo in one observed case. Both scripts now join a relative `--out` onto `workdir` before writing; an absolute `--out` still overrides as-is. Added a regression test (`test_cli_out_path.py`) covering both scripts and the absolute-path override case.

## [0.3.0] — 2026-07-03

### Added
- **Reverse-prompt mode** (`scripts/reverse_prompt.py`) — generates `<workdir>/prompts.md`, a video-gen-ready prompt sheet derived from an existing `/watch` workdir: STYLE GLOBAL block (aspect ratio, palette/light/energy), one block per detected plan (English visual description, transition), timestamped voiceover script, and on-screen text. Reuses `report.md`'s frame timestamps and transcript — no re-download, no re-extraction. Narrative fields use the same `<!-- pending Claude fill: ... -->` marker mechanism as `report.py`.
- **Storyboard mode** (`scripts/storyboard.py`) — generates a self-contained, printable `<workdir>/storyboard.html`: one card per plan with the source frame embedded as a base64 data URI, plan number/duration, and editable fields (Action, Dialogue/VO, camera movement, intention note). `--no-frames` produces a "production storyboard" variant with empty image slots for a client to shoot their own version.
- 5 unit tests covering both new modes under `scripts/tests/`.
- New `SKILL.md` section "Extended modes (fork Kawibcom)" documenting invocation, reuse of the existing workdir, and the dependency on real (non-fallback) scene-change data.

## [0.2.1] — 2026-07-03

### Fixed
- `extract_scene_change()`'s fallback-to-uniform-sampling floor (`uniform_fallback_min`) was a fixed absolute count (10), so short fast-cut videos (e.g. a 20s ad with ~9 real cuts) fell below it and had their genuine scene-change data silently discarded in favor of uniform sampling — `pacing.py` then reported "no scene-change data" for videos that clearly had cuts. The floor now scales with clip duration: `max(3, min(uniform_fallback_min, duration // 3))`. Added a regression test (`test_short_fast_cut_video_keeps_scene_change`).

## [0.2.0] — 2026-05-25

Based on [bradautomates/claude-video](https://github.com/bradautomates/claude-video) v0.1.3 by Bradley Bonanno (MIT). Its pipeline (yt-dlp + ffmpeg + Whisper) is preserved; everything below is additive.

### Added
- Scene-change frame extraction in `scripts/frames.py` — `extract_scene_change()` + `select_hero_frames()` using ffmpeg's `select=gt(scene,...)` filter. One frame per detected shot instead of uniform every-N-seconds sampling. Keeps token cost flat on long videos. Uniform sampling still available as a fallback for static/screen-recorded sources.
- 0-10s hook microscope in `scripts/hook.py` — 2 fps frames + word-level Whisper transcript on the opening 10 seconds, so the report can tell you what's on screen *as each word lands*.
- Editorial pacing metrics in `scripts/pacing.py` — shot count, cuts/min, mean + median shot length.
- Structured `report.md` emitter in `scripts/report.py` — fixed-schema ingest-ready report with `<!-- pending Claude fill: ... -->` markers for narrative sections (TL;DR, key moments, hook breakdown, editorial profile, quotable moments, entities, concepts).
- Word-level timestamps in `scripts/whisper.py` (Groq + OpenAI backends extended).
- New CLI flags in `scripts/watch.py`: `--intent`, `--no-scene-change`, `--no-hook-microscope`.
- Step 4.4 (stage to Obsidian vault) + Step 4.5 (ingest gate) in `SKILL.md` — optional auto-save to your Obsidian vault. Path resolved via `$WATCH_VAULT_DIR` or auto-detected from `~/Second brain/`, `~/Documents/Obsidian/`, `~/Obsidian/`. Skips cleanly when no vault is detected.
- 7 unit tests under `scripts/tests/` (stdlib `unittest`, no pytest dependency).

### Changed
- `SKILL.md` is now a v2 contract — describes the structured report, the marker-fill step, and the vault config. Backwards-compatible with /watch invocations that don't care about ingest.
- README documents the added features and the `$WATCH_VAULT_DIR` configuration.

## [0.1.3] — 2026-05-09

### Fixed
- Windows: `video.info.json` is read as UTF-8 (#4). Previously `Path.read_text()` defaulted to cp1252 on Windows and crashed on yt-dlp's UTF-8 output, silently dropping Title/Uploader from the report. Same fix applied to `.env` reads/writes in `whisper.py` and `setup.py`.
- `download.py` now logs info.json parse failures to stderr instead of swallowing them.

### Security
- Hardened subprocess argv against option injection (#2): inserted `--` before the URL in the yt-dlp argv, and tightened `is_url` to reject `-`-prefixed sources and require a non-empty netloc. Resolved video/audio paths to absolute via `Path.resolve()` before passing to `ffmpeg`/`ffprobe`, so a relative path starting with `-` can't be misinterpreted as a flag.

## [0.1.2] — 2026-04-24

### Fixed
- Windows console crash: removed the emoji from the long-video warning in `watch.py`; cp1252 consoles couldn't encode it.
- `setup.py` now prints `winget` / `pip` install commands on Windows instead of "unsupported platform" — matches what the README already promised.

### Changed
- `SKILL.md` notes that on Windows the scripts must be invoked with `python`, not `python3` (the latter is the Microsoft Store stub on Windows).

## [0.1.1] — 2026-04-24

### Fixed
- Added `commands/watch.md` shim so `/watch` is callable when installed as a Claude Code plugin. Without it, the plugin loaded but the skill wasn't exposed as a slash command.
- `scripts/build-skill.sh` now strips `commands/` from the claude.ai `.skill` bundle alongside `hooks/` and `.claude-plugin/`.

## [0.1.0] — 2026-04-24

Initial marketplace release.

### Added
- `/watch <url-or-path> [question]` slash command.
- yt-dlp download with native caption extraction (manual + auto-subs).
- ffmpeg frame extraction with auto-scaled fps (≤2 fps, ≤100 frames, duration-aware budget).
- `--start` / `--end` focused mode with denser frame budget and transcript range filtering.
- Whisper fallback (Groq preferred, OpenAI secondary) for videos without captions.
- `setup.py` preflight: silent `--check`, structured `--json`, and installer that auto-runs `brew install` on macOS.
- Session-start hook that prints a one-line status on first run / partial config.
- `.skill` bundle packaging for claude.ai upload via `scripts/build-skill.sh`.
