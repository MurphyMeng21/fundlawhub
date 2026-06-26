# Codex 浏览器环境适配器

运行在 Codex Desktop 或 Chrome 插件时使用此适配器。

## 浏览器工具入口

Codex 通过 `mcp__node_repl__js`（Node REPL）提供浏览器控制能力。**没有 `browser_navigate`、`browser_type`、`browser_click` 这类独立工具**。所有浏览器操作都通过 `tab` 对象的 Playwright API 完成。

**入口：`mcp__node_repl__js`（Node REPL 内的 js 执行工具）**

## 引导（Bootstrap）

首次使用浏览器前，先加载 `browser-client` 运行时。只需运行一次：

```js
const { setupBrowserRuntime } = await import(
  // 实际路径由插件版本号决定，agent 运行时会自动找到
  "<plugin-root>/scripts/browser-client.mjs"
);
await setupBrowserRuntime({ globals: globalThis });

// 获取浏览器实例
globalThis.browser = await agent.browsers.get("iab");  // Codex Desktop in-app browser
// 或
globalThis.browser = await agent.browsers.get("extension");  // Chrome 插件

// 阅读完整 API 参考
nodeRepl.write(await browser.documentation());
```

## 核心 API 映射

| 操作 | Kimi Bridge 写法 | Codex 实际写法 |
|------|-----------------|----------------|
| 打开页面 | `browser_visit(url)` | `tab.goto(url)` |
| 截图 | `browser_screenshot()` | `tab.screenshot({ fullPage: true })` 并用 `nodeRepl.emitImage(bytes)` 展示 |
| 输入文字 | `browser_input(index, text)` | `tab.playwright.getByRole("textbox", { name: "请输入" }).fill("关键词")` 或 `tab.playwright.locator("input").fill("文本")` |
| 按键盘 | — | `tab.playwright.locator.press("Enter")` |
| 点击 | `browser_click(index)` | `tab.playwright.getByText("目标").click()` 或 `tab.playwright.locator(".selector").click()` |
| 滚动 | `browser_scroll_down(n)` | `tab.playwright.locator("target").scrollIntoViewIfNeeded()` 或 `tab.playwright.evaluate(() => window.scrollBy(0, 300))` |
| 查找元素 | `browser_find(keyword)` | `tab.playwright.domSnapshot()`（返回可访问性快照文本）或 `tab.playwright.getByText("内容")` |
| 获取页标题 | — | `tab.title()` |
| 获取页面 URL | — | `tab.url()` |
| 等页面加载 | — | `tab.playwright.waitForLoadState({ state: "load" })` |
| 固定等待 | — | `tab.playwright.waitForTimeout(ms)` |
| 执行 JS | — | `tab.playwright.evaluate(fn)` |
| 打开新标签 | — | `browser.tabs.new()` |
| 列出标签 | `browser_state()` | `browser.tabs.list()` 或 `browser.user.openTabs()` |

## 标准工作流

### 按标题搜索

```js
// 1. 打开首页
await tab.goto("https://flk.npc.gov.cn/index");
await tab.playwright.waitForLoadState({ state: "load" });

// 2. 在搜索框中输入关键词
const searchBox = tab.playwright.getByRole("textbox", { name: "请输入" });
await searchBox.fill("物业管理条例");

// 3. 按回车触发搜索
// 注意：页面上的 🔍 图标实际导航到高级检索页（/advanceSearch），不要点它
await searchBox.press("Enter");
await tab.playwright.waitForTimeout(2000);

// 4. 通过 DOM 快照检查搜索结果
const snapshot = await tab.playwright.domSnapshot();
// 快照返回类似：
//   text: 北京市
//   emphasis: 物业
//   emphasis: 管理条例
//   generic: 有效
//   generic: 公布日期：2024-03-29
//   ...

// 5. 点击目标法规标题进入详情页
// 搜索结果中的标题是复合节点（纯文本 + <em> 高亮标签），需要用 evaluate 定位
await tab.playwright.evaluate(() => {
  const labels = document.querySelectorAll(".el-checkbox__label");
  for (const label of labels) {
    if (label.textContent.includes("北京市") && label.textContent.includes("物业管理条例")) {
      label.click();
      return;
    }
  }
});
await tab.playwright.waitForTimeout(2000);

// 6. 在详情页下载文件
// 先点"下载"按钮，再点"点击下载"
await tab.playwright.evaluate(() => {
  const spans = document.querySelectorAll("span");
  for (const span of spans) {
    if (span.textContent.trim() === "下载") { span.click(); break; }
  }
});
await tab.playwright.waitForTimeout(1000);
await tab.playwright.evaluate(() => {
  const divs = document.querySelectorAll("div");
  for (const div of divs) {
    if (div.textContent.trim() === "点击下载") { div.click(); break; }
  }
});
```

