# JobFinder

A local job search and tracking tool. It searches for engineering leadership roles using a Google Custom Search Engine, tracks every job you've seen, and progressively gets better at filtering through keyword rules and pattern suggestions derived from your accept/reject history.

## Features

- **New job discovery** — searches are run on demand via the dashboard or CLI; jobs are deduplicated across runs so you only ever see something new once
- **Location-filtered search** — CSE queries include an `AND ("remote" OR "new york" OR "nyc")` clause (configurable in `rules.yaml`) so only relevant listings are fetched
- **Full metadata extraction** — each listing page is scraped for title, company, location, description, and posting date in a single pass; extraction cascades through JSON-LD, script blobs, meta tags, and board-specific CSS selectors
- **Post-date scraping** — recent jobs are highlighted in the queue; the date cascade covers JSON-LD, `<script>` JSON fields, meta tags, `<time>` elements, relative dates ("3 days ago"), and a "posted on …" text scan
- **Job scoring** — each job is scored against a keyword→points config in `rules.yaml`; the queue is sorted highest-score first with a coloured badge and tooltip showing which signals matched
- **Job tracking** — every job is stored in a local SQLite database with a status: `new`, `saved`, `applied`, `interviewing`, or `rejected`; rejected jobs never resurface
- **Keyword rules** — `rules.yaml` positive/negative keyword lists per field; rule-excluded jobs are filtered transiently and re-evaluated on the next run
- **Pattern suggestions** — after you've rated enough jobs, the tool analyses word frequencies across your saved vs. rejected history and suggests new terms to add to your rules
- **Scoring validation** — the Patterns page shows per-keyword signal strength (applied/saved match rate minus rejected match rate) so you can tune scoring weights over time
- **Local web dashboard** — a Flask app for reviewing the queue, managing statuses and notes, editing rules, and triggering searches

## Setup

1. Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Ensure Google Chrome is installed (used by Selenium for the search).

## Usage

### Start the dashboard

```powershell
python run.py serve
```

Open [http://localhost:5000](http://localhost:5000) in your browser. Use the **Run Search** button in the nav to trigger a search from the UI.

### Run a search from the CLI

```powershell
python run.py search
```

Prints a summary (`N new jobs added`) without starting the web server.

### Run search then immediately open the dashboard

```powershell
python run.py search && python run.py serve
```

### Options

```
python run.py serve --port 8080    # change port (default 5000)
python run.py --db my.db search    # use a different database file
python run.py --rules my.yaml serve
```

## Dashboard pages

| Page | Path | Purpose |
|------|------|---------|
| Queue | `/` | New jobs sorted by score (then post date); coloured score badge with tooltip; quick Save/Reject buttons; recent jobs are highlighted |
| All Jobs | `/jobs` | Full list with status filter tabs |
| Job Detail | `/jobs/<id>` | All fields, notes, status dropdown, link to the listing |
| Rules | `/rules` | Edit keyword rules with a tag UI; changes take effect on the next search run |
| Patterns | `/patterns` | Suggested new rules based on your save/reject history (requires 10+ of each); scoring keyword validation table (requires 5+ applied/saved) |

## Configuring rules (`rules.yaml`)

```yaml
title:
  require_any: []          # job must match at least one of these (leave empty to skip)
  positive:    ["head of engineering", "director of engineering"]
  negative:    ["junior", "intern", "sales"]

company:
  positive:    []
  negative:    []

location:
  positive:    ["remote"]
  negative:    []

description:
  positive:    []
  negative:    []

pattern_suggestion_threshold: 10  # minimum saved + rejected before suggestions appear

# Location terms appended to every CSE query as AND ("remote" OR "new york" OR "nyc")
search_location_terms:
  - remote
  - "new york"
  - nyc

# Keyword → points scoring. Fields: title, location, description.
scoring:
  title:
    ctpo: 5
    cto: 4
    "vp of engineering": 3
  location:
    "fully remote": 4
    remote: 3
    "new york": 2
  description:
    "$240": 3
    "direct reports": 2
    startup: 1
```

- **`negative`**: any match on any field silently excludes the job from the queue (re-evaluated each run)
- **`require_any`** (title only): if non-empty, a job must match at least one term or it is excluded
- **`positive`**: informational only — used as input to pattern suggestions
- **`scoring`**: keyword→points maps per field; scores are summed and used to sort the queue
- All matching is case-insensitive substring

## Project structure

```
JobFinder/
├── jobfinder/
│   ├── scraper.py       # Selenium/requests search with location-filtered CSE queries
│   ├── date_scraper.py  # full metadata + post-date extraction cascade
│   ├── database.py      # SQLite layer
│   ├── rules.py         # rule loading, saving, and application
│   ├── patterns.py      # frequency-analysis suggestion engine
│   ├── scoring.py       # keyword scoring and validation
│   └── app.py           # Flask application factory
├── templates/           # Jinja2 HTML templates
├── static/style.css
├── rules.yaml           # your filter config (edit freely)
├── jobs.db              # SQLite database (git-ignored)
├── run.py               # CLI entry point
├── simple_search.py     # original standalone script (still works independently)
└── tests/               # unit tests (no network or browser required)
```

## Testing

```powershell
python -m pytest tests/ -v
```

All tests use static fixtures and an in-memory/temp database — no Chrome or network connection required.

## Notes

- `jobs.db` is tracked by git (small, contains your history). The WAL sidecar files (`.db-shm`, `.db-wal`) are git-ignored.
- If Chrome is not found, Selenium will fail and the tool falls back to a plain `requests` fetch (JavaScript won't execute, so results will be limited).
- The Google CSE ID is hardcoded in `jobfinder/scraper.py` — update `BASE_URL` there to point to a different search engine.
