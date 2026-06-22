#!/usr/bin/env python3
"""Update reports.json from the official Congress.gov CRS Reports API."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE_URL = "https://api.congress.gov/v3"
API_KEY_ENV = "CONGRESS_API_KEY"
OUTPUT_FILE = Path("reports.json")
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
class Report:
    id: str
    title: str
    publication_date: str
    category: str
    summary: str
    url: str


def api_get(path: str, api_key: str, params: dict[str, str | int] | None = None) -> dict[str, Any]:
    query = {"api_key": api_key, "format": "json"}
    if params:
        query.update(params)

    url = f"{API_BASE_URL}{path}?{urlencode(query)}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "CRS-Daily-Reports/1.0",
        },
    )

    with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def get_value(data: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in data and data[name] not in (None, ""):
            return data[name]
    return ""


def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return as_text(get_value(value, "name", "title", "label", "url"))
    if isinstance(value, list):
        return ", ".join(part for part in (as_text(item) for item in value) if part)
    return str(value).strip()


def normalize_date(value: Any) -> str:
    text = as_text(value)
    if not text:
        return ""

    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
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


def extract_reports_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    reports = get_value(payload, "CRSReports", "crsReports", "reports", "results")
    return reports if isinstance(reports, list) else []


def extract_detail(payload: dict[str, Any]) -> dict[str, Any]:
    report = get_value(payload, "CRSReport", "crsReport", "report")
    return report if isinstance(report, dict) else payload


def report_number(data: dict[str, Any]) -> str:
    return as_text(get_value(data, "number", "reportNumber", "id", "productNumber"))


def normalize_report(data: dict[str, Any]) -> Report:
    title = as_text(get_value(data, "title", "name"))
    summary = as_text(get_value(data, "summary", "description", "abstract"))
    topics = get_value(data, "topics", "topic")

    return Report(
        id=report_number(data),
        title=title or "Untitled CRS Report",
        publication_date=normalize_date(get_value(data, "publishDate", "publicationDate", "date")),
        category=normalize_category(topics, title, summary),
        summary=summary or "Summary not available from the Congress.gov API response.",
        url=extract_pdf_url(data),
    )


def fetch_crs_reports(api_key: str, limit: int, days: int | None) -> list[Report]:
    params: dict[str, str | int] = {
        "limit": min(limit, 250),
        "offset": 0,
    }

    if days:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        params["fromDateTime"] = since.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    list_payload = api_get("/crsreport", api_key, params)
    list_items = extract_reports_list(list_payload)
    if not list_items:
        raise RuntimeError("The CRS report list endpoint returned no report records.")

    reports: list[Report] = []
    for item in list_items[:limit]:
        number = report_number(item)
        detail = item

        if number:
            try:
                detail_payload = api_get(f"/crsreport/{number}", api_key)
                detail = extract_detail(detail_payload)
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
                print(f"Warning: using list metadata for {number}: {error}", file=sys.stderr)

        reports.append(normalize_report(detail))

    return dedupe_reports(reports)


def dedupe_reports(reports: list[Report]) -> list[Report]:
    seen: set[str] = set()
    unique: list[Report] = []

    for report in reports:
        key = report.id or report.url or report.title
        if key in seen:
            continue
        seen.add(key)
        unique.append(report)

    return unique


def write_reports_json(reports: list[Report]) -> None:
    data = [
        {
            "id": report.id,
            "title": report.title,
            "publicationDate": report.publication_date,
            "category": report.category,
            "summary": report.summary,
            "url": report.url,
        }
        for report in reports
    ]
    OUTPUT_FILE.write_text(json.dumps(data, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Update reports.json from the Congress.gov CRS Reports API.")
    parser.add_argument("--limit", type=int, default=25, help="maximum number of CRS reports to fetch")
    parser.add_argument("--days", type=int, default=14, help="only request reports updated in the last N days")
    parser.add_argument("--api-key", help=f"Congress.gov API key; defaults to ${API_KEY_ENV}")
    args = parser.parse_args()

    api_key = args.api_key or os.getenv(API_KEY_ENV)
    if not api_key:
        print(f"Missing API key. Set {API_KEY_ENV} or pass --api-key.", file=sys.stderr)
        return 1

    try:
        reports = fetch_crs_reports(api_key, max(1, args.limit), args.days)
        write_reports_json(reports)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as error:
        print(f"Update failed: {error}", file=sys.stderr)
        return 1

    print(f"Updated {OUTPUT_FILE} with {len(reports)} CRS reports.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
