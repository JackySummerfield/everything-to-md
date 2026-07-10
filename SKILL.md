---
name: everything-to-md
description: 'Convert anything to high-quality Markdown — local documents (PDF, Word, PPT, Excel), social media links (Bilibili/YouTube/Xiaohongshu videos/audio/posts), and local audio/video files via speech-to-text. Recognizes input type and routes to the right pipeline. Triggers: document conversion, 文档转换, 知识库, knowledge base, markitdown, docling, PDF to markdown, convert document, batch convert, document cleanup, split document, 小红书, xiaohongshu, B站, bilibili, video to markdown, audio to markdown, 视频转文字, 音频转文字, transcribe, 字幕提取, 抖音, douyin.'
argument-hint: 'Provide file path(s), a folder, or a media/social URL to convert'
user-invocable: true
disable-model-invocation: false
---

# Everything to Markdown

Convert anything to high-quality Markdown suitable for knowledge bases, RAG pipelines, or LLM-ready content.

Auto-switch response language based on user input language.

### Interaction Principle

**在每个有多种选择或可选步骤的环节，先给出推荐，再让用户确认后执行。** 除非是单一确定性的流程（如格式转换只有一种路径），否则都通过 `vscode_askQuestions` 让用户做最终决策。不要替用户做选择后直接执行。

---

## Architecture

```
User input
   │
   ▼
[Step 0 — Input-type Recognition]
   │
   ├─ Local document(s)   .pdf .docx .pptx .xlsx .html .epub …  ──► Track A
   │
   ├─ Media URL           Bilibili / YouTube / Xiaohongshu / …   ──► Track B
   │
   ├─ Local audio/video   .mp3 .wav .m4a .mp4 .mov .mkv …       ──► Track C
   │
   └─ Ambiguous → ask user
   │
   ▼
_raw.md  ──►  [Shared Cleanup] (references/markdown-cleanup.md)
```

## Step 0 — Input-type Recognition

1. Contains `http(s)://` URL → **Track B**
2. Local file with document extension → **Track A**
3. Local file with media extension → **Track C**
4. Ambiguous → `vscode_askQuestions`

### Output Path Rule

**Never generate intermediate files or outputs inside the skill directory itself.**

- If user provides both input path and output path → use output path directly.
- If user only provides input path without output path → **ask user for output directory** via `vscode_askQuestions`, suggesting a default like `<input_parent>/<input_stem>_md/`.
- All intermediate files (WAV, manifest.json, subtitles, etc.) go into the output directory, not the skill folder.

---

## Track A — Local Documents

### A.1 Collect & Measure

Collect paths, measure file size and page count (PDF: `fitz.open(f).page_count`). Display summary.

### A.2 Route Selection

Present routes to user via `vscode_askQuestions`:

| Route | Pipeline | Quality | Speed (CPU) | Constraints |
|-------|----------|---------|-------------|-------------|
| **A1** | PDF → ilovepdf.com → DOCX → markitdown | Best | manual + fast | Not for confidential docs |
| **A2** | PDF → pdf2docx → DOCX → markitdown | Good | ~2 s/page | Fully local. Heading numbers may be lost |
| **B** ★ | PDF → docling → MD | Good | ~2 s/page | First run downloads ~500 MB models |
| **C** | PDF → pymupdf4llm → MD | Basic | ~0.3 s/page | No ML. Font-heuristic headings only |
| **D** | PDF → marker → MD | Best | ~1 s/page | **GPU required**. Impractical on CPU |

★ = recommended default for most cases.

**Word / PPT / Excel / HTML / other**: `markitdown "<input>" -o "<output>.md"` — no route selection needed.

### A.3 Install Dependencies

| Route | Install |
|-------|---------|
| All | `pip install 'markitdown[all]'` |
| A2 | + `pip install pdf2docx` |
| B | + `pip install docling` |
| C | + `pip install pymupdf4llm` |
| D | + `pip install marker-pdf` (GPU) |

### A.4 Convert

Output convention: `<source>_raw.md` alongside source. Multiple files → `markdown/` subfolder.

Each pipeline step outputs to a distinct filename — never overwrite the previous step's output.

**Large PDFs (>200 pages)**: Use batch conversion to avoid OOM:
```bash
python scripts/convert_docling_batch.py "<input>.pdf" -o "<output_dir>" -b 100
```

### A.5 → Shared Cleanup (Step 5)

---

## Track B — Media & Social URLs

Convert a video/audio/image-post URL into Markdown with metadata + caption + transcript.

### Platform Support & Limitations

| Platform | Reliability | Notes |
|----------|-------------|-------|
| **Bilibili** | ★★★ Stable | May need page fallback on 412. Often has subtitles |
| **YouTube** | ★★★ Stable | Usually has auto-captions |
| **Xiaohongshu** | ★★☆ Mostly works | Image posts + short videos |
| **Douyin/TikTok** | ★☆☆ **Best-effort** | Anti-bot breaks yt-dlp regularly. Treat as unreliable |
| Others (1700+ sites) | Varies | Whatever yt-dlp supports |

> **Douyin Policy**: Do NOT loop retries on failure. If it fails, suggest user provide local media file (Track C) or use a more stable platform for validation.

### B.1 Install

```bash
pip install yt-dlp imageio-ffmpeg          # URL parsing + bundled ffmpeg
pip install funasr torch torchaudio         # ASR (FunASR SenseVoice, Chinese-best, CPU)
# Optional:
pip install faster-whisper                  # Multilingual ASR fallback
pip install rapidocr-onnxruntime            # OCR for image posts
```

