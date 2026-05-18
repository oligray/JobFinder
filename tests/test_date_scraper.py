from datetime import date, timedelta
from jobfinder.date_scraper import (
    _extract_date_from_html, _parse_relative_date, _normalize_date
)


def test_json_ld_datePosted():
    html = """<html><head>
    <script type="application/ld+json">{"@type":"JobPosting","datePosted":"2026-05-10"}</script>
    </head><body></body></html>"""
    assert _extract_date_from_html(html, "https://example.com") == "2026-05-10"


def test_json_ld_datePublished():
    html = """<html><head>
    <script type="application/ld+json">{"@type":"Article","datePublished":"2026-04-01T12:00:00Z"}</script>
    </head><body></body></html>"""
    assert _extract_date_from_html(html, "https://example.com") == "2026-04-01"


def test_json_ld_array_form():
    html = """<html><head>
    <script type="application/ld+json">[{"@type":"JobPosting","datePosted":"2026-03-15"}]</script>
    </head><body></body></html>"""
    assert _extract_date_from_html(html, "https://example.com") == "2026-03-15"


def test_meta_article_published_time():
    html = """<html><head>
    <meta property="article:published_time" content="2026-05-01T08:00:00+00:00">
    </head><body></body></html>"""
    assert _extract_date_from_html(html, "https://example.com") == "2026-05-01"


def test_meta_name_date():
    html = """<html><head>
    <meta name="date" content="May 10, 2026">
    </head><body></body></html>"""
    assert _extract_date_from_html(html, "https://example.com") == "2026-05-10"


def test_time_datetime_attribute():
    html = """<html><body>
    <time datetime="2026-05-12">May 12, 2026</time>
    </body></html>"""
    assert _extract_date_from_html(html, "https://example.com") == "2026-05-12"


def test_lever_sort_by_time_relative():
    today = date.today()
    expected = (today - timedelta(days=3)).isoformat()
    html = f"""<html><body>
    <span class="sort-by-time">3 days ago</span>
    </body></html>"""
    assert _extract_date_from_html(html, "https://jobs.lever.co/acme/123") == expected


def test_linkedin_posted_time_ago():
    today = date.today()
    expected = (today - timedelta(weeks=2)).isoformat()
    html = """<html><body>
    <span class="posted-time-ago__text">2 weeks ago</span>
    </body></html>"""
    assert _extract_date_from_html(html, "https://linkedin.com/jobs/view/123") == expected


def test_returns_none_for_no_date():
    html = "<html><body><p>No date information here</p></body></html>"
    assert _extract_date_from_html(html, "https://example.com") is None


def test_malformed_date_returns_none():
    assert _normalize_date("not a date at all xyz") is None


def test_normalize_iso_date():
    assert _normalize_date("2026-05-10") == "2026-05-10"


def test_normalize_with_time():
    assert _normalize_date("2026-05-10T08:30:00Z") == "2026-05-10"


def test_parse_relative_days():
    today = date.today()
    assert _parse_relative_date("Posted 5 days ago") == (today - timedelta(days=5)).isoformat()


def test_parse_relative_weeks():
    today = date.today()
    assert _parse_relative_date("1 week ago") == (today - timedelta(weeks=1)).isoformat()


def test_parse_relative_months():
    today = date.today()
    assert _parse_relative_date("2 months ago") == (today - timedelta(days=60)).isoformat()


def test_parse_relative_no_match():
    assert _parse_relative_date("just now") is None


def test_regex_fallback_finds_iso_date():
    html = "<html><body><p>Job was posted on 2026-05-15 and is still open.</p></body></html>"
    result = _extract_date_from_html(html, "https://example.com")
    assert result == "2026-05-15"
