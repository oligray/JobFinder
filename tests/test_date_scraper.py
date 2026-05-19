from datetime import date, timedelta
from unittest.mock import patch, MagicMock
from jobfinder.date_scraper import (
    _extract_date_from_html, _parse_relative_date, _normalize_date,
    scrape_job_page,
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


def test_greenhouse_published_at_in_script():
    html = """<html><head>
    <script>var data = {"job":{"id":123,"published_at":"2026-05-07T10:30:26-04:00","title":"Head of Eng"}};</script>
    </head><body></body></html>"""
    assert _extract_date_from_html(html, "https://job-boards.greenhouse.io/gitlab/jobs/123") == "2026-05-07"


def test_script_json_posted_date_field():
    html = """<html><head>
    <script type="application/json">{"postedDate":"2026-04-22","title":"Director of Engineering"}</script>
    </head><body></body></html>"""
    assert _extract_date_from_html(html, "https://example.com") == "2026-04-22"


def test_posted_context_scan_finds_date():
    html = "<html><body><p>Job was posted on 2026-05-15 and is still open.</p></body></html>"
    result = _extract_date_from_html(html, "https://example.com")
    assert result == "2026-05-15"


def test_expiry_only_returns_none():
    html = "<html><body><div>Expires 04/30/2026</div></body></html>"
    assert _extract_date_from_html(html, "https://job-boards.greenhouse.io/gitlab/jobs/123") is None


def test_expiry_date_does_not_override_post_date():
    html = """<html><head>
    <script type="application/ld+json">{"@type":"JobPosting","datePosted":"2026-03-01","validThrough":"2026-04-30"}</script>
    </head><body><div>Expires 04/30/2026</div></body></html>"""
    assert _extract_date_from_html(html, "https://example.com") == "2026-03-01"


def test_json_ld_graph_wrapper():
    html = """<html><head>
    <script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"WebPage"},{"@type":"JobPosting","datePosted":"2026-04-10"}]}</script>
    </head><body></body></html>"""
    assert _extract_date_from_html(html, "https://example.com") == "2026-04-10"


def test_json_ld_jobposting_not_first_in_list():
    html = """<html><head>
    <script type="application/ld+json">[{"@type":"Organization","name":"Acme"},{"@type":"JobPosting","datePosted":"2026-05-01"}]</script>
    </head><body></body></html>"""
    assert _extract_date_from_html(html, "https://example.com") == "2026-05-01"


def test_time_element_with_expiry_context_is_skipped():
    html = """<html><body>
    <p>Application deadline: <time datetime="2026-06-01">June 1, 2026</time></p>
    </body></html>"""
    assert _extract_date_from_html(html, "https://example.com") is None


def test_regex_skips_closing_date_finds_post_date():
    html = "<html><body><p>Posted: 2026-03-10. Closing date: 2026-06-30.</p></body></html>"
    result = _extract_date_from_html(html, "https://example.com")
    assert result == "2026-03-10"


# ---------------------------------------------------------------------------
# scrape_job_page metadata extraction tests
# ---------------------------------------------------------------------------

def _make_html(body: str) -> str:
    return f"<html><head>{body}</head><body></body></html>"


def _mock_fetch(html: str):
    return patch("jobfinder.date_scraper._fetch_html", return_value=html)


def test_scrape_job_page_json_ld_full():
    html = """<html><head>
    <script type="application/ld+json">{
      "@type": "JobPosting",
      "title": "Head of Engineering",
      "datePosted": "2026-05-01",
      "hiringOrganization": {"name": "Acme Corp"},
      "jobLocation": {"address": {"addressLocality": "New York", "addressRegion": "NY"}},
      "description": "Lead the engineering team."
    }</script>
    </head><body></body></html>"""
    with _mock_fetch(html):
        meta = scrape_job_page("https://example.com/job")
    assert meta["title"] == "Head of Engineering"
    assert meta["company"] == "Acme Corp"
    assert meta["location"] == "New York, NY"
    assert meta["posted_date"] == "2026-05-01"
    assert "Lead" in meta["description"]


def test_scrape_job_page_og_title_fallback():
    html = """<html><head>
    <meta property="og:title" content="VP Engineering | Acme">
    <meta property="og:site_name" content="Acme">
    </head><body></body></html>"""
    with _mock_fetch(html):
        meta = scrape_job_page("https://example.com/job")
    assert meta["title"] == "VP Engineering"
    assert meta["company"] == "Acme"


def test_scrape_job_page_returns_empty_meta_on_fetch_failure():
    with patch("jobfinder.date_scraper._fetch_html", return_value=None):
        meta = scrape_job_page("https://example.com/job")
    assert meta == {"title": None, "company": None, "location": None,
                    "description": None, "posted_date": None}


def test_scrape_job_page_og_description_fallback():
    html = """<html><head>
    <meta property="og:description" content="A great job opportunity for engineers.">
    </head><body></body></html>"""
    with _mock_fetch(html):
        meta = scrape_job_page("https://example.com/job")
    assert meta["description"] == "A great job opportunity for engineers."


def test_scrape_job_page_title_strip_dash_suffix():
    html = """<html><head>
    <meta property="og:title" content="Director of Engineering - Big Corp">
    </head><body></body></html>"""
    with _mock_fetch(html):
        meta = scrape_job_page("https://example.com/job")
    assert meta["title"] == "Director of Engineering"


def test_scrape_job_page_location_from_meta():
    html = """<html><head>
    <meta name="job-location" content="San Francisco, CA">
    </head><body></body></html>"""
    with _mock_fetch(html):
        meta = scrape_job_page("https://example.com/job")
    assert meta["location"] == "San Francisco, CA"
