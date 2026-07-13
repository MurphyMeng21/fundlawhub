# FundLawHub

[![GitHub](https://img.shields.io/badge/GitHub-MurphyMeng21%2Ffundlawhub-blue)](https://github.com/MurphyMeng21/fundlawhub)

一个面向私募基金管理人的中国法律法规检索工具，提供 Web 在线检索和命令行数据采集两种使用方式。

**在线检索** → `https://murphymeng21.github.io/fundlawhub/`

---

## Web 检索系统

支持按板块分类浏览、关键词模糊搜索、法规全文查看，适配桌面和移动端。

数据来源：**国家法律法规数据库** (`flk.npc.gov.cn`)，收录现行有效的法律、行政法规、司法解释，以及部分部门规章。

### 板块分类

| 板块 | 内容 |
|------|------|
| 基金运作与监管 | 证券投资基金法、私募基金条例、公司法及司法解释等 |
| 证券交易合规 | 证券法、期货和衍生品法、虚假陈述赔偿规定等 |
| 反洗钱与 CRS | 反洗钱法、受益所有人识别、客户尽职调查等 |
| 广告与市场竞争 | 广告法、反不正当竞争法、互联网广告等 |
| 程序化/量化交易 | 证券/期货市场程序化交易管理规定 |
| 税务 | 企业所得税法、增值税法、个税法、印花税法等 |
| 劳动人事 | 劳动法、劳动合同法、社会保险法、工伤保险条例等 |
| 跨境业务 | 外汇管理条例等 |
| 基础法律与知识产权 | 民法典、行政处罚法、个人信息保护法、知识产权法等 |

---

## 命令行工具

项目同时提供用于本地数据采集和维护的 Python 脚本。

### 安装

```bash
pip install -r requirements.txt
```

### 核心脚本

| 脚本 | 功能 |
|------|------|
| `scripts/download.py` | NPC 数据库搜索、下载、法条查询 |
| `scripts/article_search.py` | 跨法规法条级关键词搜索 |
| `scripts/build_search_db.py` | 将元数据与全文合并为 Web 用的 `laws.json` |
| `scripts/phase1_exact.py` | 按法规名称精确批量采集元数据 |
| `scripts/batch_fetch.py` | 按领域批量搜索法规 |
| `scripts/region_classifier.py` | 地域/制定机关分类 |

### 常用命令

```bash
# 精确搜索法规
python scripts/download.py --search "物业管理条例" --exact --status 3

# 模糊搜索
python scripts/download.py --search "私募基金" --status 3 --size 50

# 查询具体法条
python scripts/download.py --article <bbbs_id> "第三十八条"

# 跨法规法条搜索
python scripts/article_search.py "违约金" --range content --max-laws 5

# 重建 Web 数据
python scripts/build_search_db.py
```

---

## 文件结构

```
fundlawhub/
├── README.md
├── SKILL.md                          # AI Agent 使用说明
├── requirements.txt
├── docs/
│   ├── index.html                    # Web 检索系统
│   └── data/
│       └── laws.json                 # 法规数据（build_search_db.py 生成）
├── scripts/
│   ├── download.py                   # NPC 搜索/下载/法条查询
│   ├── article_search.py             # 跨法规法条搜索
│   ├── build_search_db.py            # Web 数据打包
│   ├── phase1_exact.py               # 精确批量采集
│   ├── batch_fetch.py                # 领域批量搜索
│   ├── batch_collect.py              # 多关键词采集
│   ├── download_npc.py               # DOCX 批量下载
│   ├── generate_markdown.py          # Obsidian MD 生成
│   ├── gov_rules_crawler.py          # 国家规章库
│   ├── treaty_crawler.py             # 外交条约库
│   ├── region_classifier.py          # 地域分类
│   └── common.py                     # 共享工具
├── references/                       # API 参考与适配文档
└── tests/                            # 单元测试
```

---

## 免责声明

本工具仅用于学习、研究与合规核验。请遵守 `flk.npc.gov.cn` 等官方数据库的使用规则，避免高频请求或批量抓取。

本工具不提供法律意见。法律文本的时效性和准确性请以官方公布内容为准。
