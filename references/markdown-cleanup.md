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
4. Reference: [inject_headings_example.py](./inject_headings_example.py)

## Step 3 — Apply & Report

1. Execute all approved changes.
2. Show before/after: line count, images removed, noise removed, files created.

## Step 4 — Knowledge Base Organization (optional)

If multiple documents, create top-level `README.md`:
- Title, purpose, table of contents linking to each doc/folder.
- Suggest folder conventions for future additions.
- Remind: reference in `.github/copilot-instructions.md` for agent context.
