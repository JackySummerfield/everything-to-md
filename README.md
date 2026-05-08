# doc-to-knowledgebase

A Copilot Skill that converts documents (PDF, Word, PPT, Excel, etc.) to Markdown using `markitdown` CLI, then interactively analyzes, cleans up, and organizes the output into a well-structured knowledge base.

## Features

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
- Optional: PyMuPDF (`pip install PyMuPDF`) for PDF TOC heading injection

## File Structure

```
doc-to-knowledgebase/
├── SKILL.md                              # Skill definition and workflow
└── references/
    ├── optimization-checklist.md         # Noise detection patterns
    └── inject_headings_example.py        # PDF TOC heading injection reference
```

## License

MIT — see [LICENSE](LICENSE).
