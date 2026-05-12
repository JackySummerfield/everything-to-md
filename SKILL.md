---
name: everything-to-md
description: 'Convert PDF, Word, DOCX, PPT, PPTX, Excel, XLSX documents to high-quality Markdown. Provides multiple conversion routes with time estimates. Triggers: document conversion, 文档转换, 知识库, knowledge base, markitdown, docling, PDF to markdown, convert document, batch convert, document cleanup, split document.'
argument-hint: 'Provide file path(s) or a folder containing documents to convert'
user-invocable: true
disable-model-invocation: false
---

# Everything to Markdown

Convert documents (PDF, Word, PPT, Excel, etc.) to high-quality Markdown — the essential first step for building knowledge bases, RAG pipelines, or any LLM-ready content.

Auto-switch response language based on user input language. Keep tool names and technical terms in English.

## Mandatory Checklist (Self-Check Before Each Step)

> **STOP and verify** before moving to the next step. Do NOT skip steps or deviate from the procedure.

- [ ] Step 1: Input files collected, file types and sizes measured
- [ ] Step 2: Conversion routes presented with time estimates; user selected route
- [ ] Step 3: Environment prepared (dependencies installed for chosen route)
- [ ] Step 4: Conversion executed
- [ ] Step 5: Structure analysis reported to user
- [ ] Step 6a: Image handling confirmed with user
- [ ] Step 6b: Noise removal confirmed with user
- [ ] Step 6c: Split plan confirmed with user (if applicable)
- [ ] Step 6d: Additional cleanup offered (including heading injection for PDFs)
- [ ] Step 7: All changes applied, files in subfolder, filenames use underscores, INDEX.md generated
- [ ] Step 8: Knowledge base finalized

## When To Use

- Convert one or more documents to Markdown for LLM consumption
- Build a knowledge base from a collection of documents
- Clean up converted Markdown (remove noise, images, split long docs)
- Organize multiple Markdown files with indexes

## Procedure

### Step 1 — Collect Input & Measure Files

1. Collect input from user: file path(s) or a folder path.
2. If a folder is given, find all supported files (`.pdf`, `.docx`, `.pptx`, `.xlsx`, `.xls`, `.html`, `.csv`, `.json`, `.xml`, `.epub`).
3. For each file, measure:
   - File size (MB)
   - Page count (for PDF: use PyMuPDF `fitz.open(f).page_count`; for DOCX: estimate from file size; for others: N/A)
   - File type classification: **PDF**, **Word** (.doc/.docx), or **Other**
4. Display a summary table of all files with type, size, and page count.

### Step 2 — Route Selection (by file type)

Present conversion routes to the user using `vscode_askQuestions`. Routes differ by file type.

#### 2A. PDF Files — Present These Routes

For each PDF file, calculate estimated time for each route and present:

| Route | Pipeline | Heading Quality | Table Quality | Speed (CPU) | Best For |
|-------|----------|----------------|---------------|-------------|----------|
| **A: PDF→Word→MD** | PDF → ilovepdf (manual) or pdf2docx → Word → markitdown → MD | ⭐⭐⭐ Best | ⭐⭐⭐ Best | ~1-2 s/page (pdf2docx) + fast (markitdown) | Complex layouts, high-quality needs |
| **B: PDF→Docling→MD** | PDF → docling → MD | ⭐⭐ Good | ⭐⭐ Good | ~3 s/page (CPU) / ~0.5 s/page (GPU) | Large docs, automated pipeline, MIT license |
| **C: PDF→pymupdf4llm→MD** | PDF → pymupdf4llm → MD | ⭐ Font-size heuristic | ⭐⭐ Good | ~0.3 s/page (very fast) | Quick preview, simple layouts |

