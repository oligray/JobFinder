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
_DATE_LIKE_PATTERN = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b"
    r"|\b\d{4}-\d{2}-\d{2}\b"
    r"|\b\d{1,2}/\d{1,2}/\d{2,4}\b",
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

    # 1. JSON-LD datePosted
    result = _try_json_ld(soup)
    if result:
        return result

    # 2. <meta property="article:published_time">
    result = _try_meta(soup, "article:published_time")
    if result:
        return result

    # 3. <meta name="date">
    result = _try_meta_name(soup, "date")
    if result:
        return result

    # 4. <time datetime="..."> attribute
    result = _try_time_datetime(soup)
    if result:
        return result

    # 5. <time> inner text
    result = _try_time_text(soup)
    if result:
        return result

    # 6. Board-specific CSS selectors
    result = _try_board_specific(soup, url)
    if result:
        return result

    # 7. Regex scan of page text
    result = _try_regex_scan(soup)
    if result:
        return result

    return None


def _try_json_ld(soup: BeautifulSoup) -> str | None:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, list):
                data = data[0]
            date_str = data.get("datePosted") or data.get("datePublished")
            if date_str:
                return _normalize_date(date_str)
        except Exception:
            pass
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


def _try_time_datetime(soup: BeautifulSoup) -> str | None:
    tag = soup.find("time", attrs={"datetime": True})
    if tag:
        return _normalize_date(tag["datetime"])
    return None


def _try_time_text(soup: BeautifulSoup) -> str | None:
    for tag in soup.find_all("time"):
        text = tag.get_text(strip=True)
        if text:
            result = _parse_relative_date(text) or _normalize_date(text)
            if result:
                return result
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


def _try_regex_scan(soup: BeautifulSoup) -> str | None:
    text = soup.get_text(" ", strip=True)
    match = _DATE_LIKE_PATTERN.search(text)
    if match:
        return _normalize_date(match.group(0))
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
