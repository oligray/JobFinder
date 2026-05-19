import argparse
import logging
import sys
from urllib.parse import quote

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def run_search_command(db_path: str, rules_path: str) -> dict:
    from jobfinder.scraper import run_search
    from jobfinder.date_scraper import scrape_job_page
    from jobfinder.database import get_connection, upsert_job, record_search_run
    from jobfinder.rules import load_rules, apply_rules

    print("Running search…")
    rules = load_rules(rules_path)
    urls, driver = run_search(
        domains=rules.get("job_boards"),
        pages_per_domain=rules.get("search_pages_per_board", 3),
        location_terms=rules.get("search_location_terms"),
    )
    print(f"Found {len(urls)} URLs from search.")

    conn = get_connection(db_path)
    new_count = 0
    skipped_rules = 0

    for url in urls:
        meta = scrape_job_page(url, driver)
        ok, reason = apply_rules({**meta, "url": url}, rules)
        if not ok:
            logging.info("Skipped (rules): %s — %s", url, reason)
            skipped_rules += 1
            continue
        _, was_new = upsert_job(
            conn, url,
            meta["title"], meta["company"],
            meta["location"], meta["description"],
            meta["posted_date"]
        )
        if was_new:
            new_count += 1

    if driver:
        driver.quit()

    record_search_run(conn, jobs_found=len(urls), jobs_new=new_count)

    print(f"Done. {new_count} new jobs added. {skipped_rules} excluded by rules.")
    return {"total": len(urls), "new": new_count, "skipped_rules": skipped_rules}


_CSE_BASE = "https://cse.google.com/cse?cx=30b1b200fbb65405a"
_KEYWORDS = (
    '"engineering" AND ("director" OR "head" OR "VP") '
    'AND ("hiring" OR "apply" OR "open role")'
)


def _preview_url(domain: str, page: int = 0, location_terms: list | None = None) -> str:
    query = f"site:{domain} AND {_KEYWORDS}"
    if location_terms:
        loc_clause = " OR ".join(f'"{t}"' for t in location_terms)
        query += f" AND ({loc_clause})"
    start = page * 10 + 1
    return f"{_CSE_BASE}&q={quote(query)}&start={start}"


def run_urls_command(rules_path: str, domains: list, pages: int) -> None:
    from jobfinder.rules import load_rules

    rules = load_rules(rules_path)
    location_terms = rules.get("search_location_terms")

    if not domains:
        domains = rules.get("job_boards", [])

    for domain in domains:
        print(f"\n--- {domain} ---")
        for page in range(pages):
            url = _preview_url(domain, page=page, location_terms=location_terms)
            print(f"  Page {page + 1}: {url}")


def main():
    parser = argparse.ArgumentParser(description="JobFinder — job search and tracking tool")
    parser.add_argument("--db", default="jobs.db", help="Path to SQLite database")
    parser.add_argument("--rules", default="rules.yaml", help="Path to rules config")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("search", help="Run a search and store new jobs")

    urls_parser = subparsers.add_parser("urls", help="Print CSE search URLs for job board domains")
    urls_parser.add_argument("domains", nargs="*", help="Domains to preview (default: all from rules.yaml)")
    urls_parser.add_argument("--pages", type=int, default=1, help="Number of page URLs to show per domain")

    serve_parser = subparsers.add_parser("serve", help="Start the web dashboard")
    serve_parser.add_argument("--port", type=int, default=5000)
    serve_parser.add_argument("--host", default="127.0.0.1")

    args = parser.parse_args()

    if args.command == "search":
        run_search_command(args.db, args.rules)

    elif args.command == "urls":
        run_urls_command(args.rules, args.domains, args.pages)

    elif args.command == "serve":
        from jobfinder.database import init_db
        init_db(args.db)
        from jobfinder.app import create_app
        app = create_app(db_path=args.db, rules_path=args.rules)
        print(f"Starting dashboard at http://{args.host}:{args.port}")
        app.run(host=args.host, port=args.port, debug=False)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
