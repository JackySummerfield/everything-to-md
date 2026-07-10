"""Inject heading structure from PDF TOC into Markdown (v2 — context-aware alignment).

Strategy: Anchor + Context-Aware Sequential Alignment
  Phase 1: Anchor L1 headings (high confidence, numbered titles)
  Phase 2: Extract context from PDF (text following each TOC heading)
  Phase 3: Build markdown heading contexts (text following each ## heading)
  Phase 4: Within each L1 section, align TOC entries to markdown headings
           using title + context fingerprint. Skip false headings (those followed
           immediately by another heading with no body text).
  Phase 5: Demote unmatched headings to bold text; cap at max_level.

Usage:
    python inject_headings_v2.py input.md --pdf source.pdf [-o output.md] [--max-level 6]
    python inject_headings_v2.py input.md --toc toc.json

Requires: pip install PyMuPDF
"""
import argparse
import json
import re
import sys
import time
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path


# ─── Helpers ──────────────────────────────────────────────────────────────────

def normalize(text: str) -> str:
    """Normalize title for matching: lowercase, collapse whitespace, strip trailing dots."""
    text = text.strip().lower()
    text = re.sub(r'\s+', ' ', text)
    text = text.rstrip('. ')
    return text


def similarity(a: str, b: str) -> float:
    """String similarity ratio."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def extract_toc_from_pdf(pdf_path: str) -> list:
    """Extract TOC from PDF as [(level, title, page), ...]."""
    import fitz
    with fitz.open(pdf_path) as doc:
        return doc.get_toc()


# ─── Phase 1: Anchor L1 headings ─────────────────────────────────────────────

def find_anchors(heading_texts: list, heading_indices: list, toc: list) -> list:
    """Find L1 TOC entries in markdown headings.

    Returns: [(toc_idx, heading_list_idx, line_idx), ...] sorted by line position.
    """
    l1_entries = [(i, level, title) for i, (level, title, page) in enumerate(toc) if level == 1]
    numbered_re = re.compile(r'^(\d+)\.\s+(.+)$')

    anchors = []
    used_heading_indices = set()

    for toc_idx, level, title in l1_entries:
        title_norm = normalize(title)
        m = numbered_re.match(title)

        best_h_idx = None
        best_score = 0

        for h_idx, h_text in enumerate(heading_texts):
            if h_idx in used_heading_indices:
                continue
            h_norm = normalize(h_text)

            if m:
                if h_norm == title_norm:
                    best_h_idx = h_idx
                    break
                num_prefix = f"{m.group(1)}."
                if h_text.strip().startswith(num_prefix):
                    score = similarity(h_norm, title_norm)
                    if score > best_score and score >= 0.6:
                        best_score = score
                        best_h_idx = h_idx
            else:
                if h_norm == title_norm:
                    best_h_idx = h_idx
                    break

        if best_h_idx is not None:
            used_heading_indices.add(best_h_idx)
            anchors.append((toc_idx, best_h_idx, heading_indices[best_h_idx]))

    anchors.sort(key=lambda x: x[2])
    return anchors


# ─── Phase 2: Extract PDF context ────────────────────────────────────────────

def extract_pdf_contexts(pdf_path: str, toc: list, context_chars: int = 120) -> list:
    """Extract text context following each TOC entry from its PDF page.

    Returns: list of context strings (lowercase, normalized), one per TOC entry.
    """
    import fitz

    contexts = [''] * len(toc)
    doc = fitz.open(pdf_path)

    # Group TOC entries by page for efficiency
    page_groups = {}
    for i, (level, title, page) in enumerate(toc):
        page_idx = page - 1
        if page_idx not in page_groups:
            page_groups[page_idx] = []
        page_groups[page_idx].append((i, title))

    for page_idx, entries in page_groups.items():
        if page_idx < 0 or page_idx >= len(doc):
            continue
        page_text = doc[page_idx].get_text('text')

        for toc_i, title in entries:
            pos = page_text.find(title)
            if pos < 0:
                pos = page_text.lower().find(title.lower())
                if pos >= 0:
                    pos = pos  # use case-insensitive position
            if pos >= 0:
                after = page_text[pos + len(title):pos + len(title) + context_chars]
                after = re.sub(r'\s+', ' ', after).strip().lower()
                contexts[toc_i] = after

    doc.close()
    return contexts


# ─── Phase 3: Build markdown heading contexts ────────────────────────────────

def build_md_contexts(lines: list, heading_indices: list,
                      context_chars: int = 120) -> tuple:
    """Build context for each markdown heading and classify as real/suspect.

    Returns:
        contexts: list of context strings (text following heading, lowercase)
        is_suspect: list of bools (True if heading is likely false)
    """
    heading_re = re.compile(r'^#{1,6}\s+')
    contexts = []
    is_suspect = []

    for idx, line_i in enumerate(heading_indices):
        ctx_parts = []
        followed_by_heading = False
        chars_collected = 0

        for j in range(line_i + 1, min(line_i + 10, len(lines))):
            line = lines[j].strip()
            if not line:
                continue
            if heading_re.match(lines[j]):
                followed_by_heading = True
                break
            ctx_parts.append(line)
            chars_collected += len(line)
            if chars_collected >= context_chars:
                break

        ctx = ' '.join(ctx_parts)[:context_chars].lower()
        ctx = re.sub(r'\s+', ' ', ctx)
        contexts.append(ctx)

        # Suspect: followed by heading with little/no body text
        is_suspect.append(followed_by_heading and chars_collected < 20)

    return contexts, is_suspect


# ─── Phase 4: Sequential alignment with adaptive window + resync ──────────────

def _score_match(toc_norm: str, toc_ctx: str, h_norm: str, md_ctx: str,
                 is_suspect: bool) -> float:
    """Compute combined match score for a TOC-heading pair."""
    # Quick length rejection
    if abs(len(h_norm) - len(toc_norm)) > max(len(toc_norm), 10):
        return 0.0

    # Title similarity
    if h_norm == toc_norm:
        title_score = 1.0
    else:
        title_score = similarity(h_norm, toc_norm)
        if title_score < 0.65:
            return 0.0

    # Context similarity
    if toc_ctx and md_ctx:
        ctx_score = similarity(toc_ctx[:80], md_ctx[:80])
    else:
        ctx_score = 0.5  # neutral

    # Combined score
    if title_score >= 0.95:
        combined = title_score + ctx_score * 0.3
        if is_suspect:
            combined -= 0.2
    else:
        combined = title_score * 0.6 + ctx_score * 0.4
        if is_suspect:
            combined -= 0.3

    return combined


def align_section(toc_entries: list, toc_contexts: list,
                  heading_texts: list, md_contexts: list, md_suspects: list,
                  match_threshold: float = 0.70) -> list:
    """Align TOC entries to markdown headings using two-pass forward scan.

    Pass 1: Sequential forward scan with small window (MAX_SCAN=30).
    Pass 2: For unmatched TOC entries, search within bounded ranges defined
             by neighboring matches from Pass 1. Only accepts strong matches.

    Returns:
        matches: [(heading_local_idx, toc_level), ...]
    """
    total_h = len(heading_texts)
    total_toc = len(toc_entries)

    if total_toc == 0 or total_h == 0:
        return []

    # Pre-compute normalized heading texts
    h_norms = [normalize(h) for h in heading_texts]
    toc_norms = [normalize(t) for _, t in toc_entries]

    MAX_SCAN = 30

    # ── Pass 1: Standard forward scan with lookahead protection ──
    pass1 = {}  # toc_idx → h_idx
    h_ptr = 0
    LOOKAHEAD = 5  # check next N TOC entries for exact match conflicts

    for toc_idx in range(total_toc):
        if h_ptr >= total_h:
            break

        toc_norm = toc_norms[toc_idx]
        if not toc_norm:
            continue

        toc_ctx = toc_contexts[toc_idx] if toc_idx < len(toc_contexts) else ''

        scan_limit = min(MAX_SCAN, total_h - h_ptr)
        best_h = None
        best_score = 0

        for scan in range(scan_limit):
            h_idx = h_ptr + scan
            score = _score_match(toc_norm, toc_ctx, h_norms[h_idx],
                                 md_contexts[h_idx], md_suspects[h_idx])
            if score > best_score:
                best_score = score
                best_h = h_idx
            if score >= 1.1 and not md_suspects[h_idx]:
                break

        if best_h is not None and best_score >= match_threshold:
            # Lookahead: if this is a fuzzy match, check if a later TOC entry
            # would be an exact match for the same heading. If so, skip this
            # fuzzy match to leave the heading available for the exact one.
            if best_score < 1.0:
                skip = False
                best_h_norm = h_norms[best_h]
                for la in range(1, min(LOOKAHEAD + 1, total_toc - toc_idx)):
                    future_norm = toc_norms[toc_idx + la]
                    if future_norm == best_h_norm:
                        skip = True
                        break
                if skip:
                    continue  # don't consume this heading

            pass1[toc_idx] = best_h
            h_ptr = best_h + 1

    # ── Pass 2: Match unique-title TOC entries globally ──
    # For TOC entries not matched in pass1 whose title appears exactly once
    # (or few times) in headings, match directly without positional bounds.
    title_index = {}
    for h_idx, h_norm in enumerate(h_norms):
        if h_norm not in title_index:
            title_index[h_norm] = []
        title_index[h_norm].append(h_idx)

    used_h = set(pass1.values())
    pass2 = {}

    for toc_idx in range(total_toc):
        if toc_idx in pass1:
            continue
        toc_norm = toc_norms[toc_idx]
        if not toc_norm:
            continue

        candidates = title_index.get(toc_norm)
        if not candidates:
            continue

        # Filter to unused candidates
        available = [c for c in candidates if c not in used_h]
        if not available:
            continue

        # Only match if title is rare enough to avoid ambiguity
        if len(available) > 3:
            continue

        toc_ctx = toc_contexts[toc_idx] if toc_idx < len(toc_contexts) else ''

        best_h = None
        best_score = 0
        for h_idx in available:
            score = _score_match(toc_norm, toc_ctx, h_norms[h_idx],
                                 md_contexts[h_idx], md_suspects[h_idx])
            if score > best_score:
                best_score = score
                best_h = h_idx

        # For unique candidates (only 1 available), lower threshold since
        # there's no ambiguity risk even if heading is suspect
        threshold = 0.75 if len(available) == 1 else 0.90
        if best_h is not None and best_score >= threshold:
            pass2[toc_idx] = best_h
            used_h.add(best_h)

    # Combine results
    all_matches = {**pass1, **pass2}
    matches = [(h_idx, toc_entries[toc_idx][0])
               for toc_idx, h_idx in sorted(all_matches.items(), key=lambda x: x[1])]
    return matches


# ─── Main injection logic ─────────────────────────────────────────────────────

def inject_headings_v2(md_text: str, toc: list, pdf_path: str = None,
                       toc_contexts: list = None, max_level: int = 6,
                       match_threshold: float = 0.70) -> tuple:
    """Inject correct heading levels using context-aware sequential alignment."""
    t_start = time.time()
    lines = md_text.splitlines()
    heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$')

    heading_indices = []
    heading_texts = []
    for i, line in enumerate(lines):
        m = heading_pattern.match(line)
        if m:
            heading_indices.append(i)
            heading_texts.append(m.group(2))

    total_headings = len(heading_indices)
    print(f"  Markdown: {total_headings} headings in {len(lines)} lines")
    print(f"  TOC: {len(toc)} entries")

    # Phase 1
    print("\n  Phase 1: Anchoring L1 headings...")
    anchors = find_anchors(heading_texts, heading_indices, toc)
    print(f"    Found {len(anchors)} L1 anchors")
    for toc_idx, h_idx, line_idx in anchors:
        print(f"      L{line_idx + 1}: {heading_texts[h_idx][:60]}")
    sys.stdout.flush()

    # Phase 2
    print("\n  Phase 2: Extracting PDF contexts...")
    t2 = time.time()
    if toc_contexts is None and pdf_path:
        toc_contexts = extract_pdf_contexts(pdf_path, toc)
        ctx_count = sum(1 for c in toc_contexts if c)
        print(f"    Extracted {ctx_count}/{len(toc)} contexts in {time.time()-t2:.1f}s")
    elif toc_contexts:
        ctx_count = sum(1 for c in toc_contexts if c)
        print(f"    Loaded {ctx_count} pre-extracted contexts")
    else:
        toc_contexts = [''] * len(toc)
        print(f"    No PDF — skipping context extraction")
    sys.stdout.flush()

    # Phase 3
    print("\n  Phase 3: Building markdown heading contexts...")
    t3 = time.time()
    md_contexts, md_suspects = build_md_contexts(lines, heading_indices)
    suspect_count = sum(1 for s in md_suspects if s)
    print(f"    {suspect_count} suspect headings (followed by heading, no body)")
    print(f"    Done in {time.time()-t3:.1f}s")
    sys.stdout.flush()

    # Phase 4
    print("\n  Phase 4: Context-aware alignment...")
    assigned_levels = {}
    for toc_idx, h_idx, line_idx in anchors:
        assigned_levels[h_idx] = 1

    total_matched = len(anchors)
    total_unmatched = 0

    for sec_i in range(len(anchors)):
        anchor_toc_idx, anchor_h_idx, _ = anchors[sec_i]

        h_start = anchor_h_idx + 1
        h_end = anchors[sec_i + 1][1] if sec_i + 1 < len(anchors) else total_headings
        toc_start = anchor_toc_idx + 1
        toc_end = anchors[sec_i + 1][0] if sec_i + 1 < len(anchors) else len(toc)

        section_h_texts = heading_texts[h_start:h_end]
        section_md_ctx = md_contexts[h_start:h_end]
        section_md_suspects = md_suspects[h_start:h_end]
        section_toc = [(toc[i][0], toc[i][1]) for i in range(toc_start, toc_end)]
        section_toc_ctx = toc_contexts[toc_start:toc_end]

        if not section_h_texts or not section_toc:
            total_unmatched += len(section_h_texts)
            continue

        matches = align_section(
            section_toc, section_toc_ctx,
            section_h_texts, section_md_ctx, section_md_suspects,
            match_threshold=match_threshold,
        )

        for local_h_idx, toc_level in matches:
            assigned_levels[h_start + local_h_idx] = toc_level

        total_matched += len(matches)
        total_unmatched += len(section_h_texts) - len(matches)

        sec_name = heading_texts[anchor_h_idx][:40]
        if len(section_h_texts) > 50:
            print(f"    [{sec_i+1}/{len(anchors)}] {sec_name}: "
                  f"{len(matches)}/{len(section_h_texts)} matched "
                  f"({len(section_toc)} TOC)")
            sys.stdout.flush()

    print(f"\n    Total: {total_matched} matched, {total_unmatched} unmatched")

    # Phase 5
    print("\n  Phase 5: Applying levels...")
    output_lines = lines.copy()
    stats_methods = Counter()
    stats_levels = Counter()

    for h_idx in range(total_headings):
        line_idx = heading_indices[h_idx]
        text = heading_texts[h_idx]

        if h_idx in assigned_levels:
            level = assigned_levels[h_idx]
            if level <= max_level:
                output_lines[line_idx] = f"{'#' * level} {text}"
                stats_levels[level] += 1
                stats_methods['matched'] += 1
            else:
                output_lines[line_idx] = f"**{text}**"
                stats_methods['demoted_deep'] += 1
        else:
            output_lines[line_idx] = f"**{text}**"
            stats_methods['unmatched'] += 1

    elapsed = time.time() - t_start
    print(f"  Done in {elapsed:.1f}s")

    stats = {
        'total_headings': total_headings,
        'matched': total_matched,
        'unmatched': total_unmatched,
        'suspect_headings': suspect_count,
        'methods': dict(stats_methods),
        'levels': {f'H{k}': v for k, v in sorted(stats_levels.items())},
    }

    return '\n'.join(output_lines), stats


# ─── File-level API ───────────────────────────────────────────────────────────

def inject_headings_to_file(input_path: str, toc: list, pdf_path: str = None,
                            toc_contexts: list = None, output_path: str = None,
                            max_level: int = 6, match_threshold: float = 0.70):
    """Read file, inject headings, write output."""
    input_path = Path(input_path)
    md_text = input_path.read_text(encoding='utf-8')

    output_text, stats = inject_headings_v2(
        md_text, toc, pdf_path=pdf_path, toc_contexts=toc_contexts,
        max_level=max_level, match_threshold=match_threshold,
    )

    if output_path is None:
        output_path = input_path.with_stem(input_path.stem + '_structured')
    else:
        output_path = Path(output_path)

    output_path.write_text(output_text, encoding='utf-8')
    return stats


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Inject heading structure from PDF TOC (v2 — context-aware)")
    parser.add_argument("input_md", type=str, help="Input Markdown file")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--toc", type=str, help="TOC JSON file")
    group.add_argument("--pdf", type=str, help="PDF file (for TOC + context extraction)")
    parser.add_argument("-o", "--output", type=str, default=None,
                        help="Output file (default: input_structured.md)")
    parser.add_argument("--max-level", type=int, default=6,
                        help="Max heading level; deeper becomes bold (default: 6)")
    parser.add_argument("--match-threshold", type=float, default=0.70,
                        help="Min combined score for matching (default: 0.70)")
    args = parser.parse_args()

    input_path = Path(args.input_md).resolve()
    if not input_path.exists():
        print(f"ERROR: File not found: {input_path}")
        sys.exit(1)

    if args.toc:
        toc_path = Path(args.toc).resolve()
        toc = json.loads(toc_path.read_text(encoding='utf-8'))
        print(f"TOC loaded from JSON: {len(toc)} entries")
        pdf_path = None
    else:
        pdf_path = str(Path(args.pdf).resolve())
        toc = extract_toc_from_pdf(pdf_path)
        print(f"TOC extracted from PDF: {len(toc)} entries")

    stats = inject_headings_to_file(
        str(input_path), toc, pdf_path=pdf_path,
        output_path=args.output,
        max_level=args.max_level,
        match_threshold=args.match_threshold,
    )

    output = args.output or str(input_path.with_stem(input_path.stem + '_structured'))
    print(f"\nResults:")
    print(f"  Total headings:  {stats['total_headings']}")
    print(f"  Suspect (false): {stats['suspect_headings']}")
    print(f"  Matched to TOC:  {stats['matched']}")
    print(f"  Unmatched:       {stats['unmatched']}")
    print(f"  Methods: {stats['methods']}")
    print(f"  Levels:  {stats['levels']}")
    print(f"  Output:  {output}")


if __name__ == "__main__":
    main()
