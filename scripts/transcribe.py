#!/usr/bin/env python3
"""Transcribe media to text — subtitle-first, else ASR.

Accepts either:
  * a working directory produced by ``fetch_media.py`` (reads manifest.json), or
  * a path to a local audio/video file (Track C).

Strategy:
  1. If a subtitle file (.srt/.vtt) is available, parse it to plain text and
     SKIP ASR (fastest, usually most accurate).
  2. Otherwise extract/locate audio and run ASR:
       - FunASR SenseVoice-Small (default): best for Chinese, runs on CPU,
         returns punctuation. Models from ModelScope.
       - faster-whisper (--engine whisper): multilingual fallback.

Outputs ``transcript.txt`` in the working dir (or alongside a file input),
and records the transcript source in the manifest when present.

Usage:
    python transcribe.py ./out --engine funasr
    python transcribe.py video.mp4 --engine whisper -o video_raw.md
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SUBTITLE_EXTS = {".srt", ".vtt", ".ass"}
AUDIO_EXTS = {".m4a", ".mp3", ".wav", ".webm", ".opus", ".aac", ".flac", ".ogg"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".flv", ".wmv", ".m4v"}


# --------------------------------------------------------------------------- #
# Post-processing
# --------------------------------------------------------------------------- #


def _load_glossary() -> list[tuple[re.Pattern, str]]:
    """Load alias->canonical mapping from term_glossary.json.

    File format: { "wrong term": "CorrectTerm", ... }
    Users maintain this file to improve ASR output for their domain.
    """
    path = Path(__file__).with_name("term_glossary.json")
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return []
    except Exception:
        return []

    out: list[tuple[re.Pattern, str]] = []
    for wrong, right in data.items():
        if not wrong or not right:
            continue
        pattern = re.escape(str(wrong)).replace(r"\ ", r"\s+")
        out.append((re.compile(pattern, re.I), str(right)))
    return out


_GLOSSARY_FIXES = _load_glossary()


def postprocess_transcript(text: str) -> str:
    """Clean up ASR output:
    1. Strip SenseVoice event emojis (🎼 BGM, 😊 emotion, 👏 applause …).
    2. Apply term_glossary.json corrections.
    3. Insert paragraph breaks after Chinese sentence-ending punctuation.
    """
    # 1. Remove SenseVoice event emoji tags and normalise whitespace.
    text = re.sub(r"\s*[🎼🎵🎶😊😄😢😭😡😤👏🎉]+\s*", " ", text)
    text = re.sub(r"\s{2,}", " ", text).strip()

    # 2. Apply glossary corrections (user-maintained).
    for pattern, replacement in _GLOSSARY_FIXES:
        text = pattern.sub(replacement, text)

    # 3. Paragraph breaks: after 。！？ followed by a non-punctuation character.
    text = re.sub(r"([。！？…]+)\s*(?=[^\s。！？])", r"\1\n\n", text)

    return text.strip()


# --------------------------------------------------------------------------- #
# Subtitle parsing
# --------------------------------------------------------------------------- #
def parse_subtitle(path: Path) -> str:
    """Convert an .srt/.vtt subtitle file to clean plain text."""
    raw = path.read_text(encoding="utf-8", errors="ignore")
    lines: list[str] = []
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.isdigit():  # srt sequence number
            continue
        if "-->" in s:  # timestamp line
            continue
        if s.upper().startswith("WEBVTT"):
            continue
        # strip inline vtt tags like <00:00:01.000> and <c> ... </c>
        s = re.sub(r"<[^>]+>", "", s)
        lines.append(s)
    # De-duplicate consecutive identical lines (common in auto-captions).
    out: list[str] = []
    for s in lines:
        if not out or out[-1] != s:
            out.append(s)
    return "\n".join(out).strip()


# --------------------------------------------------------------------------- #
# Audio preparation
# --------------------------------------------------------------------------- #
def _ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"  # rely on PATH


def ensure_wav(src: Path, work_dir: Path) -> Path:
    """Return a 16 kHz mono wav for ASR, converting if needed."""
    if src.suffix.lower() == ".wav":
        return src
    wav = work_dir / (src.stem + ".asr16k.wav")
    if wav.exists():
        return wav
    cmd = [_ffmpeg_exe(), "-y", "-i", str(src), "-ar", "16000", "-ac", "1", str(wav)]
    subprocess.run(cmd, check=True, capture_output=True)
    return wav


# --------------------------------------------------------------------------- #
# ASR engines
# --------------------------------------------------------------------------- #
def asr_funasr(wav: Path) -> str:
    try:
        from funasr import AutoModel
        from funasr.utils.postprocess_utils import rich_transcription_postprocess
    except ImportError:
        raise SystemExit(
            "Missing dependency for FunASR. Install with:\n"
            "    pip install funasr torch torchaudio"
        )
    model = AutoModel(
        model="iic/SenseVoiceSmall",
        vad_model="fsmn-vad",
        vad_kwargs={"max_single_segment_time": 30000},
        device="cpu",
        disable_update=True,
    )
    result = model.generate(input=str(wav), batch_size_s=300, merge_vad=True)
    text = result[0]["text"] if result else ""
    raw = rich_transcription_postprocess(text)
    return postprocess_transcript(raw)


def asr_whisper(wav: Path, model_size: str, language: str) -> str:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise SystemExit(
            "Missing dependency for whisper. Install with:\n"
            "    pip install faster-whisper"
        )
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    lang = None if language in ("auto", "", None) else language
    segments, _ = model.transcribe(str(wav), language=lang, vad_filter=True, beam_size=5)
    raw = " ".join(seg.text.strip() for seg in segments).strip()
    return postprocess_transcript(raw)


# --------------------------------------------------------------------------- #
# Input resolution
# --------------------------------------------------------------------------- #
def resolve_inputs(target: Path) -> tuple[Path, dict | None, Path | None, list[Path]]:
    """Return (work_dir, manifest_or_None, subtitle_or_None, audio_candidates)."""
    if target.is_dir():
        work_dir = target
        manifest = None
        mpath = work_dir / "manifest.json"
        if mpath.exists():
            manifest = json.loads(mpath.read_text(encoding="utf-8"))
        subs, audios = [], []
        for p in sorted(work_dir.iterdir()):
            if not p.is_file():
                continue
            ext = p.suffix.lower()
            if ext in SUBTITLE_EXTS:
                subs.append(p)
            elif ext in AUDIO_EXTS or ext in VIDEO_EXTS:
                audios.append(p)
        return work_dir, manifest, (subs[0] if subs else None), audios

    # Single file input (Track C).
    if not target.exists():
        raise SystemExit(f"Input not found: {target}")
    work_dir = target.parent
    # Look for a sidecar subtitle next to the file.
    sidecar = None
    for ext in SUBTITLE_EXTS:
        cand = target.with_suffix(ext)
        if cand.exists():
            sidecar = cand
            break
    return work_dir, None, sidecar, [target]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", help="Working dir from fetch_media.py OR a local audio/video file")
    parser.add_argument("--engine", choices=["funasr", "whisper"], default="funasr", help="ASR engine (default: funasr)")
    parser.add_argument("--language", default="auto", help="Language hint for whisper (default: auto)")
    parser.add_argument("--whisper-model", default="large-v3", help="faster-whisper model size (default: large-v3)")
    parser.add_argument("-o", "--output", default=None, help="Optional output path (default: <dir>/transcript.txt)")
    args = parser.parse_args(argv)

    target = Path(args.input)
    work_dir, manifest, subtitle, audios = resolve_inputs(target)

    source = "unknown"
    if subtitle is not None:
        print(f"Subtitle found → using it (skipping ASR): {subtitle.name}")
        text = parse_subtitle(subtitle)
        source = "subtitles"
    else:
        if not audios:
            raise SystemExit("No subtitle and no audio/video found to transcribe.")
        media = audios[0]
        print(f"No subtitle → ASR via {args.engine} on: {media.name}")
        wav = ensure_wav(media, work_dir)
        if args.engine == "funasr":
            text = asr_funasr(wav)
            source = "asr-funasr"
        else:
            text = asr_whisper(wav, args.whisper_model, args.language)
            source = "asr-whisper"

    if not text:
        print("Warning: transcript is empty.", file=sys.stderr)

    out_path = Path(args.output) if args.output else work_dir / "transcript.txt"
    out_path.write_text(text, encoding="utf-8")

    # Record the transcript source for the assemble step.
    if manifest is not None:
        manifest["transcript_source"] = source
        (work_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print(f"Transcript source: {source}")
    print(f"Characters       : {len(text)}")
    print(f"Saved            : {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