### 使用截图验证状态

```js
const pngBytes = await tab.screenshot({ fullPage: true });
await nodeRepl.emitImage(pngBytes);
```

### 批量采集（200-300 条）

**阶段一：通过浏览器收集所有法规 ID**

```js
// 1. 搜索 + 每页设 100 条
await tab.goto("https://flk.npc.gov.cn/index");
const searchBox = tab.playwright.getByRole("textbox", { name: "请输入" });
await searchBox.fill("物业管理条例");
await searchBox.press("Enter");
await tab.playwright.waitForTimeout(2000);

// 2. 翻到页面底部，选定 100 条/页
await tab.playwright.evaluate(() => {
  // 找到分页下拉框，点开
  const pagination = document.querySelector(".el-pagination .el-select");
  if (pagination) pagination.click();
});
await tab.playwright.waitForTimeout(500);
await tab.playwright.evaluate(() => {
  // 选择 100 条/页
  const items = document.querySelectorAll(".el-select-dropdown__item");
  for (const item of items) {
    if (item.textContent.trim().startsWith("100")) { item.click(); break; }
  }
});
await tab.playwright.waitForTimeout(2000);

// 3. 提取当前页所有 bbbs ID
const pageIds = await tab.playwright.evaluate(() => {
  const items = document.querySelectorAll("[data-id]");
  return Array.from(items).map(el => el.getAttribute("data-id"));
});

// 4. 翻页继续提取...
// 点击"下一页"按钮，重复步骤 3
```

**阶段二：通过 Python 脚本从 API 批量下载**

```bash
# 对每个收集到的 bbbs ID 获取详情
python scripts/download.py --info {bbbs_id}

# 下载文件
python scripts/download.py --download {bbbs_id} --format docx output.doc
```

### 读取 DOM 辅助信息

```js
// 读取页面标题
const title = await tab.title();

// 读取特定元素文本
const text = await tab.playwright.getByText("关键词").textContent();

// 批量读取列表文本
const items = await tab.playwright.locator(".result-item .title").allTextContents();

// 用 evaluate 直接操作 DOM（只读）
const data = await tab.playwright.evaluate(() => {
  return Array.from(document.querySelectorAll("[data-id]")).map(el => ({
    id: el.getAttribute("data-id"),
    text: el.textContent?.trim()
  }));
});
```

## 已知问题和注意事项

1. **不存在独立浏览器工具**：Codex 没有 `browser_navigate`、`browser_type`、`browser_click` 等独立工具名，所有操作都通过 Node REPL 内 `tab.playwright.*` 完成，或通过 `@chrome` 自然语言指令（Chrome 插件模式）。

2. **🔍 搜索按钮 ≠ 标准搜索**：首页输入框后缀区域的放大镜图标点击后实际导航到 `/advanceSearch`（高级检索），而不是标准搜索结果页 `/search`。**请用回车键** `press("Enter")` 触发标准搜索。

3. **搜索结果标题是复合 DOM 节点**：匹配的文字被拆成 `<em>` 高亮标签 + 纯文本节点。不能用简单的 `getByText("北京市物业管理条例")` 一次性定位。推荐用 `evaluate` 遍历节点的 `textContent` 做匹配。

4. **保持 `tab` 引用**：一次 bootstrap 后 `tab` 变量跨 Node REPL 调用保持有效。不需要每次都重新获取，除非发生 reset 或主动切换标签页。

5. **优先用 API 路径**：`scripts/download.py` 的 API 方式比自己用浏览器导航+点击更可靠。浏览器方案仅作为 API 失败或需要 UI 交互时的回退。

6. **标签页清理**：浏览器使用结束后调用 `browser.tabs.finalize({ keep })` 释放资源。只保留用户需要看到的标签页。
