import threading
from datetime import date

from flask import Flask, redirect, render_template, request, url_for, jsonify, flash

from .database import (
    get_connection, init_db, get_job, get_jobs, update_job_status,
    update_job_notes, get_jobs_for_pattern_analysis, record_search_run, upsert_job
)
from .rules import load_rules, save_rules, apply_rules
from .patterns import analyze_patterns

_search_state: dict = {"running": False, "last_result": None}


def create_app(db_path: str = "jobs.db", rules_path: str = "rules.yaml") -> Flask:
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.secret_key = "jobfinder-local-dev"

    init_db(db_path)

    def get_conn():
        return get_connection(db_path)

    def get_rules():
        return load_rules(rules_path)

    @app.route("/")
    def index():
        conn = get_conn()
        rules = get_rules()
        new_jobs = get_jobs(conn, statuses=["new"])
        show_excluded = request.args.get("show_excluded") == "1"

        passing, excluded = [], []
        today = date.today().isoformat()
        for job in new_jobs:
            ok, reason = apply_rules(dict(job), rules)
            job_dict = dict(job)
            job_dict["is_recent"] = bool(job["posted_date"] and job["posted_date"] >= today[:7])
            if ok:
                passing.append(job_dict)
            else:
                job_dict["exclude_reason"] = reason
                excluded.append(job_dict)

        return render_template(
            "index.html",
            jobs=passing,
            excluded=excluded,
            show_excluded=show_excluded,
            search_running=_search_state["running"],
        )

    @app.route("/jobs")
    def jobs_list():
        conn = get_conn()
        status_filter = request.args.get("status", "all")
        statuses = None if status_filter == "all" else [status_filter]
        jobs = [dict(j) for j in get_jobs(conn, statuses=statuses)]
        return render_template("jobs.html", jobs=jobs, status_filter=status_filter)

    @app.route("/jobs/<int:job_id>")
    def job_detail(job_id):
        conn = get_conn()
        job = get_job(conn, job_id)
        if not job:
            flash("Job not found.")
            return redirect(url_for("index"))
        return render_template("job_detail.html", job=dict(job))

    @app.route("/jobs/<int:job_id>/status", methods=["POST"])
    def update_status(job_id):
        status = request.form.get("status") or (request.get_json() or {}).get("status")
        valid = {"new", "saved", "applied", "rejected", "interviewing"}
        if status not in valid:
            return jsonify({"error": "invalid status"}), 400
        conn = get_conn()
        update_job_status(conn, job_id, status)
        if request.content_type and "json" in request.content_type:
            return jsonify({"ok": True})
        return redirect(request.referrer or url_for("index"))

    @app.route("/jobs/<int:job_id>/notes", methods=["POST"])
    def update_notes(job_id):
        notes = request.form.get("notes", "")
        conn = get_conn()
        update_job_notes(conn, job_id, notes)
        return redirect(url_for("job_detail", job_id=job_id))

    @app.route("/rules", methods=["GET", "POST"])
    def rules_view():
        if request.method == "POST":
            data = request.get_json()
            if data:
                save_rules(data, rules_path)
                return jsonify({"ok": True})
            flash("Invalid rules data.")
            return redirect(url_for("rules_view"))
        rules = get_rules()
        return render_template("rules.html", rules=rules)

    @app.route("/patterns")
    def patterns_view():
        conn = get_conn()
        rules = get_rules()
        threshold = rules.get("pattern_suggestion_threshold", 10)
        jobs = [dict(j) for j in get_jobs_for_pattern_analysis(conn)]

        saved_count = sum(1 for j in jobs if j["status"] == "saved")
        rejected_count = sum(1 for j in jobs if j["status"] == "rejected")
        has_enough = saved_count >= threshold and rejected_count >= threshold

        suggestions = analyze_patterns(jobs, rules) if has_enough else None
        return render_template(
            "patterns.html",
            suggestions=suggestions,
            saved_count=saved_count,
            rejected_count=rejected_count,
            threshold=threshold,
        )

    @app.route("/patterns/apply", methods=["POST"])
    def patterns_apply():
        data = request.get_json() or {}
        field = data.get("field")
        list_name = data.get("list")
        term = data.get("term", "").strip()
        if not field or list_name not in ("positive", "negative") or not term:
            return jsonify({"error": "invalid params"}), 400
        rules = get_rules()
        if field not in rules:
            return jsonify({"error": "unknown field"}), 400
        current = rules[field].get(list_name, [])
        if term not in current:
            current.append(term)
            rules[field][list_name] = current
            save_rules(rules, rules_path)
        return jsonify({"ok": True})

    @app.route("/search/run", methods=["POST"])
    def search_run():
        if _search_state["running"]:
            return jsonify({"error": "search already running"}), 409
        _search_state["running"] = True
        _search_state["last_result"] = None

        def _run():
            try:
                from .scraper import run_search
                from .date_scraper import scrape_post_date
                import logging
                logger = logging.getLogger(__name__)

                rules = get_rules()
                urls, driver = run_search(
                    domains=rules.get("job_boards"),
                    pages_per_domain=rules.get("search_pages_per_board", 3),
                )
                conn = get_conn()
                new_count = 0

                for url in urls:
                    posted_date = scrape_post_date(url, driver)
                    job_meta = {"title": None, "company": None,
                                "location": None, "description": None}
                    ok, _ = apply_rules({**job_meta, "url": url}, rules)
                    if not ok:
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
                _search_state["last_result"] = {"total": len(urls), "new": new_count}
            except Exception as e:
                _search_state["last_result"] = {"error": str(e)}
            finally:
                _search_state["running"] = False

        threading.Thread(target=_run, daemon=True).start()
        return jsonify({"started": True})

    @app.route("/search/status")
    def search_status():
        return jsonify({
            "running": _search_state["running"],
            "result": _search_state["last_result"],
        })

    return app
