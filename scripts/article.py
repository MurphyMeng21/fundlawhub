#!/usr/bin/env python3
"""
Extract one or more articles from a downloaded law/regulation DOCX.

This avoids loading the full law text into the agent context. The DOCX is
parsed locally and only the requested articles (plus optional neighbours) are
returned.

Examples:
    python scripts/article.py 217 民法典
    python scripts/article.py 51,211,347 民法典 --json
    python scripts/article.py 217 ff80808172b5f24f0172d9f04f0910af --context 0
"""

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

try:
    import docx
except ImportError:  # python-docx is only needed for article extraction
    docx = None

import download as dl


CHINESE_DIGITS = "零一二三四五六七八九十"
CHINESE_UNITS = ["", "十", "百", "千"]
CHINESE_BIG_UNITS = ["", "万", "亿"]


def arabic_to_chinese(n: int) -> str:
    """Convert a non-negative Arabic integer (0-99999) to Chinese numerals."""
    if not 0 <= n <= 99999:
        raise ValueError("Only 0-99999 is supported")
    if n == 0:
        return "零"

    parts = []
    unit_idx = 0
    while n > 0:
        segment = n % 10000
        if segment or unit_idx == 0:
            parts.append(_four_digit_to_chinese(segment) + CHINESE_BIG_UNITS[unit_idx])
        n //= 10000
        unit_idx += 1

    return "".join(reversed(parts))


def _four_digit_to_chinese(n: int) -> str:
    if n == 0:
        return ""
    if n < 20:
        if n < 10:
            return CHINESE_DIGITS[n]
        return "十" + (CHINESE_DIGITS[n % 10] if n % 10 else "")

    s = str(n).zfill(4)
    digits = []
    for i, ch in enumerate(s):
        d = int(ch)
        if d == 0:
            if digits and digits[-1] != "零":
                digits.append("零")
        else:
            digits.append(CHINESE_DIGITS[d] + CHINESE_UNITS[3 - i])
    return "".join(digits).rstrip("零")


def chinese_to_arabic(s: str) -> int:
    """Convert Chinese numerals (零-九万) to an int. Raises ValueError on failure."""
    s = s.strip().replace(" ", "").replace("零", "")
    if not s:
        return 0

    # "十" at the start implies "一十".
    if s.startswith("十"):
        s = "一" + s

    digit_map = {c: i for i, c in enumerate(CHINESE_DIGITS)}
    small_units = {"十": 10, "百": 100, "千": 1000}

    def parse_under_10000(text: str) -> int:
        value = 0
        i = 0
        while i < len(text):
            ch = text[i]
            if ch in digit_map:
                d = digit_map[ch]
                if i + 1 < len(text) and text[i + 1] in small_units:
                    value += d * small_units[text[i + 1]]
                    i += 2
                else:
                    value += d
                    i += 1
            else:
                i += 1
        return value

    if "万" in s:
        parts = s.split("万", 1)
        high = parse_under_10000(parts[0]) if parts[0] else 0
        low = parse_under_10000(parts[1]) if len(parts) > 1 and parts[1] else 0
        return high * 10000 + low
    return parse_under_10000(s)


def _build_heading_regex(style: str) -> re.Pattern:
    """Build a regex that matches article headings for the given numbering style."""
    if style == "chinese":
        return re.compile(r"第\s*([零一二三四五六七八九十百千万]+)\s*条")
    if style == "arabic":
        return re.compile(r"第\s*(\d+)\s*条")
    if style == "dotted":
        return re.compile(r"^(\d+)\s*[\.、]")
    # Try the most common forms first, then dotted fallback.
    return re.compile(r"(?:第\s*([零一二三四五六七八九十百千万]+|\d+)\s*条|^(\d+)\s*[\.、])")


