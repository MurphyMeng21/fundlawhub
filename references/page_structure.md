# Page Structure Guide

Full visual map of each page for planning navigation strategies.

## Home Page (/index)

```
+----------------------------------------------------------+
|  [Logo]  国家法律法规数据库          [说明]  [纠错]       |
+----------------------------------------------------------+
|                                                          |
|              [Scope] [Search Input     ] [Q] [高级检索]  |
|               标题     请输入...          🔍               |
|              ○精确  ○模糊                                |
|                                                          |
+----------+----------+----------+----------+----------+---+
|  宪法    |  法律    | 行政法规 | 监察法规 | 地方法规 | 司|
|          |   310    |   610    |    2     |  15780   | 法|
+----------+----------+----------+----------+----------+---+
|                                                          |
|  新法速递                    热门查询    热门下载        |
|  • 最新法规1 (date)          • 民法典 (date)             |
|  • 最新法规2 (date)          • 刑法 (date)              |
|                                                          |
|           [法律草案征求意见]  [审查建议在线提交]          |
|                                                          |
|              相关链接：国家规章库 | 条约数据库            |
+----------------------------------------------------------+
```

### Key Elements

- **Search input** (center, wide): Text entry. On type: shows suggestion dropdown below
- **Scope dropdown** (left of input): 标题(title), 正文(content), etc. Default: 标题
- **Search button** (magnifying glass icon, right of input): Triggers search → /search
- **Mode radios** (below input): 精确(exact) / 模糊(fuzzy). Default: 精确
- **高级检索** button: Opens /advanceSearch page
- **Category cards** (6 cards below search): Click to browse all in that category
- **新法速递**: Recently added laws with dates
- **热门查询/热门下载**: Popular laws, clickable

### Search Suggestions Dropdown

When typing in the search input, a dropdown appears below with:
- Matching law titles (each is clickable, goes to detail or search)
- Related search terms

Click a suggestion to execute search. Click search button (🔍) to search current input text.

---

## Search Results Page (/search)

```
+----------------------------------------------------------+
|  [Scope][Input          ] [🔍] [高级检索]                |
+----------------------------------------------------------+
|  检索条件：模糊 | 标题：xxx          [清空条件]          |
+----------------------------------------------------------+
|  排序：[默认][分类][机关][时效][公布日期][施行日期]      |
|  [全选]  批量下载文件  批量导出文件目录                   |
+----------------------------------------------------------+
|                                                          |
|  ☑ 法规标题                              [状态]          |
|     公布日期：xxxx-xx-xx | 施行日期：xxxx-xx-xx         |
|     地方法规 | 制定机关                                  |
|     [命中展示] [相关资料]                                |
|                                                          |
|  ☑ 法规标题2...                                          |
|                                                          |
+----------+-----------------------------------------------+
|  20条/页 | 共 N 条   前往 [__] 页   1  2  3  4...      |
+----------+-----------------------------------------------+
|  法律法规分类 | 制定机关 | 时效性 | 公布年份             |
|  ☑宪法      | ☑全国人大| ☑尚未生| ☑2020-2026          |
|  ☑法律      | ☑国务院  | ☑有效  | ☑2010-2019          |
|  ☑行政法规  | ☑监察委  | ☑已修改| ☑2000-2009          |
|  ☑监察法规  | ☑最高法  | ☑已废止| ...                 |
|  ☑地方法规  | ☑最高检  |        |                      |
|  ☑司法解释  | ☑地方人大|        |                      |
+----------+-----------------------------------------------+
```

### Left Sidebar Filters

- **法律法规分类**: Checkbox tree (宪法, 法律, 行政法规, 监察法规, 地方法规, 司法解释)
- **制定机关**: Checkbox (全国人大及其常委会, 国务院, 国家监察委员会, 最高人民法院, 最高人民检察院, 地方人大及其常委会)
- **时效性**: Checkbox (尚未生效, 有效, 已修改, 已废止)
- **公布年份**: Checkbox groups by decade (2020-2026, 2010-2019, etc.)

Click any filter to refine results immediately.

### Sort Bar

6 sort options as clickable buttons: 默认排序, 法律法规分类, 制定机关, 时效性, 公布日期, 施行日期
Click to sort; click again to reverse order.

### Batch Actions

- **全选** checkbox: Select all visible items on current page
- **批量下载文件**: Download selected items as a combined file
- **批量导出文件目录**: Export a catalog/list of selected items

