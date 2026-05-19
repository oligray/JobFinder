from jobfinder.scoring import score_job, validate_scoring


SCORING_CONFIG = {
    "title": {"ctpo": 5, "cto": 4, "vp of engineering": 3},
    "location": {"fully remote": 4, "remote": 3, "new york": 2},
    "description": {"$240": 3, "direct reports": 2, "startup": 1},
}


def test_score_job_no_matches():
    job = {"title": "Software Engineer", "location": "Chicago", "description": "Build stuff."}
    score, reasons = score_job(job, SCORING_CONFIG)
    assert score == 0
    assert reasons == []


def test_score_job_title_match():
    job = {"title": "CTO", "location": "", "description": ""}
    score, reasons = score_job(job, SCORING_CONFIG)
    assert score == 4
    assert any("cto" in r for r in reasons)


def test_score_job_title_case_insensitive():
    job = {"title": "CTPO Role", "location": "", "description": ""}
    score, reasons = score_job(job, SCORING_CONFIG)
    assert score == 5


def test_score_job_multiple_fields():
    job = {
        "title": "VP of Engineering",
        "location": "Fully Remote",
        "description": "Startup with $240k salary and direct reports.",
    }
    score, reasons = score_job(job, SCORING_CONFIG)
    # "Fully Remote" matches both "fully remote" (4) and "remote" (3)
    assert score == 3 + 4 + 3 + 3 + 2 + 1
    assert len(reasons) == 6


def test_score_job_none_fields_treated_as_empty():
    job = {"title": None, "location": None, "description": None}
    score, reasons = score_job(job, SCORING_CONFIG)
    assert score == 0
    assert reasons == []


def test_score_job_empty_config():
    job = {"title": "CTO", "location": "remote", "description": "startup"}
    score, reasons = score_job(job, {})
    assert score == 0


def test_validate_scoring_signal():
    jobs = [
        {"status": "applied", "title": "CTO", "location": "Remote", "description": ""},
        {"status": "saved",    "title": "CTO", "location": "",       "description": ""},
        {"status": "rejected", "title": "Engineer", "location": "", "description": ""},
        {"status": "rejected", "title": "Engineer", "location": "", "description": ""},
        {"status": "applied",  "title": "Head of Eng", "location": "", "description": ""},
    ]
    results = validate_scoring(jobs, {"title": {"cto": 4}})
    assert len(results) == 1
    row = results[0]
    assert row["keyword"] == "cto"
    assert row["applied_matches"] == 2
    assert row["rejected_matches"] == 0
    assert row["signal_strength"] == round(2 / 3 - 0 / 2, 2)


def test_validate_scoring_skips_zero_match_keywords():
    jobs = [
        {"status": "applied",  "title": "Director", "location": "", "description": ""},
        {"status": "rejected", "title": "Engineer",  "location": "", "description": ""},
    ]
    results = validate_scoring(jobs, {"title": {"ctpo": 5, "director": 2}})
    keywords = [r["keyword"] for r in results]
    assert "ctpo" not in keywords
    assert "director" in keywords


def test_validate_scoring_sorted_by_signal_descending():
    jobs = [
        {"status": "applied",  "title": "Remote CTO", "location": "remote", "description": ""},
        {"status": "rejected", "title": "Engineer",   "location": "",       "description": ""},
        {"status": "applied",  "title": "VP",         "location": "",       "description": ""},
    ]
    config = {"title": {"cto": 4, "vp": 3}, "location": {"remote": 3}}
    results = validate_scoring(jobs, config)
    signals = [r["signal_strength"] for r in results]
    assert signals == sorted(signals, reverse=True)


def test_validate_scoring_empty_jobs():
    results = validate_scoring([], SCORING_CONFIG)
    assert results == []


def test_absence_penalty_applied_when_no_salary():
    config = {
        "absence_penalties": [
            {"fields": ["description"], "keywords": ["$240", "salary"], "penalty": -3}
        ]
    }
    job = {"title": "CTO", "description": "Build great products."}
    score, reasons = score_job(job, config)
    assert score == -3
    assert any("no salary" in r for r in reasons)


def test_absence_penalty_not_applied_when_salary_present():
    config = {
        "absence_penalties": [
            {"fields": ["description"], "keywords": ["$240", "salary"], "penalty": -3}
        ]
    }
    job = {"title": "CTO", "description": "Salary up to $240k per year."}
    score, reasons = score_job(job, config)
    assert score == 0
    assert not any("no salary" in r for r in reasons)