**Route A details — PDF → Word → Markdown:**
- **Sub-option A1 (manual)**: User uploads PDF to [ilovepdf.com](https://www.ilovepdf.com/zh-cn/pdf_to_word) or Adobe Acrobat, downloads DOCX, then convert with markitdown. Best quality, but manual and **not suitable for sensitive/confidential documents**.
- **Sub-option A2 (automated)**: Use `pdf2docx` library to convert PDF→DOCX locally, then markitdown. Quality slightly lower than manual but fully local.
- After Word conversion, use `markitdown` or `pandoc` to convert DOCX→MD.
- ⚠️ Known issue: Word auto-numbering (numId) is lost during markitdown conversion → headings become unnumbered. May need post-processing with PDF TOC matching (see Step 6d).

**Route B details — PDF → Docling → Markdown:**
- Uses deep learning models (~258M params) for layout detection + table recognition.
- CPU-friendly: ~3.1 s/page on x86 CPU, ~1.3 s/page on Apple M3, ~0.5 s/page on GPU.
- Auto-removes headers/footers. MIT license, commercially friendly.
- Install: `pip install docling`
- ⚠️ Chinese OCR needs manual config (default is English only). For English docs this is not an issue.
- ⚠️ First run downloads models (~500MB).

**Route C details — PDF → pymupdf4llm → Markdown:**
- Pure rule-based extraction (no ML models). Fastest option.
- Heading detection relies on font-size heuristics — works for well-formatted PDFs, unreliable for others.
- Good table extraction for simple tables.
- Install: `pip install pymupdf4llm`

**Time estimate formula** (display to user):
```
Route A (pdf2docx + markitdown): ~2 s/page × {page_count} = {estimate} min
Route A (manual ilovepdf):       manual upload/download + ~1 s/page markitdown
Route B (docling CPU):           ~3 s/page × {page_count} = {estimate} min
Route B (docling GPU):           ~0.5 s/page × {page_count} = {estimate} min
Route C (pymupdf4llm):           ~0.3 s/page × {page_count} = {estimate} min
```

Use `vscode_askQuestions` with these routes as options. Pre-select Route B (docling) as recommended for most cases. If the document is small (<50 pages) and quality is critical, recommend Route A.

#### 2B. Word Files (.doc/.docx) — Present These Routes

| Route | Pipeline | Speed | Notes |
|-------|----------|-------|-------|
| **markitdown** (recommended) | DOCX → mammoth → HTML → MD | ~1 s/page | Best heading/table preservation for DOCX |
| **pandoc** | DOCX → pandoc → MD | ~1 s/page | Alternative, good for complex formatting |

Time estimate: nearly instant for typical documents. Use `vscode_askQuestions` only if both tools are available; otherwise default to markitdown.

#### 2C. Other Formats (PPT, Excel, HTML, etc.)

Default to `markitdown` directly. No route selection needed — just inform the user:
```
markitdown "<input-file>" -o "<output-file>.md"
```
For future optimization, note that specialized tools may be added for specific formats.

### Step 3 — Environment Preparation

Based on the user's selected route, install only the required dependencies:

**Common (always needed):**
```
pip install 'markitdown[all]'
```

**Route A (PDF→Word→MD):**
```
pip install pdf2docx    # for automated PDF→DOCX
# markitdown already covers DOCX→MD
```

**Route B (PDF→Docling→MD):**
```
pip install docling
# First run will download models (~500MB). If behind corporate proxy, may need SSL cert config.
```

**Route C (PDF→pymupdf4llm→MD):**
```
pip install pymupdf4llm
```

Confirm Python >= 3.10 with `python --version`.

### Step 4 — Conversion Execution

Create an output directory:
- Single file: output `.md` alongside the source, or in a user-specified location.
- Multiple files / folder: create `markdown/` subfolder (or user-specified name).

#### Route A — PDF → Word → Markdown

**A1 (manual ilovepdf):**
1. Instruct user to upload PDF to [ilovepdf.com/pdf_to_word](https://www.ilovepdf.com/zh-cn/pdf_to_word)
2. Download the converted DOCX
3. Convert DOCX: `markitdown "<converted>.docx" -o "<output>.md"`

**A2 (pdf2docx automated):**
```python
from pdf2docx import Converter
cv = Converter("<input>.pdf")
cv.convert("<output>.docx")
cv.close()
# Then convert DOCX → MD
```
Then: `markitdown "<output>.docx" -o "<output>.md"`

#### Route B — PDF → Docling → Markdown

```python
from docling.document_converter import DocumentConverter

converter = DocumentConverter()
result = converter.convert(source="<input>.pdf")
md_text = result.document.export_to_markdown()

with open("<output>.md", "w", encoding="utf-8") as f:
    f.write(md_text)
```

For batch processing or custom options (e.g., disable OCR for digital PDFs):
```python
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

pipeline_options = PdfPipelineOptions(do_ocr=False)  # skip OCR for digital PDFs
converter = DocumentConverter(
    format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
)
result = converter.convert(source="<input>.pdf")
md_text = result.document.export_to_markdown()
```

#### Route C — PDF → pymupdf4llm → Markdown

```python
import pymupdf4llm
import pathlib
md_text = pymupdf4llm.to_markdown("<input>.pdf")
pathlib.Path("<output>.md").write_text(md_text, encoding="utf-8")
```

#### Word / Other Formats

```bash
markitdown "<input-file>" -o "<output-file>.md"
```

Report results: list of converted files, route used per file, any failures, file sizes, and actual conversion time.

### Step 5 — Structure Analysis

For each converted Markdown file, analyze and report:

1. **Document outline**: Extract heading hierarchy (H1–H6), display as a tree.
2. **Length metrics**: Line count and estimated token count (lines × 4 as rough estimate).
3. **Image references**: Count `![...](...)`  patterns. List them with surrounding context.
4. **Noise detection**: Scan for patterns listed in [optimization-checklist.md](./references/optimization-checklist.md):
   - Page numbers (e.g., `Page X of Y`, standalone digits)
   - Headers/footers (repeated short lines at regular intervals)
   - Copyright notices, "All rights reserved", legal boilerplate
   - Preface, foreword, revision history sections
   - Table of contents (if it duplicates the actual heading structure)
   - Watermark text
5. **Tables**: Count tables, note any with excessive columns or broken formatting.

Present a concise summary to the user before proceeding.

### Step 6 — Interactive Optimization

Use `vscode_askQuestions` to present optimization options. Walk through each sub-step:

#### 6a. Image Handling

- List all detected image references with brief context.
- Explain: in help documents and manuals, images are often illustrative — the surrounding text already conveys the meaning. Removing them reduces noise and token cost.
- Ask user:
  - Remove all images?
  - Keep all images?
  - Review individually? (list each with keep/remove option)
- **Advanced option**: If user wants to preserve image content as text, suggest using `markitdown-ocr` plugin to extract text descriptions before removing image tags. This requires an OpenAI-compatible API key.

#### 6b. Noise Removal

- Present each category of detected noise with examples from the document.
- Recommend removal for: page numbers, headers/footers, copyright blocks, watermarks, standalone page breaks.
- Ask user to confirm removal for each category, or approve all at once.

#### 6c. Document Splitting (for long documents)

- If a document exceeds ~500 lines or ~2000 estimated tokens:
  - Propose splitting by top-level headings (H1 or H2, whichever forms the main chapter structure).
  - Show the proposed split plan: list of chapter files with their heading titles.
  - Ask user to confirm, adjust split level, or skip.
- For split documents, generate an `INDEX.md` containing:
  - Original document title and description
  - Table of contents with relative links to each chapter file
  - Keyword tags per chapter for searchability

#### 6d. Additional Cleanup

Offer these optional cleanups:
- Normalize heading levels (e.g., if document starts at H3, shift to H1)
- Remove excessive blank lines (collapse 3+ consecutive blanks to 2)
- Fix broken table formatting (misaligned pipes, missing headers)
- Remove redundant horizontal rules
- **PDF TOC Heading Injection** (for PDF sources): If the converted Markdown has very few headings relative to the document size (e.g., a 10,000+ page PDF with < 100 headings), the markitdown output likely lost the heading structure. In this case:
  1. Extract the PDF's Table of Contents (TOC) using PyMuPDF (`fitz.open(pdf).get_toc()`).
  2. Match TOC entries to text positions in the Markdown by searching for the heading text.
  3. Inject Markdown heading markers (`#`, `##`, `###`, etc.) at the matched positions, respecting the TOC hierarchy.
  4. See [inject_headings_example.py](./references/inject_headings_example.py) for a reference implementation.
  5. **Always offer this option** when the source is a PDF and the heading count is suspiciously low.

### Step 7 — Apply Changes

1. Execute all approved optimizations by editing the Markdown files.
2. For document splitting:
   - Create a subfolder named after the document (without extension).
   - Write each chapter as a separate `.md` file with a clean filename derived from the heading.
   - **Filename convention**: Replace all spaces with underscores in filenames. This ensures Markdown links in INDEX.md render correctly across all platforms.
   - Generate `INDEX.md` in the subfolder.
3. Show a before/after summary:
   - Original line count → optimized line count
   - Number of images removed
   - Number of noise sections removed
   - Number of files created (if split)

### Step 8 — Knowledge Base Finalization

1. If multiple documents were converted, create a top-level `README.md` in the knowledge base folder:
   - Title and purpose of the knowledge base
   - Table of contents linking to each document or document folder
   - Brief description of each document's content
2. Suggest naming conventions and folder organization for future additions.
3. Remind user that the knowledge base folder can be referenced in `.github/copilot-instructions.md` or instructions files for automatic agent context.

## Advanced Options

- **Azure Document Intelligence**: For complex PDFs where all other routes produce poor results, markitdown supports Azure Doc Intelligence:
  ```
  markitdown path-to-file.pdf -o document.md -d -e "<endpoint>"
  ```
  This requires an Azure Document Intelligence resource. Offer this only if standard routes fail.

- **MinerU** (opendatalab/MinerU): Best for Chinese documents. Needs GPU for practical speed (~0.21 s/page GPU, ~3.3 s/page CPU). Apache 2.0 license. Consider adding as Route D in the future if user has GPU and Chinese documents.

- **Marker** (VikParuchuri/marker): Good visual layout analysis but impractical on CPU (~21 s/page). Requires GPU + ~3.3GB model download. GPL license restricts commercial use. Not recommended unless user has GPU and English-only documents.

- **Plugin support**: markitdown supports 3rd-party plugins. List installed plugins with `markitdown --list-plugins`. Enable with `--use-plugins`.

- **Corporate network / SSL issues**: If behind Zscaler or similar SSL inspection proxy, models may fail to download. Fix by appending corporate root CA certificates to `certifi/cacert.pem`. See memory notes for detailed procedure.

## Error Handling

- If markitdown fails on a file, report the error and continue with remaining files.
- If a file type is unsupported, suggest alternative approaches or manual conversion.
- If the output Markdown is empty or extremely short relative to the source, warn the user — the conversion may have failed silently. Suggest trying Azure Document Intelligence as an alternative.
