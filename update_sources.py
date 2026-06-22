#!/usr/bin/env python3
"""Update sources.json from Congress.gov and configured public feeds."""

from __future__ import annotations

import argparse
import email.utils
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE_URL = "https://api.congress.gov/v3"
API_KEY_ENV = "CONGRESS_API_KEY"
CONFIG_FILE = Path("sources_config.json")
OUTPUT_FILE = Path("sources.json")
REQUEST_TIMEOUT = 30

TOPIC_MAP = {
    "Defense and National Security": "Defense",
    "Defense & Intelligence": "Defense",
    "Economics and Public Finance": "Economy",
    "Economy & Finance": "Economy",
    "Foreign Affairs": "Foreign Policy",
    "Health Policy": "Healthcare",
    "Health Care": "Healthcare",
    "Science and Technology Policy": "Technology",
    "Science & Technology": "Technology",
}

KEYWORD_CATEGORY_MAP = {
    "Defense": ["defense", "military", "army", "navy", "air force", "dod", "intelligence"],
    "Economy": ["economy", "finance", "tax", "budget", "debt", "inflation", "banking"],
    "Foreign Policy": ["foreign", "diplomacy", "international", "china", "russia", "iran", "ukraine"],
    "Healthcare": ["health", "medicare", "medicaid", "drug", "hospital", "insurance"],
    "Technology": ["technology", "science", "cyber", "artificial intelligence", "semiconductor"],
}


@dataclass
class SourceItem:
    id: str
    source: str
    title: str
    publication_date: str
    category: str
    summary: str
    url: str


def api_get(path: str, api_key: str, params: dict[str, str | int] | None = None) -> dict[str, Any]:
    query = {"api_key": api_key, "format": "json"}
    if params:
        query.update(params)

    request = Request(
        f"{API_BASE_URL}{path}?{urlencode(query)}",
        headers={"Accept": "application/json", "User-Agent": "US-Policy-Research-Dashboard/1.0"},
    )
    with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_url(url: str) -> bytes:
    request = Request(
        url,
        headers={
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
            "User-Agent": "Mozilla/5.0 (compatible; US-Policy-Research-Dashboard/1.0)",
        },
    )
    with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        return response.read()


