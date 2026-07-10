"""Merge consecutive code blocks that were split by PDF page breaks.

When PDFs are converted to Markdown, code blocks often get split at page
boundaries, resulting in patterns like:
    ```
    <blank line>
    ```language

This script detects and merges those consecutive blocks back into one.

Usage:
    python merge_code_blocks.py input_dir/ [--lang simtalk] [--dry-run]
    python merge_code_blocks.py .           # Process all .md files in current dir
    python merge_code_blocks.py file.md     # Process a single file

Requires: no external dependencies (stdlib only)
"""
import argparse
import re
import sys
from pathlib import Path


def merge_consecutive_blocks(filepath: Path, lang: str = None, dry_run: bool = False) -> int:
    """Merge consecutive fenced code blocks separated only by blank lines.

    Args:
        filepath: Path to the markdown file.
        lang: If specified, only merge blocks with this language tag.
              If None, merge any consecutive code blocks.
        dry_run: If True, don't write changes, just count.

    Returns:
        Number of block pairs merged.
    """
    content = filepath.read_text(encoding='utf-8')

    if lang:
        # Only merge blocks with the specified language
        pattern = re.compile(rf'```\n\n```{re.escape(lang)}\n')
    else:
        # Merge any consecutive code blocks (with or without language tag)
        pattern = re.compile(r'```\n\n```(\w*)\n')

    count = len(pattern.findall(content))
    if count > 0 and not dry_run:
        new_content = pattern.sub('', content)
        filepath.write_text(new_content, encoding='utf-8')

    return count


def main():
    parser = argparse.ArgumentParser(description="Merge consecutive code blocks split by page breaks")
    parser.add_argument("path", type=str, help="Markdown file or directory to process")
    parser.add_argument("--lang", type=str, default=None,
                        help="Only merge blocks with this language tag (e.g., simtalk, python)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be merged without writing changes")
    parser.add_argument("--include-hidden", action="store_true",
                        help="Include files starting with _ (excluded by default)")
    args = parser.parse_args()

    target = Path(args.path).resolve()
    if not target.exists():
        print(f"ERROR: Path not found: {target}")
        sys.exit(1)

    if target.is_file():
        md_files = [target]
    else:
        md_files = sorted(target.rglob('*.md'))

    total = 0
    lang_display = f" (lang={args.lang})" if args.lang else ""
    mode = " [DRY RUN]" if args.dry_run else ""
    print(f"Merge Consecutive Code Blocks{lang_display}{mode}")
    print("=" * 50)

    for fp in md_files:
        if not args.include_hidden and fp.name.startswith('_'):
            continue
        count = merge_consecutive_blocks(fp, lang=args.lang, dry_run=args.dry_run)
        if count > 0:
            print(f"  {fp.name}: {count} pairs merged")
            total += count

    print(f"\nTotal: {total} block pairs {'would be ' if args.dry_run else ''}merged")


if __name__ == '__main__':
    main()
