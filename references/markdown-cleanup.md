# Markdown Cleanup Procedure

Post-conversion cleanup for Markdown files produced by the everything-to-md skill.
Read this file when the user wants to clean up, split, or organize converted Markdown.

Auto-switch response language based on user input language.

## Step 1 — Structure Analysis

For each Markdown file, analyze and report:

1. **Heading tree**: H1–H6 hierarchy.
2. **Length**: line count, estimated tokens (lines × 4).
3. **Images**: count `![...]()` patterns, list with context.
4. **Noise**: scan for patterns in [optimization-checklist.md](./optimization-checklist.md) — page numbers, headers/footers, copyright, TOC duplicates, watermarks.
5. **Tables**: count, flag broken formatting.

Present summary, then proceed to cleanup options.

## Step 2 — Interactive Cleanup

Use `vscode_askQuestions` for each category:

### 2a. Images

- List image refs with context.
- Options: remove all / keep all / review individually.
- Advanced: `markitdown-ocr` plugin can extract image text before removal (needs OpenAI API key).

### 2b. Noise Removal

- Show examples per category (page numbers, headers/footers, copyright, watermarks).
- Recommend removal. Ask user to confirm per-category or all-at-once.

### 2c. Splitting (if >500 lines or >2000 tokens)

- Propose split by top-level headings (H1 or H2).
- Show plan: list of chapter files.
- On confirm: create subfolder, write chapters, generate `INDEX.md`.
- Filename convention: underscores, derived from heading text.
- INDEX.md template: see [optimization-checklist.md](./optimization-checklist.md#indexmd-template).

### 2d. Additional Cleanup

Offer:
- Normalize heading levels (shift if starting at H3+)
- Collapse excessive blank lines (3+ → 2)
- Fix broken tables
- Remove redundant horizontal rules

### 2e. PDF TOC Heading Injection

**Trigger**: source was PDF AND heading count is suspiciously low relative to doc size.

1. Extract TOC: `fitz.open(pdf).get_toc()`
2. Match TOC entries to text positions in Markdown.
3. Inject `#`/`##`/`###` at matched positions.
4. Reference: [inject_headings_example.py](../scripts/inject_headings_example.py)

### 2f. Route A Heading Recovery (PDF → Word → markitdown)

**Trigger**: source was PDF converted via Route A, AND markitdown output has bullet-style headings (`* + 1.`, `* + - 1.`) or missing heading numbers.

**Root cause**: Word auto-numbering (numId) is lost during markitdown conversion. Headings become unnumbered or render as nested list markers.

**Recovery procedure**:

1. **Extract Word heading data** (`python-docx`): for each paragraph with a Heading style, record `text`, `style.name`, and `numId` (from `paragraph._element.pPr.numPr`).
2. **Distinguish real vs fake headings**: paragraphs with `numId` = real headings (need numbering); without `numId` = fake headings (demote to `**bold text**`).
3. **Extract PDF TOC** (`fitz.open(pdf).get_toc()`) as ground truth for L1-L3 headings.
4. **Deduplicate PDF TOC**: if same title appears at multiple levels, keep the one with smallest level value.
5. **Sequential matching**: normalize titles (lowercase, strip punctuation), match MD headings to PDF TOC entries in order. Constraints:
   - Short titles (`len < 12`): require `startswith` match with ≥70% length ratio + distance limit (≤3 entries ahead) to prevent false jumps.
   - Unmatched headings at L4+: auto-number based on parent context.
6. **Apply heading levels + numbering** to the markdown output.

**Key pitfalls** (from Bangsow book case):
- PDF bookmarks may contain typos → may need hardcoded corrections
- PDF→Word conversion may shift heading levels for some chapters → handle with fallback auto-numbering
- markitdown heading format is inconsistent: `##`=chapter, `####`=section, bullet list=subsection

### 2g. Code Block Post-Processing (Technical/Programming Books)

**Trigger**: source contains code examples (programming books, API docs, tutorials) AND code blocks show quality issues after conversion.

**Common problems** (especially with docling Route B):
1. **False positive code blocks**: non-code text wrapped in ``` fences (caused by layout model misdetecting font/background)
2. **Missing language tags**: code blocks lack language identifier for syntax highlighting
3. **Single-line code**: multi-line code collapsed into one line (newlines lost during PDF extraction)
4. **Missing indentation**: block-structured code (if/for/while) has no indentation
5. **Split code blocks**: PDF page breaks create two consecutive code blocks that should be one

**Processing pipeline** (in order):
1. **False positive removal**: Detect blocks where content is clearly prose (no code patterns like `:=`, `var`, function calls). Remove fences, restore as paragraph text.
2. **Language tagging**: Identify language from content patterns (e.g., `:=` + `end` + `var` → SimTalk; `def` + `:` → Python). Add ` ```language ` tag.
3. **Split block merging**: Find consecutive code blocks separated only by blank lines → merge into one.
4. **Line break restoration**: Use language-specific syntax rules to re-insert newlines. Key signals:
   - Statement terminators (`;`, line comments `--`/`//`/`#`)
   - Declaration keywords (`var`, `local`, `param`, `def`, `int`)
   - Control flow keywords with syntax validation (`if...then`, `for...to`)
   - Assignment operators (`:=`, `=`)
5. **Indentation**: Apply language-specific indentation rules based on block openers/closers.

**Reference scripts** (reusable templates in the bangsow_pts_tutorial conversion):
- `_fix_code_blocks.py`: false positive detection + language tagging
- `_fix_linebreaks.py`: line break restoration + indentation (SimTalk-specific, adaptable to other languages)
- `_merge_blocks.py`: consecutive code block merging

## Step 3 — Apply & Report

1. Execute all approved changes.
2. Show before/after: line count, images removed, noise removed, files created.

## Step 4 — Knowledge Base Organization (optional)

If multiple documents, create top-level `README.md`:
- Title, purpose, table of contents linking to each doc/folder.
- Suggest folder conventions for future additions.
- Remind: reference in `.github/copilot-instructions.md` for agent context.
