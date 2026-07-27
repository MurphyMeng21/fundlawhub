#!/usr/bin/env python3
"""
批量筛选法规脚本 — 按领域自动检索国家法律法规数据库 + 国家规章库

限速说明：
  使用 NPC 官方 API 内置的限速器。自动根据任务大小选择模式：
  - ≤10 请求：不限速（快速小任务）
  - 11~100 请求：固定 5 req/s
  - >100 请求：自适应（1~8 req/s，遇 429 自动退避）

用法:
  # 先搜一个小领域测试
  python batch_fetch.py --domain 私募基金

  # 增加关键词匹配精度（先精确后模糊）
  python batch_fetch.py --domain 私募基金 --mode precise

  # 搜索所有 6 个领域（逐个确认）
  python batch_fetch.py --all

  # 强制使用限速模式
  python batch_fetch.py --domain 私募基金 --rate-limit adaptive

  # 下载全文 DOCX
  python batch_fetch.py --domain 私募基金 --download

  # 列出可用领域
  python batch_fetch.py --list
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (
    get_cache, sanitize_filename, init_limiter, _RateLimitMode,
    _SmartRateLimiter,
)
from download import (
    search_laws, fetch_detail, parse_detail,
    get_download_url, download_file,
)


# ============================================================
# 领域配置
# ============================================================

DOMAINS = {
    "证券期货": {
        "keywords": [
            "证券法",
            "期货",
            "期货交易",
            "证券交易所",
            "上市公司",
            "证券公司",
            "期货公司",
            "证券发行",
            "证券交易",
        ],
        "exact_titles": [  # 精确匹配确保核心法规必中
            "中华人民共和国证券法",
            "中华人民共和国期货和衍生品法",
            "证券公司监督管理条例",
            "上市公司监督管理条例",
        ],
    },
    "私募基金": {
        "keywords": [
            "私募投资基金",
            "私募股权",
            "创业投资基金",
            "基金募集",
            "基金管理人",
            "投资者适当性",
            "私募基金",
        ],
        "exact_titles": [
            "私募投资基金监督管理条例",
            "中华人民共和国证券投资基金法",
            "中华人民共和国证券法",
            "中华人民共和国公司法",
            "中华人民共和国合伙企业法",
            "中华人民共和国信托法",
        ],
    },
    "基金销售": {
        "keywords": [
            "基金销售",
            "基金托管",
            "公开募集证券投资基金",
        ],
        "exact_titles": [
            "公开募集证券投资基金销售机构监督管理办法",
            "公开募集证券投资基金信息披露管理办法",
            "公开募集证券投资基金运作管理办法",
        ],
    },
    "劳动": {
        "keywords": [
            "劳动法",
            "劳动合同",
            "劳动争议",
            "工伤保险",
            "失业保险",
            "劳务派遣",
            "工资支付",
        ],
        "exact_titles": [
            "中华人民共和国劳动法",
            "中华人民共和国劳动合同法",
            "中华人民共和国社会保险法",
            "中华人民共和国劳动争议调解仲裁法",
            "工伤保险条例",
            "失业保险条例",
            "中华人民共和国就业促进法",
            "劳动保障监察条例",
        ],
    },
    "税务": {
        "keywords": [
            "税收",
            "个人所得税",
            "企业所得税",
            "增值税",
            "消费税",
            "税收征收管理",
        ],
        "exact_titles": [
            "中华人民共和国个人所得税法",
            "中华人民共和国企业所得税法",
            "中华人民共和国税收征收管理法",
            "中华人民共和国增值税法",
        ],
    },
    "外汇管理": {
        "keywords": [
            "外汇管理",
            "结汇",
            "售汇",
            "汇率",
        ],
        "exact_titles": [
            "中华人民共和国外汇管理条例",
            "中华人民共和国人民币管理条例",
        ],
    },
}

# 不相关的标题过滤 — 按关键词匹配度排除噪音
# (keyword, pattern) 当标题匹配 pattern 时，如果标题不含 keyword 则排除
IRRELEVANT_PATTERNS = [
    # 通用 — 太宽泛的基础法律
    r"^中华人民共和国民法典",
    r"^中华人民共和国宪法",
    r"^中华人民共和国刑法",
    r"^中华人民共和国刑事诉讼法",
    r"^中华人民共和国行政诉讼法",
    r"^中华人民共和国立法法",
    r"^中华人民共和国行政许可法",
    r"^中华人民共和国行政处罚法",
    r"^中华人民共和国行政强制法",
    r"^中华人民共和国行政复议法",
    r"^中华人民共和国国家赔偿法",
    r"^中华人民共和国监察法",
    r"^中华人民共和国网络安全法",
    r"^中华人民共和国数据安全法",
    r"^中华人民共和国个人信息保护法",
    r"^中华人民共和国反不正当竞争法",
    r"^中华人民共和国反垄断法",
    r"^中华人民共和国对外关系法",
    r"^中华人民共和国国家安全法",
    r"^中华人民共和国反间谍法",
    r"^中华人民共和国国防法",
    r"^中华人民共和国保守国家秘密法",

    # 社保基金 ≠ 私募基金（"基金"这个词太宽泛）
    r"社会保险基金",
    r"医疗保障基金",
    r"自然科学基金",

    # 外商投资 ≠ 私募基金
    r"外商投资",
    r"外国投资",
    r"对外投资",
    r"农业投资",
    r"投资环境",

    # 其他领域的"基金"
    r"基金会",
    r"社会保障基金",
    r"失业保险基金",
    r"工伤保险基金",
    r"养老保险基金",

    # 税务噪音
    r"税务师",
    r"注册税务师",

    # 劳动噪音
    r"工会法",
    r"红十字会",

    # 通用噪音
    r"有线电视",
    r"社会救助",
    r"宁夏回族",
    r"梅州市",
    r"重庆市青年",
    r"广州市青年",
    r"厦门经济特区鼓励",
    r"四川省就业",
    r"企业投资项目核准",
    r"台湾同胞投资",
    r"工人等非监管",
    r"来厦创业",
    r"来穗创业",
    r"就业创业",
    r"青年创业",
    r"促进创业",
    r"创业促进",
    r"青年创新创业",
    r"创新创业",
    r"制定地方性法规条例",
    r"农村集体资产",
    r"放射性",
    r"枪支管理",
    r"疫苗管理",
    r"药品管理",
    r"农药管理",
    r"兽药",
    r"海域使用",
    r"土地管理法",
    r"城市房地产管理",
    r"治安管理处罚",
    r"出境入境管理",
    r"大型群众性",
    r"地震安全性",
    r"地图管理",
    r"直销管理",
    r"出版管理",
    r"营业性演出",
    r"企业国有资产",
    r"国有企业",
    r"行政事业性",
]

# 每个领域的额外排除规则
DOMAIN_EXCLUDES = {
    "证券期货": [
        "基金", "社保", "保险", "医疗",
    ],
    "私募基金": [
        "社会保险", "医疗保障", "自然科学基金",
        "外商投资", "农业投资", "投资环境",
        "有线电视", "社会救助",
        "政府投资", "创业",
        "储备金", "公积金", "住房",
        "医保", "医疗", "养老",
        "农村集体",
        "制定地方性法规",
        "放射性", "枪支", "疫苗", "药品", "农药", "兽药",
        "海域", "土地管理", "房地产",
        "治安管理处罚", "出境入境",
        "大型群众性", "地震", "地图",
        "直销", "出版", "营业性演出",
        "国有资产", "国有企业", "行政事业性",
        "大连区域性金融中心",  # 太笼统的区域性法规
        "天津市专业技术",
        "继续教育",
    ],
    "基金销售": [
        "私募",  # 非公开的放在基金销售里没用
        "社会保险", "医疗保障",
    ],
    "劳动": [
        "税务", "证券", "外汇",
    ],
    "税务": [
        "劳动", "社保", "证券", "外汇",
    ],
    "外汇管理": [
        "劳动", "社保", "证券",
    ],
}


def is_relevant(title: str, domain: str) -> bool:
    """检查标题是否与领域相关"""
    # 排除通用不相关
    for pattern in IRRELEVANT_PATTERNS:
        if re.search(pattern, title):
            return False

    # 排除领域特定不相关
    for exclude_word in DOMAIN_EXCLUDES.get(domain, []):
        if exclude_word in title:
            return False

    return True


# ============================================================
# 请求估算 & 限速初始化
# ============================================================

def estimate_requests(domains: list, size: int, download: bool) -> int:
    """估算总请求数，用于选择限速模式"""
    total = 0
    for domain in domains:
        if domain not in DOMAINS:
            continue
        cfg = DOMAINS[domain]
        # 每个精确标题搜索 = 1 次搜索 + 每次命中需要 detail
        total += len(cfg["exact_titles"]) * 2
        # 每个关键词搜索 = 1 次搜索 + 每次命中需要 detail（按 size 估算）
        keywords = [k for k in cfg["keywords"] if len(k) >= 2]
        total += len(keywords) * (1 + size // 2)
        # 下载
        if download:
            total += size * 2  # get_download_url + download_file
    return total


def setup_rate_limiter(domains: list, size: int = 30,
                       force_mode: str = None, download: bool = False):
    """初始化限速器"""
    estimated = estimate_requests(domains, size, download)
    limiter, forced = init_limiter("auto")

    if force_mode:
        mode_map = {
            "off": _RateLimitMode.OFF,
            "fixed": _RateLimitMode.FIXED,
            "adaptive": _RateLimitMode.ADAPTIVE,
        }
        forced = mode_map.get(force_mode)

    mode = limiter.init_for_task(estimated, forced_mode=forced)
    if mode != _RateLimitMode.OFF:
        print(f"  ⏱ 限速模式: {limiter.mode_desc()}"
              f" (预估 {estimated} 次请求)", file=sys.stderr)
    else:
        print(f"  ⏱ 不限速 (预估 {estimated} 次请求，小任务)", file=sys.stderr)
    return limiter, mode


# ============================================================
# NPC 数据库搜索
# ============================================================

def search_npc_domain(domain: str, status: list = None,
                      size: int = 30, mode: str = "normal") -> list:
    """在 NPC 数据库中搜索某个领域的所有相关法规

    mode: "normal" — 先精确后模糊
          "precise" — 只用精确标题，减少噪音
    """
    cfg = DOMAINS[domain]
    seen_bbbs = set()
    results = []

    # 阶段 1: 精确标题搜索（低噪音）
    for exact_title in cfg.get("exact_titles", []):
        try:
            data = search_laws(exact_title, page=1, size=5,
                               search_range=1, search_type=1,
                               status_filter=status)
            for row in data.get("rows", []):
                bbbs = row.get("bbbs")
                if bbbs and bbbs not in seen_bbbs:
                    seen_bbbs.add(bbbs)
                    info = parse_detail(fetch_detail(bbbs))
                    if info:
                        results.append(info)
        except Exception as e:
            print(f"  [WARN] 精确搜索 '{exact_title}' 失败: {e}", file=sys.stderr)

    if mode == "precise":
        return results

    # 阶段 2: 模糊关键词搜索
    for keyword in cfg["keywords"]:
        if len(keyword) < 2:
            continue
        try:
            data = search_laws(keyword, page=1, size=size,
                               search_range=1, search_type=2,
                               status_filter=status)
            for row in data.get("rows", []):
                bbbs = row.get("bbbs")
                if bbbs and bbbs not in seen_bbbs:
                    title = re.sub(r"<[^>]+>", "", row.get("title", ""))
                    if not is_relevant(title, domain):
                        continue
                    seen_bbbs.add(bbbs)
                    info = parse_detail(fetch_detail(bbbs))
                    if info:
                        results.append(info)
        except Exception as e:
            print(f"  [WARN] 搜索 '{keyword}' 失败: {e}", file=sys.stderr)

    return results


# ============================================================
# 数据处理
# ============================================================

def deduplicate_results(results: list) -> list:
    """按标题去重"""
    seen_titles = set()
    deduped = []
    for r in results:
        t = r.get("title", "").strip()
        if t and t not in seen_titles:
            seen_titles.add(t)
            deduped.append(r)
    return deduped


def sort_by_category(results: list) -> list:
    """按法规效力层级排序"""
    level_order = {
        "宪法": 0,
        "法律": 1, "基本法律": 1,
        "行政法规": 2, "国务院规范性文件": 2,
        "部门规章": 3,
        "地方性法规": 4, "地方政府规章": 5,
        "司法解释": 6,
    }
    return sorted(
        results,
        key=lambda r: (
            level_order.get(r.get("category", ""), 99),
            r.get("publish_date", "") or "0000",
        ),
    )


# ============================================================
# Obsidian 输出
# ============================================================

def generate_obsidian_output(domain: str, results: list, output_dir: Path):
    """生成 Obsidian 格式的法规汇编笔记"""
    if not results:
        print(f"  ⚠️  没有找到 {domain} 领域的结果")
        return

    by_category = {}
    for r in results:
        cat = r.get("category", "其他")
        by_category.setdefault(cat, []).append(r)

    now = datetime.now().strftime("%Y-%m-%d")
    title = f"{domain}法规汇编"
    filename = sanitize_filename(title) + ".md"
    filepath = output_dir / filename

    lines = [
        f"# {domain}法规汇编",
        "",
        f"> 自动检索生成日期：{now}",
        "> 来源：国家法律法规数据库 (flk.npc.gov.cn)",
        "",
        f"共收录 **{len(results)}** 部现行有效法规。",
        "",
        "## 📋 速览",
        "",
    ]
    for cat, items in by_category.items():
        lines.append(f"- **{cat}**：{len(items)} 部")
    lines.append("")

    # 核心法规标记
    exact_titles = DOMAINS[domain].get("exact_titles", [])
    lines.append("## 📖 法规列表")
    lines.append("")
    for cat, items in by_category.items():
        lines.append(f"### {cat}")
        lines.append("")
        for r in items:
            title = r.get("title", "未知")
            pub = r.get("publish_date", "") or "—"
            eff = r.get("effective_date", "") or "—"
            authority = r.get("authority", "")
            status = r.get("status_str", "")

            # 标记核心法规
            badge = ""
            if title in exact_titles:
                badge = " ⭐"

            lines.append(f"- **{title}**{badge}")
            lines.append(f"  - 发布机关：{authority}")
            lines.append(f"  - 发布日期：{pub} | 施行日期：{eff}")
            if status:
                lines.append(f"  - 状态：{status}")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"*共 {len(results)} 部法规 | 生成于 {now}*")
    lines.append("")

    filepath.write_text("\n".join(lines), encoding="utf-8")
    print(f"  📝 写入: {filepath}")
    return filepath


def generate_master_index(all_stats: dict, output_dir: Path):
    """生成总索引页"""
    now = datetime.now().strftime("%Y-%m-%d")
    filepath = output_dir / "法规汇编总索引.md"

    lines = [
        "# 📚 法规汇编总索引",
        "",
        f"> 更新日期：{now}",
        f"> 来源：国家法律法规数据库 (flk.npc.gov.cn)",
        "",
        "## 领域索引",
        "",
    ]
    for domain in sorted(all_stats.keys()):
        stats = all_stats[domain]
        total = stats["total"]
        lines.append(f"- [[{domain}法规汇编|{domain}]] — {total} 部现行有效法规")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 按领域展示
    for domain in sorted(all_stats.keys()):
        stats = all_stats[domain]
        results = stats.get("results", [])
        lines.append(f"## {domain}")
        lines.append("")
        lines.append(f"共 {stats['total']} 部法规 | ⭐ = 核心法规")
        lines.append("")

        for r in results:
            title = r.get("title", "未知")
            cat = r.get("category", "")
            authority = r.get("authority", "")
            pub = r.get("publish_date", "") or "—"
            eff = r.get("effective_date", "") or "—"

            exact_titles = DOMAINS.get(domain, {}).get("exact_titles", [])
            badge = " ⭐" if title in exact_titles else ""

            lines.append(f"- **{title}**{badge}")
            lines.append(f"  - [{cat}] {authority} | {pub}")
            lines.append("")

    filepath.write_text("\n".join(lines), encoding="utf-8")
    print(f"  📝 总索引: {filepath}")


def print_search_plan(domains: list, size: int, download: bool):
    """打印搜索计划让用户确认"""
    print(f"\n{'='*60}")
    print("📋 搜索计划")
    print(f"{'='*60}")
    for domain in domains:
        if domain not in DOMAINS:
            continue
        cfg = DOMAINS[domain]
        total_kw = len(cfg["keywords"]) + len(cfg.get("exact_titles", []))
        print(f"  {domain}: {total_kw} 个关键词, size={size}")
    total_est = estimate_requests(domains, size, download)
    mode_desc = "不限速" if total_est <= 10 else \
                "固定 5 req/s" if total_est <= 100 else \
                "自适应 1~8 req/s"
    print(f"\n  预估总请求数: ~{total_est} 次")
    print(f"  限速模式: {mode_desc}")
    if download:
        print(f"  ⚠️  下载全文: 是")
    print(f"{'='*60}")
    return total_est


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="批量筛选法规 — 按领域检索 NPC 数据库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--domain", choices=list(DOMAINS.keys()) + ["基金"],
                        help="指定领域")
    parser.add_argument("--all", action="store_true", help="搜索所有领域")
    parser.add_argument("--mode", choices=["normal", "precise"], default="normal",
                        help="搜索模式: normal=精确+模糊, precise=仅精确标题(低噪音)")
    parser.add_argument("--status", default="3",
                        help="时效性过滤 (默认 3=现行有效)")
    parser.add_argument("--size", type=int, default=30,
                        help="每个关键词的搜索结果数 (默认 30)")
    parser.add_argument("--rate-limit",
                        choices=["auto", "off", "fixed", "adaptive"],
                        default="auto",
                        help="限速模式 (默认 auto, 根据任务量自动选择)")
    parser.add_argument("--download", action="store_true",
                        help="下载全文 DOCX")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="跳过确认提示")
    parser.add_argument("--output",
                        default="/Users/yan/Desktop/for_claude/obsidian/01-法务知识库/合规研究",
                        help="输出目录")
    parser.add_argument("--list", action="store_true", help="列出可用领域")

    args = parser.parse_args()

    # --- list mode ---
    if args.list:
        print("可用领域：")
        for name, cfg in DOMAINS.items():
            kw_count = len(cfg["keywords"]) + len(cfg.get("exact_titles", []))
            print(f"  {name}: {kw_count} 个关键词")
            print(f"    核心法规: {', '.join(cfg.get('exact_titles', []))}")
            print(f"    关键词: {', '.join(cfg['keywords'])}")
            print()
        return

    # --- determine domains ---
    if args.all:
        domains = list(DOMAINS.keys())
    elif args.domain:
        if args.domain == "基金":
            domains = ["私募基金", "基金销售"]
        else:
            domains = [args.domain]
    else:
        parser.print_help()
        return

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    status_filter = [int(s.strip()) for s in args.status.split(",")]

    # --- print plan & confirm ---
    total_est = print_search_plan(domains, args.size, args.download)
    if not args.yes:
        try:
            confirm = input("\n是否继续？(y/N): ").strip().lower()
            if confirm not in ("y", "yes"):
                print("已取消")
                return
        except (EOFError, KeyboardInterrupt):
            print("\n已取消")
            return

    # --- init rate limiter ---
    limiter, mode = setup_rate_limiter(
        domains, args.size, force_mode=args.rate_limit, download=args.download
    )

    # --- search each domain ---
    all_stats = {}
    for domain in domains:
        print(f"\n{'='*60}")
        print(f"🔍 [{domain}] 正在搜索...")
        print(f"{'='*60}")

        results = search_npc_domain(
            domain, status=status_filter,
            size=args.size, mode=args.mode,
        )
        results = deduplicate_results(results)
        results = sort_by_category(results)

        print(f"  ✅ 找到 {len(results)} 部相关法规")

        by_cat = {}
        for r in results:
            cat = r.get("category", "其他")
            by_cat[cat] = by_cat.get(cat, 0) + 1
        for cat, count in sorted(by_cat.items()):
            print(f"     {cat}: {count}")

        # 生成 Obsidian 笔记
        generate_obsidian_output(domain, results, output_dir)

        # 保存原始 JSON
        json_dir = output_dir / "_data"
        json_dir.mkdir(exist_ok=True)
        json_path = json_dir / f"{sanitize_filename(domain)}_raw.json"
        json_path.write_text(
            json.dumps(results, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8"
        )

        all_stats[domain] = {
            "total": len(results),
            "by_category": by_cat,
            "results": results,
        }

        # 下载
        if args.download and results:
            dl_dir = output_dir / "_downloads" / sanitize_filename(domain)
            dl_dir.mkdir(parents=True, exist_ok=True)
            for i, r in enumerate(results):
                title = r.get("title", "unknown")
                bbbs = r.get("bbbs", "")
                try:
                    fmt = "docx"
                    url = get_download_url(bbbs, fmt)
                    fname = sanitize_filename(title) + f".{fmt}"
                    fpath = str(dl_dir / fname)
                    download_file(url, fpath)
                    print(f"  📄 [{i+1}/{len(results)}] {title}")
                except Exception as e:
                    print(f"  ⚠️  下载失败 [{title}]: {e}")

    # --- master index ---
    generate_master_index(all_stats, output_dir)

    # --- summary ---
    limiter.print_summary()
    print(f"\n{'='*60}")
    print("📊 汇总")
    print(f"{'='*60}")
    grand_total = 0
    for domain, stats in all_stats.items():
        print(f"  {domain}: {stats['total']} 部")
        grand_total += stats['total']
    print(f"  ───────────")
    print(f"  合计: {grand_total} 部")
    print(f"\n输出目录: {output_dir}")


if __name__ == "__main__":
    main()
