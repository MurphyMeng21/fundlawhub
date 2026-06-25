#!/usr/bin/env python3
"""
Region classifier for NPC law database search results.

Automatically categorizes regulations by province/region and level
(provincial vs prefecture-level city) from the 'authority' (zdjgName) field.

Key design: city-level authorities (e.g. "广州市人民代表大会常务委员会")
do NOT contain the province name. A city-to-province lookup table is required.
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict

# ---------------------------------------------------------------------------
# Province data
# ---------------------------------------------------------------------------

PROVINCE_NAMES_FULL = [
    "北京市", "天津市", "上海市", "重庆市",
    "河北省", "山西省", "内蒙古自治区",
    "辽宁省", "吉林省", "黑龙江省",
    "江苏省", "浙江省", "安徽省", "福建省", "江西省", "山东省",
    "河南省", "湖北省", "湖南省",
    "广东省", "广西壮族自治区", "海南省",
    "四川省", "贵州省", "云南省",
    "西藏自治区",
    "陕西省", "甘肃省", "青海省",
    "宁夏回族自治区", "新疆维吾尔自治区", "新疆生产建设兵团",
]

PROVINCE_SHORT = {
    "北京市": "北京", "天津市": "天津", "上海市": "上海", "重庆市": "重庆",
    "河北省": "河北", "山西省": "山西", "内蒙古自治区": "内蒙古",
    "辽宁省": "辽宁", "吉林省": "吉林", "黑龙江省": "黑龙江",
    "江苏省": "江苏", "浙江省": "浙江", "安徽省": "安徽",
    "福建省": "福建", "江西省": "江西", "山东省": "山东",
    "河南省": "河南", "湖北省": "湖北", "湖南省": "湖南",
    "广东省": "广东", "广西壮族自治区": "广西", "海南省": "海南",
    "四川省": "四川", "贵州省": "贵州", "云南省": "云南",
    "西藏自治区": "西藏",
    "陕西省": "陕西", "甘肃省": "甘肃", "青海省": "青海",
    "宁夏回族自治区": "宁夏", "新疆维吾尔自治区": "新疆",
    "新疆生产建设兵团": "新疆兵团",
}

MUNICIPALITIES = {"北京市", "天津市", "上海市", "重庆市"}
PROVINCIAL_SUFFIXES = [
    "人民代表大会常务委员会", "人民代表大会", "人大常务委员会",
]

# ---------------------------------------------------------------------------
# City-to-province mapping (~370 prefecture-level divisions)
# ---------------------------------------------------------------------------

CITY_TO_PROVINCE = {}

# 4 Municipalities
for muni in ["北京市", "天津市", "上海市", "重庆市"]:
    CITY_TO_PROVINCE[muni] = muni

# 河北省 (11)
for city in ["石家庄市", "唐山市", "秦皇岛市", "邯郸市", "邢台市", "保定市",
             "张家口市", "承德市", "沧州市", "廊坊市", "衡水市"]:
    CITY_TO_PROVINCE[city] = "河北省"

# 山西省 (11)
for city in ["太原市", "大同市", "阳泉市", "长治市", "晋城市", "朔州市",
             "晋中市", "运城市", "忻州市", "临汾市", "吕梁市"]:
    CITY_TO_PROVINCE[city] = "山西省"

# 内蒙古自治区 (12)
for city in ["呼和浩特市", "包头市", "乌海市", "赤峰市", "通辽市", "鄂尔多斯市",
             "呼伦贝尔市", "巴彦淖尔市", "乌兰察布市",
             "兴安盟", "锡林郭勒盟", "阿拉善盟"]:
    CITY_TO_PROVINCE[city] = "内蒙古自治区"

# 辽宁省 (14)
for city in ["沈阳市", "大连市", "鞍山市", "抚顺市", "本溪市", "丹东市",
             "锦州市", "营口市", "阜新市", "辽阳市", "盘锦市", "铁岭市",
             "朝阳市", "葫芦岛市"]:
    CITY_TO_PROVINCE[city] = "辽宁省"

# 吉林省 (11)
for city in ["长春市", "吉林市", "四平市", "辽源市", "通化市", "白山市",
             "松原市", "白城市", "延边朝鲜族自治州", "梅河口市", "公主岭市"]:
    CITY_TO_PROVINCE[city] = "吉林省"

# 黑龙江省 (13)
for city in ["哈尔滨市", "齐齐哈尔市", "鸡西市", "鹤岗市", "双鸭山市",
             "大庆市", "伊春市", "佳木斯市", "七台河市", "牡丹江市",
             "黑河市", "绥化市", "大兴安岭地区"]:
    CITY_TO_PROVINCE[city] = "黑龙江省"

# 江苏省 (13)
for city in ["南京市", "无锡市", "徐州市", "常州市", "苏州市", "南通市",
             "连云港市", "淮安市", "盐城市", "扬州市", "镇江市",
             "泰州市", "宿迁市"]:
    CITY_TO_PROVINCE[city] = "江苏省"

# 浙江省 (11)
for city in ["杭州市", "宁波市", "温州市", "嘉兴市", "湖州市", "绍兴市",
             "金华市", "衢州市", "舟山市", "台州市", "丽水市"]:
    CITY_TO_PROVINCE[city] = "浙江省"

# 安徽省 (16)
for city in ["合肥市", "芜湖市", "蚌埠市", "淮南市", "马鞍山市", "淮北市",
             "铜陵市", "安庆市", "黄山市", "滁州市", "阜阳市", "宿州市",
             "六安市", "亳州市", "池州市", "宣城市"]:
    CITY_TO_PROVINCE[city] = "安徽省"

# 福建省 (9)
for city in ["福州市", "厦门市", "莆田市", "三明市", "泉州市", "漳州市",
             "南平市", "龙岩市", "宁德市"]:
    CITY_TO_PROVINCE[city] = "福建省"

# 江西省 (11)
for city in ["南昌市", "景德镇市", "萍乡市", "九江市", "新余市", "鹰潭市",
             "赣州市", "吉安市", "宜春市", "抚州市", "上饶市"]:
    CITY_TO_PROVINCE[city] = "江西省"

# 山东省 (16)
for city in ["济南市", "青岛市", "淄博市", "枣庄市", "东营市", "烟台市",
             "潍坊市", "济宁市", "泰安市", "威海市", "日照市", "临沂市",
             "德州市", "聊城市", "滨州市", "菏泽市"]:
    CITY_TO_PROVINCE[city] = "山东省"

# 河南省 (18)
for city in ["郑州市", "开封市", "洛阳市", "平顶山市", "安阳市", "鹤壁市",
             "新乡市", "焦作市", "濮阳市", "许昌市", "漯河市", "三门峡市",
             "南阳市", "商丘市", "信阳市", "周口市", "驻马店市", "济源市"]:
    CITY_TO_PROVINCE[city] = "河南省"

# 湖北省 (17)
for city in ["武汉市", "黄石市", "十堰市", "宜昌市", "襄阳市", "鄂州市",
             "荆门市", "孝感市", "荆州市", "黄冈市", "咸宁市", "随州市",
             "恩施土家族苗族自治州", "仙桃市", "潜江市", "天门市", "神农架林区"]:
    CITY_TO_PROVINCE[city] = "湖北省"

# 湖南省 (14)
for city in ["长沙市", "株洲市", "湘潭市", "衡阳市", "邵阳市", "岳阳市",
             "常德市", "张家界市", "益阳市", "郴州市", "永州市", "怀化市",
             "娄底市", "湘西土家族苗族自治州"]:
    CITY_TO_PROVINCE[city] = "湖南省"

# 广东省 (21)
for city in ["广州市", "深圳市", "珠海市", "汕头市", "佛山市", "韶关市",
             "湛江市", "肇庆市", "江门市", "茂名市", "惠州市", "梅州市",
             "汕尾市", "河源市", "阳江市", "清远市", "东莞市", "中山市",
             "潮州市", "揭阳市", "云浮市"]:
    CITY_TO_PROVINCE[city] = "广东省"

# 广西壮族自治区 (14)
for city in ["南宁市", "柳州市", "桂林市", "梧州市", "北海市", "防城港市",
             "钦州市", "贵港市", "玉林市", "百色市", "贺州市", "河池市",
             "来宾市", "崇左市"]:
    CITY_TO_PROVINCE[city] = "广西壮族自治区"

# 海南省 (19)
for city in ["海口市", "三亚市", "三沙市", "儋州市", "五指山市", "琼海市",
             "文昌市", "万宁市", "东方市", "定安县", "屯昌县", "澄迈县",
             "临高县", "白沙黎族自治县", "昌江黎族自治县", "乐东黎族自治县",
             "陵水黎族自治县", "保亭黎族苗族自治县", "琼中黎族苗族自治县"]:
    CITY_TO_PROVINCE[city] = "海南省"

# 四川省 (21)
for city in ["成都市", "自贡市", "攀枝花市", "泸州市", "德阳市", "绵阳市",
             "广元市", "遂宁市", "内江市", "乐山市", "南充市", "眉山市",
             "宜宾市", "广安市", "达州市", "雅安市", "巴中市", "资阳市",
             "阿坝藏族羌族自治州", "甘孜藏族自治州", "凉山彝族自治州"]:
    CITY_TO_PROVINCE[city] = "四川省"

# 贵州省 (9)
for city in ["贵阳市", "六盘水市", "遵义市", "安顺市", "毕节市", "铜仁市",
             "黔西南布依族苗族自治州", "黔东南苗族侗族自治州", "黔南布依族苗族自治州"]:
    CITY_TO_PROVINCE[city] = "贵州省"

# 云南省 (16)
for city in ["昆明市", "曲靖市", "玉溪市", "保山市", "昭通市", "丽江市",
             "普洱市", "临沧市", "楚雄彝族自治州", "红河哈尼族彝族自治州",
             "文山壮族苗族自治州", "西双版纳傣族自治州", "大理白族自治州",
             "德宏傣族景颇族自治州", "怒江傈僳族自治州", "迪庆藏族自治州"]:
    CITY_TO_PROVINCE[city] = "云南省"

# 西藏自治区 (7)
for city in ["拉萨市", "日喀则市", "昌都市", "林芝市", "山南市", "那曲市", "阿里地区"]:
    CITY_TO_PROVINCE[city] = "西藏自治区"

# 陕西省 (10)
for city in ["西安市", "铜川市", "宝鸡市", "咸阳市", "渭南市", "延安市",
             "汉中市", "榆林市", "安康市", "商洛市"]:
    CITY_TO_PROVINCE[city] = "陕西省"

# 甘肃省 (14)
for city in ["兰州市", "嘉峪关市", "金昌市", "白银市", "天水市", "武威市",
             "张掖市", "平凉市", "酒泉市", "庆阳市", "定西市", "陇南市",
             "临夏回族自治州", "甘南藏族自治州"]:
    CITY_TO_PROVINCE[city] = "甘肃省"

# 青海省 (8)
for city in ["西宁市", "海东市", "海北藏族自治州", "黄南藏族自治州",
             "海南藏族自治州", "果洛藏族自治州", "玉树藏族自治州",
             "海西蒙古族藏族自治州"]:
    CITY_TO_PROVINCE[city] = "青海省"

# 宁夏回族自治区 (5)
for city in ["银川市", "石嘴山市", "吴忠市", "固原市", "中卫市"]:
    CITY_TO_PROVINCE[city] = "宁夏回族自治区"

# 新疆维吾尔自治区 + 兵团 (25)
for city in ["乌鲁木齐市", "克拉玛依市", "吐鲁番市", "哈密市",
             "昌吉回族自治州", "博尔塔拉蒙古自治州", "巴音郭楞蒙古自治州",
             "阿克苏地区", "克孜勒苏柯尔克孜自治州", "喀什地区", "和田地区",
             "伊犁哈萨克自治州", "塔城地区", "阿勒泰地区",
             "石河子市", "阿拉尔市", "图木舒克市", "五家渠市", "北屯市",
             "铁门关市", "双河市", "可克达拉市", "昆玉市", "胡杨河市", "新星市"]:
    CITY_TO_PROVINCE[city] = "新疆维吾尔自治区"

# Also add 新疆生产建设兵团 cities
for city in ["石河子市", "阿拉尔市", "图木舒克市", "五家渠市", "北屯市",
             "铁门关市", "双河市", "可克达拉市", "昆玉市", "胡杨河市", "新星市"]:
    CITY_TO_PROVINCE[city] = "新疆生产建设兵团"

# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def _extract_province_from_authority(authority):
    """Try to match province name directly in authority (for provincial-level)."""
    for prov in sorted(PROVINCE_NAMES_FULL, key=len, reverse=True):
        if prov in authority:
            return prov
    return None


def _extract_city_from_authority(authority):
    """Extract city name from authority by removing legislative suffixes."""
    city = authority
    for suffix in PROVINCIAL_SUFFIXES:
        if city.endswith(suffix):
            city = city[:-len(suffix)].strip()
            break
    return city.strip()


def _is_provincial_suffix(authority, province):
    """Check if authority ends with provincial legislative body suffix."""
    if province in MUNICIPALITIES:
        return True
    for suffix in PROVINCIAL_SUFFIXES:
        if authority.endswith(f"{province}{suffix}"):
            return True
    return False


NATIONAL_KEYWORDS = [
    "国务院", "全国人民代表大会", "全国人民代表大会常务委员会",
    "最高人民法院", "最高人民检察院", "中央军事委员会", "国家",
    "中央军委", "全国人大",
]


def classify_by_authority(authority, title=""):
    """Classify regulation by issuing authority.

    Returns: province, province_short, city, level, is_municipality, authority
    """
    result = {
        "province": None, "province_short": None, "city": None,
        "level": "unknown", "is_municipality": False, "authority": authority,
    }
    if not authority:
        return result

    # Strategy 0: National authorities
    for kw in NATIONAL_KEYWORDS:
        if kw in authority:
            result["province"] = "全国"
            result["province_short"] = "全国"
            result["city"] = "全国"
            result["level"] = "national"
            return result

    # Strategy 1: Try to match province name directly (for provincial-level)
    province = _extract_province_from_authority(authority)

    if province:
        # Found province name in authority -> likely provincial level
        result["province"] = province
        result["province_short"] = PROVINCE_SHORT.get(province, province)
        result["is_municipality"] = province in MUNICIPALITIES

        if _is_provincial_suffix(authority, province):
            result["level"] = "provincial"
            result["city"] = province
        else:
            # Province name present but not at end -> might be city-level with prefix
            city = _extract_city_from_authority(authority)
            if city.startswith(province):
                city = city[len(province):].strip()
            result["level"] = "city"
            result["city"] = city if city else province
        return result

    # Strategy 2: Extract city name, then look up province (for city-level)
    city = _extract_city_from_authority(authority)
    if city:
        # Handle edge case: "甘肃省临夏回族自治州物业管理条例" in title
        # but authority is "临夏回族自治州人大常务委员会"
        if city in CITY_TO_PROVINCE:
            province = CITY_TO_PROVINCE[city]
            result["province"] = province
            result["province_short"] = PROVINCE_SHORT.get(province, province)
            result["is_municipality"] = province in MUNICIPALITIES
            result["level"] = "city"
            result["city"] = city
            return result

    return result


def classify_search_results(items, authority_key="authority", title_key="title"):
    classified = []
    for item in items:
        cls = classify_by_authority(
            item.get(authority_key, "") or "",
            item.get(title_key, "") or "",
        )
        classified.append({**item,
            "classified_province": cls["province"],
            "classified_province_short": cls["province_short"],
            "classified_city": cls["city"],
            "classified_level": cls["level"],
            "is_municipality": cls["is_municipality"],
        })
    return classified



def _get_capital(province):
    return {
        "北京市": "—", "天津市": "—", "上海市": "—", "重庆市": "—",
        "河北省": "石家庄市", "山西省": "太原市", "内蒙古自治区": "呼和浩特市",
        "辽宁省": "沈阳市", "吉林省": "长春市", "黑龙江省": "哈尔滨市",
        "江苏省": "南京市", "浙江省": "杭州市", "安徽省": "合肥市",
        "福建省": "福州市", "江西省": "南昌市", "山东省": "济南市",
        "河南省": "郑州市", "湖北省": "武汉市", "湖南省": "长沙市",
        "广东省": "广州市", "广西壮族自治区": "南宁市", "海南省": "海口市",
        "四川省": "成都市", "贵州省": "贵阳市", "云南省": "昆明市",
        "西藏自治区": "拉萨市",
        "陕西省": "西安市", "甘肃省": "兰州市", "青海省": "西宁市",
        "宁夏回族自治区": "银川市", "新疆维吾尔自治区": "乌鲁木齐市",
        "新疆生产建设兵团": "—",
    }.get(province, "")


def build_existence_matrix(items, province_key="classified_province",
                           city_key="classified_city", level_key="classified_level",
                           status_key="status_code", title_key="title",
                           bbbs_key="bbbs", date_key="publish_date"):
    by_province = defaultdict(list)
    for item in items:
        prov = item.get(province_key)
        if prov:
            by_province[prov].append(item)
    matrix = []
    for prov in PROVINCE_NAMES_FULL:
        prov_items = by_province.get(prov, [])
        prov_regs = [i for i in prov_items if i.get(level_key) == "provincial"]
        prov_current = [i for i in prov_regs if i.get(status_key) == 3]
        prov_historical = [i for i in prov_regs if i.get(status_key) != 3]
        city_regs = [i for i in prov_items if i.get(level_key) == "city"]
        cities_current = {cr.get(city_key, "") for cr in city_regs if cr.get(status_key) == 3}
        matrix.append({
            "province": prov, "province_short": PROVINCE_SHORT.get(prov, prov),
            "capital": _get_capital(prov),
            "has_provincial_regulation": len(prov_current) > 0,
            "has_provincial_historical": len(prov_historical) > 0,
            "provincial_current_count": len(prov_current),
            "provincial_historical_count": len(prov_historical),
            "provincial_current_titles": "; ".join(
                f"{i.get(title_key, '')}({i.get(date_key, '')})" for i in prov_current),
            "provincial_historical_titles": "; ".join(
                f"{i.get(title_key, '')}({i.get(date_key, '')})" for i in prov_historical),
            "provincial_current_bbbs": "; ".join(i.get(bbbs_key, "") for i in prov_current),
            "city_count": len(cities_current),
            "cities_with_regulation": ", ".join(sorted(cities_current)) if cities_current else "",
            "total_regulations": len(prov_items),
        })
    return matrix


def save_classified_items(items, output_path):
    if not items:
        return
    all_keys = set()
    for item in items:
        all_keys.update(item.keys())
    priority = ["bbbs", "title", "classified_province", "classified_province_short",
                "classified_city", "classified_level", "is_municipality",
                "authority", "category", "publish_date", "effective_date", "status_code"]
    fieldnames = [k for k in priority if k in all_keys] + [k for k in sorted(all_keys) if k not in priority]
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(items)
    print(f"Saved: {output_path} ({len(items)} rows)")


def save_existence_matrix(matrix, output_path):
    if not matrix:
        return
    fieldnames = [
        "province", "province_short", "capital",
        "has_provincial_regulation", "has_provincial_historical",
        "provincial_current_count", "provincial_historical_count",
        "provincial_current_titles", "provincial_historical_titles",
        "provincial_current_bbbs",
        "city_count", "cities_with_regulation", "total_regulations",
    ]
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(matrix)
    print(f"Saved: {output_path} ({len(matrix)} provinces)")


def main():
    import sys
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    cmd = args[0]
    if cmd == "--test":
        tests = [
            ("国务院", "national", "全国", "全国"),
            ("北京市人民代表大会常务委员会", "provincial", "北京市", "北京市"),
            ("宁夏回族自治区人大常务委员会", "provincial", "宁夏回族自治区", "宁夏回族自治区"),
            ("广西壮族自治区人大常务委员会", "provincial", "广西壮族自治区", "广西壮族自治区"),
            ("广州市人民代表大会常务委员会", "city", "广东省", "广州市"),
            ("临夏回族自治州人大常务委员会", "city", "甘肃省", "临夏回族自治州"),
            ("哈尔滨市人民代表大会常务委员会", "city", "黑龙江省", "哈尔滨市"),
            ("", "unknown", None, None),
        ]
        all_passed = True
        for auth, exp_lvl, exp_prov, exp_city in tests:
            r = classify_by_authority(auth)
            ok = r["level"] == exp_lvl and r["province"] == exp_prov and r["city"] == exp_city
            if not ok:
                all_passed = False
            print(f"  [{'PASS' if ok else 'FAIL'}] '{auth}' -> level={r['level']}, prov={r['province']}, city={r['city']}")
        print(f"\n{'All tests passed!' if all_passed else 'Some tests FAILED!'}")
    elif cmd == "--classify":
        items = json.load(sys.stdin)
        classified = classify_search_results(items)
        json.dump(classified, sys.stdout, ensure_ascii=False, indent=2)
        print()
    elif cmd == "--matrix":
        if len(args) < 2:
            print("Usage: python region_classifier.py --matrix <output.csv>")
            sys.exit(1)
        items = json.load(sys.stdin)
        matrix = build_existence_matrix(items)
        save_existence_matrix(matrix, args[1])
    else:
        print(f"Unknown: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
