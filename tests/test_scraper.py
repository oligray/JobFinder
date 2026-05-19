from urllib.parse import unquote
from jobfinder.scraper import _build_domain_url


def test_build_domain_url_no_location():
    url = _build_domain_url("greenhouse.io", page=0)
    decoded = unquote(url)
    assert "site:greenhouse.io" in decoded
    assert "start=1" in decoded


def test_build_domain_url_page_offset():
    url = _build_domain_url("greenhouse.io", page=2)
    assert "start=21" in url


def test_build_domain_url_with_location_terms():
    url = _build_domain_url("jobs.lever.co", page=0, location_terms=["remote", "new york"])
    decoded = unquote(url)
    assert 'AND ("remote" OR "new york")' in decoded


def test_build_domain_url_single_location_term():
    url = _build_domain_url("jobs.lever.co", page=0, location_terms=["remote"])
    decoded = unquote(url)
    assert 'AND ("remote")' in decoded


def test_build_domain_url_empty_location_terms():
    url_none = _build_domain_url("greenhouse.io", page=0, location_terms=None)
    url_empty = _build_domain_url("greenhouse.io", page=0, location_terms=[])
    assert unquote(url_none) == unquote(url_empty)
    decoded = unquote(url_none)
    # Location clause should not appear; KEYWORDS itself may contain AND (...)
    assert '"remote"' not in decoded
    assert '"new york"' not in decoded
