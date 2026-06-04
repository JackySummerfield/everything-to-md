# everything-to-md

A Copilot Skill based on my experience that converts documents (PDF, Word, PPT, Excel, etc.) to high-quality Markdown — the essential first step for building knowledge bases, RAG pipelines, or any LLM-ready content. Provides multiple conversion routes with time estimates based on document size.

## About

- Copilot is built for **human-AI pair work** — AI does the heavy lifting, you review & steer.
- Your company only pays for GitHub Copilot (definitely not the main reason 🤔).
- No worries — Claude Code can use this skill too.

### Why Markdown?

- Markdown is for AI. HTML is for humans.
- Saves tokens (definitely not the main reason 🤔).
- No worries — you can always convert Markdown to HTML later.

## Getting Started

### Prerequisites

- [VS Code](https://code.visualstudio.com/) 1.99+
- [GitHub Copilot](https://marketplace.visualstudio.com/items?itemName=GitHub.copilot) extension (active subscription)
- Python >= 3.10

### Installation

1. **Clone the skill into your Copilot skills directory**

   ```bash
   # Windows
   git clone https://github.com/JackySummerfield/everything-to-md.git "%USERPROFILE%\.copilot\skills\everything-to-md"

   # macOS / Linux
   git clone https://github.com/JackySummerfield/everything-to-md.git ~/.copilot/skills/everything-to-md
   ```

2. **Install core dependency**

   ```bash
   pip install 'markitdown[all]'
   ```

3. **(Optional) Install route-specific dependencies**

   Choose based on your needs:

   ```bash
   # Route A2: PDF → Word → Markdown (fully local, good quality)
   pip install pdf2docx

   # Route B: PDF → Docling → Markdown (ML-based, ~500MB models on first run)
   pip install docling

   # Route C: PDF → pymupdf4llm → Markdown (fastest, rule-based)
   pip install pymupdf4llm

   # Route D: PDF → Marker → Markdown (best quality, GPU required)
   pip install marker-pdf
   ```

4. **Verify installation**

   Open VS Code Copilot Chat and say:

   ```
   Convert my PDF to markdown
   ```

   If the skill responds with a file selection prompt and route options, it's working.

## Usage

Trigger the skill with any of these phrases:

| Trigger | Description |
|---------|-------------|
| `Convert my PDF to markdown` | Start conversion workflow |
| `文档转换` | 中文触发 |
| `batch convert` | Convert multiple files |
| `document cleanup` | Post-conversion noise removal |
| `split document` | Split large MD by chapters |

### Conversion Routes (PDF)

| Route | Pipeline | Headings | Tables | Speed (CPU) | Notes |
|-------|----------|----------|--------|-------------|-------|
| **A1** | PDF → ilovepdf → DOCX → markitdown | ⭐⭐⭐ | ⭐⭐⭐ | manual + fast | Best quality. Not for confidential docs |
| **A2** | PDF → pdf2docx → DOCX → markitdown | ⭐⭐⭐ | ⭐⭐ | ~2 s/page | Fully local |
| **B** ★ | PDF → docling → MD | ⭐⭐ | ⭐⭐ | ~2 s/page | ML models. Auto-removes headers/footers |
| **C** | PDF → pymupdf4llm → MD | ⭐ | ⭐⭐ | ~0.3 s/page | No ML. Fastest |
| **D** | PDF → marker → MD | ⭐⭐⭐ | ⭐⭐⭐ | ~1 s/page (GPU) | ⚠️ GPU required |

★ = recommended default

### Features

- Multiple conversion routes with time estimates
- Batch conversion of all supported formats
- Interactive noise removal (page numbers, headers/footers, copyright blocks)
- Smart document splitting by chapter structure
- PDF TOC heading injection for documents losing heading structure
- Automatic INDEX.md generation with cross-links
- Intermediate artifact preservation (each step outputs to distinct file)

## File Structure

```
everything-to-md/
├── SKILL.md                          # Skill definition and workflow
├── README.md                         # This file
├── LICENSE                           # MIT license
├── references/
│   └── optimization-checklist.md     # Noise detection patterns
└── scripts/
    └── inject_headings_example.py    # PDF TOC heading injection reference
```

## Roadmap

- [ ] LLM-assisted page-by-page conversion for high-value documents
- [ ] Auto-detect optimal route based on document characteristics
- [ ] Support scanned PDF via OCR pipeline
- [ ] Web page → Markdown conversion (Readability + Turndown)

## Acknowledgments

- [markitdown](https://github.com/microsoft/markitdown) — Microsoft's document-to-Markdown CLI
- [docling](https://github.com/docling-project/docling) — IBM's ML-based document parser
- [pymupdf4llm](https://github.com/pymupdf/RAG) — Fast rule-based PDF extraction
- [Best-README-Template](https://github.com/othneildrew/Best-README-Template) — README structure reference

## License

MIT — see [LICENSE](LICENSE).