### B.2 Fetch

```bash
python scripts/fetch_media.py "<url>" -o "<output_dir>"
```

Downloads metadata, audio, subtitles, images. Writes `manifest.json`.

### B.3 Transcribe

```bash
python scripts/transcribe.py "<output_dir>" --engine funasr
```

**Strategy**: subtitle-first (parse .srt/.vtt if available, skip ASR). Else run ASR.

### B.4 Assemble

```bash
python scripts/assemble_media_md.py "<output_dir>" -o "<output_dir>/_raw.md" [--ocr]
```

Produces `_raw.md` with YAML frontmatter + caption + transcript.

### B.5 → Shared Cleanup (Step 5)

### Known Limitations (Track B/C)

1. **ASR quality on technical content**: FunASR/Whisper struggle with domain jargon (model names, algorithm terms). Expect ~60–80% accuracy on technical Chinese oral content without subtitles.
2. **No reliable automatic summarization**: Rule-based summarization of noisy ASR transcripts produces low-quality output. For knowledge-dense summary, use an LLM (paste transcript into ChatGPT/Claude) or wait for subtitle-source transcripts.
3. **Douyin is structurally unreliable**: yt-dlp's Douyin extractor breaks with upstream signature changes. This is not fixable at our level.
4. **Corporate network**: SSL interception (Zscaler etc.) may block model downloads. See your IT environment notes for cert patching.

---

## Track C — Local Audio/Video

Reuses Track B transcription on a local file:

```bash
python scripts/transcribe.py "<file>" --engine funasr
python scripts/assemble_media_md.py "<dir>" -o "<dir>/_raw.md"
```

Same limitations as Track B regarding ASR quality.

---

## Step 5 — Shared Cleanup

After any track produces `_raw.md`, offer cleanup per [markdown-cleanup.md](./references/markdown-cleanup.md):

- Noise removal (page numbers, headers/footers, copyright)
- Image handling (remove decorative / keep informational / OCR)
- Document splitting (>500 lines → chapters + INDEX.md)
- Heading injection (PDF TOC → proper heading levels)
- Code block post-processing (merge split blocks, tag languages)

---

## Step 6 — LLM Knowledge Distillation (Optional)

**此步骤为可选项，需询问用户是否执行。**

完成 `_raw.md` 后，通过 `vscode_askQuestions` 询问用户是否需要 LLM 知识蒸馏，并给出推荐：

| 来源 | 推荐 | 推荐理由 |
|------|------|----------|
| Track A（书籍/技术文档/帮助文档） | ❌ 建议跳过 | 已是结构化书面内容，总结会丢失细节 |
| Track B/C（视频/音频/播客转写） | ✅ 建议执行 | 口述内容口语化、冗余高，需结构化才有入库价值 |
| Track B/C 但内容为纯音乐/无信息量 | ❌ 建议跳过 | 无知识可提炼 |

用户确认执行后，才进行以下步骤。用户选择跳过则流程结束于 `_raw.md`。

### 6.2 产出要求

将 `_raw.md` 中的转写文本蒸馏为 `knowledge.md`，包含：

1. **YAML frontmatter**：title, source, author, platform, duration, date_captured, tags
2. **核心观点**（1-3 句话概括全片主旨）
3. **结构化正文**：按内容逻辑分章节，每节提炼要点
4. **关键对比/表格**（如有）
5. **术语修正**：将 ASR 错误修正为正确术语（如 "l l m" → "LLM"）
6. **一句话总结/方法论**（如适用）

### 6.3 质量标准

- 不编造原文中没有的信息
- 保留原作者的核心论点和判断（可引用原文）
- 术语使用行业标准写法
- 输出长度通常为原文的 30%-50%（视信息密度而定）
- 输出文件：`<output_dir>/knowledge.md`

### Available Scripts

| Script | Purpose |
|--------|---------|
| `convert_docling_batch.py` | Large-PDF batch conversion with OOM recovery |
| `inject_headings_v2.py` | PDF TOC → Markdown heading injection |
| `split_recursive.py` | Split large MD by chapter |
| `merge_code_blocks.py` | Merge code blocks split by page breaks |
| `fix_code_blocks_simtalk.py` | Tag SimTalk code blocks (domain-specific) |
| `fix_linebreaks_simtalk_v2.py` | Restore line breaks in SimTalk (domain-specific) |
| `fetch_media.py` | Resolve URL, download media/subtitles/images |
| `transcribe.py` | Subtitle-first → ASR transcription |
| `assemble_media_md.py` | Assemble manifest + transcript → _raw.md |

---

## Error Handling

- On failure, report error clearly and continue with remaining files.
- If output is empty/tiny relative to source, warn and suggest alternative route.
- Track B/C: if fetch fails, write `fallback_plan.json` with actionable next steps.
- Never retry failed Douyin extraction in a loop.

## What This Skill Does NOT Do

- **LLM-based summarization**: Requires API access and token cost. Out of scope for an offline-first tool.
- **Perfect ASR on domain jargon**: Speech recognition has inherent limits on unseen technical terms.
- **Guarantee Douyin/TikTok access**: Platform anti-bot is beyond our control.
- **Replace human review**: All outputs are drafts requiring human validation before entering a knowledge base.
