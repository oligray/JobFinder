from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import tempfile
import os
import webbrowser
import requests
from bs4 import BeautifulSoup

# Constants
BASE_URL = 'https://cse.google.com/cse?cx=30b1b200fbb65405a'
SEARCH_URL = BASE_URL + '&q=%22engineering%22%20AND%20(%22director%22%20OR%20%22head%22%20OR%20%22VP%22)%20AND%20(%22hiring%22%20OR%20%22apply%22%20OR%20%22open%20role%22)'
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'


def setup_chrome_options():
    """Configure Chrome driver options for web scraping."""
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(f"--user-agent={USER_AGENT}")
    return chrome_options


def search_with_selenium(search_url):
    """
    Execute JavaScript search using Selenium and return rendered HTML.
    
    Args:
        search_url (str): URL to search
        
    Returns:
        str: Rendered HTML content or None if failed
    """
    try:
        chrome_options = setup_chrome_options()
        driver = webdriver.Chrome(options=chrome_options)
        print("Chrome driver initialized successfully.")

        print(f"Navigating to: {search_url}")
        driver.get(search_url)

        print("Waiting for page to load...")
        time.sleep(5)

        try:
            WebDriverWait(driver, 10).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            print("Page loaded successfully.")
        except:
            print("Page may not have loaded completely, but continuing...")

        html_content = driver.page_source
        print(f"Retrieved {len(html_content)} characters of HTML content.")
        
        driver.quit()
        print("Browser closed.")
        
        return html_content

    except Exception as e:
        print(f"Selenium search failed: {e}")
        return None


def extract_urls_from_html(html_content, use_filter=False):
    """
    Parse HTML and extract search result URLs.
    
    Args:
        html_content (str): HTML content to parse
        use_filter (bool): If True, filter URLs for job-related keywords
        
    Returns:
        list: Unique URLs found in the HTML
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    search_results = set()
    
    if use_filter:
        # Filter for job-related URLs
        for a_tag in soup.find_all('a', href=True):
            url = a_tag.get('href')
            if url and url.startswith('http') and any(keyword in url.lower() for keyword in ['job', 'hiring', 'apply']):
                search_results.add(url)
    else:
        # Get all URLs from search results
        for a_tag in soup.find_all('a', class_='gs-title'):
            url = a_tag.get('href')
            if url and url.startswith('http'):
                search_results.add(url)
    
    return list(search_results)


def print_search_results(search_results):
    """Display search results to user."""
    print(f"Found {len(search_results)} unique search result URLs:")
    for i, url in enumerate(search_results, 1):
        print(f"{i}. {url}")


def open_results_in_browser(html_content):
    """
    Create temporary HTML file and open in default browser.
    
    Args:
        html_content (str): HTML content to save
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as temp_file:
        temp_file.write(html_content)
        temp_file_path = temp_file.name

    webbrowser.open(f'file://{temp_file_path}')
    print(f"Results saved to temporary file: {temp_file_path}")
    print("You can close the browser tab when done. The temporary file will be cleaned up on next system restart.")


def search_with_requests(search_url):
    """
    Fallback search using basic requests (doesn't execute JavaScript).
    
    Args:
        search_url (str): URL to search
        
    Returns:
        str: Response text or None if failed
    """
    print("\nFalling back to basic requests method...")
    headers = {'User-Agent': USER_AGENT}
    
    try:
        response = requests.get(search_url, headers=headers)
        if response.status_code == 200:
            print("Basic request successful. Note: This may show 'JavaScript not enabled' message.")
            return response.text
        else:
            print(f"Even basic request failed with status: {response.status_code}")
            return None
    except Exception as e:
        print(f"Basic request failed: {e}")
        return None


def print_troubleshooting_tips():
    """Display troubleshooting information."""
    print("\nTroubleshooting suggestions:")
    print("1. Make sure Google Chrome is installed")
    print("2. If Chrome isn't available, try installing it from: https://www.google.com/chrome/")
    print("3. Alternatively, we can modify the script to use Microsoft Edge or Firefox")
    print("4. Or we can use the Google Custom Search JSON API instead (requires API key)")


def main():
    """Main entry point for the job search script."""
    print("Searching for engineering leadership positions...")
    print("Launching browser to execute JavaScript...")

    # Try primary method with Selenium
    html_content = search_with_selenium(SEARCH_URL)
    
    if html_content:
        search_results = extract_urls_from_html(html_content)
        print_search_results(search_results)
        print("Opening results in browser...")
        open_results_in_browser(html_content)
    else:
        # Fallback to requests method
        print_troubleshooting_tips()
        html_content = search_with_requests(SEARCH_URL)
        
        if html_content:
            search_results = extract_urls_from_html(html_content, use_filter=True)
            print_search_results(search_results)
            open_results_in_browser(html_content)


if __name__ == "__main__":
    main()