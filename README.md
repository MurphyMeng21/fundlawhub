# CN Law Hub

[![GitHub](https://img.shields.io/badge/GitHub-ZongziForu%2Fcn--law--hub-blue)](https://github.com/ZongziForu/cn-law-hub)

A Claude Code / Kimi Agent / Codex skill for accessing three Chinese legal databases:

1. **国家法律法规数据库 (NPC)** — `flk.npc.gov.cn`
2. **国家规章库 (Gov Rules)** — `gov.cn/zhengce/xxgk/gjgzk/`
3. **外交条约库 (Treaty)** — `treaty.mfa.gov.cn`

Search, browse, download, and classify Chinese legal documents — including constitutional laws, statutes, administrative regulations, local regulations, judicial interpretations, supervisory regulations, State Council rules, and international treaties.

> **中文**：这是一个用于访问中国三大法律数据库的 Claude Code / Kimi Agent / Codex skill。支持搜索、浏览、下载和分类中国法律文件，包括宪法、法律、行政法规、地方性法规、司法解释、监察法规、国家规章以及国际条约。

---

## 中文

### 功能

- **多数据源支持**：
  - 国家法律法规数据库（`flk.npc.gov.cn`）
  - 国家规章库（`gov.cn/zhengce/xxgk/gjgzk/`）
  - 外交条约库（`treaty.mfa.gov.cn`）
- **搜索法规**：通过标题或正文关键词搜索国家法律法规数据库。
- **精确 / 模糊策略**：根据任务自动选择精确标题匹配或模糊匹配，减少噪音。
- **全文搜索**：`--range content` 可在法规正文中搜索。
- **状态筛选**：`--status 3` 只返回现行有效法规。
- **批量采集**：支持一次性采集 200–300 条法规的完整工作流。
- **下载文件**：支持 DOCX（WPS 版）和 PDF（公报原版）下载；规章库和条约库支持下载详情页和附件。
- **法规预览与单条法条查询**：`--preview` 查看结构，`--article` 按条号或关键词查询单部法规内的法条。
- **跨法规法条级搜索**：`scripts/article_search.py` 按关键词搜索多部法规，返回具体匹配的法条。
- **智能限速**：根据任务大小自动选择关闭/固定/自适应限速，避免 429。
- **本地缓存**：搜索结果、元数据、DOCX 文件默认缓存，复访提速。
- **URL 导出**：云端 agent 可只导出签名下载 URL，供本地下载使用。
- **地域自动分类**：内置 ~370 个地市/自治州到省份的映射，自动识别省级、设区市级、国家级。
- **存在性矩阵**：生成 32 省级行政区 × 法规类型的存在性矩阵 CSV。
- **多环境支持**：Kimi Agent、Claude Code（通过 kimi-webbridge）、Codex Chrome 插件。

### 安装

```bash
pip install -r requirements.txt
```

可选：部分旧法规使用 `.doc` 格式，需安装系统工具：

```bash
# macOS
brew install antiword catdoc
# Debian/Ubuntu
apt-get install antiword catdoc
```

### 快速开始

```bash
# 模糊搜索：适合主题/关键词
python scripts/download.py --search "出租车" --size 100

# 精确搜索：适合已知法规名
python scripts/download.py --search "物业管理条例" --exact --size 100

# 在法规正文中搜索
python scripts/download.py --search "违约金" --range content --size 50

# 只返回现行有效法规
python scripts/download.py --search "出租车" --status 3 --size 50

# 只导出签名下载 URL（云端 agent 友好）
python scripts/download.py --search "出租车" --urls-only --size 100 > urls.json

# 下载单部法规
python scripts/download.py --download <bbbs_id> --format docx output.doc

# 查看法规结构（编号模式、前 20 条）
python scripts/download.py --preview <bbbs_id>

# 查询单部法规中的某一条（支持 第三十八条 / 第38条 / 38）
python scripts/download.py --article <bbbs_id> "第三十八条"

# 在单部法规中搜索关键词
python scripts/download.py --article <bbbs_id> --grep "经济补偿"

# 跨法规搜索含关键词的具体法条
python scripts/article_search.py "违约金" --max-laws 5 --context 1

# 查看元数据
python scripts/download.py --info <bbbs_id>

# 查看缓存状态
python scripts/download.py --cache-stats

# 国家规章库：搜索部门规章
python scripts/gov_rules_crawler.py --search "管理办法" --categories 部门规章 --size 20

# 国家规章库：下载详情页和附件
python scripts/gov_rules_crawler.py --categories 部门规章 --size 5 --download

# 外交条约库：搜索双边条约
python scripts/treaty_crawler.py --collections 双边 --search "上海合作组织" --size 20

# 外交条约库：下载条约预览 PDF
python scripts/treaty_crawler.py --collections 双边 --size 5 --download
```

### 单条/多条法条查询

当你只需要核对某一条或搜索某部法规内的关键词时，不必把整部法规塞进 agent 上下文。

```bash
# 预览法规结构
python scripts/download.py --preview <bbbs_id>

# 按条号查询（自动识别中文/阿拉伯数字）
python scripts/download.py --article <bbbs_id> "第三十八条"
python scripts/download.py --article <bbbs_id> "第38条"
python scripts/download.py --article <bbbs_id> "38"

# 在单部法规中 grep 关键词
python scripts/download.py --article <bbbs_id> --grep "经济补偿"
```

### 跨法规法条级搜索

`scripts/article_search.py` 用于在多部法规中查找包含关键词的具体法条：

```bash
# 在标题含关键词的法规中搜索
python scripts/article_search.py "违约金" --max-laws 5 --context 1

# 在全文含关键词的法规中搜索
python scripts/article_search.py "违约金" --range content --max-laws 5

# 限定只查某一部法规
python scripts/article_search.py "善意取得" --law 民法典 --context 0

# JSON 输出
python scripts/article_search.py "违约金" --max-laws 3 --json

# 分批检索
python scripts/article_search.py "违约金" --range content --max-laws 5
python scripts/article_search.py "违约金" --range content --max-laws 5 --offset 5
python scripts/article_search.py "违约金" --range content --max-laws 5 --resume
```

### 智能限速

```bash
# 默认自动模式
python scripts/download.py --search "出租车" --urls-only --size 100

# 强制固定 5 req/s
python scripts/download.py --search "出租车" --urls-only --size 50 --rate-limit fixed

# 自适应（大任务）
python scripts/download.py --search "出租车" --urls-only --size 200 --rate-limit adaptive

# 自定义速率
python scripts/download.py --search "出租车" --urls-only --size 50 --rate-limit 3

# 关闭限速（小任务）
python scripts/download.py --info <bbbs_id> --rate-limit off
```

### 缓存管理

```bash
# 查看缓存
python scripts/download.py --cache-stats

# 单次禁用缓存
python scripts/download.py --no-cache --info <bbbs_id>

# 清空缓存
python scripts/download.py --cache-clear
```

缓存位置：`~/.cache/npc-law-db/`

### 地域分类

城市级 authority 通常不含省份名，例如 "广州市人民代表大会常务委员会" 不会包含 "广东省"。`region_classifier.py` 自动处理这个问题：

```bash
python scripts/download.py --search "物业管理条例" --urls-only --size 100 > urls.json
python scripts/region_classifier.py --classify < urls.json > classified.json
python scripts/region_classifier.py --matrix matrix.csv < classified.json
```

Python API：

```python
from scripts.region_classifier import classify_by_authority

classify_by_authority("广州市人民代表大会常务委员会")
# {
#   "province": "广东省",
#   "province_short": "广东",
#   "city": "广州市",
#   "level": "city",
#   "is_municipality": False,
#   "authority": "广州市人民代表大会常务委员会"
# }
```

### 批量采集 200–300 条法规

详见 [`references/batch_collection.md`](references/batch_collection.md)。

### 文件结构

```
cn-law-hub/
├── SKILL.md                      # 给 agent 看的 skill 主文档
├── README.md                     # 本文件
├── requirements.txt              # Python 依赖
├── scripts/
│   ├── common.py                 # 共享工具：缓存、限速、HTTP、文件 I/O
│   ├── download.py               # NPC 搜索、下载、导出 URL、预览/查询法条
│   ├── article_search.py         # NPC 跨法规法条级关键词搜索
│   ├── gov_rules_crawler.py      # 国家规章库爬虫
│   ├── treaty_crawler.py         # 外交条约库爬虫
│   └── region_classifier.py      # 地域分类与存在性矩阵
└── references/
    ├── api_reference.md          # NPC API 端点与参数参考
    ├── gov_rules_api_reference.md # 国家规章库 API 与认证参考
    ├── treaty_api_reference.md   # 外交条约库 HTML 结构参考
    ├── batch_collection.md       # 200-300 条批量采集指南
    ├── page_structure.md         # 页面结构说明
    ├── kimi_bridge_adapter.md    # Claude Code / Kimi Agent 适配
    └── codex_adapter.md          # Codex Chrome 插件适配
```

### 致谢

国家规章库（`scripts/gov_rules_crawler.py`）和外交条约库（`scripts/treaty_crawler.py`）的实现参考了 [`law-crawler-unified`](https://github.com/Li2zon3/law-crawler-unified)。本项目的相关代码根据其思路进行了适配，并针对实际站点进行了验证，未机械照搬。

### 免责声明

本工具仅用于学习和研究目的。请遵守 `flk.npc.gov.cn`、`gov.cn` 和 `treaty.mfa.gov.cn` 的使用条款，不要高频请求或用于商业用途。

---

## English

### Features

- **Multi-database support**:
  - National Laws and Regulations Database (`flk.npc.gov.cn`)
  - State Council Rules Database (`gov.cn/zhengce/xxgk/gjgzk/`)
  - Ministry of Foreign Affairs Treaty Database (`treaty.mfa.gov.cn`)
- **Search regulations**: Search by title or full-text keyword in the NPC database.
- **Exact / fuzzy strategy**: Automatically choose exact title match or fuzzy match based on the task to reduce noise.
- **Full-text search**: `--range content` searches inside the body of laws.
- **Status filter**: `--status 3` returns only currently effective laws.
- **Batch collection**: Complete workflow for collecting 200–300 regulations at once.
- **Download files**: Supports DOCX (WPS version) and PDF (gazette version) for NPC; detail pages and attachments for Gov Rules/Treaty.
- **Preview and article lookup**: `--preview` shows structure; `--article` queries a specific article or keyword inside one law.
- **Article-level search across laws**: `scripts/article_search.py` returns specific articles matching a keyword across multiple laws.
- **Smart rate limiting**: Auto OFF / FIXED / ADAPTIVE based on task size to avoid 429 errors.
- **Local cache**: Search results, metadata, and DOCX files are cached by default for faster repeat access.
- **URL export**: Cloud agents can export signed download URLs only, for local batch downloading.
- **Region auto-classification**: Built-in mapping of ~370 prefecture-level divisions to provinces; automatically identifies national, provincial, and city-level authorities.
- **Existence matrix**: Generate a 32-province × regulation-type matrix as CSV.
- **Multi-environment**: Kimi Agent, Claude Code (via kimi-webbridge), and Codex Chrome plugin.

### Installation

```bash
pip install -r requirements.txt
```

Optional: some older regulations use the `.doc` format and require system tools:

```bash
# macOS
brew install antiword catdoc
# Debian/Ubuntu
apt-get install antiword catdoc
```

### Quick Start

```bash
# Fuzzy search: good for topics/keywords
python scripts/download.py --search "taxi" --size 100

# Exact search: good when you know the regulation name
python scripts/download.py --search "Property Management Regulations" --exact --size 100

# Search inside full text of laws
python scripts/download.py --search "liquidated damages" --range content --size 50

# Only currently effective laws
python scripts/download.py --search "taxi" --status 3 --size 50

# Export signed download URLs only (cloud-agent friendly)
python scripts/download.py --search "taxi" --urls-only --size 100 > urls.json

# Download a single regulation
python scripts/download.py --download <bbbs_id> --format docx output.doc

# Preview law structure (numbering pattern, first 20 articles)
python scripts/download.py --preview <bbbs_id>

# Query an article by number (supports Chinese / Arabic / number-only)
python scripts/download.py --article <bbbs_id> "第三十八条"

# Grep keyword inside one law
python scripts/download.py --article <bbbs_id> --grep "经济补偿"

# Article-level keyword search across laws
python scripts/article_search.py "liquidated damages" --max-laws 5 --context 1

# View metadata
python scripts/download.py --info <bbbs_id>

# Check cache status
python scripts/download.py --cache-stats

# State Council Rules Database: search department rules
python scripts/gov_rules_crawler.py --search "management measures" --categories 部门规章 --size 20

# State Council Rules Database: download detail pages and attachments
python scripts/gov_rules_crawler.py --categories 部门规章 --size 5 --download

# Ministry of Foreign Affairs Treaty Database: search bilateral treaties
python scripts/treaty_crawler.py --collections 双边 --search "Shanghai Cooperation Organization" --size 20

# Ministry of Foreign Affairs Treaty Database: download treaty preview PDFs
python scripts/treaty_crawler.py --collections 双边 --size 5 --download
```

### Query Single / Multiple Articles

When you only need to verify an article or grep a keyword inside one law, there's no need to load the full regulation into the agent context.

```bash
# Preview structure
python scripts/download.py --preview <bbbs_id>

# Query by article number (auto-converts Chinese/Arabic numerals)
python scripts/download.py --article <bbbs_id> "第三十八条"
python scripts/download.py --article <bbbs_id> "第38条"
python scripts/download.py --article <bbbs_id> "38"

# Grep keyword across articles of one law
python scripts/download.py --article <bbbs_id> --grep "经济补偿"
```

### Article-Level Search Across Laws

Use `scripts/article_search.py` to find specific articles containing a keyword across multiple laws:

```bash
# Search laws whose titles contain the keyword
python scripts/article_search.py "liquidated damages" --max-laws 5 --context 1

# Search laws whose full text contains the keyword
python scripts/article_search.py "liquidated damages" --range content --max-laws 5

# Restrict to a specific law
python scripts/article_search.py "good faith acquisition" --law "Civil Code" --context 0

# JSON output
python scripts/article_search.py "liquidated damages" --max-laws 3 --json

# Progressive batch retrieval
python scripts/article_search.py "liquidated damages" --range content --max-laws 5
python scripts/article_search.py "liquidated damages" --range content --max-laws 5 --offset 5
python scripts/article_search.py "liquidated damages" --range content --max-laws 5 --resume
```

### Rate Limiting

```bash
# Auto mode (default)
python scripts/download.py --search "taxi" --urls-only --size 100

# Fixed 5 req/s
python scripts/download.py --search "taxi" --urls-only --size 50 --rate-limit fixed

# Adaptive (large tasks)
python scripts/download.py --search "taxi" --urls-only --size 200 --rate-limit adaptive

# Custom fixed rate
python scripts/download.py --search "taxi" --urls-only --size 50 --rate-limit 3

# Disable (small tasks)
python scripts/download.py --info <bbbs_id> --rate-limit off
```

### Cache Management

```bash
# Show cache stats
python scripts/download.py --cache-stats

# Disable cache for one run
python scripts/download.py --no-cache --info <bbbs_id>

# Clear cache
python scripts/download.py --cache-clear
```

Cache location: `~/.cache/npc-law-db/`

### Region Classification

City-level authorities usually do not contain the province name, e.g. "广州市人民代表大会常务委员会" does not include "广东省". `region_classifier.py` handles this automatically:

```bash
python scripts/download.py --search "Property Management Regulations" --urls-only --size 100 > urls.json
python scripts/region_classifier.py --classify < urls.json > classified.json
python scripts/region_classifier.py --matrix matrix.csv < classified.json
```

Python API:

```python
from scripts.region_classifier import classify_by_authority

classify_by_authority("广州市人民代表大会常务委员会")
# {
#   "province": "广东省",
#   "province_short": "广东",
#   "city": "广州市",
#   "level": "city",
#   "is_municipality": False,
#   "authority": "广州市人民代表大会常务委员会"
# }
```

### Batch Collection (200–300 Files)

See [`references/batch_collection.md`](references/batch_collection.md).

### File Structure

```
cn-law-hub/
├── SKILL.md                      # Main skill doc for agents
├── README.md                     # This file
├── requirements.txt              # Python dependencies
├── scripts/
│   ├── common.py                 # Shared utilities: cache, rate limiter, HTTP, file I/O
│   ├── download.py               # NPC search, download, URL export, preview/article lookup
│   ├── article_search.py         # NPC article-level keyword search across laws
│   ├── gov_rules_crawler.py      # State Council Rules Database crawler
│   ├── treaty_crawler.py         # Ministry of Foreign Affairs Treaty Database crawler
│   └── region_classifier.py      # Region classification & matrix
└── references/
    ├── api_reference.md          # NPC API endpoint & parameter reference
    ├── gov_rules_api_reference.md # State Council Rules API & auth reference
    ├── treaty_api_reference.md   # Ministry of Foreign Affairs Treaty HTML reference
    ├── batch_collection.md       # 200-300 file batch collection guide
    ├── page_structure.md         # Page structure overview
    ├── kimi_bridge_adapter.md    # Claude Code / Kimi Agent adapter
    └── codex_adapter.md          # Codex Chrome plugin adapter
```

### Acknowledgments

The Gov Rules (`scripts/gov_rules_crawler.py`) and Treaty (`scripts/treaty_crawler.py`) implementations were informed by the reference project [`law-crawler-unified`](https://github.com/Li2zon3/law-crawler-unified). The code here was adapted to fit the local architecture and verified against the live sites, not copied mechanically.

### Disclaimer

This tool is for educational and research purposes only. Please comply with the terms of use of `flk.npc.gov.cn`, `gov.cn`, and `treaty.mfa.gov.cn`, avoid high-frequency requests, and do not use it for commercial purposes.
