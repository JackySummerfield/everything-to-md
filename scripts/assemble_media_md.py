#!/usr/bin/env python3
"""Assemble a Markdown draft from a fetched media working directory.

Reads ``manifest.json`` (from fetch_media.py) and ``transcript.txt`` (from
transcribe.py), plus any downloaded images, and emits a ``_raw.md`` draft with
YAML frontmatter, the author's caption, and the transcript or image gallery.

For image posts, ``--ocr`` runs RapidOCR on each image and appends the
recognized text beneath it.

Usage:
    python assemble_media_md.py ./out -o ./out/_raw.md
    python assemble_media_md.py ./out -o ./out/_raw.md --ocr
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


def _fmt_date(yyyymmdd: str | None) -> str:
    if yyyymmdd and len(yyyymmdd) == 8 and yyyymmdd.isdigit():
        return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"
    return yyyymmdd or ""


def _fmt_duration(seconds) -> str:
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return ""
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _yaml_escape(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def ocr_image(path: Path) -> str:
    """Run RapidOCR on an image and return concatenated text (best-effort)."""
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        raise SystemExit(
            "Missing dependency for OCR. Install with:\n"
            "    pip install rapidocr-onnxruntime"
        )
    engine = getattr(ocr_image, "_engine", None)
    if engine is None:
        engine = RapidOCR()
        ocr_image._engine = engine  # cache across images
    result, _ = engine(str(path))
    if not result:
        return ""
    return "\n".join(line[1] for line in result).strip()


def build_frontmatter(manifest: dict) -> str:
    fields = {
        "source": manifest.get("source", ""),
        "platform": manifest.get("platform", ""),
        "title": manifest.get("title", ""),
        "author": manifest.get("author", ""),
        "date": _fmt_date(manifest.get("upload_date")),
        "duration": _fmt_duration(manifest.get("duration")),
        "transcript_source": manifest.get("transcript_source", ""),
    }
    lines = ["---"]
    for key, val in fields.items():
        if val in ("", None):
            continue
        lines.append(f"{key}: {_yaml_escape(str(val))}")
    tags = manifest.get("tags") or []
    if tags:
        joined = ", ".join(_yaml_escape(str(t)) for t in tags[:20])
        lines.append(f"tags: [{joined}]")
    lines.append("---")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input_dir", help="Working dir produced by fetch_media.py / transcribe.py")
    parser.add_argument("-o", "--output", default=None, help="Output markdown path (default: <dir>/_raw.md)")
    parser.add_argument("--ocr", action="store_true", help="OCR downloaded images (RapidOCR)")
    args = parser.parse_args(argv)

    work_dir = Path(args.input_dir)
    manifest_path = work_dir / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"manifest.json not found in {work_dir}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    title = manifest.get("title") or "Untitled"
    platform = manifest.get("platform") or "source"
    source = manifest.get("source") or ""
    author = manifest.get("author") or "unknown"
    date = _fmt_date(manifest.get("upload_date"))

    parts: list[str] = [build_frontmatter(manifest), "", f"# {title}", ""]
    attribution = f"> Captured from [{platform}]({source}) by {author}"
    if date:
        attribution += f" on {date}"
    parts += [attribution, ""]

    description = (manifest.get("description") or "").strip()
    if description:
        parts += ["## 文案 / Caption", "", description, ""]

    content_type = manifest.get("content_type", "media")
    files = manifest.get("files", {})

    # Transcript (media) ----------------------------------------------------- #
    has_transcript = False
    transcript_path = work_dir / "transcript.txt"
    if transcript_path.exists():
        transcript = transcript_path.read_text(encoding="utf-8").strip()
        if transcript:
            parts += ["## Transcript", "", transcript, ""]
            has_transcript = True

    # Degraded but still usable output: if media has no transcript yet, insert
    # a clear pending note so the markdown draft remains actionable.
    if content_type == "media" and not has_transcript:
        pending_reason = "Transcript not generated yet."
        plan_path = work_dir / "fallback_plan.json"
        if plan_path.exists():
            try:
                plan = json.loads(plan_path.read_text(encoding="utf-8"))
                if plan.get("error"):
                    pending_reason = f"Transcript unavailable: {plan['error']}"
            except Exception:
                pass
        parts += [
            "## Transcript",
            "",
            f"> {pending_reason}",
            ">",
            "> Next step:",
            "> 1. `python scripts/transcribe.py \"<output_dir>\" --engine funasr`",
            "> 2. or `python scripts/transcribe.py \"<output_dir>\" --engine whisper`",
            "",
        ]

    # Images (image posts) --------------------------------------------------- #
    images = files.get("images") or [
        p.name for p in sorted(work_dir.iterdir())
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    ]
    if images and content_type == "image":
        parts += ["## Images", ""]
        for name in images:
            parts.append(f"![]({name})")
            if args.ocr:
                text = ocr_image(work_dir / name)
                if text:
                    parts += ["", "> OCR:", "", text]
            parts.append("")

    out_path = Path(args.output) if args.output else work_dir / "_raw.md"
    out_path.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")

    print(f"Assembled: {out_path}")
    print(f"Sections : title{' + caption' if description else ''}"
          f"{' + transcript' if has_transcript else ' + transcript(pending)'}"
          f"{' + images' if (images and content_type == 'image') else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
