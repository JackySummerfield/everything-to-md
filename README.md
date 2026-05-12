# everything-to-md

A Copilot Skill that converts documents (PDF, Word, PPT, Excel, etc.) to high-quality Markdown — the essential first step for building knowledge bases, RAG pipelines, or any LLM-ready content. Provides multiple conversion routes with time estimates based on document size.

## Why a GitHub Copilot Skill?

- Copilot is built for **human-AI pair work** — AI does the heavy lifting, you review & steer.
- Your company only pays for GitHub Copilot *(definitely not the main reason 😀)*.
- No worries — Claude Code can use this skill too.

## Why Markdown?

- Markdown is for AI. HTML is for humans.
- Saves tokens *(definitely not the main reason 😀)*.
- No worries — you can always convert Markdown to HTML later.

## Quick Start

Clone this skill into your local Copilot skills directory:

```bash
# Windows
git clone https://github.com/JackySummerfield/everything-to-md.git "%USERPROFILE%\.copilot\skills\everything-to-md"

# macOS / Linux
git clone https://github.com/JackySummerfield/everything-to-md.git ~/.copilot/skills/everything-to-md
```

Then in VS Code Copilot Chat, just say:

```
Convert my PDF to markdown
```

or any trigger phrase like `文档转换`, `PDF to markdown`, `convert document`, etc. Copilot will pick up the skill automatically.

## Features

- Multiple conversion routes for PDF: PDF→Word→MD, PDF→Docling→MD, PDF→pymupdf4llm→MD
- Time estimates based on document size and chosen route
- Batch conversion of multiple document formats to Markdown
- Interactive noise removal (page numbers, headers/footers, copyright blocks)
- Smart document splitting by chapter structure
- PDF TOC heading injection for documents that lose heading structure during conversion
- Automatic INDEX.md generation with cross-links

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
