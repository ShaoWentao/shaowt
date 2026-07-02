#!/usr/bin/env python3
"""
Product technical file crawler for CDN Lighting official website.

This script focuses on product pages and downloadable technical files.
It separates downloaded files, skipped large files, and broken links so the
workflow can still complete and commit useful CSV indexes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
import time
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse, unquote

import requests
from bs4 import BeautifulSoup

PRODUCT_HINTS = (
    "/SeriesParameters/",
    "/Products/",
    "/InteriorLighting/",
    "/ExteriorLighting/",
    "/SmartLighting/",
    "/DecorativeLighting/",
    "/CustomLighting/",
)

TECH_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".rar", ".7z", ".ies", ".ldt", ".eulumdat", ".rfa", ".rvt",
    ".dwg", ".dxf", ".step", ".stp", ".skp", ".txt", ".csv",
}

PAGE_EXTENSIONS = {"", ".html", ".htm", ".aspx", ".asp", ".php"}
URL_RE = re.compile(r"url\((['\"]?)(.*?)\1\)", re.I)
ITEM_ID_RE = re.compile(r"itemid[_=](\d+)", re.I)
PLCID_RE = re.compile(r"plcid[_=](\d+)", re.I)


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path or "/", "", parsed.query, ""))


def same_domain(url: str, base_netloc: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() == base_netloc


def clean_name(value: str) -> str:
    value = unquote(value or "")
    value = re.sub(r"[\x00-\x1f<>:\"|?*\\/]+", "_", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:160] or "file"


def is_product_related_url(url: str) -> bool:
    lowered = url.lower()
    return any(hint.lower() in lowered for hint in PRODUCT_HINTS)


def is_html_like(url: str) -> bool:
    return Path(urlparse(url).path.lower()).suffix in PAGE_EXTENSIONS


def is_tech_file(url: str, content_type: str = "") -> bool:
    ext = Path(urlparse(url).path.lower()).suffix
    if ext in TECH_EXTENSIONS:
        return True
    ctype = content_type.lower()
    return any(token in ctype for token in [
        "pdf", "word", "excel", "powerpoint", "zip", "rar", "octet-stream",
        "autocad", "dwg", "revit",
    ])


def classify_file(url: str, content_type: str = "") -> str:
    ext = Path(urlparse(url).path.lower()).suffix
    if ext in {".ies", ".ldt", ".eulumdat"}:
        return "photometry"
    if ext in {".rfa", ".rvt", ".dwg", ".dxf", ".step", ".stp", ".skp"}:
        return "cad-bim"
    if ext == ".pdf":
        return "pdf"
    if ext in {".doc", ".docx"}:
        return "word"
    if ext in {".xls", ".xlsx", ".csv"}:
        return "spreadsheet"
    if ext in {".zip", ".rar", ".7z"}:
        return "archive"
    return "other"


def product_key_from_url(url: str) -> str:
    parsed = urlparse(url)
    text = parsed.path + "?" + parsed.query
    item = ITEM_ID_RE.search(text)
    plc = PLCID_RE.search(text)
    if item:
        if plc:
            return f"plcid_{plc.group(1)}_itemid_{item.group(1)}"
        return f"itemid_{item.group(1)}"
    stem = clean_name(Path(parsed.path).stem)
    if stem and stem != "info":
        return stem
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]


def title_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(" ", strip=True)
    title = soup.find("title")
    if title and title.get_text(strip=True):
        return title.get_text(" ", strip=True)
    return ""


def extract_links(html: str, page_url: str) -> set[str]:
    soup = BeautifulSoup(html, "html.parser")
    found: set[str] = set()
    attrs = ["href", "src", "data-src", "data-original", "data-url", "data-href"]
    for tag in soup.find_all(True):
        for attr in attrs:
            value = tag.get(attr)
            if value and not value.startswith(("#", "javascript:", "mailto:", "tel:")):
                found.add(urljoin(page_url, value))
        srcset = tag.get("srcset") or tag.get("data-srcset")
        if srcset:
            for item in srcset.split(","):
                part = item.strip().split(" ")[0]
                if part:
                    found.add(urljoin(page_url, part))
        style = tag.get("style") or ""
        for _, value in URL_RE.findall(style):
            if value and not value.startswith("data:"):
                found.add(urljoin(page_url, value))
    for style_tag in soup.find_all("style"):
        for _, value in URL_RE.findall(style_tag.get_text("\n")):
            if value and not value.startswith("data:"):
                found.add(urljoin(page_url, value))
    return {normalize_url(u) for u in found if urlparse(u).scheme in {"http", "https"}}


def local_file_path(out_dir: Path, product_key: str, file_url: str, content_type: str) -> Path:
    parsed = urlparse(file_url)
    filename = clean_name(Path(parsed.path).name)
    if not Path(filename).suffix and parsed.query:
        filename += "_" + hashlib.sha1(parsed.query.encode("utf-8")).hexdigest()[:10]
    if not filename or filename == "file":
        filename = hashlib.sha1(file_url.encode("utf-8")).hexdigest()[:16]
    category = classify_file(file_url, content_type)
    return out_dir / "files" / product_key / category / filename


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def crawl(base: str, out_dir: Path, max_pages: int, delay: float, timeout: int, max_file_mb: int) -> int:
    base = normalize_url(base)
    base_netloc = urlparse(base).netloc.lower()
    session = requests.Session()
    session.headers.update({
        "User-Agent": "CDNLightingProductFileCrawler/1.1 (+official internal archive)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })

    out_dir.mkdir(parents=True, exist_ok=True)
    queue: deque[tuple[str, str]] = deque([(base, "seed")])
    seen_pages: set[str] = set()
    seen_files: set[str] = set()
    product_pages: list[dict] = []
    link_rows: list[dict] = []
    file_rows: list[dict] = []
    skipped: list[dict] = []
    failures: list[dict] = []
    max_bytes = max_file_mb * 1024 * 1024

    while queue and len(seen_pages) < max_pages:
        page_url, source_page = queue.popleft()
        page_url = normalize_url(page_url)
        if page_url in seen_pages or not same_domain(page_url, base_netloc):
            continue
        if page_url != base and not is_html_like(page_url):
            continue
        seen_pages.add(page_url)

        try:
            response = session.get(page_url, timeout=timeout)
            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
            if response.status_code >= 400:
                failures.append({"url": page_url, "source_page": source_page, "kind": "page", "status": response.status_code, "error": "http error"})
                continue
            if "html" not in content_type and not is_html_like(page_url):
                continue
            html = response.text
            product_key = product_key_from_url(page_url) if is_product_related_url(page_url) else "site"
            product_title = title_from_html(html)

            if is_product_related_url(page_url):
                product_pages.append({
                    "product_key": product_key,
                    "product_title": product_title,
                    "product_url": page_url,
                    "source_page": source_page,
                })

            links = extract_links(html, response.url)
            for link in sorted(links):
                if not same_domain(link, base_netloc):
                    continue
                if is_tech_file(link):
                    link_rows.append({
                        "product_key": product_key,
                        "product_title": product_title,
                        "product_page": page_url,
                        "file_url": link,
                        "file_type": classify_file(link),
                    })
                    if link not in seen_files:
                        seen_files.add(link)
                        try:
                            file_response = session.get(link, timeout=timeout, stream=True, allow_redirects=True)
                            file_type = file_response.headers.get("content-type", "").split(";")[0].strip().lower()
                            final_url = normalize_url(file_response.url)
                            status = file_response.status_code
                            content_length = file_response.headers.get("content-length")
                            expected_bytes = int(content_length) if content_length and content_length.isdigit() else ""

                            if status >= 400:
                                failures.append({"url": link, "source_page": page_url, "kind": "file", "status": status, "error": "http error"})
                                file_response.close()
                                continue
                            if isinstance(expected_bytes, int) and expected_bytes > max_bytes:
                                skipped.append({
                                    "product_key": product_key,
                                    "product_title": product_title,
                                    "product_page": page_url,
                                    "file_url": link,
                                    "final_url": final_url,
                                    "status": status,
                                    "content_type": file_type,
                                    "bytes_count": expected_bytes,
                                    "reason": f"larger than {max_file_mb}MB limit",
                                })
                                file_response.close()
                                continue

                            local_path = local_file_path(out_dir, product_key, file_response.url, file_type)
                            local_path.parent.mkdir(parents=True, exist_ok=True)
                            total = 0
                            chunks: list[bytes] = []
                            too_large = False
                            for chunk in file_response.iter_content(1024 * 128):
                                if not chunk:
                                    continue
                                total += len(chunk)
                                if total > max_bytes:
                                    too_large = True
                                    break
                                chunks.append(chunk)
                            if too_large:
                                skipped.append({
                                    "product_key": product_key,
                                    "product_title": product_title,
                                    "product_page": page_url,
                                    "file_url": link,
                                    "final_url": final_url,
                                    "status": status,
                                    "content_type": file_type,
                                    "bytes_count": total,
                                    "reason": f"larger than {max_file_mb}MB limit",
                                })
                                continue

                            data = b"".join(chunks)
                            local_path.write_bytes(data)
                            file_rows.append({
                                "product_key": product_key,
                                "product_title": product_title,
                                "product_page": page_url,
                                "file_url": link,
                                "final_url": final_url,
                                "file_type": classify_file(file_response.url, file_type),
                                "content_type": file_type,
                                "status": status,
                                "bytes_count": len(data),
                                "local_path": local_path.as_posix(),
                            })
                        except Exception as exc:
                            failures.append({"url": link, "source_page": page_url, "kind": "file", "status": "", "error": str(exc)})
                elif is_html_like(link):
                    if link not in seen_pages:
                        if link == base or is_product_related_url(link) or len(seen_pages) < 200:
                            queue.append((link, page_url))
            if delay:
                time.sleep(delay)
        except Exception as exc:
            failures.append({"url": page_url, "source_page": source_page, "kind": "page", "status": "", "error": str(exc)})

    write_csv(out_dir / "product-pages.csv", product_pages, ["product_key", "product_title", "product_url", "source_page"])
    write_csv(out_dir / "product-file-links.csv", link_rows, ["product_key", "product_title", "product_page", "file_url", "file_type"])
    write_csv(out_dir / "product-files.csv", file_rows, ["product_key", "product_title", "product_page", "file_url", "final_url", "file_type", "content_type", "status", "bytes_count", "local_path"])
    write_csv(out_dir / "skipped-product-files.csv", skipped, ["product_key", "product_title", "product_page", "file_url", "final_url", "status", "content_type", "bytes_count", "reason"])
    write_csv(out_dir / "failed-product-files.csv", failures, ["url", "source_page", "kind", "status", "error"])

    print(f"Product pages found: {len(product_pages)}")
    print(f"Product file links found: {len(link_rows)}")
    print(f"Product files downloaded: {len(file_rows)}")
    print(f"Skipped large files: {len(skipped)}")
    print(f"Failures: {len(failures)}")
    print(f"Output folder: {out_dir}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Download product technical files from CDN Lighting official website.")
    parser.add_argument("--base", default="https://www.cdnlight.com/", help="Base URL")
    parser.add_argument("--out", default="cdnlight-product-files", help="Output folder")
    parser.add_argument("--max-pages", type=int, default=5000, help="Maximum pages to check")
    parser.add_argument("--delay", type=float, default=0.25, help="Delay between page requests")
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout")
    parser.add_argument("--max-file-mb", type=int, default=95, help="Skip files larger than this limit")
    args = parser.parse_args()
    return crawl(args.base, Path(args.out), args.max_pages, args.delay, args.timeout, args.max_file_mb)


if __name__ == "__main__":
    sys.exit(main())
