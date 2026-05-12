---
name: everything-to-md
description: 'Convert PDF, Word, DOCX, PPT, PPTX, Excel, XLSX documents to high-quality Markdown. Provides multiple conversion routes with time estimates. Triggers: document conversion, 文档转换, 知识库, knowledge base, markitdown, docling, PDF to markdown, convert document, batch convert, document cleanup, split document.'
argument-hint: 'Provide file path(s) or a folder containing documents to convert'
user-invocable: true
disable-model-invocation: false
---

# Everything to Markdown

Convert documents (PDF, Word, PPT, Excel, etc.) to high-quality Markdown.

Auto-switch response language based on user input language.

## Checklist

- [ ] Files collected, types & sizes measured
- [ ] Route selected by user (with time estimates)
- [ ] Dependencies installed
- [ ] Conversion executed & results reported
- [ ] Post-conversion cleanup offered (→ [markdown-cleanup.md](./references/markdown-cleanup.md))

## Procedure

### Step 1 — Collect & Measure

1. Collect file path(s) or folder. Find all supported files (`.pdf`, `.docx`, `.pptx`, `.xlsx`, `.xls`, `.html`, `.csv`, `.json`, `.xml`, `.epub`).
2. For each file, get: file size (MB), page count (PDF: `fitz.open(f).page_count`), file type.
3. Display summary table.

### Step 2 — Route Selection

Use `vscode_askQuestions` to present routes based on file type.

#### PDF Routes

| Route | Pipeline | Headings | Tables | Speed (CPU) | Notes |
|-------|----------|----------|--------|-------------|-------|
| **A1** | PDF → [ilovepdf](https://www.ilovepdf.com/zh-cn/pdf_to_word) (manual) → DOCX → markitdown | ⭐⭐⭐ | ⭐⭐⭐ | manual + fast | Best quality. Not for confidential docs |
| **A2** | PDF → pdf2docx → DOCX → markitdown | ⭐⭐⭐ | ⭐⭐ | ~2 s/page | Fully local. ⚠️ numId lost → may need TOC fix |
| **B** ★ | PDF → docling → MD | ⭐⭐ | ⭐⭐ | ~3 s/page | ML models (~500MB). MIT license. Auto-removes headers/footers |
| **C** | PDF → pymupdf4llm → MD | ⭐ | ⭐⭐ | ~0.3 s/page | No ML. Font-size heuristic headings. Fastest |

★ = recommended default. For <50 pages where quality matters, recommend A.

Display time estimates: `speed × page_count = X min`.

#### Word Routes

Default: `markitdown`. Alternative: `pandoc` (if available).

#### Other Formats (PPT, Excel, HTML, etc.)

Default: `markitdown "<input>" -o "<output>.md"`. No route selection needed.

### Step 3 — Install Dependencies

Install only what the chosen route needs:

| Route | Install |
|-------|---------|
| All | `pip install 'markitdown[all]'` |
| A2 | + `pip install pdf2docx` |
| B | + `pip install docling` (first run downloads ~500MB models) |
| C | + `pip install pymupdf4llm` |

Confirm Python >= 3.10.

### Step 4 — Convert

Output convention: single file → `.md` alongside source. Multiple files → `markdown/` subfolder.

#### Route A — PDF → Word → Markdown

```python
# A2 (automated)
from pdf2docx import Converter
cv = Converter("<input>.pdf")
cv.convert("<output>.docx")
cv.close()
```
Then: `markitdown "<output>.docx" -o "<output>.md"`

For A1 (manual): instruct user to upload to ilovepdf, download DOCX, then run markitdown.

#### Route B — PDF → Docling → Markdown

```python
from docling.document_converter import DocumentConverter
result = DocumentConverter().convert(source="<input>.pdf")
with open("<output>.md", "w", encoding="utf-8") as f:
    f.write(result.document.export_to_markdown())
```

To skip OCR on digital PDFs:
```python
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
converter = DocumentConverter(
    format_options={InputFormat.PDF: PdfFormatOption(
        pipeline_options=PdfPipelineOptions(do_ocr=False)
    )}
)
```

#### Route C — PDF → pymupdf4llm → Markdown

```python
import pymupdf4llm, pathlib
pathlib.Path("<output>.md").write_text(
    pymupdf4llm.to_markdown("<input>.pdf"), encoding="utf-8"
)
```

#### Word / Other Formats

```bash
markitdown "<input-file>" -o "<output-file>.md"
```

Report: files converted, route used, failures, sizes, actual time.

### Step 5 — Post-Conversion

After conversion, offer to run cleanup by reading and following [markdown-cleanup.md](./references/markdown-cleanup.md). This covers:
- Structure analysis (headings, length, noise detection)
- Image handling (remove / keep / OCR)
- Noise removal (page numbers, headers/footers, copyright)
- Document splitting (long docs → chapters + INDEX.md)
- Heading injection (PDF TOC → Markdown headings for docs that lost structure)
- Knowledge base organization (README.md, cross-links)

## Advanced Options

- **Azure Doc Intelligence**: `markitdown file.pdf -o out.md -d -e "<endpoint>"` — for complex PDFs when all routes fail.
- **MinerU**: Best for Chinese docs, needs GPU. Apache 2.0. Future Route D candidate.
- **Marker**: Good visual analysis but ~21 s/page on CPU. GPL. GPU-only practical use.

## Error Handling

- On failure, report error and continue with remaining files.
- If output is empty/tiny relative to source, warn user and suggest trying another route.
