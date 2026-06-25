---
name: npc-law-db
description: Access and retrieve laws/regulations from China's National Laws and Regulations Database (flk.npc.gov.cn). Use when the user needs to search, browse, download, or extract Chinese legal documents including constitutional laws, statutes, administrative regulations, local regulations, judicial interpretations, and supervisory regulations. Covers searching by title/content, advanced filtering by category/issuing authority/effective status/date ranges, pagination, sorting, batch download, and single document download. Supports multi-environment browser automation (Kimi native, Claude Code via kimi-bridge, Codex Chrome plugin).
---

# National Laws and Regulations Database (国家法律法规数据库)

Official database: `https://flk.npc.gov.cn`. Maintained by NPC Standing Committee.

## Environment Selection

This skill supports multiple agent environments. **Read the adapter for your environment first**:

| Environment | Read This | Tool prerequisite |
|-------------|-----------|-------------------|
| **Kimi Agent (cloud)** | `references/kimi_bridge_adapter.md` | Native `mshtools-browser_*` tools |
| **Claude Code (local)** | `references/kimi_bridge_adapter.md` | Invoke the `kimi-webbridge` skill first to obtain browser tools |
| **Codex (Chrome plugin)** | `references/codex_adapter.md` | Chrome browser plugin |

> **Claude Code quick start:** Before running any browser workflow, tell the user to run `/kimi-webbridge` (or invoke the `kimi-webbridge` skill). The browser tools (`browser_visit`, `browser_click`, etc.) referenced in this skill are provided by that bridge, not by Claude Code natively.

## Setup

The bundled Python script needs `requests`. Install once:

```bash
pip install -r requirements.txt
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

# 3. Get signed download URLs only (for local batch download)
python scripts/download.py --search "出租车" --urls-only --size 100 > urls.json

# 4. Get metadata
python scripts/download.py --info {bbbs_id}

# 5. Download file
python scripts/download.py --download {bbbs_id} --format docx output.doc
```

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

**Strategy rule for the agent:** If the user gives an exact or near-exact regulation name, prefer `searchRange=1` + `searchType=1` (title exact). Use fuzzy only when the request is clearly a broad topic or when exact returns too few results. When uncertain, ask the user instead of guessing.

For full parameter reference see `references/api_reference.md`.

### Browser-Only Search → Download Workflow

Use this only when the API fails or for tasks that require the UI (e.g., advanced search with complex AND/OR logic):

```
1. Visit /index
2. Enter keyword in search input (center of page)
3. Click magnifying glass icon to search
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

### Authority / Region Categorization

Issuing authority names (`zdjgName`) are irregular, especially for autonomous regions. Use the bundled helper instead of string matching:

```python
from scripts.authority_map import categorize_by_authority

categorize_by_authority("宁夏回族自治区人大常务委员会")
# {'region': '宁夏回族自治区', 'level': 'provincial', 'authority': '...'}
```

The helper covers all 34 provincial-level regions and common naming variants. For classification tasks, prefer the official `zdjgfl` codes from `GET /law-search/search/enumData` when available; use `categorize_by_authority()` for post-processing search results.

### For 200-300 File Collection Tasks

**Read `references/batch_collection.md`** before starting. The current recommended approach:
1. Use the Search API to collect all target IDs in pages of 100
2. Use the Download API (`/law-search/download/pc`) to fetch each file
3. Save to local disk for persistence
4. Browser automation is only needed as a fallback

## Key Concepts

| Term | Meaning |
|------|---------|
| bbbs | Unique law ID used in detail URLs (`?id=xxx`) |
| 标题 | Title field (default search scope) |
| 模糊/精确 | Fuzzy vs exact match modes |
| 时效性 | Effective status: 有效/已修改/已废止/尚未生效 |
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
