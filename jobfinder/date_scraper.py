import json
import logging
import re
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
)

_RELATIVE_PATTERN = re.compile(
    r"(\d+)\s+(day|days|week|weeks|month|months)\s+ago", re.IGNORECASE
)

# Date-like value pattern (used in multiple steps below)
_DATE_VALUE = (
    r"(?:\d{4}-\d{2}-\d{2}(?:T[\d:+\-Z.]+)?"          # ISO 8601
    r"|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b"  # "May 7, 2026"
    r"|\b\d{1,2}/\d{1,2}/\d{2,4}\b)"                   # MM/DD/YY(YY)
)

# Known posting-date field names found in script tags / JSON blobs
_SCRIPT_DATE_FIELDS = re.compile(
    r'"(?:published_at|postedDate|post_date|posted_date|publishedAt'
    r'|datePosted|datePublished|open_date|job_posted_date)"\s*:\s*"(' + _DATE_VALUE + r')"',
    re.IGNORECASE,
)

# Words that signal a date is an expiry/deadline, not a post date
_EXPIRY_CONTEXT = re.compile(
    r"(expir|deadline|closing|close\s+date|apply\s+by|applications?\s+close"
    r"|valid\s+through|last\s+date|end\s+date)",
    re.IGNORECASE,
)

# Positive text context: "posted" or "published" with up to ~15 chars before the date
# Covers "Posted: DATE", "posted on DATE", "Published DATE", etc.
_POSTED_CONTEXT = re.compile(
    r"(?:posted|published|date\s+posted|listing\s+date|listing\s+posted)"
    r"[^,\n]{0,20}?(" + _DATE_VALUE + r")",
    re.IGNORECASE,
)


def scrape_post_date(url: str, driver=None) -> str | None:
    """
    Fetch a job listing page and attempt to extract its post date.
    Returns ISO "YYYY-MM-DD" or None.
    If driver (Selenium WebDriver) is provided, reuses it. Otherwise uses requests.
    """
    html = _fetch_html(url, driver)
    if not html:
        return None
    return _extract_date_from_html(html, url)


def _fetch_html(url: str, driver=None) -> str | None:
    if driver:
        try:
            driver.get(url)
            return driver.page_source
        except Exception as e:
            logger.warning("Driver fetch failed for %s: %s", url, e)
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
        if resp.status_code == 200:
            return resp.text
    except Exception as e:
        logger.warning("Requests fetch failed for %s: %s", url, e)
    return None