def get_value(data: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in data and data[name] not in (None, ""):
            return data[name]
    return ""


def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return clean_text(value)
    if isinstance(value, dict):
        return as_text(get_value(value, "name", "title", "label", "url"))
    if isinstance(value, list):
        return ", ".join(part for part in (as_text(item) for item in value) if part)
    return clean_text(str(value))


def clean_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", unescape(value))
    return re.sub(r"\s+", " ", text).strip()


def shorten(value: str, max_length: int = 420) -> str:
    if len(value) <= max_length:
        return value
    return value[: max_length - 1].rsplit(" ", 1)[0] + "..."


def normalize_date(value: Any) -> str:
    text = as_text(value)
    if not text:
        return ""

    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%B %d, %Y",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass

    try:
        parsed = email.utils.parsedate_to_datetime(text)
        if parsed:
            return parsed.date().isoformat()
    except (TypeError, ValueError):
        pass

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return text[:10] if len(text) >= 10 else ""


def normalize_category(topics: Any, title: str, summary: str) -> str:
    topic_text = as_text(topics)
    for topic in [part.strip() for part in topic_text.split(",") if part.strip()]:
        if topic in TOPIC_MAP:
            return TOPIC_MAP[topic]

    haystack = f"{topic_text} {title} {summary}".lower()
    for category, keywords in KEYWORD_CATEGORY_MAP.items():
        if any(keyword in haystack for keyword in keywords):
            return category
    return topic_text.split(",")[0].strip() if topic_text else "Other"


def parse_xml_feed(content: bytes) -> ET.Element:
    text = content.decode("utf-8", errors="replace")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    if re.search(r"<html[\s>]", text[:1000], flags=re.IGNORECASE):
        raise ValueError("feed URL returned HTML instead of RSS/Atom XML")

    def replace_named_entity(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in {"amp", "lt", "gt", "quot", "apos"}:
            return match.group(0)
        replacement = unescape(match.group(0))
        return replacement if replacement != match.group(0) else ""

    text = re.sub(r"&([A-Za-z][A-Za-z0-9]+);", replace_named_entity, text)
    text = re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;|#[0-9]+;|#x[0-9A-Fa-f]+;)", "&amp;", text)
    return ET.fromstring(text.encode("utf-8"))


def extract_reports_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    reports = get_value(payload, "CRSReports", "crsReports", "reports", "results")
    return reports if isinstance(reports, list) else []


def extract_detail(payload: dict[str, Any]) -> dict[str, Any]:
    report = get_value(payload, "CRSReport", "crsReport", "report")
    return report if isinstance(report, dict) else payload


def report_number(data: dict[str, Any]) -> str:
    return as_text(get_value(data, "number", "reportNumber", "id", "productNumber"))


def extract_pdf_url(data: dict[str, Any]) -> str:
    formats = get_value(data, "formats", "format")
    if isinstance(formats, list):
        for item in formats:
            if not isinstance(item, dict):
                continue
            item_type = as_text(get_value(item, "type", "name")).lower()
            item_url = as_text(get_value(item, "url", "link"))
            if item_url and ("pdf" in item_type or item_url.lower().endswith(".pdf")):
                return item_url
        for item in formats:
            if isinstance(item, dict):
                item_url = as_text(get_value(item, "url", "link"))
                if item_url:
                    return item_url
    return as_text(get_value(data, "url", "reportUrl"))


def fetch_crs_items(api_key: str | None, limit: int, days: int | None) -> list[SourceItem]:
    if not api_key:
        print(f"Warning: {API_KEY_ENV} is not set; skipping CRS.", file=sys.stderr)
        return []

    params: dict[str, str | int] = {"limit": min(limit, 250), "offset": 0}
    if days:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        params["fromDateTime"] = since.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    payload = api_get("/crsreport", api_key, params)
    items = extract_reports_list(payload)
    results: list[SourceItem] = []

    for item in items[:limit]:
        number = report_number(item)
        detail = item
        if number:
            try:
                detail = extract_detail(api_get(f"/crsreport/{number}", api_key))
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
                print(f"Warning: using CRS list metadata for {number}: {error}", file=sys.stderr)

        title = as_text(get_value(detail, "title", "name"))
        summary = as_text(get_value(detail, "summary", "description", "abstract"))
        topics = get_value(detail, "topics", "topic")
        results.append(
            SourceItem(
                id=number,
                source="Congressional Research Service",
                title=title or "Untitled CRS Report",
                publication_date=normalize_date(get_value(detail, "publishDate", "publicationDate", "date")),
                category=normalize_category(topics, title, summary),
                summary=shorten(summary or "Summary not available from the Congress.gov API response."),
                url=extract_pdf_url(detail),
            )
        )

    return results


def xml_text(element: ET.Element, names: tuple[str, ...]) -> str:
    wanted = {name.split("}")[-1] for name in names}
    for name in names:
        child = element.find(name)
        if child is not None:
            value = clean_text(" ".join(child.itertext()))
            if value:
                return value
    for child in list(element):
        if child.tag.split("}")[-1] in wanted:
            value = clean_text(" ".join(child.itertext()))
            if value:
                return value
            if "term" in child.attrib:
                return clean_text(child.attrib["term"])
    return ""


def xml_link(element: ET.Element) -> str:
    link = xml_text(element, ("link", "{http://www.w3.org/2005/Atom}link"))
    if link:
        return link
    for child in element.findall("{http://www.w3.org/2005/Atom}link"):
        href = child.attrib.get("href", "").strip()
        if href:
            return href
    for child in list(element):
        if child.tag.split("}")[-1] == "link":
            href = child.attrib.get("href", "").strip()
            if href:
                return href
    return ""


def parse_feed(source_name: str, feed_url: str, limit: int) -> list[SourceItem]:
    root = parse_xml_feed(fetch_url(feed_url))
    entries = root.findall("./channel/item") or root.findall("{http://www.w3.org/2005/Atom}entry")
    items: list[SourceItem] = []

    for entry in entries:
        title = xml_text(entry, ("title", "{http://www.w3.org/2005/Atom}title"))
        summary = xml_text(
            entry,
            (
                "description",
                "summary",
                "{http://www.w3.org/2005/Atom}summary",
                "{http://www.w3.org/2005/Atom}content",
                "{http://purl.org/rss/1.0/modules/content/}encoded",
            ),
        )
        category = xml_text(entry, ("category", "{http://www.w3.org/2005/Atom}category"))
        url = xml_link(entry)
        published = xml_text(
            entry,
            (
                "pubDate",
                "published",
                "updated",
                "{http://www.w3.org/2005/Atom}published",
                "{http://www.w3.org/2005/Atom}updated",
                "{http://purl.org/dc/elements/1.1/}date",
            ),
        )
        url = url or feed_url
        summary = summary or "Description not available from the source feed."
        if not title or not url:
            continue

        items.append(
            SourceItem(
                id=url or f"{source_name}:{title}",
                source=source_name,
                title=title,
                publication_date=normalize_date(published),
                category=normalize_category(category, title, summary),
                summary=shorten(summary),
                url=url,
            )
        )
        if len(items) >= limit:
            break

    return items


def load_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        raise RuntimeError(f"Missing {CONFIG_FILE}.")
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def fetch_feed_items(config: dict[str, Any], per_source_limit: int) -> list[SourceItem]:
    results: list[SourceItem] = []
    for source in config.get("sources", []):
        if source.get("type") != "rss":
            continue

        name = source["name"]
        feed_url = source.get("feed_url", "")
        if not feed_url:
            print(f"Warning: no feed URL configured for {name}; skipping.", file=sys.stderr)
            continue

        try:
            items = parse_feed(name, feed_url, per_source_limit)
            if not items:
                print(f"Warning: {name} feed returned no usable entries: {feed_url}", file=sys.stderr)
                continue
            print(f"Fetched {len(items)} items from {name}.", file=sys.stderr)
            results.extend(items)
        except (ET.ParseError, HTTPError, URLError, TimeoutError, ValueError) as error:
            print(f"Warning: failed to read {name} feed {feed_url}: {error}", file=sys.stderr)

    return results


def dedupe_items(items: list[SourceItem]) -> list[SourceItem]:
    seen: set[str] = set()
    unique: list[SourceItem] = []
    for item in items:
        key = item.url or f"{item.source}:{item.title}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def sort_items(items: list[SourceItem]) -> list[SourceItem]:
    return sorted(items, key=lambda item: item.publication_date or "0000-00-00", reverse=True)


def write_sources_json(items: list[SourceItem]) -> None:
    data = [
        {
            "id": item.id,
            "source": item.source,
            "title": item.title,
            "publicationDate": item.publication_date,
            "category": item.category,
            "summary": item.summary,
            "url": item.url,
        }
        for item in items
    ]
    OUTPUT_FILE.write_text(json.dumps(data, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Update sources.json from CRS and configured policy feeds.")
    parser.add_argument("--crs-limit", type=int, default=5, help="maximum CRS reports to fetch")
    parser.add_argument("--feed-limit", type=int, default=5, help="maximum feed entries per source")
    parser.add_argument("--days", type=int, default=14, help="CRS API lookback window in days")
    parser.add_argument("--api-key", help=f"Congress.gov API key; defaults to ${API_KEY_ENV}")
    args = parser.parse_args()

    try:
        config = load_config()
        api_key = args.api_key or os.getenv(API_KEY_ENV)
        items: list[SourceItem] = []
        try:
            crs_items = fetch_crs_items(api_key, max(1, args.crs_limit), args.days)
            if crs_items:
                print(f"Fetched {len(crs_items)} items from Congressional Research Service.", file=sys.stderr)
            items.extend(crs_items)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as error:
            print(f"Warning: failed to read Congressional Research Service API: {error}", file=sys.stderr)

        items.extend(fetch_feed_items(config, max(1, args.feed_limit)))
        items = sort_items(dedupe_items(items))
        if not items:
            raise RuntimeError("No source items were fetched.")
        write_sources_json(items)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as error:
        print(f"Update failed: {error}", file=sys.stderr)
        return 1

    print(f"Updated {OUTPUT_FILE} with {len(items)} policy research items.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
