# Media & Social URL → Markdown

Pipeline for **Track B** (social media / video / audio links) and **Track C** (local audio/video).

---

## Pipeline Overview

```
URL or share text
   │
   ▼
fetch_media.py  →  manifest.json + audio/subtitles/images
   │
   ▼
transcribe.py   →  transcript.txt  (subtitle-first; else ASR)
   │
   ▼
assemble_media_md.py  →  _raw.md  (frontmatter + caption + transcript)
```

---

## Commands

```bash
# 1. Fetch
python scripts/fetch_media.py "<url>" -o "./out" \
    [--cookies cookies.txt] [--cookies-from-browser edge]

# 2. Transcribe
python scripts/transcribe.py "./out" --engine funasr

# 3. Assemble
python scripts/assemble_media_md.py "./out" -o "./out/_raw.md" [--ocr]
```

Each script supports `--help`.

---

## Platform Notes

| Platform | Reliability | Subtitles | Cookie needed |
|----------|-------------|-----------|---------------|
| Bilibili | Stable (page fallback on 412) | Sometimes (CC) | No |
| YouTube | Stable | Often (auto-captions) | No |
| Xiaohongshu | Mostly works | Rare | No |
| Douyin/TikTok | **Unreliable** | Rare | Yes (and still may fail) |

### Douyin-specific

Douyin uses signed parameters (`a_bogus`) that yt-dlp cannot reliably generate. Even with complete fresh cookies, extraction may fail. This is an upstream limitation, not a bug in this pipeline.

**Policy**: One attempt. If it fails, suggest Track C (local file) or a stable platform.

### Bilibili 412 fallback

When yt-dlp gets HTTP 412, `fetch_media.py` automatically tries a direct-page fallback:
- Parses `window.__INITIAL_STATE__` and `window.__playinfo__`
- Downloads audio via DASH stream
- Attempts to fetch subtitles via player API (`/x/player/v2`)

### Cookie handling

- `--cookies <file>`: Netscape cookies.txt OR browser-export JSON (auto-converted)
- `--cookies-from-browser edge|chrome|firefox`: reads browser cookie store
- ⚠️ Chromium v127+ App-Bound Encryption may block cookie reading → use JSON export via browser extension instead

---

## ASR Engines

| Engine | Best for | Speed (CPU) | Install |
|--------|----------|-------------|---------|
| FunASR SenseVoice | Chinese | ~17x realtime | `pip install funasr torch torchaudio` |
| faster-whisper | Multilingual | ~8x realtime | `pip install faster-whisper` |

**Subtitle-first strategy**: If subtitles (.srt/.vtt) exist, they are used directly — no ASR needed. This produces the highest quality transcript.

### ASR Quality Reality

On technical Chinese oral content without subtitles:
- **Accuracy**: ~60–80% on domain jargon (model names, algorithm names get garbled)
- **Punctuation**: FunASR outputs punctuation; quality varies
- **Mitigation**: `transcribe.py` applies `term_glossary.json` corrections post-ASR

The `term_glossary.json` file maps common ASR errors to correct terms. Extend it for your domain:
```json
{
  "错误识别": "正确术语",
  "deept": "DeepSeek"
}
```

---

## Honest Assessment: What Works vs. What Doesn't

### Works well
- Bilibili/YouTube videos with subtitles → near-perfect transcript
- Short Chinese videos (< 10 min) with clear speech → usable transcript
- Image posts (Xiaohongshu) → caption + images + optional OCR

### Works with caveats
- Technical Chinese without subtitles → transcript has jargon errors, needs human review
- Long videos (> 30 min) → works but quality degrades, review needed

### Does not work reliably
- Douyin URL extraction → structurally unreliable
- Automatic knowledge summarization of noisy transcripts → rule-based NLP cannot replace LLM understanding
- Domain-specific term correction without prior dictionary → garbage in, garbage out

### Recommended workflow for knowledge extraction from video

1. Run the pipeline to get `transcript.txt`
2. Check quality score in `transcript_meta.json`
3. If score < 70, try to find subtitle source or use alternative ASR engine
4. For actual knowledge extraction: paste cleaned transcript into an LLM (ChatGPT/Claude/etc.)
5. Human reviews and edits the LLM output before adding to knowledge base

---

## Output Format

```markdown
---
source: "https://..."
platform: "BiliBili"
title: "..."
author: "..."
duration: "6:19"
transcript_source: "subtitles"  # or: asr-funasr / asr-whisper
tags: [...]
---

# {title}

> Captured from [{platform}]({source}) by {author}

## Caption

{description}

## Transcript

{transcript text}
```
