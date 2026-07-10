"""Recursively split a large Markdown file by heading levels.

Splits by H1 first, then any resulting file larger than a threshold
gets split by H2, then H3, etc., up to a configurable max level.

Usage:
    python split_recursive.py input.md -o output_dir [--threshold 200] [--max-level 4]

Options:
    -o, --output-dir   Output directory (required)
    --threshold        File size in KB above which to continue splitting (default: 200)
    --max-level        Maximum heading level to split on (default: 4)
    --dry-run          Show what would be split without writing files

Requires: no external dependencies (stdlib only)
"""
import argparse
import re
import sys
from pathlib import Path


def sanitize_filename(title: str) -> str:
    """Convert a heading title to a safe filename."""
    title = re.sub(r'[^\w\s-]', '', title).strip()
    title = re.sub(r'\s+', '_', title)
    return title[:80]


def split_markdown_to_list(text: str, level: int):
    """Split markdown text at the given heading level. Returns list of (title, content) tuples."""
    heading_pattern = re.compile(rf'^({"#" * level})\s+(.+)$', re.MULTILINE)
    
    chapters = []
    last_end = 0
    last_title = None
    
    for m in heading_pattern.finditer(text):
        if last_end > 0 or m.start() > 0:
            chunk = text[last_end:m.start()]
            chapters.append((last_title, chunk))
        last_title = m.group(2).strip()
        last_end = m.start()
    
    # Last chunk
    if last_end < len(text):
        chapters.append((last_title, text[last_end:]))
    
    return chapters


def generate_filename(title: str, index: int) -> str:
    """Generate a prefixed filename from a heading title."""
    if title is None:
        return "00_Front_Matter"
    safe = sanitize_filename(title)
    num_match = re.match(r'^(\d+)', title)
    if num_match:
        num = int(num_match.group(1))
        # Remove the leading number from safe name to avoid duplication (e.g. "12_12_Foo" → "12_Foo")
        safe = re.sub(r'^\d+_?', '', safe)
        return f"{num:02d}_{safe}" if safe else f"{num:02d}"
    else:
        return f"{index:02d}_{safe}"


def recursive_split(text: str, output_dir: Path, level: int, max_level: int,
                    threshold_kb: float, dry_run: bool = False, indent: str = ""):
    """Recursively split markdown text and write files."""
    chapters = split_markdown_to_list(text, level)
    
    # If only 1 chapter (no split happened), nothing to do at this level
    if len(chapters) <= 1:
        return []
    
    output_dir.mkdir(parents=True, exist_ok=True)
    written_files = []
    
    for i, (title, content) in enumerate(chapters):
        # Skip empty front matter
        if title is None and len(content.strip()) == 0:
            continue
        # Skip non-numbered H1 titles (e.g., "Table of Contents", "List of Figures")
        if level == 1 and title is not None and not re.match(r'^\d+', title):
            continue
        
        filename = generate_filename(title, i)
        size_kb = len(content.encode('utf-8')) / 1024
        
        # Decide whether to recurse
        if size_kb > threshold_kb and level < max_level:
            # Try splitting at next level
            sub_chapters = split_markdown_to_list(content, level + 1)
            if len(sub_chapters) > 1:
                # Worth splitting: create subdirectory
                subdir = output_dir / filename
                print(f"{indent}[DIR] {filename}/ ({size_kb:.0f} KB -> split by H{level+1})")
                sub_files = recursive_split(
                    content, subdir, level + 1, max_level, threshold_kb, dry_run, indent + "  "
                )
                written_files.extend(sub_files)
                continue
        
        # Write as file
        filepath = output_dir / f"{filename}.md"
        lines = content.count('\n') + 1
        print(f"{indent}  {filepath.name}: {lines} lines ({size_kb:.0f} KB)")
        if not dry_run:
            filepath.write_text(content, encoding='utf-8')
        written_files.append(filepath)
    
    return written_files


def main():
    parser = argparse.ArgumentParser(description="Recursively split Markdown by heading levels")
    parser.add_argument("input_md", type=str, help="Path to input Markdown file")
    parser.add_argument("-o", "--output-dir", type=str, required=True,
                        help="Output directory")
    parser.add_argument("--threshold", type=float, default=200,
                        help="File size threshold in KB for further splitting (default: 200)")
    parser.add_argument("--max-level", type=int, default=4,
                        help="Maximum heading level to split on (default: 4)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show plan without writing files")
    args = parser.parse_args()

    input_path = Path(args.input_md).resolve()
    if not input_path.exists():
        print(f"ERROR: File not found: {input_path}")
        sys.exit(1)

    output_dir = Path(args.output_dir).resolve()
    print(f"Input: {input_path}")
    print(f"Output: {output_dir}")
    print(f"Threshold: {args.threshold} KB, Max level: H{args.max_level}")
    if args.dry_run:
        print("=== DRY RUN ===")
    print()

    text = input_path.read_text(encoding='utf-8')
    files = recursive_split(text, output_dir, level=1, max_level=args.max_level,
                            threshold_kb=args.threshold, dry_run=args.dry_run)
    
    print(f"\nTotal: {len(files)} files written")


if __name__ == "__main__":
    main()
