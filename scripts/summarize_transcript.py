#!/usr/bin/env python3
"""Transcript preprocessing: structure, keywords, and quality assessment.

This script does what rule-based NLP can reliably do on spoken transcripts:
1. Clean oral filler words and normalize whitespace.
2. Detect structural cues (numbered points, topic transitions).
3. Extract keywords (technical terms, proper nouns).
4. Assess transcript quality (punctuation density, garble indicators).
5. Produce a lightweight metadata file for downstream use.

It does NOT attempt knowledge summarization — that requires an LLM.
For knowledge-dense summary, paste the cleaned transcript into ChatGPT/Claude.

Input:  working directory with transcript.txt, OR a transcript file path.
Output: transcript_meta.json (structured metadata for the transcript).
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

STOPWORDS = {
    "我们", "你们", "他们", "这个", "那个", "这些", "那些", "就是", "其实", "然后",
    "所以", "因为", "如果", "的话", "一个", "一种", "一些", "还有", "已经", "以及",
    "比如", "现在", "之前", "之后", "可以", "不能", "没有", "不是", "还是", "需要",
    "这样", "那样", "这里", "那里", "什么", "怎么", "为什么", "啊", "呀", "呢", "吧",
    "哦", "嗯", "呃", "哎", "哎呀",
}

FILLER_PATTERNS = [
    r"(呃|嗯|啊|呀|吧|呢|哎呀?)",
    r"(就是说|然后呢|的话呢|这个呢|那个呢)",
]


def resolve_input(path_str: str) -> tuple[Path, Path]:
    p = Path(path_str)
    if p.is_dir():
        tp = p / "transcript.txt"
        if not tp.exists():
            raise SystemExit(f"transcript.txt not found in: {p}")
        return p, tp
    if p.is_file():
        return p.parent, p
    raise SystemExit(f"Input not found: {path_str}")


def clean_text(text: str) -> str:
    """Remove emoji noise and normalize whitespace."""
    text = re.sub(r"[🎼🎵🎶😊😄😢😭😡😤👏🎉]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def strip_fillers(text: str) -> str:
    """Remove oral filler words for cleaner downstream processing."""
    for p in FILLER_PATTERNS:
        text = re.sub(p, " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_keywords(text: str, topk: int = 20) -> list[str]:
    """Extract keywords: English/acronym terms + Chinese terms via jieba."""
    # English/acronym terms
    en_terms = re.findall(r"\b[A-Za-z][A-Za-z0-9.+_-]{1,20}\b", text)

    # Chinese terms
    try:
        import jieba.analyse  # type: ignore
        zh_terms = jieba.analyse.textrank(text, topK=topk * 2, withWeight=False)
    except Exception:
        zh_terms = re.findall(r"[\u4e00-\u9fff]{2,6}", text)

    all_terms = [t.strip() for t in (en_terms + list(zh_terms)) if t.strip()]
    filtered = [t for t in all_terms if t not in STOPWORDS and len(t) > 1]
    freq = Counter(filtered)
    return [k for k, _ in freq.most_common(topk)]


def detect_structure(text: str) -> list[str]:
    """Detect spoken structural cues like '第一个...', '第二个...'."""
    matches = re.findall(r"第([一二三四五六七八九十\d]+)[个种类点步]", text)
    seen = []
    for m in matches:
        label = f"第{m}"
        if label not in seen:
            seen.append(label)
    return seen


def assess_quality(text: str) -> dict:
    """Assess transcript quality and return score + issues."""
    issues: list[str] = []
    score = 100

    # Punctuation density
    punct = len(re.findall(r"[。！？!?，,；;]", text))
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    if cjk > 0:
        density = punct / cjk
        if density < 0.015:
            score -= 20
            issues.append("标点密度极低，句边界不清晰（ASR 未输出标点或标点丢失）")

    # Long unbroken runs
    segments = re.split(r"[。！？!?\n]", text)
    long_runs = sum(1 for s in segments if len(s.strip()) > 200)
    if long_runs >= 3:
        score -= 15
        issues.append(f"存在 {long_runs} 个超长连句（>200字无断句），理解困难")

    # Text too short
    if len(text) < 300:
        score -= 15
        issues.append("转录文本过短（<300字），信息覆盖可能不足")

    # Common garble indicators (generic, not topic-specific)
    garble_indicators = [
        r"[a-z]{1,2}\s+[a-z]{1,2}\s+[a-z]{1,2}",  # single-char spaced letters
    ]
    garble_hits = sum(len(re.findall(p, text, re.I)) for p in garble_indicators)
    if garble_hits >= 5:
        score -= 15
        issues.append("检测到多处字母拆分（如 'g l m'），可能是术语误识别")

    score = max(0, min(100, score))
    return {"score": score, "issues": issues}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", help="Working dir (with transcript.txt) OR transcript file path")
    args = parser.parse_args(argv)

    work_dir, transcript_path = resolve_input(args.input)
    raw_text = transcript_path.read_text(encoding="utf-8", errors="ignore")
    text = clean_text(raw_text)

    quality = assess_quality(text)
    keywords = extract_keywords(text)
    structure = detect_structure(text)
    cleaned = strip_fillers(text)

    meta = {
        "char_count": len(text),
        "keywords": keywords,
        "detected_structure": structure,
        "quality": quality,
        "cleaned_char_count": len(cleaned),
    }

    meta_path = work_dir / "transcript_meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # Also write cleaned transcript for convenience
    cleaned_path = work_dir / "transcript_cleaned.txt"
    cleaned_path.write_text(cleaned, encoding="utf-8")

    print(f"Quality score  : {quality['score']}/100")
    if quality["issues"]:
        for issue in quality["issues"]:
            print(f"  ⚠ {issue}")
    print(f"Keywords ({len(keywords)}): {', '.join(keywords[:10])}")
    if structure:
        print(f"Structure cues : {', '.join(structure)}")
    print(f"Output         : {meta_path}")
    print(f"Cleaned text   : {cleaned_path}")

    if quality["score"] < 70:
        print()
        print("💡 Transcript quality is low. Recommendations:")
        print("   1. Check if the platform has subtitles (re-fetch with subtitle priority)")
        print("   2. Try --engine whisper for comparison")
        print("   3. For knowledge extraction, paste transcript_cleaned.txt into an LLM")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
