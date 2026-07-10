#!/usr/bin/env python3
"""Fetch social-media / video / audio content via yt-dlp into a working directory.

Resolves the URL (including short links and pasted share text), extracts metadata,
detects the content type (video/audio vs image post), and downloads audio,
subtitles, and images. Writes a ``manifest.json`` describing everything for the
downstream transcribe / assemble steps.

Usage:
    python fetch_media.py "<url-or-share-text>" -o ./out
    python fetch_media.py "<url>" -o ./out --no-audio --sub-langs zh-Hans,zh,en

Designed to fail gracefully with a clear message when yt-dlp is missing.
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests

URL_RE = re.compile(r"https?://[^\s\u4e00-\u9fff]+", re.IGNORECASE)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
SUBTITLE_EXTS = {".srt", ".vtt", ".ass"}
AUDIO_EXTS = {".m4a", ".mp3", ".wav", ".webm", ".opus", ".aac", ".flac", ".ogg"}


def extract_url(text: str) -> str:
    """Pull the first http(s) URL out of arbitrary pasted share text."""
    text = text.strip()
    match = URL_RE.search(text)
    if not match:
        raise SystemExit(
            f"No http(s):// URL found in input: {text!r}\n"
            "Paste a link or share text that contains one."
        )
    # Strip common trailing punctuation that share text may append.
    return match.group(0).rstrip("，。、）)】>\"'")


def _ffmpeg_location() -> str | None:
    """Return a bundled ffmpeg path from imageio-ffmpeg if available."""
    try:
        import imageio_ffmpeg

        return str(Path(imageio_ffmpeg.get_ffmpeg_exe()).parent)
    except Exception:
        return None  # fall back to system ffmpeg on PATH


def ensure_netscape_cookies(cookies_path: str, out_dir: Path) -> str:
    """Accept a cookies file as either Netscape .txt or browser-export .json.

    JSON exports (EditThisCookie / J2TEAM Cookies / Cookie-Editor) are converted
    to a Netscape cookies.txt that yt-dlp understands. Returns the usable path.
    """
    src = Path(cookies_path)
    if not src.exists():
        raise SystemExit(f"Cookies file not found: {src}")

    text = src.read_text(encoding="utf-8", errors="ignore").lstrip()
    if not text.startswith(("[", "{")):
        return str(src)  # already Netscape format

    data = json.loads(text)
    cookies = data.get("cookies", data) if isinstance(data, dict) else data
    lines = ["# Netscape HTTP Cookie File"]
    for c in cookies:
        domain = c.get("domain", "")
        if not domain or "name" not in c:
            continue
        flag = "TRUE" if domain.startswith(".") else "FALSE"
        path = c.get("path", "/")
        secure = "TRUE" if c.get("secure") else "FALSE"
        exp = int(c.get("expirationDate") or c.get("expires") or 0)
        lines.append("\t".join([domain, flag, path, secure, str(exp), c["name"], str(c.get("value", ""))]))

    converted = out_dir / "cookies.netscape.txt"
    converted.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Converted JSON cookies → {converted} ({len(lines) - 1} cookies)")
    return str(converted)


def build_opts(
    out_dir: Path,
    *,
    want_audio: bool,
    want_subs: bool,
    want_images: bool,
    sub_langs: list[str],
    source_url: str,
    cookies_from_browser: str | None = None,
    cookies_file: str | None = None,
    user_agent: str | None = None,
    referer: str | None = None,
) -> dict:
    opts: dict = {
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "writethumbnail": want_images,
        "ignoreerrors": False,
    }

    # Some platforms (e.g. Douyin) require fresh cookies even when not logged in.
    if cookies_from_browser:
        # Value like "chrome", "edge", "firefox"; yt-dlp expects a tuple.
        opts["cookiesfrombrowser"] = (cookies_from_browser,)
    if cookies_file:
        opts["cookiefile"] = cookies_file

    # Use browser-like headers to reduce anti-bot blocks on some platforms.
    headers = {}
    if user_agent:
        headers["User-Agent"] = user_agent
    if referer:
        headers["Referer"] = referer
    elif "bilibili" in source_url or "b23.tv" in source_url:
        headers["Referer"] = "https://www.bilibili.com/"
    if headers:
        opts["http_headers"] = headers

    ff = _ffmpeg_location()
    if ff:
        opts["ffmpeg_location"] = ff

    if want_subs:
        opts.update(
            {
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": sub_langs,
                "subtitlesformat": "srt/vtt/best",
            }
        )

    if want_audio:
        opts.update(
            {
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "wav",
                        "preferredquality": "0",
                    }
                ],
                # 16 kHz mono wav is ideal for ASR.
                "postprocessor_args": {"ffmpegextractaudio": ["-ar", "16000", "-ac", "1"]},
            }
        )
    else:
        opts["skip_download"] = True

    return opts


def _classify(info: dict) -> str:
    """Return 'media' (has playable audio/video) or 'image' (photo post)."""
    if info.get("duration") or info.get("acodec") not in (None, "none") or info.get("formats"):
        # Most video/audio entries have formats or a duration.
        if info.get("duration") or any(
            f.get("acodec") not in (None, "none") for f in info.get("formats", [])
        ):
            return "media"
    # Image posts expose thumbnails / images but no audio formats.
    if info.get("thumbnails") or info.get("_type") == "playlist":
        return "image"
    return "media"


def _collect_files(out_dir: Path, stem: str) -> dict:
    audio, subs, images = [], [], []
    for p in sorted(out_dir.iterdir()):
        if not p.is_file() or not p.name.startswith(stem):
            continue
        ext = p.suffix.lower()
        if ext in SUBTITLE_EXTS:
            subs.append(p.name)
        elif ext in IMAGE_EXTS:
            images.append(p.name)
        elif ext in AUDIO_EXTS:
            audio.append(p.name)
    return {"audio": audio, "subtitles": subs, "images": images}


def _platform_key_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "douyin" in host:
        return "douyin"
    if "bilibili" in host or "b23.tv" in host:
        return "bilibili"
    if "xiaohongshu" in host or "xhslink" in host:
        return "xiaohongshu"
    if "youtube" in host or "youtu.be" in host:
        return "youtube"
    return "unknown"


def _write_fallback_plan(out_dir: Path, url: str, error_message: str) -> Path:
    """Write a structured degradation plan for callers and users.

    This makes failures actionable and script-friendly:
      1) local-file fallback (Track C)
      2) stable smoke-test platform fallback (Bilibili/YouTube)
    """
    platform = _platform_key_from_url(url)
    plan = {
        "status": "fetch_failed",
        "input_url": url,
        "platform_hint": platform,
        "error": error_message,
        "degradation_strategy": {
            "next_best_path": "track_c_local_media",
            "actions": [
                {
                    "id": "track_c_local_media",
                    "title": "Use local media file and continue with Track C",
                    "why": "Most reliable path when URL extraction is blocked by anti-bot/signature checks.",
                    "example": "python scripts/transcribe.py \"<local_media_file>\" --engine funasr -o \"<output>_raw.md\"",
                },
                {
                    "id": "smoke_test_stable_platform",
                    "title": "Smoke-test full pipeline with Bilibili/YouTube",
                    "why": "These platforms are usually more stable and often provide subtitles.",
                    "example": "python scripts/fetch_media.py \"<bilibili_or_youtube_url>\" -o \"<output_dir>\"",
                },
            ],
        },
    }
    if platform == "douyin":
        plan["platform_note"] = (
            "Douyin URL extraction is best-effort. Even with complete/fresh cookies,"
            " upstream signature/anti-bot changes can break yt-dlp extractors."
        )

    path = out_dir / "fallback_plan.json"
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _requests_cookiejar_from_netscape(cookie_file: str | None) -> requests.cookies.RequestsCookieJar | None:
    if not cookie_file:
        return None
    path = Path(cookie_file)
    if not path.exists():
        return None
    jar = http.cookiejar.MozillaCookieJar(str(path))
    try:
        jar.load(ignore_discard=True, ignore_expires=True)
    except Exception:
        return None
    rjar = requests.cookies.RequestsCookieJar()
    for c in jar:
        rjar.set(c.name, c.value, domain=c.domain, path=c.path)
    return rjar


def _extract_json_blob(html: str, marker: str, end_hint: str) -> dict | None:
    idx = html.find(marker)
    if idx < 0:
        return None
    start = idx + len(marker)
    end = html.find(end_hint, start)
    if end < 0:
        return None
    blob = html[start:end]
    try:
        return json.loads(blob)
    except Exception:
        return None


def _srt_time(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3600 * 1000)
    m, rem = divmod(rem, 60 * 1000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _write_srt_from_bili_sub_json(payload: dict, out_path: Path) -> bool:
    body = payload.get("body") or []
    if not body:
        return False
    lines = []
    for i, item in enumerate(body, start=1):
        start = float(item.get("from", 0.0))
        end = float(item.get("to", start + 1.0))
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        lines += [str(i), f"{_srt_time(start)} --> {_srt_time(end)}", content, ""]
    if not lines:
        return False
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return True


def _fetch_bili_subtitles_via_api(
    *,
    aid: int | str | None,
    cid: int | str | None,
    bvid: str | None,
    headers: dict,
    cookies: requests.cookies.RequestsCookieJar | None,
) -> list[dict]:
    """Query Bilibili player API for subtitle list when page playinfo has none."""
    if not cid:
        return []

    params = {"cid": str(cid)}
    if aid:
        params["aid"] = str(aid)
    elif bvid:
        params["bvid"] = str(bvid)
    else:
        return []

    try:
        r = requests.get(
            "https://api.bilibili.com/x/player/v2",
            params=params,
            headers=headers,
            cookies=cookies,
            timeout=25,
        )
        r.raise_for_status()
        payload = r.json() or {}
    except Exception:
        return []

    data = payload.get("data") or {}
    subtitle = data.get("subtitle") or {}
    subs = subtitle.get("subtitles") or []
    return subs if isinstance(subs, list) else []


def _try_bilibili_page_fallback(
    *,
    url: str,
    out_dir: Path,
    user_agent: str | None,
    referer: str | None,
    cookie_file: str | None,
) -> dict | None:
    """Fallback extractor for Bilibili when yt-dlp is blocked with HTTP 412.

    Reads publicly accessible page HTML, parses window.__INITIAL_STATE__ and
    window.__playinfo__, downloads first audio track and subtitles (if present).
    """
    headers = {
        "User-Agent": user_agent
        or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Referer": referer or "https://www.bilibili.com/",
    }
    cookies = _requests_cookiejar_from_netscape(cookie_file)

    page = requests.get(url, headers=headers, cookies=cookies, timeout=25)
    page.raise_for_status()
    html = page.text

    initial = _extract_json_blob(html, "window.__INITIAL_STATE__=", ";(function")
    playinfo = _extract_json_blob(html, "window.__playinfo__=", "</script>")
    if not initial or not playinfo:
        return None

    video_data = initial.get("videoData") or {}
    bvid = video_data.get("bvid") or initial.get("bvid") or "bilibili"
    aid = video_data.get("aid") or initial.get("aid")
    pages = video_data.get("pages") or []
    cid = None
    if pages and isinstance(pages[0], dict):
        cid = pages[0].get("cid")
    title = video_data.get("title") or initial.get("h1Title") or "Bilibili Video"
    author = (video_data.get("owner") or {}).get("name") or ""
    desc = video_data.get("desc") or ""
    duration = video_data.get("duration")
    tags = [t.get("tag_name") for t in (initial.get("tags") or []) if isinstance(t, dict) and t.get("tag_name")]

    files = {"audio": [], "subtitles": [], "images": []}

    # Download first DASH audio stream.
    dash = ((playinfo.get("data") or {}).get("dash") or {})
    audio_list = dash.get("audio") or []
    if audio_list:
        audio_url = audio_list[0].get("baseUrl") or audio_list[0].get("base_url")
        if audio_url:
            audio_path = out_dir / f"{bvid}.m4a"
            with requests.get(audio_url, headers=headers, cookies=cookies, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(audio_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            f.write(chunk)
            files["audio"].append(audio_path.name)

    # Download subtitle if available and convert to SRT for subtitle-first transcription.
    subtitle_obj = ((playinfo.get("data") or {}).get("subtitle") or {})
    subs = subtitle_obj.get("subtitles") or []
    if not subs:
        # Some pages omit subtitle list in __playinfo__; retry via player API.
        subs = _fetch_bili_subtitles_via_api(
            aid=aid,
            cid=cid,
            bvid=bvid,
            headers=headers,
            cookies=cookies,
        )
    if subs:
        sub_url = subs[0].get("subtitle_url")
        if sub_url:
            if sub_url.startswith("//"):
                sub_url = "https:" + sub_url
            elif sub_url.startswith("/"):
                sub_url = "https://api.bilibili.com" + sub_url
            sub_json = requests.get(sub_url, headers=headers, cookies=cookies, timeout=25)
            sub_json.raise_for_status()
            sub_payload = sub_json.json()
            sub_path = out_dir / f"{bvid}.srt"
            if _write_srt_from_bili_sub_json(sub_payload, sub_path):
                files["subtitles"].append(sub_path.name)

    # Build a manifest that matches the normal shape expected by downstream steps.
    return {
        "source": video_data.get("short_link_v2") or video_data.get("share_url") or url,
        "platform": "BiliBili",
        "content_type": "media",
        "title": title,
        "author": author,
        "upload_date": None,
        "duration": duration,
        "description": desc,
        "tags": tags,
        "id": bvid,
        "files": files,
        "extraction_mode": "bilibili_page_fallback",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("url", help="URL or pasted share text containing a URL")
    parser.add_argument("-o", "--output-dir", default="./out", help="Working directory (default: ./out)")
    parser.add_argument("--no-audio", action="store_true", help="Skip audio download")
    parser.add_argument("--no-subs", action="store_true", help="Skip subtitle download")
    parser.add_argument("--no-images", action="store_true", help="Skip image/thumbnail download")
    parser.add_argument(
        "--sub-langs",
        default="zh-Hans,zh,zh-CN,en",
        help="Comma-separated subtitle languages (default: zh-Hans,zh,zh-CN,en)",
    )
    parser.add_argument(
        "--cookies-from-browser",
        default=None,
        metavar="BROWSER",
        help="Load cookies from an installed browser (chrome/edge/firefox/...). "
        "Needed for platforms like Douyin that require fresh cookies even when not logged in.",
    )
    parser.add_argument(
        "--cookies",
        default=None,
        metavar="FILE",
        help="Path to a cookies file — Netscape cookies.txt OR a browser-export .json "
        "(EditThisCookie / J2TEAM / Cookie-Editor). JSON is auto-converted.",
    )
    parser.add_argument(
        "--user-agent",
        default=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        help="HTTP User-Agent for yt-dlp requests (default: desktop Chrome UA).",
    )
    parser.add_argument(
        "--referer",
        default=None,
        help="Optional HTTP Referer override. By default Bilibili links use https://www.bilibili.com/ .",
    )
    parser.add_argument(
        "--no-fallback-plan",
        action="store_true",
        help="Disable writing fallback_plan.json on fetch failure.",
    )
    args = parser.parse_args(argv)

    try:
        import yt_dlp
    except ImportError:
        print(
            "Missing dependency: yt-dlp. Install with:\n"
            "    pip install yt-dlp imageio-ffmpeg",
            file=sys.stderr,
        )
        return 2

    url = extract_url(args.url)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sub_langs = [s.strip() for s in args.sub_langs.split(",") if s.strip()]
    cookies_file = args.cookies
    if cookies_file:
        cookies_file = ensure_netscape_cookies(cookies_file, out_dir)
    opts = build_opts(
        out_dir,
        want_audio=not args.no_audio,
        want_subs=not args.no_subs,
        want_images=not args.no_images,
        sub_langs=sub_langs,
        source_url=url,
        cookies_from_browser=args.cookies_from_browser,
        cookies_file=cookies_file,
        user_agent=args.user_agent,
        referer=args.referer,
    )

    print(f"Resolving and downloading: {url}")
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as exc:  # noqa: BLE001 - report any extractor/network error
        msg = str(exc)
        platform = _platform_key_from_url(url)

        # Automatic degrade: Bilibili sometimes blocks extractor API (HTTP 412).
        # Try a direct page fallback before declaring failure.
        if platform == "bilibili" and "412" in msg:
            try:
                manifest = _try_bilibili_page_fallback(
                    url=url,
                    out_dir=out_dir,
                    user_agent=args.user_agent,
                    referer=args.referer,
                    cookie_file=cookies_file,
                )
                if manifest is not None:
                    manifest_path = out_dir / "manifest.json"
                    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
                    print("Bilibili extractor blocked (412) -> switched to direct-page fallback")
                    print(f"Title        : {manifest.get('title')}")
                    print(f"Audio        : {manifest.get('files', {}).get('audio') or '—'}")
                    print(f"Subtitles    : {manifest.get('files', {}).get('subtitles') or '—'}")
                    print(f"Manifest     : {manifest_path}")
                    return 0
            except Exception as fb_exc:  # noqa: BLE001
                msg += f" | page fallback failed: {fb_exc}"

        hint = (
            "The platform may be unsupported, login-gated, or region-locked."
        )
        if "cookie" in msg.lower():
            hint = (
                "This platform needs fresh cookies. Re-run with cookies from your browser, e.g.:\n"
                f'    python fetch_media.py "{url}" -o "{out_dir}" --cookies-from-browser edge\n'
                "(use the browser where you can open the link: chrome / edge / firefox)."
            )
        if platform == "douyin":
            hint += (
                "\n\nAuto-degrade suggestion: Douyin is best-effort due upstream signature changes. "
                "If this keeps failing, switch to Track C with a local media file."
            )

        fallback_path = None
        if not args.no_fallback_plan:
            fallback_path = _write_fallback_plan(out_dir, url, msg)

        print(f"yt-dlp failed: {exc}\n{hint}", file=sys.stderr)
        if fallback_path is not None:
            print(f"Fallback plan : {fallback_path}", file=sys.stderr)
        return 1

    if info.get("_type") == "playlist" and info.get("entries"):
        info = next((e for e in info["entries"] if e), info)

    content_type = _classify(info)
    stem = str(info.get("id", ""))
    files = _collect_files(out_dir, stem)

    manifest = {
        "source": info.get("webpage_url") or url,
        "platform": info.get("extractor_key") or info.get("extractor"),
        "content_type": content_type,
        "title": info.get("title"),
        "author": info.get("uploader") or info.get("channel") or info.get("creator"),
        "upload_date": info.get("upload_date"),
        "duration": info.get("duration"),
        "description": info.get("description"),
        "tags": info.get("tags") or info.get("categories") or [],
        "id": stem,
        "files": files,
    }

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nContent type : {content_type}")
    print(f"Title        : {manifest['title']}")
    print(f"Audio        : {files['audio'] or '—'}")
    print(f"Subtitles    : {files['subtitles'] or '—'}")
    print(f"Images       : {len(files['images'])} file(s)")
    print(f"Manifest     : {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