def detect_numbering_style(detail_data: dict) -> str:
    """Inspect detail API content.children TOC and guess the article numbering style."""
    children = detail_data.get("data", {}).get("content", {}).get("children", []) if detail_data else []
    if not children and isinstance(detail_data, list):
        children = detail_data

    headings = []
    def walk(nodes):
        for node in nodes:
            if not isinstance(node, dict):
                continue
            t = node.get("title", "") or node.get("label", "") or ""
            if t:
                headings.append(t)
            kids = node.get("children", [])
            if kids:
                walk(kids)
    walk(children)

    # Score each style by how many headings match.
    chinese_re = re.compile(r"第\s*[零一二三四五六七八九十百千万]+\s*条")
    arabic_re = re.compile(r"第\s*\d+\s*条")
    dotted_re = re.compile(r"^\d+\s*[\.、]")

    scores = {"chinese": 0, "arabic": 0, "dotted": 0}
    for h in headings:
        if chinese_re.search(h):
            scores["chinese"] += 1
        elif arabic_re.search(h):
            scores["arabic"] += 1
        elif dotted_re.search(h):
            scores["dotted"] += 1

    if max(scores.values(), default=0) == 0:
        return "auto"
    return max(scores, key=scores.get)


def _parse_article_number(text: str, pattern: re.Pattern) -> Optional[int]:
    m = pattern.match(text.strip())
    if not m:
        return None
    num_str = m.group(1) or m.group(2)
    if not num_str:
        return None
    try:
        return int(num_str) if num_str.isdigit() else chinese_to_arabic(num_str)
    except Exception:
        return None


def _extract_paragraphs(docx_path: str, pattern: re.Pattern) -> List[Tuple[int, int, str, Optional[int]]]:
    """Return (idx, article_number, text, parsed_heading_number) for each paragraph."""
    if docx is None:
        raise RuntimeError("python-docx is required for article extraction. Install: pip install python-docx")

    document = docx.Document(docx_path)
    paragraphs = []
    current_article = 0  # 0 = preamble / before first article

    for idx, para in enumerate(document.paragraphs):
        text = para.text.strip()
        if not text:
            continue
        heading_num = _parse_article_number(text, pattern)
        if heading_num is not None:
            current_article = heading_num
        paragraphs.append((idx, current_article, text, heading_num))

    return paragraphs


def extract_articles_from_docx(
    docx_path: str,
    article_numbers: List[int],
    context: int = 1,
    style: str = "auto",
) -> dict:
    """
    Extract requested articles from a DOCX file.

    Returns {
        "found": [int],
        "not_found": [int],
        "segments": [{"article_number": int, "text": str, "is_heading": bool}],
        "style_used": str,
    }
    """
    target_set = set(article_numbers)
    wanted = set()
    for n in article_numbers:
        for i in range(max(0, n - context), n + context + 1):
            wanted.add(i)

    def try_extract(pattern: re.Pattern) -> Optional[dict]:
        paragraphs = _extract_paragraphs(docx_path, pattern)
        if not paragraphs:
            return None

        found = set()
        for _, art, _, heading_num in paragraphs:
            if heading_num in target_set:
                found.add(heading_num)

        if not found:
            return None

        # Collect all paragraphs whose article_number is in wanted range of any found target.
        # (If a target is missing, its context range is irrelevant.)
        effective_wanted = set()
        for n in found:
            for i in range(max(0, n - context), n + context + 1):
                effective_wanted.add(i)

        segments = []
        seen_idx = set()
        for idx, art, text, heading_num in paragraphs:
            if art in effective_wanted and idx not in seen_idx:
                seen_idx.add(idx)
                segments.append({
                    "article_number": art,
                    "text": text,
                    "is_heading": heading_num is not None,
                })

        return {
            "found": sorted(found),
            "not_found": sorted(target_set - found),
            "segments": segments,
            "style_used": style,
        }

    # Fast path: most common Chinese numbering.
    if style == "auto":
        for fast_style in ("chinese", "arabic", "dotted"):
            pattern = _build_heading_regex(fast_style)
            result = try_extract(pattern)
            if result and not result["not_found"]:
                result["style_used"] = fast_style
                return result

    pattern = _build_heading_regex(style)
    result = try_extract(pattern)
    if result:
        return result

    return {
        "found": [],
        "not_found": sorted(article_numbers),
        "segments": [],
        "style_used": style,
    }


