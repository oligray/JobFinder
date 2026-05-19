import logging
import time
from urllib.parse import quote

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.wait import WebDriverWait
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://cse.google.com/cse?cx=30b1b200fbb65405a"
# These are hard coded search terms...
KEYWORDS = (
    '"engineering" AND ("director" OR "head" OR "VP" OR "manager" OR "CTPO") '
    'AND ("hiring" OR "apply" OR "open role")'
)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
)

# Fallback used when no job_boards are configured
_BROAD_SEARCH_URL = BASE_URL + "&q=" + quote(KEYWORDS)


def setup_chrome_options() -> Options:
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(f"--user-agent={USER_AGENT}")
    return chrome_options


def _build_domain_url(
    domain: str,
    page: int = 0,
    location_terms: list[str] | None = None,
) -> str:
    """Build a CSE URL targeting a specific job board domain."""
    query = f"site:{domain} AND {KEYWORDS}"
    if location_terms:
        loc_clause = " OR ".join(f'"{t}"' for t in location_terms)
        query += f" AND ({loc_clause})"
    start = page * 10 + 1
    return f"{BASE_URL}&q={quote(query)}&start={start}"


def _init_driver() -> webdriver.Chrome | None:
    try:
        driver = webdriver.Chrome(options=setup_chrome_options())
        logger.info("Chrome driver initialised.")
        return driver
    except Exception as e:
        logger.error("Chrome driver init failed: %s", e)
        return None


def _fetch_with_driver(driver: webdriver.Chrome, url: str) -> str | None:
    try:
        driver.get(url)
        time.sleep(3)
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        return driver.page_source
    except Exception as e:
        logger.warning("Driver navigation failed for %s: %s", url, e)
        return None


def search_with_requests(search_url: str) -> str | None:
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(search_url, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.text
        logger.warning("Requests fallback status: %d", response.status_code)
        return None
    except Exception as e:
        logger.error("Requests fallback failed: %s", e)
        return None


def extract_urls_from_html(html_content: str, domain_filter: str | None = None) -> list[str]:
    """
    Extract result URLs from CSE HTML.
    If domain_filter is set, only return URLs that contain that domain.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    if "Your search did not match any results." in soup.get_text():
        domain_hint = domain_filter or "unknown"
        logger.warning(
            "No CSE results for domain '%s' — verify the domain is correct in rules.yaml",
            domain_hint,
        )
        return []
    results: set[str] = set()
    for a in soup.find_all("a", class_="gs-title"):
        url = a.get("href")
        if url and url.startswith("http"):
            if domain_filter is None or domain_filter in url:
                results.add(url)
    return list(results)


def run_search(
    domains: list[str] | None = None,
    pages_per_domain: int = 3,
    location_terms: list[str] | None = None,
) -> tuple[list[str], webdriver.Chrome | None]:
    """
    Primary entry point.

    If domains is provided, runs one targeted `site:domain` query per domain,
    paginating up to pages_per_domain pages each.
    Falls back to a single broad keyword search if domains is empty/None.

    Returns (url_list, driver_or_None). Caller must call driver.quit() when done.
    """
    driver = _init_driver()
    all_urls: set[str] = set()

    search_domains = domains or []

    if search_domains:
        for domain in search_domains:
            logger.info("Searching domain: %s", domain)
            for page in range(pages_per_domain):
                url = _build_domain_url(domain, page, location_terms)
                html = _fetch_with_driver(driver, url) if driver else search_with_requests(url)
                if not html:
                    break
                page_urls = extract_urls_from_html(html, domain_filter=domain)
                if not page_urls:
                    logger.info("No results on page %d for %s, stopping.", page + 1, domain)
                    break
                logger.info("Page %d: %d URLs from %s", page + 1, len(page_urls), domain)
                all_urls.update(page_urls)
    else:
        logger.info("No domains configured, running broad keyword search.")
        html = _fetch_with_driver(driver, _BROAD_SEARCH_URL) if driver else search_with_requests(_BROAD_SEARCH_URL)
        if html:
            all_urls.update(extract_urls_from_html(html))

    logger.info("Total unique URLs found: %d", len(all_urls))
    return list(all_urls), driver
