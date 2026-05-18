import logging
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.wait import WebDriverWait
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://cse.google.com/cse?cx=30b1b200fbb65405a"
SEARCH_URL = (
    BASE_URL
    + '&q=%22engineering%22%20AND%20(%22director%22%20OR%20%22head%22%20OR%20%22VP%22)'
    + '%20AND%20(%22hiring%22%20OR%20%22apply%22%20OR%20%22open%20role%22)'
)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
)


def setup_chrome_options() -> Options:
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(f"--user-agent={USER_AGENT}")
    return chrome_options


def search_with_selenium(search_url: str) -> tuple[str | None, webdriver.Chrome | None]:
    """
    Execute JavaScript search using Selenium.
    Returns (html_content, driver) — caller is responsible for quitting the driver.
    Returns (None, None) on failure.
    """
    try:
        driver = webdriver.Chrome(options=setup_chrome_options())
        logger.info("Chrome driver initialized.")
        logger.info("Navigating to: %s", search_url)
        driver.get(search_url)

        time.sleep(5)
        try:
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except Exception:
            logger.warning("Page may not have loaded completely.")

        html = driver.page_source
        logger.info("Retrieved %d characters of HTML.", len(html))
        return html, driver
    except Exception as e:
        logger.error("Selenium search failed: %s", e)
        return None, None


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


def extract_urls_from_html(html_content: str, use_filter: bool = False) -> list[str]:
    soup = BeautifulSoup(html_content, "html.parser")
    results: set[str] = set()

    if use_filter:
        for a in soup.find_all("a", href=True):
            url = a.get("href")
            if url and url.startswith("http") and any(
                kw in url.lower() for kw in ("job", "hiring", "apply")
            ):
                results.add(url)
    else:
        for a in soup.find_all("a", class_="gs-title"):
            url = a.get("href")
            if url and url.startswith("http"):
                results.add(url)

    return list(results)


def run_search(search_url: str = SEARCH_URL) -> tuple[list[str], webdriver.Chrome | None]:
    """
    Primary entry point. Tries Selenium first, falls back to requests.
    Returns (url_list, driver_or_None).
    The driver is kept alive so callers can reuse it for post-date scraping.
    Caller must call driver.quit() when done.
    """
    html, driver = search_with_selenium(search_url)
    if html:
        urls = extract_urls_from_html(html)
        return urls, driver

    if driver:
        driver.quit()

    logger.info("Falling back to requests method.")
    html = search_with_requests(search_url)
    if html:
        return extract_urls_from_html(html, use_filter=True), None
    return [], None
