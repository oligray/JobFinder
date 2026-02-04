import pytest
from main import searchSite, jobsiteList

def test_searchSite_with_valid_site():
    """Test that searchSite can be called with a valid site URL."""
    # This test will initially fail since the function is not implemented
    result = searchSite(jobsiteList[0])
    # Placeholder assertion - replace with actual expected behavior
    assert result is not None

def test_jobsiteList_not_empty():
    """Test that jobsiteList has at least one site."""
    assert len(jobsiteList) > 0

def test_jobsiteList_contains_strings():
    """Test that all items in jobsiteList are strings."""
    for site in jobsiteList:
        assert isinstance(site, str)


def test_build_search_url_outputs_expected_url():
    """Output the generated search URL for manual inspection and assert it's well formed."""
    from main import build_search_url
    url = build_search_url('greenhouse.io')
    print(url)
    assert url.startswith("https://www.google.com/search?q=site:greenhouse.io")