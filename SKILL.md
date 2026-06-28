---
name: npc-law-db
description: Access and retrieve laws/regulations from China's National Laws and Regulations Database (flk.npc.gov.cn). Use when the user needs to search, browse, download, or extract Chinese legal documents including constitutional laws, statutes, administrative regulations, local regulations, judicial interpretations, and supervisory regulations. Covers searching by title/content, advanced filtering by category/issuing authority/effective status/date ranges, pagination, sorting, batch download, single document download, and article-level keyword extraction. Supports multi-environment browser automation (Kimi native, Claude Code via kimi-bridge, Codex).
---

# National Laws and Regulations Database (国家法律法规数据库)

Official database: `https://flk.npc.gov.cn`. Maintained by NPC Standing Committee.

## Environment Selection

This skill supports multiple agent environments. **Read the adapter for your environment first**:

| Environment | Read This | Tool prerequisite |
|-------------|-----------|-------------------|
| **Kimi Agent (cloud)** | `references/kimi_bridge_adapter.md` | Native `mshtools-browser_*` tools |
| **Claude Code (local)** | `references/kimi_bridge_adapter.md` | Invoke the `kimi-webbridge` skill first to obtain browser tools |
| **Codex** | `references/codex_adapter.md` | `mcp__node_repl__js` (Node REPL) for browser control |

> **Claude Code quick start:** Before running any browser workflow, tell the user to run `/kimi-webbridge` (or invoke the `kimi-webbridge` skill). The browser tools (`browser_visit`, `browser_click`, etc.) referenced in this skill are provided by that bridge, not by Claude Code natively.
>
> **Codex quick start:** All browser operations use the Playwright API through the Node REPL (`mcp__node_repl__js`). Read `references/codex_adapter.md` for the complete bootstrap and API mapping. The adapter covers both Codex Desktop (in-app browser) and Codex Chrome plugin.

## Setup

The bundled Python script needs `requests`. DOCX parsing uses the Python stdlib; old `.doc` files require optional system tools. Install once:

```bash
pip install -r requirements.txt
# Optional: for old .doc format support (some regulations use pre-2007 Word format)
apt-get install antiword catdoc  # Linux
brew install antiword catdoc     # macOS
```

## Page Structure Overview

**Read `references/page_structure.md`** for complete visual layout of all pages before planning any retrieval task. Understanding the page structure helps you:
- Predict where elements will appear after actions
- Know which filters/sorts are available without exploring
- Plan the most efficient navigation path for the task

Key pages:
- `/index` — Home with quick search, category cards, hot queries
- `/search` — Results with filters (left sidebar), sort, pagination, batch actions
- `/advanceSearch` — Multi-criteria advanced search form
- `/detail?id={bbbs}` — Full text viewer with download options

## Quick Reference

### API-First Search → Download Workflow (Recommended)

**The agent must decide the search strategy before calling the API.** Do not default to fuzzy for every query:

- **Known title / specific regulation** (e.g. "物业管理条例", "北京市生活垃圾管理条例"): use `--exact` (title + exact match) to reduce noise
- **Broad topic / unsure of title** (e.g. "出租车", "环境保护"): omit `--exact` to use fuzzy search
- **Ambiguous query**: ask the user whether they want exact title match or broad fuzzy match, or run both and compare

```bash
# 1. Fuzzy search by topic
python scripts/download.py --search "出租车" --size 100

# 2. Exact title search (less noise)
python scripts/download.py --search "物业管理条例" --exact --size 100

# 3. Search full text of laws
python scripts/download.py --search "违约金" --range content --size 50

# 4. Filter by effective status
python scripts/download.py --search "出租车" --status 3 --size 50

# 5. Get signed download URLs only (for local batch download)
python scripts/download.py --search "出租车" --urls-only --size 100 > urls.json

# 6. Get metadata
python scripts/download.py --info {bbbs_id}

# 7. Download file
python scripts/download.py --download {bbbs_id} --format docx output.doc
```

### Query Individual Articles (Preview / Article Lookup)

For retrieving specific articles instead of full files:

```bash
# Preview law structure — shows article count + numbering pattern + first 20 articles
python scripts/download.py --preview {bbbs_id}

# Query by article number (supports multiple formats, auto-converts)
python scripts/download.py --article {bbbs_id} "第三十八条"   # Chinese
python scripts/download.py --article {bbbs_id} "第38条"      # Arabic
python scripts/download.py --article {bbbs_id} "38"          # Number only

# Grep keyword across all articles of one law
python scripts/download.py --article {bbbs_id} --grep "经济补偿"
```

| Command | Use when | Output |
|---------|---------|--------|
| `--preview` | Understand structure before querying | Title, article count, **numbering pattern**, TOC |
| `--article "第X条"` | Know the article number | Single article (supports Chinese/Arabic/auto-convert) |
| `--article --grep` | Find all articles with keyword in one law | All matching articles |

