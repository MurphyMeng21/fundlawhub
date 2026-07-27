#!/usr/bin/env python3
"""
Phase 1 精确版：按法规名称精确搜索 NPC 数据库，获取元数据。
输出: 发布机构 / 发布日期 / 生效日期 / 状态 / bbbs_id

用法：
  python scripts/phase1_exact.py
  （读取法规清单中的 NPC 条目，逐一精确匹配）
"""

import json
import os
import re
import sys
import time

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

# cn-law-hub/scripts → workspace/ → for_claude/ → for_claude/obsidian/
FCLAUDE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.join(FCLAUDE, "obsidian", "01-法务知识库", "合规研究", "_data")

# 法规清单：(搜索关键词, 所属板块, 层级)
TARGETS = [
    # 一、基金运作
    ("证券投资基金法", "基金运作", "法律"),
    ("信托法", "基金运作", "法律"),
    ("公司法", "基金运作", "法律"),
    ("合伙企业法", "基金运作", "法律"),
    ("私募投资基金监督管理条例", "基金运作", "行政法规"),
    # 公司法司法解释
    ("最高人民法院关于适用《中华人民共和国公司法》若干问题的规定（二）", "基金运作", "司法解释"),
    ("最高人民法院关于适用《中华人民共和国公司法》若干问题的规定（三）", "基金运作", "司法解释"),
    ("最高人民法院关于适用《中华人民共和国公司法》若干问题的规定（四）", "基金运作", "司法解释"),
    ("最高人民法院关于适用《中华人民共和国公司法》若干问题的规定（五）", "基金运作", "司法解释"),
    ("最高人民法院关于适用《中华人民共和国公司法》时间效力的若干规定", "基金运作", "司法解释"),
    # 二、证券交易合规
    ("证券法", "证券交易", "法律"),
    ("期货和衍生品法", "证券交易", "法律"),
    ("刑法", "证券交易", "法律"),
    ("反洗钱法", "证券交易", "法律"),
    ("期货交易管理条例", "证券交易", "行政法规"),
    ("股票发行与交易管理暂行条例", "证券交易", "行政法规"),
    ("关于严格公正执法司法服务保障资本市场高质量发展的指导意见", "证券交易", "司法解释"),
    ("最高人民法院关于审理证券市场虚假陈述侵权民事赔偿案件的若干规定", "证券交易", "司法解释"),
    # 三、反洗钱
    ("反洗钱法", "反洗钱", "法律"),
    # 四、广告与竞争
    ("广告法", "广告竞争", "法律"),
    ("反不正当竞争法", "广告竞争", "法律"),
    # 七、税务
    ("企业所得税法", "税务", "法律"),
    ("个人所得税法", "税务", "法律"),
    ("增值税法", "税务", "法律"),
    ("印花税法", "税务", "法律"),
    ("税收征收管理法", "税务", "法律"),
    ("企业所得税法实施条例", "税务", "行政法规"),
    ("个人所得税法实施条例", "税务", "行政法规"),
    ("增值税暂行条例", "税务", "行政法规"),
    # 八、劳动人事
    ("劳动法", "劳动", "法律"),
    ("劳动合同法", "劳动", "法律"),
    ("社会保险法", "劳动", "法律"),
    ("劳动争议调解仲裁法", "劳动", "法律"),
    ("劳动合同法实施条例", "劳动", "行政法规"),
    ("工伤保险条例", "劳动", "行政法规"),
    ("失业保险条例", "劳动", "行政法规"),
    ("住房公积金管理条例", "劳动", "行政法规"),
    ("职工带薪年休假条例", "劳动", "行政法规"),
    ("女职工劳动保护特别规定", "劳动", "行政法规"),
    ("最高人民法院关于审理劳动争议案件适用法律问题的解释（一）", "劳动", "司法解释"),
    ("最高人民法院关于审理劳动争议案件适用法律问题的解释（二）", "劳动", "司法解释"),
    # 九、跨境
    ("外汇管理条例", "跨境", "行政法规"),
    # 十、基础法律/知识产权
    ("民法典", "基础法律", "法律"),
    ("行政处罚法", "基础法律", "法律"),
    ("个人信息保护法", "基础法律", "法律"),
    ("著作权法", "基础法律", "法律"),
    ("商标法", "基础法律", "法律"),
    ("专利法", "基础法律", "法律"),
    ("最高人民法院关于适用《中华人民共和国民法典》有关担保制度的解释", "基础法律", "司法解释"),
]


def search_exact(keyword):
    """精确搜索，返回最佳匹配。"""
    payload = {
        "searchRange": 1,       # 标题
        "searchType": 1,        # 精确
        "searchContent": keyword,
        "pageNum": 1,
        "pageSize": 5,
        "orderByParam": {"order": "-1", "sort": ""},
        "flfgCodeId": [], "zdjgCodeId": [],
        "sxx": [], "gbrq": [], "sxrq": [], "gbrqYear": [],
        "xgzlSearch": False,
    }
    resp = requests.post(f"{BASE_URL}/law-search/search/list",
                         headers=HEADERS, json=payload,
                         verify=False, timeout=10)
    data = resp.json()
    if data.get("code") != 200:
        return None
    rows = data.get("rows", [])
    if not rows:
        return None
    # 选 sxx=3（现行有效）优先，否则取第一条
    for row in rows:
        if row.get("sxx") == 3:
            return row
    return rows[0]


def main():
    results = []
    found = 0
    missing = 0

    print(f"共 {len(TARGETS)} 部法规\n")

    for keyword, category, level in TARGETS:
        print(f"  🔍 [{category}] {keyword[:50]} ...", end=" ", flush=True)
        try:
            row = search_exact(keyword)
            if row:
                title = re.sub(r"<[^>]+>", "", row.get("title", ""))
                item = {
                    "keyword": keyword,
                    "category": category,
                    "level": level,
                    "bbbs": row.get("bbbs"),
                    "title": title,
                    "authority": row.get("zdjgName"),           # 发布机构
                    "publish_date": row.get("gbrq"),             # 发布日期
                    "effective_date": row.get("sxrq"),           # 施行/生效日期
                    "status_code": row.get("sxx"),
                    "status_str": STATUS_MAP.get(row.get("sxx", 0), "未知"),
                    "flxz": row.get("flxz"),                     # 法规分类
                }
                results.append(item)
                found += 1
                print(f"✅ {item['status_str']} | {item['authority'] or '?'}")
            else:
                results.append({"keyword": keyword, "category": category, "level": level, "error": "未找到"})
                missing += 1
                print("❌ 未找到")
        except Exception as e:
            results.append({"keyword": keyword, "category": category, "level": level, "error": str(e)})
            missing += 1
            print(f"⚠️ {e}")
        time.sleep(0.4)

    # 保存
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, "npc_metadata.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"✅ 找到: {found} 部")
    print(f"❌ 未找到: {missing} 部")
    print(f"💾 已保存: {output_path}")

    # 按板块统计
    from collections import Counter
    by_cat = Counter(r["category"] for r in results if "error" not in r)
    print(f"\n📊 按板块: {dict(by_cat)}")


if __name__ == "__main__":
    main()
