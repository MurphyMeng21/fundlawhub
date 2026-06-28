#!/usr/bin/env python3
"""
Search for specific articles across laws by keyword.

Usage:
  # Search across laws whose titles contain keyword
  python article_search.py "违约金" --max-laws 5 --context 1

  # Search across laws whose full text contains keyword
  python article_search.py "违约金" --range content --max-laws 5

  # Search within a specific law
  python article_search.py "善意取得" --law "民法典" --context 0

  # JSON output for further processing
  python article_search.py "违约金" --max-laws 3 --json

  # Only currently effective laws
  python article_search.py "抵押权" --status 3 --max-laws 10

  # Progressive batch retrieval
  python article_search.py "违约金" --range content --max-laws 5        # batch 1
  python article_search.py "违约金" --range content --max-laws 5 --offset 5
  python article_search.py "违约金" --range content --max-laws 5 --resume
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from download import (
    search_laws, get_download_url, _request, _cache,
    _extract_paragraphs_from_docx, _split_into_articles,
    _is_article_line, sxx_to_str,
)


def search_articles(keyword: str, law_keyword: str = None,
                    search_range: int = 1, max_laws: int = 5,
                    offset: int = 0, resume: bool = False,
                    context: int = 0, status_filter: list = None,
                    json_output: bool = False):
    """Search for keyword across articles of multiple laws."""
    if law_keyword is None:
        law_keyword = keyword

    print(f"Step 1/3: Searching for laws containing '{law_keyword}' "
          f"({'title' if search_range == 1 else 'full text'})...",
          file=sys.stderr)

    fetch_size = max(max_laws * 2, offset + max_laws + 5)
    search_data = search_laws(law_keyword, size=fetch_size,
                               search_range=search_range, search_type=2,
                               status_filter=status_filter)

    if search_data.get("code") != 200:
        print(f"Search failed: {search_data.get('msg')}", file=sys.stderr)
        return []

    all_rows = search_data.get("rows", [])
    total_found = search_data.get("total", 0)

    if offset > 0:
        all_rows = all_rows[offset:]
        print(f"  Found {total_found} laws, skipping first {offset}, "
              f"processing laws {offset}-{offset + max_laws - 1}...",
              file=sys.stderr)
    else:
        print(f"  Found {total_found} laws, processing laws 0-{max_laws - 1}...",
              file=sys.stderr)

    all_matches = []
    processed = 0
    skipped_resume = 0
    skipped_offset = offset

    for row in all_rows:
        if processed >= max_laws:
            break

        bbbs = row.get("bbbs")
        title = re.sub(r"<[^>]+>", "", row.get("title", ""))
        status_code = row.get("sxx", 0)

        if resume:
            docx_key = _cache._key("docx", bbbs)
            if _cache.get_file(docx_key) is not None:
                skipped_resume += 1
                skipped_offset += 1
                continue

        print(f"Step 2/3: [{processed+1}/{max_laws}] {title[:50]}...",
              end=" ", file=sys.stderr, flush=True)

        docx_key = _cache._key("docx", bbbs)
        docx_bytes = _cache.get_file(docx_key)

        if docx_bytes is None:
            try:
                url = get_download_url(bbbs, "docx")
                resp = _request("GET", url)
                docx_bytes = resp.content
                _cache.set_file(docx_key, docx_bytes)
            except Exception as e:
                print(f"SKIP (download: {e})", file=sys.stderr)
                skipped_offset += 1
                continue

        try:
            paragraphs = _extract_paragraphs_from_docx(docx_bytes)
            articles = _split_into_articles(paragraphs)

            matched_indices = set()
            for i, (num, text) in enumerate(articles):
                if keyword in text:
                    for ctx in range(max(0, i - context), min(len(articles), i + context + 1)):
                        matched_indices.add(ctx)

            if matched_indices:
                sorted_indices = sorted(matched_indices)
                law_matches = []
                for idx in sorted_indices:
                    num, text = articles[idx]
                    law_matches.append({
                        "article_num": num,
                        "text": text,
                        "is_match": keyword in text,
                    })

                all_matches.append({
                    "title": title,
                    "bbbs": bbbs,
                    "status_str": sxx_to_str(status_code),
                    "status_code": status_code,
                    "total_articles": len(articles),
                    "matched_articles": len([m for m in law_matches if m["is_match"]]),
                    "articles": law_matches,
                })
                print(f"FOUND {len([m for m in law_matches if m['is_match']])} matches",
                      file=sys.stderr)
            else:
                print("no match", file=sys.stderr)

            processed += 1

        except Exception as e:
            print(f"SKIP (parse: {e})", file=sys.stderr)
            skipped_offset += 1

    next_offset = skipped_offset + processed
    has_more = next_offset < total_found

    print(f"\nStep 3/3: Done. {len(all_matches)} laws with matches. "
          f"Processed: {processed}, Total available: {total_found}",
          file=sys.stderr)

    if resume and skipped_resume > 0:
        print(f"  Resume: skipped {skipped_resume} already-cached laws",
              file=sys.stderr)

    if json_output:
        output = {
            "keyword": keyword,
            "laws_with_matches": all_matches,
            "batch_info": {
                "total_found": total_found,
                "this_batch_offset": offset,
                "this_batch_processed": processed,
                "next_offset": next_offset if has_more else None,
                "has_more": has_more,
            },
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        _print_human_readable(all_matches, keyword, context)
        if has_more:
            print(f"\n{'─' * 70}")
            print(f"已处理: {next_offset}/{total_found} 部法规")
            print(f"继续检索: python article_search.py '{keyword}' ", end="")
            if search_range == 2:
                print("--range content ", end="")
            print(f"--max-laws {max_laws} --offset {next_offset}")
            if max_laws < 10:
                print(f"或扩大批次: --max-laws 10 --offset {offset}")

    return all_matches


def _print_human_readable(results: list, keyword: str, context: int):
    """Print results in human-readable format."""
    total_laws = len(results)
    total_articles = sum(l["matched_articles"] for l in results)

    print(f"\n{'=' * 70}")
    print(f"\n关键词: '{keyword}' | 命中法规: {total_laws}部 | 命中法条: {total_articles}条")
    print(f"{'=' * 70}")

    for law in results:
        print(f"\n{'─' * 70}")
        print(f"【{law['title']}】{law['status_str']} | 共{law['total_articles']}条")

        for art in law["articles"]:
            if art["is_match"]:
                print(f"\n  >> {art['article_num']} [匹配]")
            else:
                print(f"\n  >> {art['article_num']} [上下文]")

            text = art["text"]
            lines = text.split("\n")
            for line in lines[:5]:
                if keyword in line:
                    highlighted = line.replace(keyword, f"**{keyword}**")
                    print(f"    {highlighted[:120]}")
                else:
                    print(f"    {line[:120]}")
            if len(lines) > 5:
                print(f"    ... ({len(lines) - 5} more lines)")


def main():
    parser = argparse.ArgumentParser(
        description="Search for specific articles across laws by keyword.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("keyword", help="Keyword to search within articles")
    parser.add_argument("--law", metavar="KEYWORD", help="Keyword to find candidate laws (default: same as keyword)")
    parser.add_argument("--range", choices=["title", "content"], default="title",
                        help="Search range for finding laws: title (default) or content")
    parser.add_argument("--max-laws", type=int, default=5,
                        help="Max laws to download and parse per batch (default: 5)")
    parser.add_argument("--offset", type=int, default=0,
                        help="Skip first N laws (for progressive batch retrieval)")
    parser.add_argument("--resume", action="store_true",
                        help="Skip laws whose DOCX is already in cache")
    parser.add_argument("--context", type=int, default=0,
                        help="Number of surrounding articles to include (default: 0)")
    parser.add_argument("--status", help="Filter by status: 1=已废止,2=已修改,3=现行有效,4=尚未生效")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text")
    parser.add_argument("--no-cache", action="store_true", help="Disable cache")

    args = parser.parse_args()

    if args.no_cache:
        from download import _CacheManager
        global _cache
        _cache = _CacheManager(enabled=False)

    status_filter = None
    if args.status:
        status_filter = [int(s.strip()) for s in args.status.split(",")]

    search_range = 2 if args.range == "content" else 1

    search_articles(
        keyword=args.keyword,
        law_keyword=args.law,
        search_range=search_range,
        max_laws=args.max_laws,
        offset=args.offset,
        resume=args.resume,
        context=args.context,
        status_filter=status_filter,
        json_output=args.json,
    )


if __name__ == "__main__":
    main()
