import requests

jobsiteList = ['greenhouse.io','jobs.ashbyhq.com']

def build_search_url(siteURL: str, keywords: str = "('engineering') AND ('manager' OR 'director') AND ('hiring' OR 'apply' OR 'open role')") -> str:
    """Build a Google search URL for a given site and optional keywords."""
    query = f"site:{siteURL} AND {keywords}"
    return f"https://www.google.com/search?q={query.replace(' ', '+')}"


def searchSite(siteURL: str):
    """Perform a Google Search with the string passed in"""
    search_url = build_search_url(siteURL)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(search_url, headers=headers)
    if response.status_code == 200:
        return response.text
    else:
        return None

if __name__ == "__main__":
    for site in jobsiteList:
        result = searchSite(site)
        if result:
            print(f"Results for {site}: {len(result)} characters")
        else:
            print(f"No results for {site}")