import tempfile
import os
import pytest
from jobfinder.database import init_db, get_connection, upsert_job, get_jobs, get_job, update_job_status, update_job_notes, get_jobs_for_pattern_analysis, record_search_run


@pytest.fixture
def db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    conn = get_connection(path)
    yield conn, path
    conn.close()
    for suffix in ("", "-shm", "-wal"):
        try:
            os.unlink(path + suffix)
        except OSError:
            pass


def test_upsert_inserts_new_job(db):
    conn, _ = db
    job_id, was_new = upsert_job(conn, "https://example.com/job/1", "Head of Engineering", "Acme", "Remote", "Great role", "2026-05-10")
    conn.commit()
    assert was_new
    assert job_id > 0


def test_upsert_deduplicates_by_url(db):
    conn, _ = db
    upsert_job(conn, "https://example.com/job/1", "Head of Engineering", "Acme", "Remote", None, None)
    conn.commit()
    _, was_new = upsert_job(conn, "https://example.com/job/1", "Different Title", "Different Co", None, None, None)
    conn.commit()
    assert not was_new
    jobs = get_jobs(conn)
    assert len(jobs) == 1


def test_upsert_coalesce_preserves_existing_values(db):
    conn, _ = db
    upsert_job(conn, "https://example.com/job/1", "Head of Engineering", "Acme", None, None, "2026-05-01")
    conn.commit()
    upsert_job(conn, "https://example.com/job/1", "Different Title", "Different Co", "NYC", "Body text", "2026-06-01")
    conn.commit()
    job = get_jobs(conn)[0]
    assert job["title"] == "Head of Engineering"
    assert job["company"] == "Acme"
    assert job["posted_date"] == "2026-05-01"
    assert job["location"] == "NYC"
    assert job["description"] == "Body text"


def test_upsert_fills_null_fields_on_rerun(db):
    conn, _ = db
    upsert_job(conn, "https://example.com/job/1", None, None, None, None, None)
    conn.commit()
    upsert_job(conn, "https://example.com/job/1", "Head of Engineering", "Acme", None, None, None)
    conn.commit()
    job = get_jobs(conn)[0]
    assert job["title"] == "Head of Engineering"
    assert job["company"] == "Acme"


def test_upsert_does_not_overwrite_status_or_notes(db):
    conn, _ = db
    job_id, _ = upsert_job(conn, "https://example.com/job/1", "Head of Engineering", "Acme", None, None, None)
    conn.commit()
    update_job_status(conn, job_id, "applied")
    update_job_notes(conn, job_id, "Applied via LinkedIn")
    upsert_job(conn, "https://example.com/job/1", "Head of Engineering", "Acme", None, None, None)
    conn.commit()
    job = get_job(conn, job_id)
    assert job["status"] == "applied"
    assert job["notes"] == "Applied via LinkedIn"


def test_get_jobs_filters_by_status(db):
    conn, _ = db
    id1, _ = upsert_job(conn, "https://example.com/job/1", "Head of Eng", "Acme", None, None, None)
    id2, _ = upsert_job(conn, "https://example.com/job/2", "VP Eng", "Beta", None, None, None)
    conn.commit()
    update_job_status(conn, id1, "rejected")
    new_jobs = get_jobs(conn, statuses=["new"])
    assert len(new_jobs) == 1
    assert new_jobs[0]["url"] == "https://example.com/job/2"


def test_get_jobs_for_pattern_analysis(db):
    conn, _ = db
    id1, _ = upsert_job(conn, "https://a.com/1", "Head of Eng", "Acme", None, None, None)
    id2, _ = upsert_job(conn, "https://a.com/2", "VP Eng", "Beta", None, None, None)
    id3, _ = upsert_job(conn, "https://a.com/3", "Junior Eng", "Gamma", None, None, None)
    conn.commit()
    update_job_status(conn, id1, "saved")
    update_job_status(conn, id2, "declined")
    rows = get_jobs_for_pattern_analysis(conn)
    urls = {r["company"] for r in rows}
    assert "Acme" in urls
    assert "Beta" in urls
    assert "Gamma" not in urls


def test_record_search_run(db):
    conn, _ = db
    record_search_run(conn, jobs_found=10, jobs_new=3)
    row = conn.execute("SELECT * FROM search_runs").fetchone()
    assert row["jobs_found"] == 10
    assert row["jobs_new"] == 3