> **Numbering pattern detection**: `--preview` first queries the lightweight Detail API to detect whether the law uses Chinese numerals (第一条), Arabic numerals (第1条), or mixed. This avoids failed lookups. If `--article` returns no match, it shows the detected format (e.g., "This law uses: 第一条") and suggests `--preview`.
>
> **How it works**: Detail API content tree → detect numbering → download DOCX → parse → split by "第X条" → match. No file saved by default.

### Search API

```
POST https://flk.npc.gov.cn/law-search/search/list
```

Working payload:
```json
{
  "searchRange": 1, "searchType": 2, "searchContent": "出租车",
  "pageNum": 1, "pageSize": 100,
  "orderByParam": {"order": "-1", "sort": ""},
  "flfgCodeId": [], "zdjgCodeId": [], "sxx": [], "gbrq": [], "sxrq": [], "gbrqYear": [],
  "xgzlSearch": false
}
```

| Field | Meaning |
|-------|---------|
| `searchRange` | `1`=标题, `2`=正文 |
| `searchType` | `1`=精确, `2`=模糊 |
| `pageSize` | Up to at least 100 |
| `sxx` | Status filter: `1`=已废止, `2`=已修改, `3`=现行有效, `4`=尚未生效 |

**Strategy rule for the agent:** If the user gives an exact or near-exact regulation name, prefer `searchRange=1` + `searchType=1` (title exact). Use fuzzy only when the request is clearly a broad topic or when exact returns too few results. When uncertain, ask the user instead of guessing.

For full parameter reference see `references/api_reference.md`.

### Browser-Only Search → Download Workflow

Use this only when the API fails or for tasks that require the UI (e.g., advanced search with complex AND/OR logic):

```
1. Visit /index
2. Enter keyword in search input (center of page)
3. Press Enter to search (do not click the magnifying glass icon, which opens /advanceSearch)
4. On /search results: click a title to open detail
5. On /detail: click 下载 → 点击下载 to save file
```

### Detail API (for metadata)

```
GET https://flk.npc.gov.cn/law-search/search/flfgDetails?bbbs={bbbs_id}
```

Returns: title, dates, category, status, and `ossFile` paths.

Use bundled script: `python scripts/download.py --info {bbbs_id}`

### Download API

```
GET https://flk.npc.gov.cn/law-search/download/pc?format={docx|pdf}&bbbs={bbbs_id}
```

Returns a signed OSS URL in `data.url`. Use that URL to download the actual file.

```bash
python scripts/download.py --download {bbbs_id} --format docx output.doc
```

> **Note:** The `ossFile` paths from the detail API are **not** directly downloadable. The site serves the SPA index page for those URLs. Always use the download API or browser download button.

### Article-Level Search (`scripts/article_search.py`)

For finding **specific articles** that contain a keyword (not just which laws):

```bash
# Search across laws whose titles contain keyword, find matching articles
python scripts/article_search.py "违约金" --max-laws 5

# Search across laws whose full text contains keyword
python scripts/article_search.py "违约金" --range content --max-laws 5

# Show surrounding context (1 article before/after each match)
python scripts/article_search.py "抵押权" --range content --max-laws 3 --context 1

# Search within a specific law only
python scripts/article_search.py "善意取得" --law "民法典" --context 0

# JSON output for further processing
python scripts/article_search.py "违约金" --max-laws 3 --json
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `keyword` | (required) | Keyword to search within articles |
| `--law` | same as keyword | Keyword to find candidate laws |
| `--range title/content` | title | Search law titles or full text |
| `--max-laws` | 5 | Max laws to download and parse |
| `--context` | 0 | Surrounding articles to include |
| `--status` | all | Filter by status code |
| `--json` | | Output JSON instead of text |
| `--offset` | 0 | Skip first N laws (batch retrieval) |
| `--resume` | | Skip laws whose DOCX is already in cache |

**How it works:**
1. Find candidate laws (by title or full text)
2. Download DOCX for each law (cached)
3. Parse DOCX → split into articles by "第X条"
4. Return all matching articles with optional context

**Progressive Batch Retrieval:**

When the first batch doesn't yield enough results, continue with subsequent batches:

```bash
# Batch 1: process first 5 laws
python scripts/article_search.py "违约金" --range content --max-laws 5
# → "已处理: 5/342 部法规"

# Batch 2: process laws 5-9
python scripts/article_search.py "违约金" --range content --max-laws 5 --offset 5

# Or: use --resume to skip already-processed laws and continue with new ones
python scripts/article_search.py "违约金" --range content --max-laws 5 --resume
```

### Authority / Region Categorization

Issuing authority names (`zdjgName`) are irregular, especially for autonomous regions, and city-level authorities usually do not include the province name. Use the bundled `region_classifier.py` instead of string matching:

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

The classifier covers all provincial-level regions, ~370 city/prefecture-level divisions, and common naming variants. For classification tasks, prefer the official `zdjgfl` codes from `GET /law-search/search/enumData` when available; use `region_classifier.py` for post-processing search results.

CLI usage:

```bash
# Run built-in tests
python scripts/region_classifier.py --test

