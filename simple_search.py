from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import tempfile
import os
from bs4 import BeautifulSoup

# Set up Chrome options
chrome_options = Options()
# chrome_options.add_argument("--headless")  # Commented out for debugging
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

base_url = 'https://cse.google.com/cse?cx=30b1b200fbb65405a'
search_url = base_url + '&q=%22engineering%22%20AND%20(%22director%22%20OR%20%22head%22%20OR%20%22VP%22)%20AND%20(%22hiring%22%20OR%20%22apply%22%20OR%20%22open%20role%22)'

print("Searching for engineering leadership positions...")
print("Launching browser to execute JavaScript...")

try:
    # Try to initialize Chrome driver
    driver = webdriver.Chrome(options=chrome_options)
    print("Chrome driver initialized successfully.")

    # Navigate to the search URL
    print(f"Navigating to: {search_url}")
    driver.get(search_url)

    # Wait for the page to load
    print("Waiting for page to load...")
    time.sleep(5)  # Give time for JavaScript to load

    # Try to find search results or wait for page elements
    try:
        # Wait up to 10 seconds for some content to load
        WebDriverWait(driver, 10).until(
            lambda driver: driver.execute_script("return document.readyState") == "complete"
        )
        print("Page loaded successfully.")
    except:
        print("Page may not have loaded completely, but continuing...")

    # Get the fully rendered HTML
    html_content = driver.page_source
    print(f"Retrieved {len(html_content)} characters of HTML content.")

    # Parse the HTML to extract search result URLs
    soup = BeautifulSoup(html_content, 'html.parser')
    search_results = []
    
    # Find all links in search results (typically with class 'gs-title' for Google CSE)
    for a_tag in soup.find_all('a', class_='gs-title'):
        url = a_tag.get('href')
        if url and url.startswith('http'):
            search_results.append(url)
    
    print(f"Found {len(search_results)} search result URLs:")
    for i, url in enumerate(search_results, 1):
        print(f"{i}. {url}")

    # Close the browser
    driver.quit()
    print("Browser closed.")

    print("Opening results in browser...")

    # Create a temporary HTML file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as temp_file:
        temp_file.write(html_content)
        temp_file_path = temp_file.name

    # Open the HTML file in the default web browser
    import webbrowser
    webbrowser.open(f'file://{temp_file_path}')

    print(f"Results saved to temporary file: {temp_file_path}")
    print("You can close the browser tab when done. The temporary file will be cleaned up on next system restart.")

except Exception as e:
    print(f"An error occurred: {e}")
    print("\nTroubleshooting suggestions:")
    print("1. Make sure Google Chrome is installed")
    print("2. If Chrome isn't available, try installing it from: https://www.google.com/chrome/")
    print("3. Alternatively, we can modify the script to use Microsoft Edge or Firefox")
    print("4. Or we can use the Google Custom Search JSON API instead (requires API key)")

    # Fallback to the original requests method
    print("\nFalling back to basic requests method...")
    import requests
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(search_url, headers=headers)
    if response.status_code == 200:
        print("Basic request successful. Note: This may show 'JavaScript not enabled' message.")
        
        # Parse the HTML to extract search result URLs
        soup = BeautifulSoup(response.text, 'html.parser')
        search_results = []
        
        # Find all links in search results
        for a_tag in soup.find_all('a', href=True):
            url = a_tag.get('href')
            if url and url.startswith('http') and ('job' in url.lower() or 'hiring' in url.lower() or 'apply' in url.lower()):
                search_results.append(url)
        
        print(f"Found {len(search_results)} search result URLs from basic request:")
        for i, url in enumerate(search_results, 1):
            print(f"{i}. {url}")
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as temp_file:
            temp_file.write(response.text)
            temp_file_path = temp_file.name
        import webbrowser
        webbrowser.open(f'file://{temp_file_path}')
        print(f"Basic results saved to: {temp_file_path}")
    else:
        print(f"Even basic request failed with status: {response.status_code}")