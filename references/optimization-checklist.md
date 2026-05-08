# Optimization Checklist

Reference patterns and heuristics for cleaning up converted Markdown documents.

## Noise Patterns

### Page Numbers

Regex patterns to detect page numbers:

- `^Page\s+\d+\s+of\s+\d+\s*$` — "Page 3 of 45"
- `^Page\s+\d+\s*$` — "Page 3"
- `^\s*-\s*\d+\s*-\s*$` — "- 3 -"
- `^\s*\d+\s*$` — Standalone digit on its own line (caution: may match list items or table data; only flag when appearing at regular intervals between large text blocks)

### Headers and Footers

- Repeated short lines (< 80 chars) appearing at regular intervals (e.g., every 40-60 lines)
- Company name, document title, or date repeated on many pages
- Lines matching `^(Confidential|Draft|Internal Use Only|CONFIDENTIAL).*$`

### Copyright and Legal

- `©|\(c\)|Copyright` — Copyright symbols and text
- `All [Rr]ights [Rr]eserved`
- `Licensed under|License Agreement|Terms of Use|Terms and Conditions`
- Blocks containing "This document is proprietary", "Do not distribute", "Disclaimer"
- `NOTICE:|WARRANTY:|LIABILITY:` — Legal notice headers

### Preface and Boilerplate

- Sections titled: "Preface", "Foreword", "About This Document", "Document History", "Revision History", "Change Log", "Version History"
- Sections titled: "How to Use This Guide", "Conventions Used", "Typographic Conventions"
- Very short "Introduction" sections that only describe the document structure

### Table of Contents

- Sections titled "Table of Contents", "Contents", "TOC"
- Lines with dotted leaders: `\.{3,}` followed by digits
- Lines that are just heading text + page numbers

### Watermarks

- Repeated diagonal or centered text: "DRAFT", "CONFIDENTIAL", "SAMPLE", "DO NOT COPY"
- Text appearing inside image alt text that matches watermark patterns

## Image Assessment Heuristics

### Likely Removable (Decorative/Illustrative)

- Screenshots in help documentation (the surrounding text describes the UI steps)
- Decorative banners, logos, icons
- Flow diagrams that duplicate a textual description in the same section
- "Figure X:" captions where the figure is described in the next paragraph
- Images with generic alt text: "image", "screenshot", "figure", "diagram", ""

### Likely Worth Keeping (Informational)

- Architecture diagrams with no textual equivalent
- Data visualizations (charts, graphs) with specific data points
- Code screenshots (though these should ideally be converted to code blocks)
- Unique reference images (product photos, hardware layouts)
- Mathematical equations rendered as images

### OCR Option

If the user wants to preserve image content as text:
1. Install: `pip install markitdown-ocr openai`
2. Set `OPENAI_API_KEY` environment variable
3. Re-convert with OCR enabled (Python API):
   ```python
   from markitdown import MarkItDown
   from openai import OpenAI
   md = MarkItDown(enable_plugins=True, llm_client=OpenAI(), llm_model="gpt-4o")
   result = md.convert("document.pdf")
   ```

## Document Splitting Strategy

### When to Split

- Document exceeds ~500 lines
- Document has 5+ top-level sections (H1 or H2)
- Estimated token count > 2000

### How to Split

1. Identify the primary heading level for chapters (usually H1 or H2):
   - If H1 appears only once (document title), split by H2
   - If H1 appears multiple times, split by H1
2. Each chapter file should include:
   - The chapter heading as its first line
   - All content until the next heading at the same level
   - Sub-headings adjusted if needed (e.g., H2→H1, H3→H2)
3. Filename convention: `01-heading-text.md`, `02-heading-text.md`, etc.
   - Lowercase, hyphens replacing spaces
   - Two-digit prefix for sort order
   - Max 50 chars in filename

### INDEX.md Template

```markdown
# [Document Title]

> [Brief description of the document's content and purpose]

## Contents

| # | Chapter | Description | Keywords |
|---|---------|-------------|----------|
| 1 | [Chapter Title](./01-chapter-title.md) | Brief description | keyword1, keyword2 |
| 2 | [Chapter Title](./02-chapter-title.md) | Brief description | keyword1, keyword2 |

## Source

- Original file: `[filename]`
- Converted: [date]
- Total chapters: [N]
```

## Knowledge Base README.md Template

For multi-document knowledge bases:

```markdown
# [Knowledge Base Name]

> [Purpose and scope of this knowledge base]

## Documents

| Document | Description | Chapters | Last Updated |
|----------|-------------|----------|--------------|
| [Doc Name](./doc-name/INDEX.md) | Brief description | N | YYYY-MM-DD |

## Usage

Reference this knowledge base in your Copilot instructions:
- Add to `.github/copilot-instructions.md`
- Or create a `.github/instructions/kb.instructions.md` with `applyTo` pattern

## Conventions

- Each document gets its own subfolder
- Long documents are split into chapter files
- Every subfolder has an `INDEX.md` with table of contents
- Filenames: lowercase, hyphenated, prefixed with sort order
```
