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

_DATE_VALUE = (
    r"(?:\d{4}-\d{2}-\d{2}(?:T[\d:+\-Z.]+)?"
    r"|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b"
    r"|\b\d{1,2}/\d{1,2}/\d{2,4}\b)"
)

_SCRIPT_DATE_FIELDS = re.compile(
    r'"(?:published_at|postedDate|post_date|posted_date|publishedAt'
    r'|datePosted|datePublished|open_date|job_posted_date)"\s*:\s*"(' + _DATE_VALUE + r')"',
    re.IGNORECASE,
)

# Script tag field patterns for non-date metadata
_SCRIPT_TITLE = re.compile(r'"(?:title|job_title|jobTitle)"\s*:\s*"([^"]{3,200})"', re.IGNORECASE)
_SCRIPT_COMPANY = re.compile(r'"(?:company_name|companyName|company|organization)"\s*:\s*"([^"]{2,100})"', re.IGNORECASE)
_SCRIPT_LOCATION = re.compile(r'"(?:location|office_location|job_location|city)"\s*:\s*"([^"]{2,100})"', re.IGNORECASE)

_EXPIRY_CONTEXT = re.compile(
    r"(expir|deadline|closing|close\s+date|apply\s+by|applications?\s+close"
    r"|valid\s+through|last\s+date|end\s+date)",
    re.IGNORECASE,
)

_POSTED_CONTEXT = re.compile(
    r"(?:posted|published|date\s+posted|listing\s+date|listing\s+posted)"
    r"[^,\n]{0,20}?(" + _DATE_VALUE + r")",
    re.IGNORECASE,
)

# Common CSS selectors for job description content
_DESCRIPTION_SELECTORS = [
    {"class": "content-intro"},           # Greenhouse
    {"class": "posting-description"},     # Lever
    {"class": "job-description"},
    {"id": "job-description"},
    {"class": "description"},
    {"data-testid": "job-description"},
    {"class": "jobsearch-jobDescriptionText"},  # Indeed
]

