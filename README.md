# everything-to-md

A Copilot Skill that converts documents (PDF, Word, PPT, Excel, etc.) to high-quality Markdown — the essential first step for building knowledge bases, RAG pipelines, or any LLM-ready content. Provides multiple conversion routes with time estimates based on document size.

## Features

- Multiple conversion routes for PDF: PDF→Word→MD, PDF→Docling→MD, PDF→pymupdf4llm→MD
- Time estimates based on document size and chosen route
- Batch conversion of multiple document formats to Markdown
- Interactive noise removal (page numbers, headers/footers, copyright blocks)
- Smart document splitting by chapter structure
- PDF TOC heading injection for documents that lose heading structure during conversion
- Automatic INDEX.md generation with cross-links

## Usage

In VS Code Copilot Chat, use any of these trigger phrases:

- `文档转换` / `knowledge base` / `PDF to markdown` / `convert document` / `batch convert`

Or invoke directly as a skill command.

## Requirements

- Python >= 3.10
- [markitdown](https://github.com/microsoft/markitdown) CLI (`pip install 'markitdown[all]'`)
- Optional: [docling](https://github.com/docling-project/docling) for ML-based PDF conversion
- Optional: [pymupdf4llm](https://github.com/pymupdf/RAG) for fast rule-based PDF conversion
- Optional: [pdf2docx](https://github.com/ArtifexSoftware/pdf2docx) for PDF→Word route

## File Structure

```
everything-to-md/
├── SKILL.md                              # Skill definition and workflow
└── references/
    ├── optimization-checklist.md         # Noise detection patterns
    └── inject_headings_example.py        # PDF TOC heading injection reference
```

## License

MIT — see [LICENSE](LICENSE).
