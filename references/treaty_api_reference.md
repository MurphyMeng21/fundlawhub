# 外交条约库 (treaty.mfa.gov.cn) 参考

## 数据源

- 官方站点：`https://treaty.mfa.gov.cn/web/`
- 数据格式：纯 HTML，无公开 JSON API
- 解析依赖：`beautifulsoup4`
- 缓存 namespace：`npc-law-db-treaty`

## 列表页

### URL 模式

| 集合 | URL 模板 |
|------|----------|
| 全部 | `allinfos.jsp?nPageIndex_={page}` |
| 双边 | `shuangbian.jsp?nPageIndex_={page}` |
| 多边 | `duobian.jsp?nPageIndex_={page}` |

基础 URL：`https://treaty.mfa.gov.cn/web/`

### 页码提取

总页数从页面文本中提取：

```regex
当前:\s*\d+\s*/\s*(\d+)\s*页
```

示例：`当前: 1/747 页` → 747 页。

### 列表项提取

列表页中每个条约对应一个 `<a>` 标签：

- `href` 属性包含 `detail`，指向详情页
- `title` 属性或标签文本为条约标题
- 使用 `urllib.parse.urljoin(BASE_URL, href)` 拼接完整 URL

## 详情页

### 容器

详情内容位于 `<div class="neirong">` 内。标题通常位于 `<p class="neirongp">`。

### 元数据字段

字段通过正则从 `div.neirong` 的文本中提取：

| 字段 | 正则 |
|------|------|
| 类别 | `类别：\s*([^\n]+)` |
| 领域 | `领域：\s*([^\n]+)` |
| 我国签署时间 | `我国签署时间：\s*([^\n]+)` |
| 条约生效时间 | `条约生效时间：\s*([^\n]+)` |
| 对我国生效时间 | `对我国生效时间：\s*([^\n]+)` |
| 保存机关 | `保存机关：\s*([^\n]+)` |
| 签署地点 | `签署地点：\s*([^\n]+)` |
| 港澳情况 | `港澳情况：\s*([^\n]+)` |
| 我国声明保留情况 | `我国声明保留情况：\s*([^\n]+)` |
| 其他 | `其他：\s*([^\n]+)` |

### PDF 预览链接

详情页中的 PDF 链接通过 `<a href="...pdf">` 提取。标签文字取自相邻元素或父元素文本。

## 输出文件

每个集合输出到独立目录：

```
treaty_output/
├── summary.json
├── logs/
└── {collection}/
    ├── metadata.jsonl
    ├── metadata.csv
    ├── stats_report.json
    ├── stats_report.md
    ├── summary.json
    └── files/
```

## 注意事项

- HTML 结构变更会直接影响解析。
- 详情页解析为每条约一次请求，批量任务请注意限速。