def _extract_date_from_html(html: str, url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")

    # 1. JSON-LD: datePosted / datePublished on any JobPosting node
    result = _try_json_ld(soup)
    if result:
        return result

    # 2. Script tag JSON blobs: published_at, postedDate, post_date, etc.
    result = _try_script_json(soup)
    if result:
        return result

    # 3. <meta property="article:published_time">
    result = _try_meta(soup, "article:published_time")
    if result:
        return result

    # 4. <meta name="date"> / <meta name="published_date">
    result = _try_meta_name(soup, "date") or _try_meta_name(soup, "published_date")
    if result:
        return result

    # 5. Board-specific CSS selectors
    result = _try_board_specific(soup, url)
    if result:
        return result

    # 6. <time datetime="..."> — only accept if the surrounding text suggests posting
    result = _try_time_datetime(soup)
    if result:
        return result

    # 7. Relative date anywhere in visible text ("3 days ago", "2 weeks ago")
    result = _try_relative_date(soup)
    if result:
        return result

    # 8. Last resort: scan visible text for a date preceded by "Posted" / "Published"
    result = _try_posted_context_scan(soup)
    if result:
        return result

    return None


def _try_json_ld(soup: BeautifulSoup) -> str | None:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            result = _search_ld_node(data)
            if result:
                return result
        except Exception:
            pass
    return None


def _search_ld_node(node) -> str | None:
    """Recursively find datePosted on any JobPosting in the JSON-LD tree."""
    if isinstance(node, list):
        for item in node:
            result = _search_ld_node(item)
            if result:
                return result
        return None
    if not isinstance(node, dict):
        return None
    if "@graph" in node:
        return _search_ld_node(node["@graph"])
    # datePosted is the post date; validThrough is expiry — intentionally ignored
    date_str = node.get("datePosted") or node.get("datePublished")
    if date_str:
        return _normalize_date(str(date_str))
    for value in node.values():
        if isinstance(value, (dict, list)):
            result = _search_ld_node(value)
            if result:
                return result
    return None


def _try_script_json(soup: BeautifulSoup) -> str | None:
    """
    Scan all <script> tags (not just JSON-LD) for known posting-date field names.
    Covers Greenhouse's published_at, and similar patterns on other boards.
    """
    for script in soup.find_all("script"):
        content = script.string or ""
        if not content:
            continue
        match = _SCRIPT_DATE_FIELDS.search(content)
        if match:
            result = _normalize_date(match.group(1))
            if result:
                return result
    return None


def _try_meta(soup: BeautifulSoup, prop: str) -> str | None:
    tag = soup.find("meta", property=prop)
    if tag and tag.get("content"):
        return _normalize_date(tag["content"])
    return None


def _try_meta_name(soup: BeautifulSoup, name: str) -> str | None:
    tag = soup.find("meta", attrs={"name": name})
    if tag and tag.get("content"):
        return _normalize_date(tag["content"])
    return None


def _try_board_specific(soup: BeautifulSoup, url: str) -> str | None:
    # Lever: <span class="sort-by-time">
    tag = soup.find(class_="sort-by-time")
    if tag:
        text = tag.get_text(strip=True)
        return _parse_relative_date(text) or _normalize_date(text)

    # LinkedIn: posted-time-ago__text
    tag = soup.find(class_="posted-time-ago__text")
    if tag:
        text = tag.get_text(strip=True)
        return _parse_relative_date(text) or _normalize_date(text)

    # Indeed: myJobsStateDate
    tag = soup.find(attrs={"data-testid": "myJobsStateDate"})
    if tag:
        text = tag.get_text(strip=True)
        return _parse_relative_date(text) or _normalize_date(text)

    return None


def _try_time_datetime(soup: BeautifulSoup) -> str | None:
    """Accept <time datetime="..."> unless the surrounding element suggests expiry."""
    for tag in soup.find_all("time", attrs={"datetime": True}):
        parent_text = tag.parent.get_text(" ", strip=True) if tag.parent else ""
        if _EXPIRY_CONTEXT.search(parent_text):
            continue
        return _normalize_date(tag["datetime"])
    return None


def _try_relative_date(soup: BeautifulSoup) -> str | None:
    """Find relative dates anywhere in visible text."""
    text = soup.get_text(" ", strip=True)
    return _parse_relative_date(text)


def _try_posted_context_scan(soup: BeautifulSoup) -> str | None:
    """Find a date that immediately follows 'posted', 'published', etc."""
    text = soup.get_text(" ", strip=True)
    match = _POSTED_CONTEXT.search(text)
    if match:
        return _normalize_date(match.group(1))
    return None


def _parse_relative_date(text: str) -> str | None:
    match = _RELATIVE_PATTERN.search(text)
    if not match:
        return None
    n = int(match.group(1))
    unit = match.group(2).lower().rstrip("s")
    today = date.today()
    if unit == "day":
        delta = timedelta(days=n)
    elif unit == "week":
        delta = timedelta(weeks=n)
    elif unit == "month":
        delta = timedelta(days=n * 30)
    else:
        return None
    return (today - delta).isoformat()


def _normalize_date(raw: str) -> str | None:
    if not raw:
        return None
    try:
        parsed = dateutil_parser.parse(raw, fuzzy=True)
        return parsed.date().isoformat()
    except Exception:
        return None
