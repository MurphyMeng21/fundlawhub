# NPC Law DB Skill

[![GitHub](https://img.shields.io/badge/GitHub-ZongziForu%2Fnpc--law--db-blue)](https://github.com/ZongziForu/npc-law-db)

A Claude Code / Kimi Agent skill for accessing China's **National Laws and Regulations Database** (`flk.npc.gov.cn`).

Search, browse, download, and classify Chinese legal documents — including constitutional laws, statutes, administrative regulations, local regulations, judicial interpretations, and supervisory regulations.

> **中文**：这是一个用于访问中国国家法律法规数据库（`flk.npc.gov.cn`）的 Claude Code / Kimi Agent skill。支持搜索、浏览、下载和分类中国法律文件，包括宪法、法律、行政法规、地方性法规、司法解释和监察法规。

---

## 中文

### 功能

- **搜索法规**：通过标题或正文关键词搜索国家法律法规数据库。
- **精确 / 模糊策略**：根据任务自动选择精确标题匹配或模糊匹配，减少噪音。
- **批量采集**：支持一次性采集 200–300 条法规的完整工作流。
- **下载文件**：支持 DOCX（WPS 版）和 PDF（公报原版）下载。
- **获取单条/多条法条**：下载整部法规 DOCX 后，在本地只提取指定条款（如民法典第 217 条），避免把全文塞进 agent 上下文，节省 token。
- **URL 导出**：云端 agent 可只导出签名下载 URL，供本地下载使用。
- **地域自动分类**：内置 ~370 个地市/自治州到省份的映射，自动识别省级、设区市级、国家级。
- **存在性矩阵**：生成 32 省级行政区 × 法规类型的存在性矩阵 CSV。
- **多环境支持**：Kimi Agent、Claude Code（通过 kimi-webbridge）、Codex Chrome 插件。

### 安装

```bash
pip install -r requirements.txt
```

### 快速开始

```bash
# 模糊搜索：适合主题/关键词
python scripts/download.py --search "出租车" --size 100

# 精确搜索：适合已知法规名
python scripts/download.py --search "物业管理条例" --exact --size 100

# 只导出签名下载 URL（云端 agent 友好）
python scripts/download.py --search "出租车" --urls-only --size 100 > urls.json

# 下载单部法规
python scripts/download.py --download <bbbs_id> --format docx output.doc

# 获取单条法条（本地解析 DOCX，只返回目标条款）
python scripts/article.py 217 民法典

# 批量获取多条法条
python scripts/article.py 51,211,347 民法典 --json

# 查看元数据
python scripts/download.py --info <bbbs_id>
```

### 获取单条/多条法条

当你只需要核对某一条或某几条法条时，不必把整部法规塞进 agent 上下文。`scripts/article.py` 会下载该法规的 DOCX，在本地提取指定条款，默认附带前后各 1 条作为上下文：

```bash
# 单条法条
python scripts/article.py 217 民法典

# 多条法条（逗号分隔）
python scripts/article.py 51,211,347 民法典

# JSON 输出
python scripts/article.py 217 民法典 --json

# 只输出目标条，不带上下文
python scripts/article.py 217 民法典 --context 0

# 保留下载的 DOCX
python scripts/article.py 217 民法典 --keep-docx 民法典.docx
```

`article.py` 支持两种法规定位方式：
- 32 位 `bbbs_id`（十六进制）
- 搜索关键词（自动取搜索结果第一条，并在 stderr 打印选中法规的标题）

> **说明**：`article.py` 会先尝试最常见的“第X条”中文数字编号快速提取；若失败，则自动调用 detail API 从目录树探测实际编号风格（中文数字 / 阿拉伯数字 / 列表式），然后重新提取。

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
npc-law-db/
├── SKILL.md                      # 给 agent 看的 skill 主文档
├── README.md                     # 本文件
├── requirements.txt              # Python 依赖
├── scripts/
│   ├── download.py               # 搜索、下载、导出 URL
│   ├── region_classifier.py      # 地域分类与存在性矩阵
│   └── article.py                # 单条/批量法条提取
└── references/
    ├── api_reference.md          # API 端点与参数参考
    ├── batch_collection.md       # 200-300 条批量采集指南
    ├── page_structure.md         # 页面结构说明
    ├── kimi_bridge_adapter.md    # Claude Code / Kimi Agent 适配
    └── codex_adapter.md          # Codex Chrome 插件适配
```

### 免责声明

本工具仅用于学习和研究目的。请遵守 `flk.npc.gov.cn` 的使用条款，不要高频请求或用于商业用途。

---

## English

### Features

- **Search regulations**: Search by title or full-text keyword in the NPC database.
- **Exact / fuzzy strategy**: Automatically choose exact title match or fuzzy match based on the task to reduce noise.
- **Batch collection**: Complete workflow for collecting 200–300 regulations at once.
- **Download files**: Supports DOCX (WPS version) and PDF (gazette version).
- **Extract single / multiple articles**: After downloading a regulation DOCX, extract only the requested articles locally (e.g. Civil Code Article 217) without loading the full text into the agent context.
- **URL export**: Cloud agents can export signed download URLs only, for local batch downloading.
- **Region auto-classification**: Built-in mapping of ~370 prefecture-level divisions to provinces; automatically identifies national, provincial, and city-level authorities.
- **Existence matrix**: Generate a 32-province × regulation-type matrix as CSV.
- **Multi-environment**: Kimi Agent, Claude Code (via kimi-webbridge), and Codex Chrome plugin.

### Installation

```bash
pip install -r requirements.txt
```

### Quick Start

```bash
# Fuzzy search: good for topics/keywords
python scripts/download.py --search "taxi" --size 100

# Exact search: good when you know the regulation name
python scripts/download.py --search "Property Management Regulations" --exact --size 100

# Export signed download URLs only (cloud-agent friendly)
python scripts/download.py --search "taxi" --urls-only --size 100 > urls.json

# Download a single regulation
python scripts/download.py --download <bbbs_id> --format docx output.doc

# Extract a single article (parse DOCX locally, return only the target article)
python scripts/article.py 217 "Civil Code"

# Extract multiple articles
python scripts/article.py 51,211,347 "Civil Code" --json

# View metadata
python scripts/download.py --info <bbbs_id>
```

### Extract Single / Multiple Articles

When you only need to verify one or a few articles, there's no need to load the full regulation into the agent context. `scripts/article.py` downloads the regulation DOCX and extracts only the requested articles locally, with 1 neighbouring article on each side by default:

```bash
# Single article
python scripts/article.py 217 "Civil Code"

# Multiple articles (comma-separated)
python scripts/article.py 51,211,347 "Civil Code"

# JSON output
python scripts/article.py 217 "Civil Code" --json

# Only the target article, no context
python scripts/article.py 217 "Civil Code" --context 0

# Keep the downloaded DOCX
python scripts/article.py 217 "Civil Code" --keep-docx civil_code.docx
```

`article.py` accepts two kinds of law identifiers:
- 32-character `bbbs_id` (hex)
- Search keyword (uses the first search result; prints the selected title to stderr)

> **Note**: `article.py` first tries the most common `第X条` Chinese-numeral format. If any target article is missing, it calls the detail API once to detect the actual numbering style from the TOC (Chinese numerals / Arabic numerals / dotted list) and re-extracts.

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
npc-law-db/
├── SKILL.md                      # Main skill doc for agents
├── README.md                     # This file
├── requirements.txt              # Python dependencies
├── scripts/
│   ├── download.py               # Search, download, URL export
│   ├── region_classifier.py      # Region classification & matrix
│   └── article.py                # Single / batch article extraction
└── references/
    ├── api_reference.md          # API endpoint & parameter reference
    ├── batch_collection.md       # 200-300 file batch collection guide
    ├── page_structure.md         # Page structure overview
    ├── kimi_bridge_adapter.md    # Claude Code / Kimi Agent adapter
    └── codex_adapter.md          # Codex Chrome plugin adapter
```

### Disclaimer

This tool is for educational and research purposes only. Please comply with the terms of use of `flk.npc.gov.cn`, avoid high-frequency requests, and do not use it for commercial purposes.
