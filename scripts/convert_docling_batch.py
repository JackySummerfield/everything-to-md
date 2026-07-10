"""Batch convert large PDF to Markdown using Docling (Route B).

Features:
- Text + tables + code blocks (layout detection)
- No images, no OCR (configurable)
- Single process, model loaded ONCE, process pages in small batches to avoid OOM
- Per-batch progress with speed and ETA
- **Resume support**: each batch saved to disk immediately; restart skips completed batches

Usage:
    python convert_docling_batch.py input.pdf [-o output_dir] [-b batch_size] [-p total_pages]
    python convert_docling_batch.py input.pdf -o ./output -b 100

If total_pages is not specified, PyMuPDF is used to detect it automatically.
Requires: pip install docling PyMuPDF
"""
import argparse
import time
import sys
from pathlib import Path


def get_page_count(pdf_path: str) -> int:
    """Get total page count using PyMuPDF."""
    import fitz
    with fitz.open(pdf_path) as doc:
        return len(doc)


def main():
    parser = argparse.ArgumentParser(description="Batch convert large PDF to Markdown via Docling")
    parser.add_argument("input_pdf", type=str, help="Path to input PDF file")
    parser.add_argument("-o", "--output-dir", type=str, default=None,
                        help="Output directory (default: same as input PDF)")
    parser.add_argument("-b", "--batch-size", type=int, default=100,
                        help="Pages per batch (default: 100, reduce if OOM)")
    parser.add_argument("-p", "--total-pages", type=int, default=None,
                        help="Total pages (auto-detected if omitted)")
    parser.add_argument("--output-name", type=str, default="_full_docling.md",
                        help="Output filename (default: _full_docling.md)")
    parser.add_argument("--ocr", action="store_true", help="Enable OCR (default: off)")
    parser.add_argument("--threads", type=int, default=8, help="CPU threads (default: 8)")
    args = parser.parse_args()

    input_pdf = Path(args.input_pdf).resolve()
    if not input_pdf.exists():
        print(f"ERROR: File not found: {input_pdf}")
        sys.exit(1)

    output_dir = Path(args.output_dir) if args.output_dir else input_pdf.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    total_pages = args.total_pages or get_page_count(str(input_pdf))
    batch_size = args.batch_size

    print(f"Input:  {input_pdf.name} ({input_pdf.stat().st_size / 1024 / 1024:.1f} MB, {total_pages} pages)")
    print(f"Output: {output_dir / args.output_name}")
    print(f"Batch:  {batch_size} pages/batch, {(total_pages + batch_size - 1) // batch_size} batches")

    # Import and initialize Docling
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.datamodel.accelerator_options import AcceleratorOptions

    print("\nLoading model & initializing converter (one-time cost)...")
    t_init = time.time()

    pipeline_options = PdfPipelineOptions(
        accelerator_options=AcceleratorOptions(num_threads=args.threads),
        do_ocr=args.ocr,
        do_table_structure=True,
        do_picture_classification=False,
        do_picture_description=False,
        do_chart_extraction=False,
        do_code_enrichment=False,
        do_formula_enrichment=False,
        generate_page_images=False,
        generate_picture_images=False,
        generate_table_images=False,
        images_scale=0.5,
    )

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )
    print(f"  Model loaded in {time.time() - t_init:.1f}s")

    # Batch output directory for resume support
    batch_dir = output_dir / "_batches"
    batch_dir.mkdir(parents=True, exist_ok=True)

    # Process in batches with resume
    failed_ranges = []
    t_global = time.time()
    total_batches = (total_pages + batch_size - 1) // batch_size
    skipped = 0

    print(f"\nConverting {total_pages} pages in {total_batches} batches")
    print(f"Batch files: {batch_dir}")
    print("=" * 70)

    for batch_idx, start in enumerate(range(0, total_pages, batch_size)):
        end = min(start + batch_size, total_pages)
        batch_file = batch_dir / f"batch_{start + 1:06d}_{end:06d}.md"

        # Resume: skip already completed batches
        if batch_file.exists() and batch_file.stat().st_size > 0:
            skipped += 1
            if skipped <= 3 or skipped == total_batches:
                print(f"  [{batch_idx + 1:3d}/{total_batches}] p{start + 1:>5d}-{end:<5d} SKIPPED (exists)")
            elif skipped == 4:
                print(f"  ... skipping remaining completed batches ...")
            continue

        if skipped > 0 and batch_idx == skipped:
            print(f"  ({skipped} batches skipped, resuming from batch {batch_idx + 1})")

        t0 = time.time()
        try:
            result = converter.convert(
                source=str(input_pdf),
                page_range=(start + 1, end),
            )
            md_text = result.document.export_to_markdown()
            elapsed = time.time() - t0

            # Save batch immediately to disk
            batch_file.write_text(md_text, encoding="utf-8")
            status = f"OK {len(md_text) / 1024:.0f}KB"

        except Exception as e:
            elapsed = time.time() - t0
            error_text = f"\n<!-- ERROR p{start + 1}-{end}: {e} -->\n"
            # Write error marker (small file) so we can detect and retry later
            batch_file.with_suffix(".error").write_text(error_text, encoding="utf-8")
            failed_ranges.append((start + 1, end, str(e)))
            status = f"FAILED: {e}"

        # Progress
        pages_done = end - (skipped * batch_size)
        elapsed_total = time.time() - t_global
        avg_spd = elapsed_total / max(pages_done, 1)
        remaining_pages = total_pages - end
        eta = remaining_pages * avg_spd

        print(f"  [{batch_idx + 1:3d}/{total_batches}] p{start + 1:>5d}-{end:<5d} "
              f"{elapsed:5.1f}s ({elapsed / (end - start):.1f}s/pg) | {status} | "
              f"avg {avg_spd:.1f}s/pg | ETA {eta / 60:.1f}min")
        sys.stdout.flush()

    # Merge all batch files in order
    print(f"\n{'=' * 70}")
    print("Merging batch files...")
    all_md_parts = []
    for start in range(0, total_pages, batch_size):
        end = min(start + batch_size, total_pages)
        batch_file = batch_dir / f"batch_{start + 1:06d}_{end:06d}.md"
        error_file = batch_file.with_suffix(".error")
        if batch_file.exists():
            all_md_parts.append(batch_file.read_text(encoding="utf-8"))
        elif error_file.exists():
            all_md_parts.append(error_file.read_text(encoding="utf-8"))
        else:
            all_md_parts.append(f"\n<!-- MISSING p{start + 1}-{end} -->\n")

    full_md = "\n\n".join(all_md_parts)
    output_file = output_dir / args.output_name
    output_file.write_text(full_md, encoding="utf-8")

    total_time = time.time() - t_global
    print(f"DONE! {output_file}")
    print(f"  Size: {len(full_md) / 1024 / 1024:.2f} MB")
    print(f"  Time: {total_time / 60:.1f} min (skipped {skipped} cached batches)")
    print(f"  Failed: {len(failed_ranges)} batches")

    if failed_ranges:
        print("\n  Failed pages (delete .error file & re-run to retry):")
        for s, e, err in failed_ranges:
            print(f"    p{s}-{e}: {err}")


if __name__ == "__main__":
    main()
