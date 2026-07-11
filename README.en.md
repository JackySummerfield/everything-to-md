<div align="center">

[中文](README.md) · English

# 📄 Everything to Markdown

#### Convert anything to high-quality Markdown — documents, videos, audio — clean input for knowledge bases and LLM pipelines

![VS Code 1.99+](https://img.shields.io/badge/VS_Code-1.99+-007ACC?style=for-the-badge&logo=visualstudiocode&logoColor=white)
![GitHub Copilot](https://img.shields.io/badge/GitHub_Copilot-Skill-000?style=for-the-badge&logo=githubcopilot&logoColor=white)
![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

[Why This Exists](#-why-this-exists) · [What It Does](#-what-it-does) · [Quick Start](#-quick-start) · [Architecture](#-architecture)

</div>

---

## 🤔 Why This Exists

Building a knowledge base, RAG pipeline, or LLM-ready dataset? Step one is always turning raw materials into clean Markdown. But sources vary wildly — PDFs, Word docs, Bilibili videos, YouTube, local recordings — each with its own toolchain and pitfalls.

This Skill unifies all those paths into a single entry point: **tell the AI what you want to convert, it auto-detects the type, picks the right pipeline, outputs `_raw.md`, then guides you through interactive cleanup.**

## 📋 What It Does

| Input Type | Examples | Conversion Method |
|-----------|----------|------------------|
| Local documents | PDF, Word, PPT, Excel, HTML, EPUB | markitdown / docling / pymupdf4llm / marker (multiple routes) |
| Video/audio URLs | Bilibili, YouTube, Xiaohongshu | yt-dlp subtitle extraction / audio download → ASR → Markdown |
| Local media files | .mp3, .wav, .mp4, .mov | FunASR / Whisper speech-to-text → Markdown |

### Honest Assessment

| Capability | Status |
|-----------|--------|
| PDF/Word/PPT → Markdown | ✅ Reliable — multiple routes, battle-tested |
| Bilibili/YouTube with subtitles | ✅ High quality |
| Chinese audio ASR (clear speech) | ⚠️ Usable — expect jargon errors |
| Douyin/TikTok URL extraction | ❌ Unreliable (upstream anti-bot) |
| Auto-summarization | ❌ Rule-based quality is low — use LLM post-processing |

**Key insight**: This tool produces *transcripts*, not *summaries*. For knowledge extraction from spoken content, feed the transcript to an LLM.

## 🚀 Quick Start

### Prerequisites

- VS Code 1.99+ with GitHub Copilot
- Python ≥ 3.10

### Install Core Dependency

```bash
pip install 'markitdown[all]'
```

### Install As Needed

```bash
# Document routes
pip install pdf2docx           # PDF → Word → MD
pip install docling            # PDF → ML-based MD (~500MB models on first run)
pip install pymupdf4llm        # PDF → fast rule-based MD

# Media/audio
pip install yt-dlp imageio-ffmpeg
pip install funasr torch torchaudio    # Chinese ASR (FunASR)
pip install faster-whisper             # Multilingual ASR fallback
pip install rapidocr-onnxruntime       # OCR for image posts
```

### Usage

In Copilot Chat:

```
Convert my PDF to markdown
Convert this Bilibili video to markdown: https://www.bilibili.com/video/BVxxxxx
Transcribe this audio file
```

## 🏗 Architecture

```
User input → [Type Detection] → Track A (docs) / B (URLs) / C (local media) → _raw.md → Interactive cleanup
```

- **Track A**: Multiple conversion routes available (docling / pymupdf4llm / markitdown / marker). The Skill recommends the best fit and asks for confirmation.
- **Track B**: Extracts subtitles first; falls back to audio download + ASR if no subtitles.
- **Track C**: Direct speech-to-text on local files.

All intermediate files go to a user-specified output directory — never pollutes the Skill folder.

## 📁 File Structure

```
everything-to-md/
├── SKILL.md                        # AI workflow definition
├── README.md                       # Chinese docs
├── README.en.md                    # English docs (this file)
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
    ├── convert_docling_batch.py    # Large PDF batch conversion
    ├── inject_headings_v2.py       # PDF TOC → Markdown headings
    ├── split_recursive.py          # Split large MD by chapter
    ├── merge_code_blocks.py        # Merge split code blocks
    └── fix_*.py                    # Domain-specific fix scripts
```

## 🏷️ Triggers

`convert document` · `PDF to markdown` · `knowledge base` · `batch convert` · `document cleanup` · `bilibili` · `xiaohongshu` · `video to markdown` · `audio to markdown` · `transcribe`

## 📝 License

MIT
