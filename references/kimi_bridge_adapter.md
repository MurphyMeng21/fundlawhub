# Kimi / Claude Code Environment Adapter

Use this adapter when running in Kimi Agent (cloud) or Claude Code with kimi-bridge.

## Browser Tools

Your environment provides these browser automation tools:

```
browser_visit(url)              # Load page, return element list
browser_click(element_index)    # Click element by index
browser_input(element_index, text)  # Type into input field
browser_scroll_up/down(amount)  # Scroll page
browser_find(keyword)           # Find text, scroll to it
browser_screenshot()            # Capture current view
browser_state()                 # List open tabs
```

All tools wait for page load automatically. Element indices are zero-based and recalculated after each scroll.

## Standard Workflow

### Search by Title

```python
# 1. Visit home page
browser_visit("https://flk.npc.gov.cn/index")

# 2. Find element indices from output, then:
browser_input({input_index}, "keyword")      # Type search term
browser_click({search_button_index})          # Click magnifying glass icon

# 3. On results page (/search):
# - Results appear with indices. Click a title:
browser_click({title_div_index})

# 4. On detail page (/detail):
# - Click 下载 button, then click 点击下载
browser_click({download_button_index})
browser_click({click_download_index})
```

### Batch ID Collection (Fastest for Large Tasks)

For collecting many law IDs (e.g., 200-300 files):

```python
# 1. Set page size to 100 (maximum)
browser_visit("https://flk.npc.gov.cn/search?keyword=xxx&size=100")

# 2. Scroll through results, extract IDs from the page
# IDs appear in the title div elements or can be inferred from links

# 3. Use pagination to go through all pages
# Look for page number elements and click next

# 4. Once you have all IDs, use the detail API or visit each detail page
# to get download URLs in batch
```

### Using the Download Script

Your environment can run Python. Use the bundled script:

```bash
# Get file URLs for a law
python scripts/download.py --info {bbbs_id}

# Output shows:
#   ossWordPath: https://flk.npc.gov.cn/prod/20231201/uuid.docx
#   ossPdfPath:  https://flk.npc.gov.cn/prod/20231201/uuid.pdf

# Download the file
python scripts/download.py "https://flk.npc.gov.cn/prod/.../uuid.docx" output.docx
```

Or in Python directly:

```python
import subprocess
result = subprocess.run(
    ["python", "scripts/download.py", "--info", bbbs_id],
    capture_output=True, text=True
)
print(result.stdout)  # Parse URLs from output
```

## File Storage

### Kimi Agent (Cloud)
- Files saved to `/mnt/agents/output/` are accessible to you
- Temporary files in `/tmp/` may be cleaned up
- For large collections: process in batches of 20-30, export periodically

### Claude Code (Local)
- Files saved to your local disk (current working directory)
- No cloud storage limits
- Preferred environment for 200-300 file collection tasks

## Tips

- **Element indices change after scroll**. Always re-read the page after scrolling.
- **Search suggestions** appear below the input as you type. You can click a suggestion or the search button.
- **Filters are on the left sidebar** of the search results page. Click to refine immediately.
- **For pagination**: Scroll to the bottom to find page controls. The dropdown for page size is at bottom-left.
- **Screenshot for debugging**: Use `browser_screenshot()` when unsure about element layout.
