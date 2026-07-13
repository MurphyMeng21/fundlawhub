#!/usr/bin/env python3
"""
build_search_db.py — Merge NPC/CSRC metadata + full-text .md files into one laws.json
for the static web search app.

Usage:
  python scripts/build_search_db.py
"""
import json, os, re, hashlib, sys
from pathlib import Path
from datetime import datetime, timezone

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
# Data lives under obsidian/
OBSIDIAN_BASE = Path("/Users/yan/Desktop/for_claude/obsidian/01-法务知识库/合规研究")
NPC_META = OBSIDIAN_BASE / "_data" / "npc_metadata.json"
CSRC_META = OBSIDIAN_BASE / "_data" / "csrc_metadata.json"
MD_ROOT = OBSIDIAN_BASE / "_data" / "法规原文"
OUTPUT_DIR = PROJECT_DIR / "web" / "data"
OUTPUT_FILE = OUTPUT_DIR / "laws.json"

# --- Category mapping: NPC category key -> display name, dir name ---
CATEGORY_CONFIG = {
    "基金运作": {"display": "基金运作与监管", "dir": "基金运作"},
    "证券交易": {"display": "证券交易合规", "dir": "证券交易"},
    "反洗钱":   {"display": "反洗钱与CRS", "dir": "反洗钱"},
    "广告竞争": {"display": "广告与市场竞争", "dir": "广告竞争"},
    "税务":     {"display": "税务", "dir": "税务"},
    "劳动":     {"display": "劳动人事", "dir": "劳动人事"},
    "跨境":     {"display": "跨境业务", "dir": "跨境"},
    "基础法律": {"display": "基础法律与知识产权", "dir": "基础法律"},
    "量化交易": {"display": "程序化/量化交易", "dir": "量化交易"},
    "交易所":   {"display": "交易所规则", "dir": "交易所"},
}

LEVEL_ORDER = {"法律": 1, "行政法规": 2, "司法解释": 3, "司法文件": 4, "部门规章": 5, "自律规则": 6, "行政规范": 7}


def safe_filename(title: str) -> str:
    """Replicate the filename sanitization used by download_npc.py."""
    return re.sub(r'[\\/:*?"<>|]', '_', title)[:60]


