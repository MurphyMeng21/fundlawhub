# Codex Chrome Plugin Environment Adapter

Use this adapter when running in Codex with the Chrome browser plugin.

## Browser Tool Mapping

Codex controls Chrome directly. Tool names differ from Kimi. Map as follows:

| Kimi Tool | Codex Equivalent | Notes |
|-----------|-----------------|-------|
| `browser_visit(url)` | `browser_navigate(url)` or `@chrome open {url}` | Navigate to URL |
| `browser_click(index)` | `browser_click(x, y)` or element selector | Codex may use coordinates or CSS selectors |
| `browser_input(index, text)` | `browser_type(selector, text)` or `@chrome type {text}` | Text input |
| `browser_scroll_down(amount)` | `browser_scroll(x, y, dx, dy)` or `@chrome scroll {amount}` | Scroll page |
| `browser_find(keyword)` | `browser_find(keyword)` or manual scroll+search | Find text on page |
| `browser_screenshot()` | `browser_screenshot()` or `@chrome screenshot` | Capture view |
| `browser_state()` | Check Chrome tabs manually | Tab management |

**Important**: Codex's Chrome plugin may use natural language commands like:
- `@chrome open https://flk.npc.gov.cn`
- `@chrome click the search button`
- `@chrome type "劳动合同法" into the search box`
- `@chrome scroll down`

Adapt the workflow below to your Codex tool format. The **page structure** and **element locations** remain the same regardless of tool syntax.

## Standard Workflow

### Search by Title

```
# 1. Open home page
browser_navigate("https://flk.npc.gov.cn/index")
# or: @chrome open flk.npc.gov.cn

# 2. Type keyword in the center search input
browser_type("input[placeholder*='请输入']", "keyword")
# or: @chrome type "keyword" in the search box

# 3. Click the magnifying glass search button (right of input)
browser_click("button.search-btn")  # or by coordinates
# or: @chrome click the search button

# 4. Wait for /search results page to load
# Screenshot to verify results appeared

# 5. Click a law title to enter detail page
browser_click("div.law-title:contains('目标法规')")
# or: @chrome click the law titled "xxx"

# 6. On detail page, click 下载, then click 点击下载
browser_click("span:contains('下载')")
# Wait for download panel, then:
browser_click("div:contains('点击下载')")
# File downloads to Chrome's default download folder
```

### Batch ID Collection (Fastest Approach)

For 200-300 files, use this two-phase strategy:

**Phase 1: Collect all IDs via browser**

```
# 1. Search with large page size
browser_navigate("https://flk.npc.gov.cn/search")
browser_type("search-input", "your-keyword")
browser_click("search-button")

# 2. Change page size to 100 (maximum)
# Scroll to bottom, find "20条/页" dropdown, select "100条/页"

# 3. For each page:
#    - Screenshot or extract all law titles and their IDs
#    - Click next page
#    - Repeat until done

# 4. Compile a list of all bbbs IDs
```

**Phase 2: Batch download via script + API**

```bash
# Use the bundled Python script with Codex's Python execution
python scripts/download.py --info {bbbs_id_1}
python scripts/download.py --info {bbbs_id_2}
# ... for each ID, collect file URLs

# Then download each file
python scripts/download.py "{file_url_1}" "output_1.docx"
python scripts/download.py "{file_url_2}" "output_2.docx"
```

Or create a batch script in Codex:

```python
import subprocess, json, os

ids = [...]  # Your collected bbbs IDs
os.makedirs("downloads", exist_ok=True)

for i, bbbs_id in enumerate(ids):
    result = subprocess.run(
        ["python", "scripts/download.py", "--info", bbbs_id],
        capture_output=True, text=True
    )
    # Parse output to extract ossWordPath URL
    # Then download: browser_navigate(url) or python requests
    print(f"[{i+1}/{len(ids)}] Processed {bbbs_id}")
```

## File Storage

- Files download to **Chrome's default download folder**
- Use `@chrome download` or check `~/Downloads/` (macOS) / `C:\Users\{user}\Downloads\` (Windows)
- For organization: Create a target folder and move downloaded files there
- **Advantage over cloud**: No storage limits, files persist permanently

## Codex-Specific Tips

- **Chrome is your real browser**: If automation fails, you can manually click in Chrome while Codex watches
- **Screenshots are crucial**: Use `@chrome screenshot` frequently to verify state
- **Natural language works**: Codex often understands "click the search button" better than element indices
- **Console access**: Open Chrome DevTools (F12) to run JavaScript for extracting data:
  ```javascript
  // Extract all law IDs from current search page
  Array.from(document.querySelectorAll('[data-id]')).map(el => el.dataset.id)
  ```
- **URL manipulation**: Codex can directly navigate to constructed URLs, e.g.:
  ```
  @chrome open https://flk.npc.gov.cn/detail?id={bbbs_id}
  ```

## Browser Console Method (for API Discovery)

Since you have full Chrome access, use DevTools Console to discover APIs:

1. Open Chrome DevTools (F12) → Network tab
2. Perform an action on the website (e.g., search, download)
3. Watch the Network tab for API requests
4. Right-click → Copy → Copy as cURL (fetch)
5. Paste into Codex to replicate

See `references/api_reference.md` → "Browser Console Method" section for detailed steps.
