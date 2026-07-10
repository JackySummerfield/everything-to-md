# everything-to-md

Convert **anything** to high-quality Markdown — the essential first step for building knowledge bases, RAG pipelines, or LLM-ready content.

## What it does

| Input | Track | Method |
|-------|-------|--------|
| PDF, Word, PPT, Excel, HTML | **A** | markitdown / docling / pymupdf4llm / marker |
| Video/audio URL (Bilibili, YouTube, Xiaohongshu…) | **B** | yt-dlp → subtitles/ASR → Markdown |
| Local audio/video file | **C** | ASR (FunASR / whisper) → Markdown |

## Quick Start

```bash
# 1. Install
pip install 'markitdown[all]'

# 2. Use in VS Code Copilot Chat
> Convert my PDF to markdown
> 把这个B站链接转成markdown：https://www.bilibili.com/video/BVxxxxx
> 视频转文字
```

## Prerequisites

- VS Code 1.99+ with GitHub Copilot
- Python >= 3.10

### Optional dependencies (install as needed)

```bash
# Document conversion routes
pip install pdf2docx           # Route A2: PDF → Word → MD
pip install docling            # Route B: PDF → ML-based MD (~500MB models)
pip install pymupdf4llm        # Route C: PDF → fast rule-based MD

# Media/audio (Track B & C)
pip install yt-dlp imageio-ffmpeg
pip install funasr torch torchaudio    # Chinese ASR (FunASR SenseVoice)
pip install faster-whisper             # Multilingual ASR fallback
pip install rapidocr-onnxruntime       # OCR for image posts
```

## Architecture

```
User input → [Input-type Recognition] → Track A / B / C → _raw.md → Cleanup
```

The skill recognizes the input type, routes to the appropriate pipeline, produces an initial `_raw.md` draft, then offers interactive cleanup (noise removal, splitting, heading injection).

## Limitations & Honest Assessment

| Capability | Status |
|-----------|--------|
| PDF/Word/PPT → Markdown | ✅ Reliable (multiple routes, battle-tested) |
| Bilibili/YouTube with subtitles | ✅ High quality |
| Chinese audio ASR (clear speech) | ⚠️ Usable but expect jargon errors |
| Douyin/TikTok URL extraction | ❌ Unreliable (upstream anti-bot) |
| Auto-summarization of transcripts | ❌ Rule-based = low quality. Use LLM instead |

**Key insight**: This tool reliably produces *transcripts*, not *summaries*. For knowledge extraction from spoken content, the transcript is a starting point — feed it to an LLM for actual comprehension.

## File Structure

```
everything-to-md/
├── SKILL.md                        # Workflow definition for Copilot
├── README.md                       # This file
├── references/
│   ├── markdown-cleanup.md         # Post-conversion cleanup procedures
│   ├── media-url-to-md.md          # Track B/C pipeline details
│   └── optimization-checklist.md   # Noise detection patterns
└── scripts/
    ├── fetch_media.py              # URL → metadata + audio/subtitles/images
    ├── transcribe.py               # Subtitle-first → ASR transcription
    ├── summarize_transcript.py     # Quality assessment + keyword extraction
    ├── assemble_media_md.py        # Assemble final _raw.md
    ├── term_glossary.json          # ASR error → correct term mapping
    ├── convert_docling_batch.py    # Large-PDF batch conversion
    ├── inject_headings_v2.py       # PDF TOC → Markdown headings
    ├── split_recursive.py          # Split large MD by chapter
    ├── merge_code_blocks.py        # Merge split code blocks
    ├── fix_code_blocks_simtalk.py  # SimTalk-specific (domain)
    └── fix_linebreaks_simtalk_v2.py # SimTalk-specific (domain)
```

## Triggers

`convert document`, `文档转换`, `知识库`, `PDF to markdown`, `batch convert`, `document cleanup`, `split document`, `B站`, `bilibili`, `小红书`, `xiaohongshu`, `video to markdown`, `audio to markdown`, `视频转文字`, `音频转文字`, `transcribe`

## License

MIT
