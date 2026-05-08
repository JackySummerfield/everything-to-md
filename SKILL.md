---
name: doc-to-knowledgebase
description: 'Convert PDF, Word, DOCX, PPT, PPTX, Excel, XLSX documents to Markdown and build a knowledge base. Uses markitdown CLI. Triggers: document conversion, 文档转换, 知识库, knowledge base, markitdown, PDF to markdown, convert document, batch convert, document cleanup, split document.'
argument-hint: 'Provide file path(s) or a folder containing documents to convert'
user-invocable: true
disable-model-invocation: false
---

# Document-to-Markdown Knowledge Base Builder

Convert documents (PDF, Word, PPT, Excel, etc.) to Markdown using `markitdown`, then interactively analyze, clean up, and organize the output into a well-structured knowledge base.

Auto-switch response language based on user input language. Keep tool names and technical terms in English.

## Mandatory Checklist (Self-Check Before Each Step)

> **STOP and verify** before moving to the next step. Do NOT skip steps or deviate from the procedure.

- [ ] Step 1: Environment confirmed (markitdown installed, Python >= 3.10)
- [ ] Step 2: All files converted via `markitdown` CLI (NOT custom Python code)
- [ ] Step 3: Structure analysis reported to user
- [ ] Step 4a: Image handling confirmed with user
- [ ] Step 4b: Noise removal confirmed with user
- [ ] Step 4c: Split plan confirmed with user (if applicable)
- [ ] Step 4d: Additional cleanup offered (including heading injection for PDFs)
- [ ] Step 5: All changes applied, files in subfolder, filenames use underscores, INDEX.md generated
- [ ] Step 6: Knowledge base finalized

## When To Use

- Convert one or more documents to Markdown for LLM consumption
- Build a knowledge base from a collection of documents
- Clean up converted Markdown (remove noise, images, split long docs)
- Organize multiple Markdown files with indexes

## Procedure

### Step 1 — Environment Check

1. Run `pip show markitdown` to check if markitdown is installed.
2. If not installed, run:
   ```
   pip install 'markitdown[all]'
   ```
3. Confirm Python >= 3.10 with `python --version`.
4. If the user mentions needing OCR for images, also check/install `markitdown-ocr`.

### Step 2 — Document Conversion

1. Collect input from user: file path(s) or a folder path.
2. If a folder is given, find all supported files (`.pdf`, `.docx`, `.pptx`, `.xlsx`, `.xls`, `.html`, `.csv`, `.json`, `.xml`, `.epub`).
3. Create an output directory. Convention:
   - Single file: output `.md` alongside the source, or in a user-specified location.
   - Multiple files / folder: create `knowledgebase/` folder (or user-specified name).
4. For each file, run:
   ```
   markitdown "<input-file>" -o "<output-file>.md"
   ```
5. Report results: list of converted files, any failures, and file sizes.

### Step 3 — Structure Analysis

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

### Step 4 — Interactive Optimization

Use `vscode_askQuestions` to present optimization options. Walk through each sub-step:

#### 4a. Image Handling

- List all detected image references with brief context.
- Explain: in help documents and manuals, images are often illustrative — the surrounding text already conveys the meaning. Removing them reduces noise and token cost.
- Ask user:
  - Remove all images?
  - Keep all images?
  - Review individually? (list each with keep/remove option)
- **Advanced option**: If user wants to preserve image content as text, suggest using `markitdown-ocr` plugin to extract text descriptions before removing image tags. This requires an OpenAI-compatible API key.

#### 4b. Noise Removal

- Present each category of detected noise with examples from the document.
- Recommend removal for: page numbers, headers/footers, copyright blocks, watermarks, standalone page breaks.
- Ask user to confirm removal for each category, or approve all at once.

#### 4c. Document Splitting (for long documents)

- If a document exceeds ~500 lines or ~2000 estimated tokens:
  - Propose splitting by top-level headings (H1 or H2, whichever forms the main chapter structure).
  - Show the proposed split plan: list of chapter files with their heading titles.
  - Ask user to confirm, adjust split level, or skip.
- For split documents, generate an `INDEX.md` containing:
  - Original document title and description
  - Table of contents with relative links to each chapter file
  - Keyword tags per chapter for searchability

#### 4d. Additional Cleanup

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

### Step 5 — Apply Changes

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

### Step 6 — Knowledge Base Finalization

1. If multiple documents were converted, create a top-level `README.md` in the knowledge base folder:
   - Title and purpose of the knowledge base
   - Table of contents linking to each document or document folder
   - Brief description of each document's content
2. Suggest naming conventions and folder organization for future additions.
3. Remind user that the knowledge base folder can be referenced in `.github/copilot-instructions.md` or instructions files for automatic agent context.

## Advanced Options

- **Azure Document Intelligence**: For complex PDFs with difficult layouts, markitdown supports Azure Doc Intelligence:
  ```
  markitdown path-to-file.pdf -o document.md -d -e "<endpoint>"
  ```
  This requires an Azure Document Intelligence resource. Offer this if standard conversion produces poor results.

- **Plugin support**: markitdown supports 3rd-party plugins. List installed plugins with `markitdown --list-plugins`. Enable with `--use-plugins`.

## Error Handling

- If markitdown fails on a file, report the error and continue with remaining files.
- If a file type is unsupported, suggest alternative approaches or manual conversion.
- If the output Markdown is empty or extremely short relative to the source, warn the user — the conversion may have failed silently. Suggest trying Azure Document Intelligence as an alternative.
