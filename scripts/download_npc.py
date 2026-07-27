#!/usr/bin/env python3
"""批量下载 NPC 法规 DOCX 原文。"""
import json, os, time, re, requests, urllib3
urllib3.disable_warnings()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FCLAUDE = os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR)))
META = os.path.join(FCLAUDE, "obsidian", "01-法务知识库", "合规研究", "_data", "npc_metadata.json")
OUTDIR = os.path.join(FCLAUDE, "obsidian", "01-法务知识库", "合规研究", "_data", "法规原文")

# 板块 → 子目录映射
CAT_DIR = {
    "基金运作": "基金运作", "证券交易": "证券交易", "反洗钱": "反洗钱",
    "广告竞争": "广告竞争", "税务": "税务", "劳动": "劳动人事",
    "跨境": "跨境", "基础法律": "基础法律",
}

with open(META) as f:
    items = json.load(f)

to_dl = [i for i in items if i.get("bbbs") and not i.get("error")]
print(f"共 {len(to_dl)} 部待下载\n")

ok = fail = skip = 0
for i, item in enumerate(to_dl):
    bbbs = item["bbbs"]
    title = item["title"]
    cat = item.get("category", "其他")
    subdir = CAT_DIR.get(cat, "基础法律")
    out_dir = os.path.join(OUTDIR, subdir)
    os.makedirs(out_dir, exist_ok=True)

    safe_name = re.sub(r'[\\/:*?"<>|]', '_', title)[:60]
    out_path = os.path.join(out_dir, f"{safe_name}.docx")

    if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
        print(f"[{i+1}/{len(to_dl)}] ⏭ {title[:40]}... (已有)")
        skip += 1
        continue

    print(f"[{i+1}/{len(to_dl)}] 📥 {title[:40]}...", end=" ", flush=True)
    try:
        # 1. 获取签名 URL
        r1 = requests.get(
            "https://flk.npc.gov.cn/law-search/download/pc",
            params={"format": "docx", "bbbs": bbbs},
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": f"https://flk.npc.gov.cn/detail?id={bbbs}",
                "Accept": "application/json",
            },
            verify=False, timeout=15,
        )
        url_data = r1.json()
        if url_data.get("code") != 200:
            raise RuntimeError(url_data.get("msg", "API error"))
        dl_url = url_data.get("data", {}).get("url")
        if not dl_url:
            raise RuntimeError("无下载URL")

        # 2. 下载文件
        r2 = requests.get(dl_url, headers={"User-Agent": "Mozilla/5.0"},
                          verify=False, timeout=60)
        ct = r2.headers.get("Content-Type", "")
        if "text/html" in ct and len(r2.content) < 5000:
            raise RuntimeError("返回HTML而非文件")
        if len(r2.content) < 500:
            raise RuntimeError(f"文件太小({len(r2.content)}b)")

        with open(out_path, "wb") as f:
            f.write(r2.content)
        print(f"✅ {len(r2.content)//1024}KB")
        ok += 1
    except Exception as e:
        print(f"❌ {str(e)[:50]}")
        fail += 1

    if i < len(to_dl) - 1:
        time.sleep(0.8)

print(f"\n✅{ok} ⏭{skip} ❌{fail}")
