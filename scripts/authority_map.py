#!/usr/bin/env python3
"""
Authority / region categorization helper for NPC laws.

The database's issuing authority strings (zdjgName) are irregular, especially
for autonomous regions. This module normalizes them into standard regions
and levels so downstream scripts don't have to parse strings by hand.

Example:
    from authority_map import categorize_by_authority
    categorize_by_authority("宁夏回族自治区人大常务委员会")
    # {"region": "宁夏回族自治区", "level": "provincial", "authority": "..."}
"""

# Standard region + common authority-name variants seen in the database.
# Order matters: longer/more specific variants should come before shorter ones.
REGION_VARIANTS = [
    # Municipalities
    ("北京市", ["北京市人民代表大会", "北京市人民代表大会常务委员会", "北京市人大常委会"]),
    ("天津市", ["天津市人民代表大会", "天津市人民代表大会常务委员会", "天津市人大常委会"]),
    ("上海市", ["上海市人民代表大会", "上海市人民代表大会常务委员会", "上海市人大常委会"]),
    ("重庆市", ["重庆市人民代表大会", "重庆市人民代表大会常务委员会", "重庆市人大常委会"]),
    # Provinces
    ("河北省", ["河北省人民代表大会", "河北省人民代表大会常务委员会", "河北省人大常委会"]),
    ("山西省", ["山西省人民代表大会", "山西省人民代表大会常务委员会", "山西省人大常委会"]),
    ("辽宁省", ["辽宁省人民代表大会", "辽宁省人民代表大会常务委员会", "辽宁省人大常委会"]),
    ("吉林省", ["吉林省人民代表大会", "吉林省人民代表大会常务委员会", "吉林省人大常委会"]),
    ("黑龙江省", ["黑龙江省人民代表大会", "黑龙江省人民代表大会常务委员会", "黑龙江省人大常委会"]),
    ("江苏省", ["江苏省人民代表大会", "江苏省人民代表大会常务委员会", "江苏省人大常委会"]),
    ("浙江省", ["浙江省人民代表大会", "浙江省人民代表大会常务委员会", "浙江省人大常委会"]),
    ("安徽省", ["安徽省人民代表大会", "安徽省人民代表大会常务委员会", "安徽省人大常委会"]),
    ("福建省", ["福建省人民代表大会", "福建省人民代表大会常务委员会", "福建省人大常委会"]),
    ("江西省", ["江西省人民代表大会", "江西省人民代表大会常务委员会", "江西省人大常委会"]),
    ("山东省", ["山东省人民代表大会", "山东省人民代表大会常务委员会", "山东省人大常委会"]),
    ("河南省", ["河南省人民代表大会", "河南省人民代表大会常务委员会", "河南省人大常委会"]),
    ("湖北省", ["湖北省人民代表大会", "湖北省人民代表大会常务委员会", "湖北省人大常委会"]),
    ("湖南省", ["湖南省人民代表大会", "湖南省人民代表大会常务委员会", "湖南省人大常委会"]),
    ("广东省", ["广东省人民代表大会", "广东省人民代表大会常务委员会", "广东省人大常委会"]),
    ("海南省", ["海南省人民代表大会", "海南省人民代表大会常务委员会", "海南省人大常委会"]),
    ("四川省", ["四川省人民代表大会", "四川省人民代表大会常务委员会", "四川省人大常委会"]),
    ("贵州省", ["贵州省人民代表大会", "贵州省人民代表大会常务委员会", "贵州省人大常委会"]),
    ("云南省", ["云南省人民代表大会", "云南省人民代表大会常务委员会", "云南省人大常委会"]),
    ("陕西省", ["陕西省人民代表大会", "陕西省人民代表大会常务委员会", "陕西省人大常委会"]),
    ("甘肃省", ["甘肃省人民代表大会", "甘肃省人民代表大会常务委员会", "甘肃省人大常委会"]),
    ("青海省", ["青海省人民代表大会", "青海省人民代表大会常务委员会", "青海省人大常委会"]),
    ("台湾省", ["台湾省人民代表大会", "台湾省人民代表大会常务委员会", "台湾省人大常委会"]),
    # Autonomous regions (note the irregular "人大常务委员会" variants)
    ("内蒙古自治区", ["内蒙古自治区人民代表大会", "内蒙古自治区人民代表大会常务委员会", "内蒙古自治区人大常务委员会", "内蒙古自治区人大常委会"]),
    ("广西壮族自治区", ["广西壮族自治区人民代表大会", "广西壮族自治区人民代表大会常务委员会", "广西壮族自治区人大常务委员会", "广西壮族自治区人大常委会"]),
    ("西藏自治区", ["西藏自治区人民代表大会", "西藏自治区人民代表大会常务委员会", "西藏自治区人大常务委员会", "西藏自治区人大常委会"]),
    ("宁夏回族自治区", ["宁夏回族自治区人民代表大会", "宁夏回族自治区人民代表大会常务委员会", "宁夏回族自治区人大常务委员会", "宁夏回族自治区人大常委会"]),
    ("新疆维吾尔自治区", ["新疆维吾尔自治区人民代表大会", "新疆维吾尔自治区人民代表大会常务委员会", "新疆维吾尔自治区人大常务委员会", "新疆维吾尔自治区人大常委会"]),
    # Special Administrative Regions (unlikely to appear, but included for completeness)
    ("香港特别行政区", ["香港特别行政区立法会"]),
    ("澳门特别行政区", ["澳门特别行政区立法会"]),
]