def normalize_date(value):
    """Normalize dates to ISO string or None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d")
    if isinstance(value, str):
        value = value.strip()
        if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
            return value
        if len(value) >= 10:
            return value[:10]
    return str(value) if value else None


def is_broken_md(content: str) -> bool:
    """Detect HTML error pages or truncated content."""
    if len(content) < 200:
        return True
    head = content.strip()[:500].lower()
    if head.startswith("<!doctype") or head.startswith("<html"):
        return True
    if "page not found" in head or "404" in head[:100]:
        return True
    return False


def load_md_index(md_root: Path) -> dict[str, dict[str, str]]:
    """Walk 法规原文/ and return {dir_name: {safe_title: (path, content)}}."""
    index = {}
    if not md_root.exists():
        print(f"  WARNING: MD root not found: {md_root}")
        return index

    for cat_dir in md_root.iterdir():
        if not cat_dir.is_dir() or cat_dir.name.startswith('.'):
            continue
        dir_name = cat_dir.name
        index[dir_name] = {}
        for md_file in cat_dir.glob("*.md"):
            safe_name = md_file.stem  # filename without .md
            try:
                content = md_file.read_text(encoding='utf-8')
            except Exception as e:
                print(f"  WARNING: Cannot read {md_file}: {e}")
                content = ""
            index[dir_name][safe_name] = content
    return index


def match_md(title: str, category_key: str, md_index: dict) -> tuple[str | None, bool]:
    """Find matching .md content for a title. Returns (content, is_broken)."""
    cfg = CATEGORY_CONFIG.get(category_key)
    if not cfg:
        return None, False
    dir_name = cfg["dir"]
    dir_files = md_index.get(dir_name, {})

    expected = safe_filename(title)
    # Exact match
    if expected in dir_files:
        content = dir_files[expected]
        return content, is_broken_md(content)

    # Fuzzy: try removing 中华人民共和国 prefix
    alt = safe_filename(title.replace("中华人民共和国", ""))
    if alt in dir_files:
        content = dir_files[alt]
        return content, is_broken_md(content)

    # Fuzzy: try partial match (title contains filename or vice versa)
    for fname, content in dir_files.items():
        if len(fname) > 6 and (fname in expected or expected in fname):
            return content, is_broken_md(content)

    return None, False


def process_npc_entries(md_index: dict) -> list[dict]:
    """Process npc_metadata.json entries."""
    if not NPC_META.exists():
        print(f"  WARNING: npc_metadata.json not found at {NPC_META}")
        return []

    with open(NPC_META, encoding='utf-8') as f:
        raw = json.load(f)

    results = []
    for item in raw:
        if item.get("error"):
            # Skip entries with fetch errors (e.g., timeout)
            continue

        title = item.get("title", item.get("keyword", ""))
        cat_key = item.get("category", "")
        full_text, is_broken = match_md(title, cat_key, md_index)

        preview = full_text[:200] if full_text and not is_broken else ""

        results.append({
            "id": hashlib.md5(title.encode()).hexdigest()[:12],
            "title": title,
            "authority": item.get("authority") or "",
            "publish_date": normalize_date(item.get("publish_date")),
            "effective_date": normalize_date(item.get("effective_date")),
            "status_str": item.get("status_str", ""),
            "level": item.get("level", ""),
            "categories": [cat_key],
            "category_display": [CATEGORY_CONFIG.get(cat_key, {}).get("display", cat_key)],
            "source": "npc",
            "bbbs": item.get("bbbs"),
            "full_text": full_text or "",
            "full_text_preview": preview,
            "full_text_error": is_broken,
            "has_full_text": bool(full_text and not is_broken),
            "note": item.get("note") or "",
        })
    return results


def process_csrc_entries(md_index: dict) -> list[dict]:
    """Process csrc_metadata.json entries."""
    if not CSRC_META.exists():
        print(f"  WARNING: csrc_metadata.json not found at {CSRC_META}")
        return []

    with open(CSRC_META, encoding='utf-8') as f:
        raw = json.load(f)

    # Keywords -> category mapping for CSRC entries
    # Order matters: more specific categories first
    CSRC_CAT_KEYWORDS = {
        "量化交易": ["程序化", "量化"],
        "基金运作": ["私募", "基金", "信托"],
        "反洗钱": ["反洗钱", "受益所有人", "尽职调查", "可疑交易"],
        "广告竞争": ["广告", "营销", "互联网"],
        "证券交易": ["证券", "期货", "股票", "监管措施", "行政处罚"],
        "跨境": ["境外", "跨境", "QDII", "外汇"],
        "税务": ["税", "增值税", "所得"],
    }

    results = []
    for item in raw:
        name = item.get("name", "")
        full_text = item.get("text_full", "") or ""

        # Determine category from keywords in name
        cat_key = "证券交易"  # default for CSRC
        found_cat = None
        for candidate, keywords in CSRC_CAT_KEYWORDS.items():
            for kw in keywords:
                if kw in name:
                    found_cat = candidate
                    break
            if found_cat:
                break
        if found_cat:
            cat_key = found_cat

        # Try to find .md file if text_full is empty/same as preview
        if not full_text or full_text == item.get("text_preview", ""):
            # Try matching in the detected category first, then others
            search_order = [cat_key] + [c for c in CSRC_CAT_KEYWORDS if c != cat_key]
            for ck in search_order:
                found, is_broken = match_md(name, ck, md_index)
                if found and not is_broken:
                    full_text = found
                    break

        preview = full_text[:200] if full_text else ""
        display = CATEGORY_CONFIG.get(cat_key, {}).get("display", cat_key)

        results.append({
            "id": hashlib.md5(name.encode()).hexdigest()[:12],
            "title": name,
            "authority": item.get("fileno", ""),
            "publish_date": normalize_date(item.get("publish_date")),
            "effective_date": None,
            "status_str": "现行有效",
            "level": "部门规章",
            "categories": [cat_key],
            "category_display": [display],
            "source": "csrc",
            "bbbs": None,
            "full_text": full_text,
            "full_text_preview": preview,
            "full_text_error": False,
            "has_full_text": bool(full_text),
            "note": "",
        })
    return results


def find_orphan_md_files(md_index: dict, matched_titles: set) -> list[dict]:
    """Find .md files that don't match any metadata entry."""
    orphans = []
    for dir_name, files in md_index.items():
        for fname, content in files.items():
            if fname in matched_titles:
                continue
            # Check if any matched title's safe name matches this
            title = fname.replace('.md', '')
            matched_titles.add(fname)

            broken = is_broken_md(content)
            preview = content[:200] if content and not broken else ""

            # Find category key from dir name
            cat_key = dir_name
            for k, v in CATEGORY_CONFIG.items():
                if v["dir"] == dir_name:
                    cat_key = k
                    break

            orphans.append({
                "id": hashlib.md5(title.encode()).hexdigest()[:12],
                "title": title,
                "authority": "",
                "publish_date": None,
                "effective_date": None,
                "status_str": "",
                "level": "",
                "categories": [cat_key],
                "category_display": [CATEGORY_CONFIG.get(cat_key, {}).get("display", dir_name)],
                "source": "file",
                "bbbs": None,
                "full_text": content or "",
                "full_text_preview": preview,
                "full_text_error": broken,
                "has_full_text": bool(content and not broken),
                "note": "自动从文件导入，无对应元数据",
            })
    return orphans


