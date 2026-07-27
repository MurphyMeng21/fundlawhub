#!/usr/bin/env python3
"""
Phase 1 批量采集：只取元数据，不拿下载 URL。
直接调 NPC 搜索 API，翻页拿满，按 bbbs 去重。

策略来自 references/batch_collection.md Phase 1。
用法：
  python scripts/phase1_collect.py --domain 劳动 --keywords "劳动合同,劳动争议,社会保险"
  python scripts/phase1_collect.py --domain 私募基金 --keywords "私募" --content-keywords "私募"
"""

import argparse
import json
import os
import re
import sys
import time
from collections import Counter

import requests
import urllib3

urllib3.disable_warnings()

BASE_URL = "https://flk.npc.gov.cn"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://flk.npc.gov.cn/search",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
}

STATUS_MAP = {1: "已废止", 2: "已修改", 3: "现行有效", 4: "尚未生效"}

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "obsidian", "01-法务知识库", "合规研究", "_data"
)


def search_api(keyword, page=1, size=100, search_range=1, search_type=2,
               status_filter=None):
    """调 NPC 搜索 API，返回 (total, rows)。"""
    payload = {
        "searchRange": search_range,
        "searchType": search_type,
        "searchContent": keyword,
        "pageNum": page,
        "pageSize": size,
        "orderByParam": {"order": "-1", "sort": ""},
        "flfgCodeId": [], "zdjgCodeId": [],
        "sxx": status_filter or [],
        "gbrq": [], "sxrq": [], "gbrqYear": [],
        "xgzlSearch": False,
    }
    resp = requests.post(f"{BASE_URL}/law-search/search/list",
                         headers=HEADERS, json=payload,
                         verify=False, timeout=30)
    data = resp.json()
    if data.get("code") != 200:
        raise RuntimeError(f"API error: {data.get('msg')}")
    return data.get("total", 0), data.get("rows", [])


def collect_by_keyword(keyword, search_range=1, search_type=2,
                       status_filter=None, max_results=500):
    """翻页采集一个关键词的全部结果（纯元数据，无下载 URL）。"""
    items = []
    page = 1
    while True:
        total, rows = search_api(keyword, page=page, size=100,
                                 search_range=search_range,
                                 search_type=search_type,
                                 status_filter=status_filter)
        for row in rows:
            items.append({
                "bbbs": row.get("bbbs"),
                "title": re.sub(r"<[^>]+>", "", row.get("title", "")),
                "category": row.get("flxz"),
                "authority": row.get("zdjgName"),
                "publish_date": row.get("gbrq"),
                "effective_date": row.get("sxrq"),
                "status_code": row.get("sxx"),
                "status_str": STATUS_MAP.get(row.get("sxx", 0), "未知"),
            })
        if len(items) >= total or not rows or len(items) >= max_results:
            break
        page += 1
        time.sleep(0.3)
    return items


def run(domain, keywords, content_keywords=None):
    """多关键词采集 + bbbs 去重合并。"""
    seen = {}
    content_keywords = content_keywords or []

    for kw in keywords:
        print(f"  🔍 标题: '{kw}' ...", end=" ", flush=True)
        try:
            results = collect_by_keyword(kw, search_range=1, search_type=2,
                                         status_filter=[3])
            new = sum(1 for r in results if r["bbbs"] and r["bbbs"] not in seen)
            for r in results:
                if r["bbbs"] and r["bbbs"] not in seen:
                    seen[r["bbbs"]] = r
            print(f"{len(results)}条, +{new}")
        except Exception as e:
            print(f"⚠️ {e}")
        if kw != keywords[-1]:
            time.sleep(1)

    for kw in content_keywords:
        print(f"  🔍 正文: '{kw}' ...", end=" ", flush=True)
        try:
            results = collect_by_keyword(kw, search_range=2, search_type=2,
                                         status_filter=[3])
            new = sum(1 for r in results if r["bbbs"] and r["bbbs"] not in seen)
            for r in results:
                if r["bbbs"] and r["bbbs"] not in seen:
                    seen[r["bbbs"]] = r
            print(f"{len(results)}条, +{new}")
        except Exception as e:
            print(f"⚠️ {e}")
        if kw != content_keywords[-1]:
            time.sleep(2)

    merged = list(seen.values())
    # 排序：法律 > 行政法规 > 司法解释 > 其他
    cat_order = {"法律": 0, "行政法规": 1, "司法解释": 2, "监察法规": 3,
                 "法规性决定": 4, "地方法规": 5}
    merged.sort(key=lambda x: (cat_order.get(x.get("category"), 9),
                                x.get("publish_date") or ""),
                reverse=False)
    # 然后按发布日期降序（同类别内新的在前）
    merged.sort(key=lambda x: (cat_order.get(x.get("category"), 9),
                                -(int((x.get("publish_date") or "0")[:4]))))
    return merged


def main():
    p = argparse.ArgumentParser(description="Phase 1: 法规元数据采集（无下载URL）")
    p.add_argument("--domain", required=True, help="领域名称")
    p.add_argument("--keywords", required=True, help="标题关键词，逗号分隔")
    p.add_argument("--content-keywords", default="",
                   help="正文关键词，逗号分隔")
    p.add_argument("--output-dir", default=DATA_DIR)
    args = p.parse_args()

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    ck = [k.strip() for k in args.content_keywords.split(",") if k.strip()]

    print(f"\n📋 {args.domain}")
    print(f"🔑 标题: {', '.join(keywords)}")
    if ck:
        print(f"🔍 正文: {', '.join(ck)}")
    print()

    results = run(args.domain, keywords, ck)

    os.makedirs(args.output_dir, exist_ok=True)
    path = os.path.join(args.output_dir, f"{args.domain}_raw.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    cats = Counter(r.get("category", "?") for r in results)
    print(f"\n✅ {args.domain}: {len(results)} 部 | {dict(cats)}")
    print(f"💾 {path}")


if __name__ == "__main__":
    main()