# Title suffix patterns to strip: "Job Title | Company" or "Job Title - Company" or "Job Title at Company"
_TITLE_SUFFIX = re.compile(r"\s*[\|\-–—]\s*.{2,50}$|\s+at\s+\S.{1,50}$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scrape_job_page(url: str, driver=None) -> dict:
    """
    Fetch a job listing page and extract all available metadata.
    Returns dict with keys: title, company, location, description, posted_date.
    All values may be None if not found.
    """
    html = _fetch_html(url, driver)
    if not html:
        return _empty_meta()
    soup = BeautifulSoup(html, "html.parser")

    # Start with whatever JSON-LD gives us (often most complete)
    meta = _extract_from_json_ld(soup)

    # Fill gaps from script blobs, meta tags, CSS selectors
    if not meta.get("title"):
        meta["title"] = _extract_title(soup)
    if not meta.get("company"):
        meta["company"] = _extract_company(soup)
    if not meta.get("location"):
        meta["location"] = _extract_location(soup)
    if not meta.get("description"):
        meta["description"] = _extract_description(soup)
    if not meta.get("posted_date"):
        meta["posted_date"] = _extract_date_from_soup(soup, url)

    return meta


def scrape_post_date(url: str, driver=None) -> str | None:
    """Thin wrapper — kept for backward compatibility."""
    return scrape_job_page(url, driver).get("posted_date")


# ---------------------------------------------------------------------------
# JSON-LD extraction (all fields at once)
# ---------------------------------------------------------------------------

def _extract_from_json_ld(soup: BeautifulSoup) -> dict:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            result = _extract_job_node(data)
            if result:
                return result
        except Exception:
            pass
    return _empty_meta()


def _extract_job_node(node) -> dict:
    """
    Recursively walk a JSON-LD tree and return all JobPosting fields found.
    Returns {} if no JobPosting node is found.
    """
    if isinstance(node, list):
        for item in node:
            result = _extract_job_node(item)
            if result:
                return result
        return {}
    if not isinstance(node, dict):
        return {}
    if "@graph" in node:
        return _extract_job_node(node["@graph"])

    meta: dict = {}

    # Date (validThrough is expiry — never used)
    date_str = node.get("datePosted") or node.get("datePublished")
    if date_str:
        meta["posted_date"] = _normalize_date(str(date_str))

    # Title
    if node.get("title"):
        meta["title"] = str(node["title"])

    # Company via hiringOrganization
    org = node.get("hiringOrganization")
    if isinstance(org, dict):
        meta["company"] = org.get("name") or org.get("legalName")
    elif isinstance(org, str):
        meta["company"] = org

    # Location via jobLocation
    loc = node.get("jobLocation")
    if loc:
        meta["location"] = _parse_ld_location(loc)

    # Description (cap size)
    desc = node.get("description")
    if isinstance(desc, str):
        meta["description"] = desc[:5000]

    if meta:
        return {**_empty_meta(), **meta}

    # Nothing useful here — recurse into nested objects
    for value in node.values():
        if isinstance(value, (dict, list)):
            result = _extract_job_node(value)
            if result:
                return result
    return {}


def _parse_ld_location(loc) -> str | None:
    if isinstance(loc, str):
        return loc
    if isinstance(loc, list):
        loc = loc[0]
    if not isinstance(loc, dict):
        return None
    addr = loc.get("address")
    if isinstance(addr, dict):
        parts = [
            addr.get("addressLocality"),
            addr.get("addressRegion"),
            addr.get("addressCountry"),
        ]
        return ", ".join(p for p in parts if p) or None
    if isinstance(addr, str):
        return addr
    return loc.get("name") or loc.get("description")


# ---------------------------------------------------------------------------
# Fallback extractors (used when JSON-LD is absent or incomplete)
# ---------------------------------------------------------------------------

def _extract_title(soup: BeautifulSoup) -> str | None:
    # og:title
    tag = soup.find("meta", property="og:title")
    if tag and tag.get("content"):
        return _strip_title_suffix(tag["content"])
    # <title>
    tag = soup.find("title")
    if tag and tag.string:
        return _strip_title_suffix(tag.string.strip())
    # Script blob
    for script in soup.find_all("script"):
        m = _SCRIPT_TITLE.search(script.string or "")
        if m:
            return m.group(1).strip()
    return None


def _extract_company(soup: BeautifulSoup) -> str | None:
    tag = soup.find("meta", property="og:site_name")
    if tag and tag.get("content"):
        return tag["content"].strip()
    for script in soup.find_all("script"):
        m = _SCRIPT_COMPANY.search(script.string or "")
        if m:
            return m.group(1).strip()
    return None


def _extract_location(soup: BeautifulSoup) -> str | None:
    for name in ("job-location", "location"):
        tag = soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return tag["content"].strip()
    for script in soup.find_all("script"):
        m = _SCRIPT_LOCATION.search(script.string or "")
        if m:
            val = m.group(1).strip()
            if val and val.lower() not in ("null", "none", ""):
                return val
    return None


def _extract_description(soup: BeautifulSoup) -> str | None:
    for attrs in _DESCRIPTION_SELECTORS:
        tag = soup.find(attrs=attrs)
        if tag:
            text = tag.get_text(" ", strip=True)
            if len(text) > 100:
                return text[:5000]
    # og:description as last resort
    tag = soup.find("meta", property="og:description")
    if tag and tag.get("content"):
        return tag["content"][:5000]
    tag = soup.find("meta", attrs={"name": "description"})
    if tag and tag.get("content"):
        return tag["content"][:5000]
    return None


def _strip_title_suffix(text: str) -> str:
    return _TITLE_SUFFIX.sub("", text).strip()


# ---------------------------------------------------------------------------
# Date extraction (operates on pre-built soup)
# ---------------------------------------------------------------------------

def _extract_date_from_soup(soup: BeautifulSoup, url: str) -> str | None:
    result = _try_script_json(soup)
    if result:
        return result
    result = _try_meta(soup, "article:published_time")
    if result:
        return result
    result = _try_meta_name(soup, "date") or _try_meta_name(soup, "published_date")
    if result:
        return result
    result = _try_board_specific(soup, url)
    if result:
        return result
    result = _try_time_datetime(soup)
    if result:
        return result
    result = _try_relative_date(soup)
    if result:
        return result
    return _try_posted_context_scan(soup)


def _extract_date_from_html(html: str, url: str) -> str | None:
    """Legacy entry point — builds soup then delegates."""
    soup = BeautifulSoup(html, "html.parser")
    result = _extract_from_json_ld(soup).get("posted_date")
    return result or _extract_date_from_soup(soup, url)


# ---------------------------------------------------------------------------
# Internal date helpers (unchanged)
# ---------------------------------------------------------------------------

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
        logger.warning("HTTP %d for %s — skipping", resp.status_code, url)
    except Exception as e:
        logger.warning("Requests fetch failed for %s: %s", url, e)
    return None


def _try_script_json(soup: BeautifulSoup) -> str | None:
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
    tag = soup.find(class_="sort-by-time")
    if tag:
        text = tag.get_text(strip=True)
        return _parse_relative_date(text) or _normalize_date(text)
    tag = soup.find(class_="posted-time-ago__text")
    if tag:
        text = tag.get_text(strip=True)
        return _parse_relative_date(text) or _normalize_date(text)
    tag = soup.find(attrs={"data-testid": "myJobsStateDate"})
    if tag:
        text = tag.get_text(strip=True)
        return _parse_relative_date(text) or _normalize_date(text)
    return None


def _try_time_datetime(soup: BeautifulSoup) -> str | None:
    for tag in soup.find_all("time", attrs={"datetime": True}):
        parent_text = tag.parent.get_text(" ", strip=True) if tag.parent else ""
        if _EXPIRY_CONTEXT.search(parent_text):
            continue
        return _normalize_date(tag["datetime"])
    return None


def _try_relative_date(soup: BeautifulSoup) -> str | None:
    text = soup.get_text(" ", strip=True)
    return _parse_relative_date(text)


def _try_posted_context_scan(soup: BeautifulSoup) -> str | None:
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


def _empty_meta() -> dict:
    return {"title": None, "company": None, "location": None,
            "description": None, "posted_date": None}
