#!/usr/bin/env python3
"""
Shared utilities for npc-law-db scripts.

Provides: cache, rate limiting, HTTP client, file I/O, text utilities.
Used by: download.py, treaty_crawler.py, gov_rules_crawler.py, article_search.py
"""

import argparse
import csv
import hashlib
import json
import logging
import os
import random
import re
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from io import BytesIO
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse
from xml.etree import ElementTree as ET

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

VERIFY_SSL = os.getenv("NPC_LAW_VERIFY_SSL", "0") == "1"
NO_CACHE = os.getenv("NPC_LAW_NO_CACHE", "0") == "1"
MAX_RETRIES = 4
BASE_BACKOFF = 1.0
MAX_BACKOFF = 30.0

SAFE_CHAR_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
EM_TAG_RE = re.compile(r"</?em[^>]*>", re.IGNORECASE)
SPACE_RE = re.compile(r"\s+")

# ---------------------------------------------------------------------------
# Text / filename utilities
# ---------------------------------------------------------------------------


def sanitize_filename(name: str, fallback: str = "unnamed") -> str:
    name = SAFE_CHAR_RE.sub("_", name).strip().rstrip(".")
    return name or fallback


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def clean_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " | ".join(clean_text(item) for item in value if clean_text(item))
    text = str(value)
    text = EM_TAG_RE.sub("", text)
    text = SPACE_RE.sub(" ", text).strip()
    return text


def decode_filename_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    values = parse_qs(parsed.query).get("response-content-disposition")
    if not values:
        return None
    disposition = values[0]
    match = re.search(r'filename="([^"]+)"', disposition, re.IGNORECASE)
    if not match:
        return None
    filename = match.group(1)
    try:
        filename = unquote(unquote(filename))
    except Exception:
        filename = unquote(filename)
    return sanitize_filename(filename)


