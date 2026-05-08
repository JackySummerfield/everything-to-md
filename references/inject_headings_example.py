"""
Example: Inject heading structure from PDF TOC into Markdown files.

This script demonstrates how to use PyMuPDF (fitz) to extract the PDF's
Table of Contents and inject Markdown heading markers into converted
Markdown files that lack proper heading structure.

Usage:
    Adapt the CHAPTERS list and paths to your specific document.
    Requires: pip install PyMuPDF

Key steps:
    1. Extract TOC from PDF with fitz.open(pdf).get_toc()
    2. For each chapter file, find TOC entries within its page range
    3. Match TOC titles to lines in the Markdown text
    4. Replace matched lines with proper Markdown headings (# ## ### etc.)
"""

import fitz  # PyMuPDF
import re
import os


def normalize_title(title):
    """Normalize a title for fuzzy matching in text."""
    return re.sub(r'\s+', ' ', title.strip().lower())


def extract_chapter_toc(full_toc, start_page, end_page):
    """Get TOC entries for a specific page range."""
    entries = []
    for level, title, page in full_toc:
        if start_page <= page <= end_page:
            entries.append((level, title, page))
    return entries


def inject_headings(md_path, toc_entries, chapter_title):
    """Inject markdown headings into a file based on TOC entries."""
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')

    # Remove existing auto-generated H1 if present
    if lines and lines[0].startswith('# '):
        lines = lines[1:]
        while lines and lines[0].strip() == '':
            lines = lines[1:]

    if not toc_entries:
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(f"# {chapter_title}\n\n" + '\n'.join(lines))
        return 0

    min_level = min(e[0] for e in toc_entries)

    heading_map = []
    for level, title, page in toc_entries:
        adjusted = min(level - min_level + 1, 6)
        heading_md = '#' * adjusted + ' ' + title
        heading_map.append((title, heading_md))

    result_lines = []
    used_headings = set()
    injected = 0

    for line in lines:
        stripped = line.strip()

        # Skip redundant horizontal rules
        if stripped in ('---', '***', '___'):
            continue

        matched = False
        for h_idx, (title, heading_md) in enumerate(heading_map):
            if h_idx in used_headings:
                continue

            norm_stripped = normalize_title(stripped)
            norm_title = normalize_title(title)

            if norm_stripped == norm_title or (
                norm_stripped.startswith(norm_title)
                and len(norm_stripped) - len(norm_title) < 5
            ):
                result_lines.append(heading_md)
                used_headings.add(h_idx)
                matched = True
                injected += 1
                break

        if not matched:
            result_lines.append(line)

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(result_lines))

    return injected


def main():
    # --- ADAPT THESE TO YOUR DOCUMENT ---
    PDF_PATH = "path/to/your/document.pdf"
    MD_DIR = "path/to/markdown/output"

    # List of (chapter_title, md_filename, start_page)
    CHAPTERS = [
        ("Chapter 1", "Chapter_1.md", 1),
        ("Chapter 2", "Chapter_2.md", 50),
        # Add more chapters...
    ]
    # --- END ADAPTATION ---

    doc = fitz.open(PDF_PATH)
    total_pages = len(doc)
    full_toc = doc.get_toc()  # Returns [(level, title, page), ...]
    doc.close()

    print(f"PDF TOC entries: {len(full_toc)}")

    # Calculate page ranges for each chapter
    for i, (title, fname, start) in enumerate(CHAPTERS):
        end = CHAPTERS[i + 1][2] - 1 if i + 1 < len(CHAPTERS) else total_pages
        md_path = os.path.join(MD_DIR, fname)

        if not os.path.exists(md_path):
            print(f"  SKIP: {fname} not found")
            continue

        chapter_toc = extract_chapter_toc(full_toc, start, end)
        injected = inject_headings(md_path, chapter_toc, title)
        print(f"  {fname}: {len(chapter_toc)} TOC entries, {injected} headings injected")


if __name__ == "__main__":
    main()
