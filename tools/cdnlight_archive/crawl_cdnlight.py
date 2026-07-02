#!/usr/bin/env python3
"""
CDN Lighting official website archive crawler.

Purpose:
- Crawl pages under https://www.cdnlight.com/
- Download same-domain HTML, images, CSS, JS, and product technical attachments
- Build manifest.csv and failed-urls.csv for checking completeness

Run:
python tools/cdnlight_archive/crawl_cdnlight.py --base https://www.cdnlight.com/ --out cdnlight-official-archive --max-pages 3000
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import sys
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qsl, quote, unquote, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

ATTACHMENT_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".rar", ".7z", ".ies", ".ldt", ".eulumdat", ".rfa", ".rvt",
    ".dwg", ".dxf", ".step", ".stp", ".skp", ".txt", ".csv",
}
ASSET_EXTENSIONS = {
    ".css", ".js", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".otf", ".mp4", ".webm",
}
HTML_CONTENT_TYPES = {"text/html", "application/xhtml+xml"}

URL_RE = re.compile(r"url\((['\"]?)(.*?)\1\)", re.I)
SRCSET_SPLIT_RE = re.compile(r"\s*,\s*")


@dataclass
class FetchResult:
    url: str
    final_url: str
    status: int
    content_type: str
    bytes_count: int
    local_path: str
    source_page: str
    category: str
    note: str = ""


def normalize_url(url: str) -> str:
    url = url.strip()
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    query = parsed.query
    fragment = ""
    return urlunparse((scheme, netloc, path, "", query, fragment))


def same_domain(url: str, base_netloc: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() == base_netloc


def clean_filename(name: str) -> str:
    name = unquote(name or "")
    name = name.replace("\\", "_").replace("/", "_")
    name = re.sub(r"[\x00-\x1f<>:\"|?*]+", "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:180] or "index"


def filename_from_content_disposition(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"filename\*=UTF-8''([^;]+)", value, re.I)
    if match:
        return clean_filename(match.group(1))
    match = re.search(r'filename="?([^";]+)"?', value, re.I)
    if match:
        return clean_filename(match.group(1))
    return None


def guess_category(url: str, content_type: str) -> str:
    path = urlparse(url).path.lower()
    ext = Path(path).suffix.lower()
    if ext in ATTACHMENT_EXTENSIONS:
        return "attachment"
    if ext in ASSET_EXTENSIONS:
        return "asset"
    if content_type.split(";")[0].strip().lower() in HTML_CONTENT_TYPES:
        return "html"
    if content_type:
        if any(key in content_type.lower() for key in ["pdf", "word", "excel", "zip", "octet-stream"]):
            return "attachment"
        if any(key in content_type.lower() for key in ["image", "javascript", "css", "font", "video"]):
            return "asset"
    return "other"


def is_probable_html_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    ext = Path(path).suffix.lower()
    return ext in {"", ".html", ".htm", ".aspx", ".asp", ".php"}


def local_path_for(url: str, out_dir: Path, category: str, content_type: str, disposition_name: str | None = None) -> Path:
    parsed = urlparse(url)
    path = parsed.path
    query = parsed.query
    query_hash = hashlib.sha1(query.encode("utf-8")).hexdigest()[:10] if query else ""

    if disposition_name:
        filename = disposition_name
        folder = out_dir / ("product-files" if category == "attachment" else category)
        return folder / filename

    parts = [clean_filename(part) for part in path.split("/") if part]
    if not parts:
        parts = ["index"]

    filename = parts[-1]
    ext = Path(filename).suffix

    if category == "html":
        if ext.lower() not in {".html", ".htm"}:
            filename = Path(filename).stem + (f"_{query_hash}" if query_hash else "") + ".html"
        elif query_hash:
            filename = Path(filename).stem + f"_{query_hash}" + ext
        base_folder = out_dir / "site"
    elif category == "attachment":
        if query_hash and not ext:
            filename = filename + f"_{query_hash}"
        base_folder = out_dir / "product-files"
    else:
        if query_hash:
            filename = Path(filename).stem + f"_{query_hash}" + ext
        base_folder = out_dir / "assets"

    folder_parts = parts[:-1]
    return base_folder.joinpath(*folder_parts, filename)


def extract_urls_from_html(html: str, page_url: str) -> set[str]:
    soup = BeautifulSoup(html, "html.parser")
    found: set[str] = set()

    attrs = ["href", "src", "data-src", "data-original", "poster"]
    for tag in soup.find_all(True):
        for attr in attrs:
            value = tag.get(attr)
            if value and not value.startswith(("#", "javascript:", "mailto:", "tel:")):
                found.add(urljoin(page_url, value))
        srcset = tag.get("srcset") or tag.get("data-srcset")
        if srcset:
            for item in SRCSET_SPLIT_RE.split(srcset):
                part = item.strip().split(" ")[0]
                if part:
                    found.add(urljoin(page_url, part))

    for style in soup.find_all("style"):
        found.update(extract_urls_from_css(style.get_text("\n"), page_url))

    for tag in soup.find_all(style=True):
        found.update(extract_urls_from_css(tag.get("style") or "", page_url))

    return {normalize_url(u) for u in found if urlparse(u).scheme in {"http", "https"}}


def extract_urls_from_css(css: str, page_url: str) -> set[str]:
    found: set[str] = set()
    for _, value in URL_RE.findall(css or ""):
        value = value.strip()
        if value and not value.startswith(("data:", "#")):
            found.add(urljoin(page_url, value))
    return {normalize_url(u) for u in found if urlparse(u).scheme in {"http", "https"}}


def write_csv(path: Path, rows: Iterable[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def crawl(base: str, out_dir: Path, max_pages: int, delay: float, timeout: int, max_file_mb: int) -> int:
    base = normalize_url(base)
    base_netloc = urlparse(base).netloc.lower()
    out_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({
        "User-Agent": "CDNLightingArchiveCrawler/1.0 (+official internal archive)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/*,*/*;q=0.8",
    })

    queue: deque[tuple[str, str]] = deque([(base, "seed")])
    seen: set[str] = set()
    manifest: list[dict] = []
    failed: list[dict] = []
    pages_crawled = 0
    max_bytes = max_file_mb * 1024 * 1024

    while queue:
        url, source_page = queue.popleft()
        url = normalize_url(url)
        if url in seen:
            continue
        if not same_domain(url, base_netloc):
            continue
        seen.add(url)

        try:
            response = session.get(url, timeout=timeout, stream=True, allow_redirects=True)
            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
            category = guess_category(response.url, content_type)
            disposition_name = filename_from_content_disposition(response.headers.get("content-disposition"))
            local_path = local_path_for(response.url, out_dir, category, content_type, disposition_name)
            local_path.parent.mkdir(parents=True, exist_ok=True)

            total = 0
            chunks: list[bytes] = []
            for chunk in response.iter_content(chunk_size=1024 * 128):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    raise RuntimeError(f"file larger than limit: {max_file_mb}MB")
                chunks.append(chunk)
            data = b"".join(chunks)

            local_path.write_bytes(data)

            result = FetchResult(
                url=url,
                final_url=normalize_url(response.url),
                status=response.status_code,
                content_type=content_type,
                bytes_count=len(data),
                local_path=str(local_path.as_posix()),
                source_page=source_page,
                category=category,
            )
            manifest.append(result.__dict__)

            if response.status_code >= 400:
                failed.append({"url": url, "source_page": source_page, "status": response.status_code, "error": "http error"})
                continue

            should_parse = category == "html" or (content_type in HTML_CONTENT_TYPES) or is_probable_html_url(url)
            if should_parse and (max_pages <= 0 or pages_crawled < max_pages):
                pages_crawled += 1
                try:
                    text = data.decode(response.encoding or "utf-8", errors="ignore")
                except Exception:
                    text = data.decode("utf-8", errors="ignore")
                urls = extract_urls_from_html(text, response.url)
                urls.update(extract_urls_from_css(text, response.url))
                for next_url in sorted(urls):
                    if same_domain(next_url, base_netloc) and next_url not in seen:
                        queue.append((next_url, url))

            if delay:
                time.sleep(delay)

        except Exception as exc:
            failed.append({"url": url, "source_page": source_page, "status": "", "error": str(exc)})

    fields = ["url", "final_url", "status", "content_type", "bytes_count", "local_path", "source_page", "category", "note"]
    write_csv(out_dir / "manifest.csv", manifest, fields)
    write_csv(out_dir / "failed-urls.csv", failed, ["url", "source_page", "status", "error"])

    print(f"Downloaded records: {len(manifest)}")
    print(f"Failed records: {len(failed)}")
    print(f"Archive folder: {out_dir}")
    return 0 if not failed else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive CDN Lighting official website content and technical files.")
    parser.add_argument("--base", default="https://www.cdnlight.com/", help="Base URL to crawl")
    parser.add_argument("--out", default="cdnlight-official-archive", help="Output folder")
    parser.add_argument("--max-pages", type=int, default=3000, help="Maximum HTML pages to parse; 0 means unlimited")
    parser.add_argument("--delay", type=float, default=0.25, help="Delay between requests in seconds")
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds")
    parser.add_argument("--max-file-mb", type=int, default=95, help="Skip files larger than this limit")
    args = parser.parse_args()
    return crawl(args.base, Path(args.out), args.max_pages, args.delay, args.timeout, args.max_file_mb)


if __name__ == "__main__":
    sys.exit(main())