# Authorities that should be treated as national-level.
NATIONAL_KEYWORDS = [
    "全国人民代表大会",
    "全国人民代表大会常务委员会",
    "全国人大常委会",
    "国务院",
    "最高人民法院",
    "最高人民检察院",
    "中央军事委员会",
    "国家",
    "中央军委",
]


def _detect_level(authority: str) -> str:
    """Best-effort level detection from authority string."""
    if any(kw in authority for kw in ("自治区", "省人民代表大会")) and "市" not in authority:
        return "provincial"
    if "自治州" in authority or "州人民代表大会" in authority:
        return "prefectural"
    if "市人民代表大会" in authority or "市人大常委会" in authority or "市人大" in authority:
        return "municipal"
    if "区" in authority or "县" in authority or "旗" in authority:
        return "county"
    if "全国" in authority or "中央" in authority or "国家" in authority or "最高" in authority:
        return "national"
    return "unknown"


def categorize_by_authority(authority: str) -> dict:
    """
    Normalize an authority (zdjgName) string into region and level.

    Returns:
        {
            "region": str | None,   # Standard region name, or "全国", or None if unmatched
            "level": str,           # national | provincial | prefectural | municipal | county | unknown
            "authority": str,       # Original authority string
        }
    """
    if not authority:
        return {"region": None, "level": "unknown", "authority": authority}

    # National authorities
    for kw in NATIONAL_KEYWORDS:
        if kw in authority:
            return {"region": "全国", "level": "national", "authority": authority}

    # Regional authorities
    for region, variants in REGION_VARIANTS:
        for variant in variants:
            if authority.startswith(variant) or variant in authority:
                return {"region": region, "level": _detect_level(authority), "authority": authority}

    # Fallback: if the region name itself appears anywhere
    for region, _ in REGION_VARIANTS:
        if region in authority:
            return {"region": region, "level": _detect_level(authority), "authority": authority}

    return {"region": None, "level": _detect_level(authority), "authority": authority}


def demo():
    """Self-check with representative authority strings."""
    samples = [
        "全国人民代表大会常务委员会",
        "宁夏回族自治区人大常务委员会",
        "宁夏回族自治区人民代表大会常务委员会",
        "广东省人民代表大会常务委员会",
        "深圳市人民代表大会常务委员会",
        "北京市人民代表大会",
        "国务院",
        "最高人民法院",
    ]
    for a in samples:
        print(a, "->", categorize_by_authority(a))


if __name__ == "__main__":
    demo()
