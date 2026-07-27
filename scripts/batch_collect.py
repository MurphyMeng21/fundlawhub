#!/usr/bin/env python3
"""
批量采集脚本：用多个关键词搜索 NPC 数据库，合并去重，输出 raw JSON。
用于 cn-law-hub → Obsidian 法规汇编工作流。

用法：
  python scripts/batch_collect.py --domain 劳动 --keywords "劳动,社会保险,工伤保险,工资"
  python scripts/batch_collect.py --domain 税务 --keywords "税收,税务,所得税,增值税"
"""

import argparse
import json
import sys
import os
import subprocess
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_PY = os.path.join(SCRIPT_DIR, "download.py")
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(SCRIPT_DIR)),
    "obsidian", "01-法务知识库", "合规研究", "_data"
)


def search_keyword(keyword: str, size: int = 200, search_range: str = "title", timeout: int = 300) -> list:
    """Run download.py --search and return list of results.

    Args:
        keyword: Search keyword
        size: Max results per search
        search_range: "title" (default, more precise) or "content" (broader, more noise)
        timeout: Subprocess timeout in seconds
    """
    cmd = [
        sys.executable, DOWNLOAD_PY,
        "--search", keyword,
        "--status", "3",
        "--size", str(size),
        "--urls-only",
        "--rate-limit", "fixed",
    ]
    if search_range == "content":
        cmd.insert(cmd.index("--size") - 1, "--range")
        cmd.insert(cmd.index("--size") - 1, "content")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=SCRIPT_DIR)
        stdout = result.stdout.strip()
        if not stdout:
            return []
        data = json.loads(stdout)
        if isinstance(data, list):
            return data
        return []
    except (json.JSONDecodeError, subprocess.TimeoutExpired) as e:
        print(f"  ⚠️ 关键词 '{keyword}' 搜索失败: {e}", file=sys.stderr)
        return []


def collect_domain(domain: str, keywords: list[str], content_keywords: list[str] = None) -> list:
    """Search multiple keywords, merge and deduplicate by bbbs_id.

    Args:
        domain: Domain name
        keywords: Title-search keywords (precise)
        content_keywords: Content-search keywords (broader, for domains where
                          relevant laws may not have keyword in title)
    """
    seen = {}
    total_found = 0
    content_keywords = content_keywords or []

    for kw in keywords:
        print(f"  🔍 标题: '{kw}' ...", end=" ", flush=True)
        results = search_keyword(kw, search_range="title")
        new_count = 0
        for item in results:
            bbbs = item.get("bbbs")
            if bbbs and bbbs not in seen:
                seen[bbbs] = item
                new_count += 1
        total_found += len(results)
        print(f"返回 {len(results)} 条, 新增 {new_count} 条")
        if kw != keywords[-1]:
            time.sleep(1)  # gentle delay between keywords

    for kw in content_keywords:
        print(f"  🔍 正文: '{kw}' ...", end=" ", flush=True)
        results = search_keyword(kw, search_range="content")
        new_count = 0
        for item in results:
            bbbs = item.get("bbbs")
            if bbbs and bbbs not in seen:
                seen[bbbs] = item
                new_count += 1
        total_found += len(results)
        print(f"返回 {len(results)} 条, 新增 {new_count} 条")
        if kw != content_keywords[-1]:
            time.sleep(2)

    merged = list(seen.values())
    print(f"  ✅ {domain}: 合并去重后共 {len(merged)} 部法规 (原始 {total_found} 条)")
    return merged


def main():
    parser = argparse.ArgumentParser(description="批量采集法规数据")
    parser.add_argument("--domain", required=True, help="领域名称，如 劳动、税务")
    parser.add_argument("--keywords", required=True, help="逗号分隔的标题关键词列表")
    parser.add_argument("--content-keywords", default="", help="逗号分隔的正文关键词列表（用于发现标题不含关键词的相关法规）")
    parser.add_argument("--output-dir", default=DATA_DIR, help="输出目录")
    args = parser.parse_args()

    keywords = [kw.strip() for kw in args.keywords.split(",") if kw.strip()]
    content_keywords = [kw.strip() for kw in args.content_keywords.split(",") if kw.strip()]
    print(f"\n📋 领域: {args.domain}")
    print(f"🔑 标题关键词: {', '.join(keywords)}")
    if content_keywords:
        print(f"🔍 正文关键词: {', '.join(content_keywords)}")
    print()

    results = collect_domain(args.domain, keywords, content_keywords)

    # Save
    os.makedirs(args.output_dir, exist_ok=True)
    output_path = os.path.join(args.output_dir, f"{args.domain}_raw.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n💾 已保存: {output_path}")
    print(f"📊 共 {len(results)} 部现行有效法规")


if __name__ == "__main__":
    main()
