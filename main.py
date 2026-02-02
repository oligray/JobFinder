import requests

jobsiteList = ['greenhouse.io','jobs.ashbyhq.com']

def searchSite(siteURL: str):
    # Perform a Google Search with the string passed in
    query = f"site:{siteURL} jobs"
    search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(search_url, headers=headers)
    if response.status_code == 200:
        return response.text
    else:
        return None