def resolve_law_id(identifier: str) -> Tuple[str, dict]:
    """Return (bbbs_id, detail_info). If identifier is a keyword, search and use first result."""
    if re.fullmatch(r"[0-9a-fA-F]{32}", identifier):
        detail = dl.parse_detail(dl.fetch_detail(identifier))
        if not detail:
            raise RuntimeError(f"Could not fetch detail for bbbs_id {identifier}")
        return identifier, detail

    data = dl.search_laws(identifier, page=1, size=5, search_range=1, search_type=2)
    rows = data.get("rows", []) if data.get("code") == 200 else []
    if not rows:
        data = dl.search_laws(identifier, page=1, size=5, search_range=2, search_type=2)
        rows = data.get("rows", []) if data.get("code") == 200 else []
    if not rows:
        raise RuntimeError(f"No law found for keyword: {identifier}")

    bbbs = rows[0].get("bbbs")
    detail = dl.parse_detail(dl.fetch_detail(bbbs))
    if not detail:
        raise RuntimeError(f"Could not fetch detail for bbbs_id {bbbs}")
    return bbbs, detail


def _download_docx(bbbs_id: str, detail: dict) -> str:
    """Download the DOCX to a temp file and return the path."""
    url = dl.get_download_url(bbbs_id, "docx")
    suffix = ".docx"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = tmp.name
    dl.download_file(url, tmp_path)
    return tmp_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="article.py",
        description="Extract one or more articles from a law/regulation DOCX.",
    )
    parser.add_argument("articles", help="Article number(s), e.g. 217 or 51,211,347")
    parser.add_argument("law", help="Law identifier: 32-char bbbs_id or search keyword")
    parser.add_argument("--context", type=int, default=1, help="Number of neighbouring articles to include (default: 1)")
    parser.add_argument("--style", default="auto", choices=["auto", "chinese", "arabic", "dotted"], help="Article numbering style")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of plain text")
    parser.add_argument("--keep-docx", metavar="PATH", help="Keep the downloaded DOCX at this path")
    return parser


def parse_article_numbers(s: str) -> List[int]:
    numbers = []
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            numbers.append(int(part))
        except ValueError:
            raise argparse.ArgumentTypeError(f"Invalid article number: {part}")
    if not numbers:
        raise argparse.ArgumentTypeError("At least one article number is required")
    return numbers


def main():
    parser = build_parser()
    args = parser.parse_args()

    article_numbers = parse_article_numbers(args.articles)

    bbbs_id, detail = resolve_law_id(args.law)
    print(f"# {detail['title']} (bbbs: {bbbs_id})", file=sys.stderr)

    docx_path = _download_docx(bbbs_id, detail)
    try:
        if args.keep_docx:
            os.replace(docx_path, args.keep_docx)
            docx_path = args.keep_docx

        style = args.style
        result = extract_articles_from_docx(docx_path, article_numbers, context=args.context, style=style)

        # Fallback to detail API style detection if anything is missing.
        if result["not_found"] and style == "auto":
            detected = detect_numbering_style(dl.fetch_detail(bbbs_id))
            if detected != "auto":
                result = extract_articles_from_docx(docx_path, article_numbers, context=args.context, style=detected)

        if args.json:
            payload = {
                "law": detail["title"],
                "bbbs": bbbs_id,
                "style_used": result["style_used"],
                "found": result["found"],
                "not_found": result["not_found"],
                "segments": result["segments"],
            }
            json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
            print()
        else:
            for seg in result["segments"]:
                print(seg["text"])
            if result["not_found"]:
                print(f"\n# Not found: {result['not_found']}", file=sys.stderr)
    finally:
        if not args.keep_docx and os.path.exists(docx_path):
            os.unlink(docx_path)


if __name__ == "__main__":
    main()