def deduplicate(entries: list[dict]) -> list[dict]:
    """Deduplicate by id, merging categories for duplicates."""
    seen = {}
    for entry in entries:
        eid = entry["id"]
        if eid in seen:
            # Merge categories
            existing = seen[eid]
            for cat in entry["categories"]:
                if cat not in existing["categories"]:
                    existing["categories"].append(cat)
            for cd in entry["category_display"]:
                if cd not in existing["category_display"]:
                    existing["category_display"].append(cd)
            # Keep the better full_text
            if not existing["has_full_text"] and entry["has_full_text"]:
                existing["full_text"] = entry["full_text"]
                existing["full_text_preview"] = entry["full_text_preview"]
                existing["has_full_text"] = True
                existing["full_text_error"] = False
        else:
            seen[eid] = entry

    return list(seen.values())


def sort_entries(entries: list[dict]) -> list[dict]:
    """Sort by level order, then by publish_date descending."""
    def sort_key(e):
        lvl = LEVEL_ORDER.get(e.get("level", ""), 99)
        pub = e.get("publish_date") or "0000-00-00"
        return (lvl, pub)
    return sorted(entries, key=sort_key)


def main():
    print("Building laws.json ...\n")

    # 1. Load .md index
    print("1. Loading full-text .md files...")
    md_index = load_md_index(MD_ROOT)
    total_md = sum(len(v) for v in md_index.values())
    print(f"   Found {total_md} .md files in {len(md_index)} directories")

    # 2. Process NPC metadata
    print("\n2. Processing NPC metadata...")
    npc_entries = process_npc_entries(md_index)
    print(f"   {len(npc_entries)} entries from NPC")

    # 3. Process CSRC metadata
    print("\n3. Processing CSRC metadata...")
    csrc_entries = process_csrc_entries(md_index)
    print(f"   {len(csrc_entries)} entries from CSRC")

    # 4. Track matched titles
    matched_titles = set()
    for e in npc_entries + csrc_entries:
        matched_titles.add(safe_filename(e["title"]))

    # 5. Find orphan .md files
    print("\n4. Finding orphan .md files...")
    orphan_entries = find_orphan_md_files(md_index, matched_titles)
    print(f"   {len(orphan_entries)} orphan entries")

    # 6. Merge & deduplicate
    all_entries = npc_entries + csrc_entries + orphan_entries
    all_entries = deduplicate(all_entries)
    all_entries = sort_entries(all_entries)

    # 7. Stats
    print(f"\n5. Final stats:")
    print(f"   Total unique entries: {len(all_entries)}")
    has_text = sum(1 for e in all_entries if e["has_full_text"])
    print(f"   With full text: {has_text}")
    broken = sum(1 for e in all_entries if e["full_text_error"])
    print(f"   Broken files: {broken}")
    no_text = sum(1 for e in all_entries if not e["has_full_text"] and not e["full_text_error"])
    print(f"   Missing text: {no_text}")

    # Category breakdown
    from collections import Counter
    cat_counts = Counter()
    for e in all_entries:
        for cat in e["categories"]:
            cat_counts[cat] += 1
    print("\n   By category:")
    for cat, n in cat_counts.most_common():
        display = CATEGORY_CONFIG.get(cat, {}).get("display", cat)
        print(f"     {display}: {n}")

    # 8. Write output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_entries, f, ensure_ascii=False, indent=2)

    size_kb = os.path.getsize(OUTPUT_FILE) / 1024
    print(f"\n6. Output: {OUTPUT_FILE}")
    print(f"   Size: {size_kb:.1f} KB")
    print("\nDone!")


if __name__ == "__main__":
    main()
