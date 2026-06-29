# 国家规章库 (gov.cn/zhengce/xxgk/gjgzk) 参考

## 数据源

- 官方站点：`https://www.gov.cn/zhengce/xxgk/gjgzk/`
- 数据格式：私有 Athena API + 详情页 HTML
- 认证方式：动态 RSA（从首页 JS bundle 中提取参数）
- 解析依赖：`beautifulsoup4`, `cryptography`
- 缓存 namespace：`npc-law-db-govrules`

## 认证流程

### 1. 获取首页 JS bundle

访问 `https://www.gov.cn/zhengce/xxgk/gjgzk/index.htm?searchWord=`，从 HTML 中提取：

```regex
<script src="(index\.js\?[^"]+)"></script>
```

### 2. 提取认证参数

下载 JS bundle 后，用正则提取三个参数：

```regex
var s="(?P<base>https://[^"]+)",o=encodeURIComponent\(a\("(?P<pub>[^"]+)","(?P<seed>[^"]+)"\)\),c=encodeURIComponent\("(?P<name>[^"]+)"\)
```

- `base`：API 基础 URL
- `pub`：Base64 编码的 RSA 公钥
- `seed`：待加密的随机字符串
- `name`：应用名称

### 3. 生成 app_key

1. 将 `pub` 包装为 PEM 格式公钥
2. 使用 RSA PKCS1v15 加密 `seed`
3. Base64 编码加密结果
4. URL-quote 后得到 `app_key`

### 4. 请求头

所有 Athena API 请求需携带：

```http
athenaappname: {app_name}
athenaappkey: {app_key}
Content-Type: application/json;charset=UTF-8
Referer: https://www.gov.cn/
```

## 搜索接口

```
POST {base_url}/athena/forward/BD8730CDDA12515E2D9E1B21AA11C0D6
```

### 请求体关键字段

| 字段 | 说明 |
|------|------|
| `code` | 固定值 `"18258ab0ac9"` |
| `searchFields` | 搜索条件数组 |
| `sorts` | 排序规则 |
| `resultFields` | 返回字段列表 |
| `trackTotalHits` | `"true"` |
| `tableName` | `"t_1860c735d31"` |
| `pageSize` | 每页条数（默认 500） |
| `pageNo` | 页码 |
| `granularity` | `"ALL"` |

### searchFields 字段映射

| fieldName | 含义 |
|-----------|------|
| `f_202321807875` | 规章分类：部门规章 / 地方政府规章 |
| `f_202321360426` | 标题 |
| `f_202321758948` | 正文摘要 |
| `f_202321423473` | 文号 |
| `f_202321159816` | 其他标识 |
| `f_20232380533` | 主题词 |
| `f_202328191239` | 发文机关 |
| `f_20221110222856` | 其他机关 |

### 响应结构

```json
{
  "resultCode": {"code": 200},
  "result": {
    "data": {
      "list": [...],
      "pager": {
        "total": 12345,
        "pageCount": 25
      }
    }
  }
}
```

## 详情页

详情页 URL 在搜索结果字段 `doc_pub_url` 中。页面主体内容位于 `.pages_content`。

附件通过选择器提取：

```css
a[href][appendix="true"], a[href][data-appendix="true"]
```

## 输出文件

每个分类输出到独立目录：

```
gov_rules_output/
├── summary.json
├── logs/
└── {category}/
    ├── metadata.jsonl
    ├── metadata.csv
    ├── stats_report.json
    ├── stats_report.md
    ├── summary.json
    └── files/
        └── {rule_title}/
            ├── page.html
            ├── page.txt
            └── attachments...
```

## 注意事项

- JS bundle 中的认证参数可能过期，长时间运行若遇到 401/403 需重新调用认证发现。
- Athena API 字段名可能随 gov.cn 前端更新而变化。
- 搜索时使用 `f_202321807875` 过滤分类（部门规章/地方政府规章）。
