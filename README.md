<div align="center">

中文 · [English](README.en.md)

# 📄 Everything to Markdown

#### 把任何东西转成高质量 Markdown — 文档、视频、音频一网打尽，为知识库和 LLM 场景提供干净的输入

![VS Code 1.99+](https://img.shields.io/badge/VS_Code-1.99+-007ACC?style=for-the-badge&logo=visualstudiocode&logoColor=white)
![GitHub Copilot](https://img.shields.io/badge/GitHub_Copilot-Skill-000?style=for-the-badge&logo=githubcopilot&logoColor=white)
![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

[为什么做这个](#-为什么做这个) · [它能做什么](#-它能做什么) · [快速开始](#-快速开始) · [架构](#-架构)

</div>

---

## 🤔 为什么做这个

搭建知识库、做 RAG、喂 LLM — 第一步永远是把原始资料变成干净的 Markdown。但资料来源五花八门：PDF、Word、PPT、B站视频、YouTube、小红书、本地录音……每种格式对应不同的工具链和坑。

本 Skill 把这些路径统一成一个入口：**告诉 AI 你要转什么，它自动识别类型、选择管线、输出 `_raw.md`，再引导你做交互式清理。**

## 📋 它能做什么

| 输入类型 | 示例 | 转换方式 |
|---------|------|---------|
| 本地文档 | PDF, Word, PPT, Excel, HTML, EPUB | markitdown / docling / pymupdf4llm / marker，多路由可选 |
| 视频/音频链接 | B站、YouTube、小红书 | yt-dlp 提取字幕/音频 → ASR → Markdown |
| 本地音视频文件 | .mp3, .wav, .mp4, .mov | FunASR / Whisper 语音转文字 → Markdown |

### 能力边界（老实说）

| 场景 | 状态 |
|------|------|
| PDF/Word/PPT → Markdown | ✅ 可靠，多路由经过实战验证 |
| B站/YouTube 有字幕的视频 | ✅ 高质量 |
| 中文语音 ASR（清晰语音） | ⚠️ 能用，专业术语可能出错 |
| 抖音/TikTok 链接 | ❌ 不可靠（上游反爬） |
| 自动摘要 | ❌ 规则式质量低，建议用 LLM 二次处理 |

**关键认知**：这个工具产出的是**转录稿**，不是**摘要**。语音内容的知识提取，应该把转录稿喂给 LLM 来做。

## 🚀 快速开始

### 前置条件

- VS Code 1.99+ + GitHub Copilot
- Python ≥ 3.10

### 安装核心依赖

```bash
pip install 'markitdown[all]'
```

### 按需安装（用到哪个装哪个）

```bash
# 文档转换路由
pip install pdf2docx           # PDF → Word → MD
pip install docling            # PDF → ML 转换（首次下载 ~500MB 模型）
pip install pymupdf4llm        # PDF → 快速规则式转换

# 视频/音频
pip install yt-dlp imageio-ffmpeg
pip install funasr torch torchaudio    # 中文 ASR (FunASR)
pip install faster-whisper             # 多语言 ASR 备选
pip install rapidocr-onnxruntime       # 图片帖子 OCR
```

### 使用

在 Copilot Chat 中直接说：

```
把这个 PDF 转成 markdown
把这个B站链接转成markdown：https://www.bilibili.com/video/BVxxxxx
视频转文字
```

## 🏗 架构

```
用户输入 → [类型识别] → Track A (文档) / B (URL) / C (本地音视频) → _raw.md → 交互式清理
```

- **Track A**：支持多种转换路由（docling / pymupdf4llm / markitdown / marker），Skill 会推荐最适合的，让你确认后执行
- **Track B**：先提取字幕，没有字幕则下载音频走 ASR
- **Track C**：直接对本地文件做语音识别

所有中间文件输出到用户指定目录，不会污染 Skill 目录。

## 📁 文件结构

```
everything-to-md/
├── SKILL.md                        # AI 工作流定义
├── README.md                       # 中文说明（本文件）
├── README.en.md                    # English docs
├── references/
│   ├── markdown-cleanup.md         # 转换后清理流程
│   ├── media-url-to-md.md          # Track B/C 管线细节
│   └── optimization-checklist.md   # 噪声检测模式
└── scripts/
    ├── fetch_media.py              # URL → 元数据 + 音频/字幕/图片
    ├── transcribe.py               # 字幕优先 → ASR 转录
    ├── summarize_transcript.py     # 质量评估 + 关键词提取
    ├── assemble_media_md.py        # 组装最终 _raw.md
    ├── term_glossary.json          # ASR 纠错词表
    ├── convert_docling_batch.py    # 大 PDF 分批转换
    ├── inject_headings_v2.py       # PDF 目录 → Markdown 标题
    ├── split_recursive.py          # 按章节拆分大 MD
    ├── merge_code_blocks.py        # 合并被截断的代码块
    └── fix_*.py                    # 领域特定修复脚本
```

## 🏷️ 触发词

`文档转换` · `PDF to markdown` · `convert document` · `知识库` · `batch convert` · `document cleanup` · `B站` · `bilibili` · `小红书` · `video to markdown` · `音频转文字` · `视频转文字` · `transcribe`

## 📝 License

MIT
