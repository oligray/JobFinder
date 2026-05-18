# JobFinder

A simple job search utility that performs a Google Custom Search and displays results in a browser.

## Setup

1. Create and activate a virtual environment (Windows PowerShell):
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Run

```bash
python simple_search.py
```

## Testing

Run tests with pytest:

```bash
pytest -v
```

## Notes

- `simple_search.py` uses Selenium to render JavaScript-enabled Google Search pages.
- If Selenium fails, ensure Chrome is installed and accessible on your PATH.
- You can also use the Google Custom Search API for more reliable programmatic results.

## Debug mode

To run in debug mode and see extra logs while executing:

```bash
python simple_search.py --debug
```

This prints additional runtime information and helps diagnose browser/driver issues quickly.