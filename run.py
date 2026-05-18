import argparse
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def run_search_command(db_path: str, rules_path: str) -> dict:
    from jobfinder.scraper import run_search
    from jobfinder.date_scraper import scrape_post_date
    from jobfinder.database import get_connection, upsert_job, record_search_run
    from jobfinder.rules import load_rules, apply_rules

    print("Running search…")
    rules = load_rules(rules_path)
    urls, driver = run_search(
        domains=rules.get("job_boards"),
        pages_per_domain=rules.get("search_pages_per_board", 3),
    )
    print(f"Found {len(urls)} URLs from search.")

    rules = load_rules(rules_path)
    conn = get_connection(db_path)
    new_count = 0
    skipped_rules = 0

    for url in urls:
        posted_date = scrape_post_date(url, driver)
        job_meta = {"title": None, "company": None, "location": None, "description": None}
        ok, reason = apply_rules({**job_meta, "url": url}, rules)
        if not ok:
            logging.info("Skipped (rules): %s — %s", url, reason)
            skipped_rules += 1
            continue
        _, was_new = upsert_job(
            conn, url,
            job_meta["title"], job_meta["company"],
            job_meta["location"], job_meta["description"],
            posted_date
        )
        if was_new:
            new_count += 1

    if driver:
        driver.quit()

    record_search_run(conn, jobs_found=len(urls), jobs_new=new_count)

    print(f"Done. {new_count} new jobs added. {skipped_rules} excluded by rules.")
    return {"total": len(urls), "new": new_count, "skipped_rules": skipped_rules}


def main():
    parser = argparse.ArgumentParser(description="JobFinder — job search and tracking tool")
    parser.add_argument("--db", default="jobs.db", help="Path to SQLite database")
    parser.add_argument("--rules", default="rules.yaml", help="Path to rules config")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("search", help="Run a search and store new jobs")

    serve_parser = subparsers.add_parser("serve", help="Start the web dashboard")
    serve_parser.add_argument("--port", type=int, default=5000)
    serve_parser.add_argument("--host", default="127.0.0.1")

    args = parser.parse_args()

    if args.command == "search":
        run_search_command(args.db, args.rules)

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