def redact_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return url
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def format_request_exception(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    url = getattr(response, "url", "")
    status_code = getattr(response, "status_code", None)
    if url:
        redacted = redact_url(url)
        if status_code is not None:
            return f"{exc.__class__.__name__}: status={status_code} url={redacted}"
        return f"{exc.__class__.__name__}: url={redacted}"
    return str(exc)


def extract_year(value: str) -> str:
    match = re.search(r"(\d{4})", clean_text(value))
    return match.group(1) if match else "未知"


# ---------------------------------------------------------------------------
# File I/O helpers
# ---------------------------------------------------------------------------


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                fieldnames.append(key)
                seen.add(key)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    index = 2
    while True:
        candidate = path.with_name(f"{stem}__{index}{suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def render_markdown_report(title: str, sections: list) -> str:
    lines = [f"# {title}", ""]
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.extend([f"生成时间：{generated_at}", ""])
    for heading, payload in sections:
        lines.append(f"## {heading}")
        if isinstance(payload, str):
            lines.extend([payload, ""])
            continue
        if isinstance(payload, dict):
            for key, value in payload.items():
                lines.append(f"- {key}: {value}")
            lines.append("")
            continue
        if isinstance(payload, list):
            if payload and isinstance(payload[0], dict):
                for row in payload:
                    name = row.get("name", "")
                    count = row.get("count", "")
                    extra = row.get("extra", "")
                    text = f"- {name}: {count}"
                    if extra:
                        text += f" ({extra})"
                    lines.append(text)
            else:
                for row in payload:
                    lines.append(f"- {row}")
            lines.append("")
            continue
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Cache manager
# ---------------------------------------------------------------------------


class _CacheManager:
    """File-based cache with TTL support."""

    def __init__(self, enabled: bool = True, namespace: str = "npc-law-db"):
        self.enabled = enabled and not NO_CACHE
        self.dir = Path.home() / ".cache" / namespace
        if self.enabled:
            self.dir.mkdir(parents=True, exist_ok=True)

    def _key(self, *parts: str) -> str:
        raw = "|".join(parts)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _path(self, key: str, suffix: str = ".json") -> Path:
        return self.dir / f"{key}{suffix}"

    def get(self, key: str, max_age: float = 3600):
        if not self.enabled:
            return None
        path = self._path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if time.time() - data.get("_cached_at", 0) > max_age:
                return None
            return data.get("payload")
        except Exception:
            return None

    def set(self, key: str, payload: dict) -> None:
        if not self.enabled:
            return
        try:
            self._path(key).write_text(
                json.dumps({"_cached_at": time.time(), "payload": payload}, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def get_file(self, key: str, max_age: float = 604800) -> bytes | None:
        if not self.enabled:
            return None
        path = self._path(key, ".bin")
        meta_path = self._path(key, ".meta")
        if not path.exists() or not meta_path.exists():
            return None
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if time.time() - meta.get("cached_at", 0) > max_age:
                return None
            return path.read_bytes()
        except Exception:
            return None

    def set_file(self, key: str, data: bytes) -> None:
        if not self.enabled:
            return
        try:
            self._path(key, ".bin").write_bytes(data)
            self._path(key, ".meta").write_text(
                json.dumps({"cached_at": time.time()}), encoding="utf-8"
            )
        except Exception:
            pass

    def clear(self) -> None:
        import shutil
        if self.dir.exists():
            shutil.rmtree(self.dir)
            self.dir.mkdir(parents=True, exist_ok=True)

    def stats(self) -> dict:
        if not self.dir.exists():
            return {"entries": 0, "size_kb": 0}
        entries = list(self.dir.iterdir())
        total_size = sum(f.stat().st_size for f in entries if f.is_file())
        return {"entries": len(entries) // 2, "size_kb": round(total_size / 1024, 1)}


_cache = _CacheManager()


def get_cache(namespace: str = "npc-law-db") -> _CacheManager:
    if namespace == "npc-law-db":
        return _cache
    return _CacheManager(namespace=namespace)


# ---------------------------------------------------------------------------
# Smart Rate Limiter
# ---------------------------------------------------------------------------


class _RateLimitMode(Enum):
    AUTO = auto()
    OFF = auto()
    FIXED = auto()
    ADAPTIVE = auto()


@dataclass
class _RateLimitConfig:
    fixed_rps: float = 5.0
    adaptive_initial_rps: float = 5.0
    adaptive_min_rps: float = 1.0
    adaptive_max_rps: float = 8.0
    small_task_threshold: int = 10
    large_task_threshold: int = 100
    backoff_on_429: float = 2.0


class _SmartRateLimiter:
    """Task-size-aware rate limiter: no throttle for small tasks, auto-throttle for large."""

    def __init__(self, config: Optional[_RateLimitConfig] = None):
        self.cfg = config or _RateLimitConfig()
        self.mode: _RateLimitMode = _RateLimitMode.OFF
        self._current_rps: float = self.cfg.adaptive_initial_rps
        self._consecutive_success: int = 0
        self._consecutive_429: int = 0
        self._last_request_time: float = 0
        self._total_requests: int = 0
        self._limited_requests: int = 0
        self._start_time: Optional[float] = None
        self._429_count: int = 0

    @staticmethod
    def estimate_task_size(**kwargs) -> int:
        total = 0
        if kwargs.get("search"):
            pages = max(1, (kwargs.get("size", 20) + 99) // 100)
            total += pages
            if kwargs.get("urls_only"):
                avg_per_page = min(100, kwargs.get("size", 20))
                total += pages * avg_per_page
        if "download_list" in kwargs:
            total += len(kwargs["download_list"])
        if "info_list" in kwargs:
            total += len(kwargs["info_list"])
        if "preview_list" in kwargs:
            total += len(kwargs["preview_list"])
        if "article_count" in kwargs:
            total += kwargs["article_count"]
        if kwargs.get("info"):
            total += 1
        if kwargs.get("download"):
            total += 1
        if kwargs.get("preview"):
            total += 1
        if kwargs.get("article"):
            total += 1
        return max(1, total)

    def init_for_task(self, estimated_requests: int,
                      forced_mode: Optional[_RateLimitMode] = None) -> _RateLimitMode:
        if forced_mode:
            self.mode = forced_mode
        else:
            if estimated_requests <= self.cfg.small_task_threshold:
                self.mode = _RateLimitMode.OFF
            elif estimated_requests <= self.cfg.large_task_threshold:
                self.mode = _RateLimitMode.FIXED
            else:
                self.mode = _RateLimitMode.ADAPTIVE
        self._current_rps = self.cfg.adaptive_initial_rps
        self._consecutive_success = 0
        self._consecutive_429 = 0
        self._last_request_time = 0
        self._total_requests = 0
        self._limited_requests = 0
        self._start_time = time.time()
        self._429_count = 0
        return self.mode

    def mode_desc(self) -> str:
        return {
            _RateLimitMode.OFF: "off (small task)",
            _RateLimitMode.FIXED: f"fixed {self.cfg.fixed_rps:.0f} req/s",
            _RateLimitMode.ADAPTIVE: f"adaptive ({self._current_rps:.1f} req/s)",
            _RateLimitMode.AUTO: "auto",
        }.get(self.mode, "unknown")

    def acquire(self):
        if self.mode == _RateLimitMode.OFF:
            return
        self._total_requests += 1
        interval = 1.0 / (self._current_rps if self.mode == _RateLimitMode.ADAPTIVE
                          else self.cfg.fixed_rps)
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < interval:
            time.sleep(interval - elapsed)
            self._limited_requests += 1
        self._last_request_time = time.time()

    def report_success(self, response_time_ms: float = 0):
        if self.mode != _RateLimitMode.ADAPTIVE:
            return
        self._consecutive_success += 1
        self._consecutive_429 = 0
        if self._consecutive_success >= 5 and response_time_ms < 500:
            self._current_rps = min(self._current_rps * 1.1, self.cfg.adaptive_max_rps)
            self._consecutive_success = 0

    def report_429(self):
        self._429_count += 1
        self._consecutive_success = 0
        self._consecutive_429 += 1
        exp = min(BASE_BACKOFF * (2 ** (self._consecutive_429 - 1)), MAX_BACKOFF)
        jitter = random.uniform(0, exp * 0.3)
        backoff = max(0.1, exp + jitter)
        print(f"  [429] Rate limited. Backing off {backoff:.1f}s..."
              f" (strike {self._consecutive_429})", file=sys.stderr)
        time.sleep(backoff)
        if self.mode == _RateLimitMode.ADAPTIVE:
            self._current_rps = max(self._current_rps * 0.6, self.cfg.adaptive_min_rps)
            print(f"  [Adaptive] Reduced to {self._current_rps:.1f} req/s", file=sys.stderr)

    def report_slow(self, response_time_ms: float):
        if self.mode == _RateLimitMode.ADAPTIVE and response_time_ms > 2000:
            self._current_rps = max(self._current_rps * 0.85, self.cfg.adaptive_min_rps)

    def print_summary(self):
        if self._total_requests == 0:
            return
        elapsed = time.time() - (self._start_time or time.time())
        actual_rps = self._total_requests / elapsed if elapsed > 0 else 0
        r429 = f" | 429s: {self._429_count}" if self._429_count else ""
        print(f"\n[RateLimit] {self.mode_desc()} | "
              f"{self._total_requests} requests in {elapsed:.1f}s "
              f"({actual_rps:.1f} req/s){r429}",
              file=sys.stderr)


# ---------------------------------------------------------------------------
# Global limiter + HTTP request helper
# ---------------------------------------------------------------------------

_limiter: Optional[_SmartRateLimiter] = None


def _get_limiter() -> _SmartRateLimiter:
    if _limiter is None:
        return _SmartRateLimiter()
    return _limiter


def init_limiter(mode_str: str = "auto", **kwargs):
    global _limiter
    config = _RateLimitConfig(**kwargs) if kwargs else None
    _limiter = _SmartRateLimiter(config)
    mode_map = {
        "off": _RateLimitMode.OFF,
        "fixed": _RateLimitMode.FIXED,
        "adaptive": _RateLimitMode.ADAPTIVE,
        "auto": _RateLimitMode.AUTO,
    }
    forced = None
    if mode_str in mode_map and mode_map[mode_str] != _RateLimitMode.AUTO:
        forced = mode_map[mode_str]
    return _limiter, forced


def _backoff(attempt: int) -> float:
    exp = min(BASE_BACKOFF * (2 ** (attempt - 1)), MAX_BACKOFF)
    jitter = random.uniform(0, exp * 0.3)
    return max(0.1, exp + jitter)


RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def http_request(method, url, headers=None, **kwargs):
    """Make an HTTP request with rate limiting, 429 handling, and retries."""
    kwargs.setdefault("timeout", kwargs.pop("timeout", 30))
    kwargs.setdefault("verify", VERIFY_SSL)

    limiter = _get_limiter()
    limiter.acquire()

    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            start = time.time()
            resp = requests.request(method, url, headers=headers, **kwargs)
            elapsed_ms = (time.time() - start) * 1000

            if resp.status_code == 429:
                limiter.report_429()
                last_err = "HTTP 429"
                if attempt < MAX_RETRIES:
                    continue
                raise RuntimeError(f"HTTP 429 Too Many Requests after {MAX_RETRIES} retries")

            if resp.status_code in RETRYABLE_STATUS_CODES:
                last_err = f"HTTP {resp.status_code}"
                if attempt < MAX_RETRIES:
                    time.sleep(_backoff(attempt))
                    continue
                raise RuntimeError(f"HTTP {resp.status_code} after {MAX_RETRIES} retries")

            limiter.report_success(elapsed_ms)

            if elapsed_ms > 2000:
                limiter.report_slow(elapsed_ms)

            if resp.status_code < 500:
                return resp

            last_err = f"HTTP {resp.status_code}"
        except requests.RequestException as e:
            last_err = format_request_exception(e)

        if attempt < MAX_RETRIES:
            time.sleep(_backoff(attempt))

    raise RuntimeError(f"Request failed after {MAX_RETRIES} attempts: {last_err}")


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------


def add_rate_limit_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--rate-limit",
        choices=["auto", "off", "fixed", "adaptive"],
        default="auto",
        help="Rate limiting mode (default: auto)",
    )


def add_output_arg(parser: argparse.ArgumentParser, default: str = ".") -> None:
    parser.add_argument("-o", "--output", default=default, help="Output directory")


def add_no_cache_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--no-cache", action="store_true", help="Disable cache")


def add_common_cli_args(parser: argparse.ArgumentParser) -> None:
    add_rate_limit_arg(parser)
    add_output_arg(parser)
    add_no_cache_arg(parser)


# ---------------------------------------------------------------------------
# Chinese numeral conversion
# ---------------------------------------------------------------------------

_CN_NUMERALS = {
    "零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
    "十": 10, "百": 100, "千": 1000, "万": 10000,
}
_CN_NUMBERS = {}


def chinese_to_int(cn: str) -> int:
    if not cn:
        return 0
    if cn in _CN_NUMBERS:
        return _CN_NUMBERS[cn]
    total = 0
    partial = 0
    for ch in cn:
        val = _CN_NUMERALS.get(ch, 0)
        if val >= 10:
            if partial == 0:
                partial = 1
            total += partial * val
            partial = 0
        else:
            partial = partial * 10 + val if partial else val
    total += partial
    return total


def int_to_chinese(n: int) -> str:
    if n <= 0:
        return ""
    if n in _CN_NUMBERS:
        return _CN_NUMBERS[n]
    if n < 10:
        return ["", "一", "二", "三", "四", "五", "六", "七", "八", "九"][n]
    if n < 20:
        return "十" + ("" if n == 10 else int_to_chinese(n - 10))
    if n < 100:
        tens, ones = divmod(n, 10)
        return int_to_chinese(tens) + "十" + ("" if ones == 0 else int_to_chinese(ones))
    if n < 1000:
        hunds, rest = divmod(n, 100)
        prefix = int_to_chinese(hunds) + "百"
        if rest == 0:
            return prefix
        if rest < 10:
            return prefix + "零" + int_to_chinese(rest)
        if rest < 20:
            return prefix + "一" + int_to_chinese(rest)
        return prefix + int_to_chinese(rest)
    if n < 10000:
        thous, rest = divmod(n, 1000)
        prefix = int_to_chinese(thous) + "千"
        if rest == 0:
            return prefix
        if rest < 100:
            return prefix + "零" + int_to_chinese(rest)
        return prefix + int_to_chinese(rest)
    return str(n)


for _i in range(1, 200):
    _CN_NUMBERS[_i] = int_to_chinese(_i)


# ---------------------------------------------------------------------------
# Logger setup
# ---------------------------------------------------------------------------


def setup_logger(output_root: Path, name: str = "law_crawler") -> logging.Logger:
    ensure_dir(output_root)
    ensure_dir(output_root / "logs")
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers = []
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    file_handler = logging.FileHandler(output_root / "logs" / "run.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    return logger


# ---------------------------------------------------------------------------
# DOCX / article helpers
# ---------------------------------------------------------------------------


def extract_paragraphs_from_docx(content: bytes) -> list:
    """Extract text paragraphs. Supports .docx (ZIP) and .doc (OLE) formats."""
    if content[:4] == b"PK\x03\x04":  # ZIP = DOCX
        with zipfile.ZipFile(BytesIO(content), "r") as z:
            with z.open("word/document.xml") as f:
                tree = ET.parse(f)
        W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        return ["".join(t.text for t in p.iter(f"{W}t") if t.text)
                for p in tree.iter(f"{W}p")
                if any(t.text for t in p.iter(f"{W}t"))]

    # Old .doc format - try antiword or catdoc
    for tool in ["antiword", "catdoc"]:
        try:
            result = subprocess.run([tool, "-"], input=content, capture_output=True, timeout=30)
            if result.returncode == 0:
                text = result.stdout.decode("utf-8", errors="replace")
                if text.strip():
                    return [line for line in text.split("\n") if line.strip()]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    raise RuntimeError(
        "File is in old .doc format (not .docx) and no conversion tool found. "
        "Install antiword or catdoc: apt-get install antiword catdoc"
    )


def is_article_line(line: str) -> bool:
    return bool(re.match(r"^第[一二三四五六七八九十百千万零\d]+条", line.strip()))


def extract_article_number(line: str) -> str:
    m = re.match(r"(第[一二三四五六七八九十百千万零\d]+条)", line.strip())
    return m.group(1) if m else line[:20]


def split_into_articles(paragraphs: list) -> list:
    articles = []
    current_num = "题注/前言"
    current_lines = []
    for line in paragraphs:
        line_stripped = line.strip()
        if not line_stripped:
            continue
        if is_article_line(line_stripped):
            if current_lines:
                articles.append((current_num, "\n".join(current_lines)))
            current_num = extract_article_number(line_stripped)
            current_lines = [line_stripped]
        else:
            current_lines.append(line_stripped)
    if current_lines:
        articles.append((current_num, "\n".join(current_lines)))
    return articles


def match_article_query(query: str, article_number: str) -> bool:
    query = query.strip()
    if query in article_number:
        return True
    m = re.match(r"^第(\d+)条$", query)
    if m:
        n = int(m.group(1))
        return f"第{int_to_chinese(n)}条" == article_number or f"第{n}条" == article_number
    if re.match(r"^\d+$", query):
        n = int(query)
        return f"第{int_to_chinese(n)}条" == article_number
    if re.match(r"^[一二三四五六七八九十百千万零]+$", query):
        return f"第{query}条" == article_number
    return False