# Classify search results from download.py --urls-only
python scripts/download.py --search "物业管理条例" --urls-only --size 100 > urls.json
python scripts/region_classifier.py --classify < urls.json > classified.json

# Generate province existence matrix
python scripts/region_classifier.py --matrix matrix.csv < classified.json
```

### Rate Limiting

Automatic rate limiting is **enabled by default** to prevent 429 errors during bulk operations:

```bash
# Auto mode (default) — small tasks unlimited, medium=5rps, large=adaptive
python scripts/download.py --search "出租车" --urls-only --size 100

# Force fixed rate (5 requests/second)
python scripts/download.py --search "出租车" --urls-only --size 50 --rate-limit fixed

# Force adaptive (auto-adjust 1-8 rps based on server response)
python scripts/download.py --search "出租车" --urls-only --size 200 --rate-limit adaptive

# Custom fixed rate
python scripts/download.py --search "出租车" --urls-only --size 50 --rate-limit 3

# Disable (small tasks only)
python scripts/download.py --info {bbbs_id} --rate-limit off
```

| Mode | Trigger | Speed | Use case |
|------|---------|-------|----------|
| **OFF** | <=10 requests | Unlimited | Single query, preview, one article |
| **FIXED** | 11-100 requests | 5 req/s | Medium batch download |
| **ADAPTIVE** | >100 requests | 1-8 req/s | Large collection, auto-adjusts |

> **429 handling**: When a 429 is received, the limiter backs off exponentially (2s, 4s, 8s...) and reduces speed. In adaptive mode, speed drops by 40% per 429 and recovers slowly on success.

### Cache Management

Local file cache is **enabled by default** to speed up repeated queries:

```bash
# Check cache status
python scripts/download.py --cache-stats

# Disable cache for a single run
python scripts/download.py --no-cache --info {bbbs_id}

# Clear all cache
python scripts/download.py --cache-clear
```

| Cache Type | TTL | Speedup |
|------------|-----|---------|
| Search results | 1 hour | ~4x (API ~800ms → cache ~200ms) |
| Detail metadata | 24 hours | ~3x (API ~600ms → cache ~200ms) |
| DOCX files | 7 days | ~9x (download ~90ms → read ~10ms) |
| Signed URLs | not cached | expire ~1 hour |

Cache location: `~/.cache/npc-law-db/`

### File Format Note

The database serves two formats:
- **DOCX** (most files): Modern ZIP-based format, parsed natively with stdlib
- **DOC** (some older regulations): Pre-2007 binary format, requires `antiword` or `catdoc`

The script auto-detects format and handles both transparently. If conversion tools are missing, you'll get a clear error with install instructions.

### For 200-300 File Collection Tasks

**Read `references/batch_collection.md`** before starting. The current recommended approach:
1. Use the Search API to collect all target IDs in pages of 100
2. Use the Download API (`/law-search/download/pc`) to fetch each file
3. Save to local disk for persistence
4. Browser automation is only needed as a fallback

## Status Code Mapping (sxx field)

All search and detail results include a `status_code` (sxx) integer. Verified mapping:

| sxx | Status | Example |
|-----|--------|---------|
| `1` | **已废止** | 合同法（被民法典取代） |
| `2` | **已修改** | 劳动法（2009年版，已有新版） |
| `3` | **现行有效** | 劳动合同法 |
| `4` | **尚未生效** | 生态环境法典（2026-03-12公布） |

Filter by status: `--status 3` (only current), `--status 3,4` (current + upcoming)

## Key Concepts

| Term | Meaning |
|------|---------|
| bbbs | Unique law ID used in detail URLs (`?id=xxx`) |
| 标题 | Title field (default search scope) |
| 模糊/精确 | Fuzzy vs exact match modes |
| 时效性 | Effective status: 已废止/已修改/现行有效/尚未生效 |
| 公布日期 | Publish date |
| 施行日期 | Effective date |
| 命中展示 | Show keyword match locations in the law |

## Sort Options

1. 默认排序 2. 法律法规分类 3. 制定机关 4. 时效性 5. 公布日期 6. 施行日期

## Category Codes

宪法 / 法律 / 行政法规 / 监察法规 / 地方法规 / 司法解释

## Download Options

- **WPS版本**: Formatted DOCX (default view)
- **公报原版**: Official gazette PDF
- Both available via detail page 下载 button

## Advanced Search

Visit `/advanceSearch`. Supports:
- Multi-field: title, full text, related materials title/text
- Date ranges: publish date, effective date
- Dropdowns: category, issuing authority
- Checkboxes: effective status (multi-select)
- Logic: 并且(AND) / 或者(OR) / 不含(NOT) between conditions

## Batch Operations on Results Page

- **全选**: Select all items on current page
- **批量下载文件**: Download selected items
- **批量导出文件目录**: Export catalog of selected items

## Pagination

Page sizes: 10/20/30/40/50/100 per page. Use 100 for fastest bulk ID collection.
