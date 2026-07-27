#!/usr/bin/env python3
"""从 npc_metadata.json 按板块生成 Obsidian Markdown 法规汇编。"""

import json
import os

# cn-law-hub/scripts → workspace/ → for_claude/ → for_claude/obsidian/
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE, "obsidian", "01-法务知识库", "合规研究", "_data")
OUTPUT_DIR = os.path.join(BASE, "obsidian", "01-法务知识库", "合规研究")

SECTION_NAMES = {
    "基金运作": "基金运作与监管",
    "证券交易": "证券交易合规",
    "反洗钱": "反洗钱与CRS",
    "广告竞争": "广告与市场竞争",
    "税务": "税务",
    "劳动": "劳动人事",
    "跨境": "跨境业务",
    "基础法律": "基础法律与知识产权",
}

LEVEL_ORDER = {"法律": 0, "行政法规": 1, "司法解释": 2}


def generate():
    with open(os.path.join(DATA_DIR, "npc_metadata.json"), encoding="utf-8") as f:
        data = json.load(f)

    # 分组
    sections = {}
    for item in data:
        if item.get("error"):
            continue
        cat = item["category"]
        if cat not in sections:
            sections[cat] = []
        sections[cat].append(item)

    # 每个板块内排序：法律 > 行政法规 > 司法解释
    for items in sections.values():
        items.sort(key=lambda x: (LEVEL_ORDER.get(x.get("level"), 9),
                                   x.get("publish_date") or ""))

    index_lines = [
        "# 法规汇编总索引",
        "",
        f"> 更新日期：2026-07-01",
        "> 数据来源：国家法律法规数据库 (flk.npc.gov.cn) Phase 1 精确采集",
        "",
    ]

    # 生成各板块文档
    for cat_key, cat_name in SECTION_NAMES.items():
        items = sections.get(cat_key, [])
        if not items:
            continue

        filename = f"{cat_name}.md"
        filepath = os.path.join(OUTPUT_DIR, filename)

        lines = [
            f"# {cat_name}",
            "",
            f"> 自动采集日期：2026-07-01",
            f"> 来源：国家法律法规数据库 (flk.npc.gov.cn)",
            f"> 状态：仅收录现行有效版本",
            "",
            f"共收录 **{len(items)}** 部现行有效法规。",
            "",
        ]

        # 统计分类
        from collections import Counter
        lvl_count = Counter(i.get("level", "?") for i in items)
        lines.append("## 📊 层级分布")
        lines.append("")
        for lvl in ["法律", "行政法规", "司法解释"]:
            if lvl in lvl_count:
                lines.append(f"- **{lvl}**：{lvl_count[lvl]} 部")
        lines.append("")

        # 法规列表
        lines.append("## 📖 法规列表")
        lines.append("")

        current_level = None
        for item in items:
            lvl = item.get("level", "")
            if lvl != current_level:
                current_level = lvl
                lines.append(f"### {lvl}")
                lines.append("")

            title = item.get("title", item.get("keyword", "?"))
            authority = item.get("authority") or "—"
            pub_date = item.get("publish_date") or "—"
            eff_date = item.get("effective_date") or "—"
            status = item.get("status_str", "?")

            lines.append(f"**{title}**")
            lines.append(f"- 发布机构：{authority}")
            lines.append(f"- 发布日期：{pub_date} | 施行日期：{eff_date}")
            lines.append(f"- 状态：{status}")
            lines.append("")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        print(f"✅ {filename} ({len(items)} 部)")

        # 总索引条目
        index_lines.append(f"## {cat_name}")
        index_lines.append("")
        for item in items:
            title = item.get("title", item.get("keyword", "?"))
            authority = item.get("authority") or "—"
            pub_date = item.get("publish_date") or "—"
            lvl = item.get("level", "")
            index_lines.append(f"- **{title}**")
            index_lines.append(f"  - [{lvl}] {authority} | {pub_date}")
        index_lines.append("")

    # 写总索引
    index_path = os.path.join(OUTPUT_DIR, "法规汇编总索引.md")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("\n".join(index_lines))

    print(f"\n✅ 法规汇编总索引.md")
    print(f"📂 输出目录: {OUTPUT_DIR}")


if __name__ == "__main__":
    generate()