### Pagination

- **Page size dropdown**: 10/20/30/40/50/100 per page (bottom left)
- **Page numbers**: 1, 2, 3... click to navigate
- **Jump input**: Enter page number and confirm
- **Total count**: "共 N 条" shown above pagination

### Result Item Structure

Each result contains:
- Checkbox for selection
- Title (clickable → detail page)
- Status badge (有效/已废止/尚未生效)
- 公布日期 (publish date)
- 施行日期 (effective date)
- 法律法规分类 (category)
- 制定机关 (issuing authority)
- 命中展示 button: Show where keyword matched
- 相关资料 button: Show related documents

---

## Detail Page (/detail?id={bbbs})

```
+----------------------------------------------------------+
|  [Logo]  国家法律法规数据库          [说明]  [纠错]       |
+----------------------------------------------------------+
|                                                          |
|              法规标题                        [状态标签]   |
|  ====================================================    |
|  法律法规分类：xxx    制定机关：xxx                       |
|  公布日期：xxxx-xx-xx    施行日期：xxxx-xx-xx             |
|                                                          |
|  [目录] [下载]                    [WPS版本] [公报原版]   |
|                                                          |
|  +--------------------------------------------------+    |
|  |  Zoom: - 100% +    [查找...] [...]                |  |
|  |                                                  |    |
|  |              法规全文 (28 pages)                  |    |
|  |                                                  |    |
|  |  第一章  总则                                     |    |
|  |  第一条  xxxxxx                                   |    |
|  |  ...                                              |    |
|  +--------------------------------------------------+    |
|                                                          |
|  关联推荐：                                              |
|  • 相关法规1  [状态]  分类  日期                        |
|  • 相关法规2  [状态]  分类  日期                        |
|                                                          |
+----------------------------------------------------------+
```

### Top Metadata Bar

- **法规标题**: Law title
- **Status badge**: 有效(green) / 已废止 / 尚未生效(yellow)
- **法律法规分类**: Category
- **制定机关**: Issuing authority
- **公布日期**: Publish date
- **施行日期**: Effective date

### Action Buttons

| Button | Function |
|--------|----------|
| 目录 | Toggle table of contents sidebar |
| 下载 | Open download options panel |
| WPS版本 | Show WPS-formatted version (default) |
| 公报原版 | Show official gazette version |

### Download Panel (appears when 下载 clicked)

```
+-----------+
| [⬇]       |
| 点击下载   |   [QR code]
|            |   扫码下载
+-----------+
```

Click "点击下载" to download the current version (WPS or gazette).

### Document Viewer

- Page counter: "1/28" style
- Zoom: - 100% + controls
- 查找: Search within document
- Full text rendered as paginated view

### Related Laws (关联推荐)

Right sidebar shows related laws with: title, status badge, category, date. Click to navigate.

---

## Advanced Search Page (/advanceSearch)

```
+----------------------------------------------------------+
|  高级检索                                                |
+----------------------------------------------------------+
|  [并且] 法律标题：    [________________] [模糊▼] [+]    |
|  [并且] 法律全文：    [________________] [模糊▼] [+]    |
|  [并且] 相关资料标题：[________________] [模糊▼] [+]    |
|  [并且] 相关资料全文：[________________] [模糊▼] [+]    |
|  [并且] 公布日期：    [____] - [____]              [+]  |
|  [并且] 施行日期：    [____] - [____]              [+]  |
|  [并且] 法律法规分类：[请选择... ▼]                  [+]  |
|  [并且] 制定机关：    [请选择... ▼]                  [+]  |
|  [并且] 时效性：      [ ]尚未生效 [ ]有效 [ ]已修改 [ ]已废止 |
|                                                          |
|              [   确 定   ]  [   重 置   ]               |
|              [收起]                                      |
|                                                          |
+----------------------------------------------------------+
|  (Results area - same as search results page)            |
+----------------------------------------------------------+
```

### Logic Operators

Each field row starts with a dropdown: **并且**(AND) / **或者**(OR) / **不含**(NOT)

### Field Features

- Title/full-text fields: Support 精确/模糊 toggle
- Date fields: Start date - End date range
- Category/issuing authority: Dropdown select
- Status: Multi-checkbox
- [+] button: Add another condition of same type

### Action Buttons

- **确定**: Execute search
- **重置**: Clear all fields
- **收起**: Collapse search panel, show results only

After search executes, results appear below with the same layout as /search page.
