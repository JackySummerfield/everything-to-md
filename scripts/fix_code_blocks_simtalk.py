"""Identify and fix false code blocks in Docling output (SimTalk-specific).

Docling wraps some non-code text in fenced code blocks (```).
This script:
1. Identifies false code blocks (regular text wrongly in ```)
2. Removes backtick fencing from text blocks
3. Keeps real SimTalk code blocks and adds language tag

Usage:
    python fix_code_blocks_simtalk.py path/to/dir/         # Process all .md in directory
    python fix_code_blocks_simtalk.py chapter.md           # Process single file
    python fix_code_blocks_simtalk.py . --dry-run          # Preview without writing
    python fix_code_blocks_simtalk.py . --glob "0*.md"     # Custom glob pattern

Requires: no external dependencies (stdlib only)
"""
import argparse
import re
import sys
from pathlib import Path
from collections import Counter

# SimTalk indicators - if a block contains these, it's likely real code
SIMTALK_INDICATORS = [
    ':=', 'var ', 'end;', 'waituntil', 'self.', 'root.',
    '.MU', '.statNumIn', '.statThroughput', '.cont',
    'EventController', 'method(', '->method', 'do\n', 'loop\n',
    '.move(', '.create(', '.operate', '.NumMU', 'elseif',
    'param ', 'return ', 'inspect(', '.name', 'is_a(',
    'print ', '--', '.resume', '.stop', '.reset',
    'integer', 'real', 'boolean', 'string', 'object', 'table',
    'byref ', 'result ', '.startPause', '.endSim',
]

# Patterns that indicate normal text (not code)
TEXT_INDICATORS = [
    'the ', 'The ', 'you ', 'You ', 'this ', 'This ',
    'are ', 'is a ', 'can be ', 'will be ', 'should ',
    'In this ', 'For example', 'Figure ', 'Fig. ',
    'Chapter ', 'Section ', 'Table ',
    'simulation', 'following', 'example',
]


def is_likely_code(content: str) -> bool:
    """Heuristic: is this block likely SimTalk code?"""
    lines = content.strip().splitlines()

    code_score = sum(1 for ind in SIMTALK_INDICATORS if ind in content)
    text_score = sum(1 for ind in TEXT_INDICATORS if ind in content)

    # Strong code signals
    if code_score >= 2:
        return True

    # Single line with semicolons, assignments, or method calls → code
    if len(lines) <= 3 and (';' in content or ':=' in content or '--' in content):
        return True

    # If more text indicators than code → not code
    if text_score > code_score and text_score >= 2:
        return False

    # Multi-line block with no code indicators but lots of prose → text
    if len(lines) > 3 and code_score == 0:
        avg_words = sum(len(l.split()) for l in lines) / len(lines)
        if avg_words > 8:  # Prose has many words per line
            return False

    # Default: if it has any code indicator, keep as code
    return code_score > 0


def process_file(filepath: Path, dry_run: bool = False) -> dict:
    """Process one markdown file, fix false code blocks."""
    text = filepath.read_text(encoding='utf-8')

    stats = {'code_kept': 0, 'text_freed': 0, 'total': 0}

    def replace_block(match):
        lang = match.group(1) or ''
        content = match.group(2)
        stats['total'] += 1

        if is_likely_code(content):
            stats['code_kept'] += 1
            if not lang:
                return f'```simtalk\n{content}```'
            return match.group(0)
        else:
            stats['text_freed'] += 1
            return content.strip()

    result = re.sub(r'```(\w*)\n(.*?)```', replace_block, text, flags=re.DOTALL)

    # Clean up excessive blank lines (3+ → 2)
    result = re.sub(r'\n{4,}', '\n\n\n', result)

    if not dry_run and result != text:
        filepath.write_text(result, encoding='utf-8')
    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Fix false code blocks in Docling output (SimTalk)")
    parser.add_argument("path", type=str,
                        help="Markdown file or directory to process")
    parser.add_argument("--glob", type=str, default="[0-9]*.md",
                        help="Glob pattern for files when path is a directory (default: [0-9]*.md)")
    parser.add_argument("--all", action="store_true",
                        help="Process ALL .md files (overrides --glob)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show results without modifying files")
    args = parser.parse_args()

    target = Path(args.path).resolve()
    if not target.exists():
        print(f"ERROR: Path not found: {target}")
        sys.exit(1)

    if target.is_file():
        files = [target]
    else:
        pattern = '*.md' if args.all else args.glob
        files = sorted(target.glob(pattern))

    if not files:
        print(f"No files matched in {target}")
        sys.exit(0)

    mode = " [DRY RUN]" if args.dry_run else ""
    print(f"SimTalk Code Block Classifier{mode}")
    print(f"Processing {len(files)} files...")
    print("=" * 60)

    total_stats = Counter()
    for f in files:
        stats = process_file(f, dry_run=args.dry_run)
        total_stats.update(stats)
        if stats['total'] > 0:
            print(f"  {f.name}: {stats['total']} blocks → "
                  f"{stats['code_kept']} code, {stats['text_freed']} text freed")

    print(f"\n{'=' * 60}")
    print(f"Total: {total_stats['total']} blocks processed")
    print(f"  Kept as code (```simtalk): {total_stats['code_kept']}")
    print(f"  Freed as text: {total_stats['text_freed']}")


if __name__ == "__main__":
    main()
