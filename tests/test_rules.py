import tempfile
import os
import pytest
from jobfinder.rules import load_rules, save_rules, apply_rules


SAMPLE_RULES = {
    "title": {
        "require_any": [],
        "positive": ["head of engineering"],
        "negative": ["junior", "intern", "sales"],
    },
    "company": {"positive": [], "negative": ["bad corp"]},
    "location": {"positive": [], "negative": []},
    "description": {"positive": [], "negative": []},
    "pattern_suggestion_threshold": 10,
}


def test_apply_rules_passes_clean_job():
    job = {"title": "Head of Engineering", "company": "Good Corp", "location": "Remote", "description": "Great role"}
    ok, reason = apply_rules(job, SAMPLE_RULES)
    assert ok
    assert reason == ""


def test_apply_rules_negative_title():
    job = {"title": "Junior Engineer", "company": "Good Corp", "location": "Remote", "description": ""}
    ok, reason = apply_rules(job, SAMPLE_RULES)
    assert not ok
    assert "junior" in reason.lower()


def test_apply_rules_negative_company():
    job = {"title": "Head of Engineering", "company": "Bad Corp", "location": "Remote", "description": ""}
    ok, reason = apply_rules(job, SAMPLE_RULES)
    assert not ok
    assert "company" in reason


def test_apply_rules_case_insensitive():
    job = {"title": "JUNIOR ENGINEER", "company": "Acme", "location": None, "description": None}
    ok, _ = apply_rules(job, SAMPLE_RULES)
    assert not ok


def test_apply_rules_require_any_fails():
    rules = {
        "title": {"require_any": ["head", "director", "vp"], "positive": [], "negative": []},
        "company": {"positive": [], "negative": []},
        "location": {"positive": [], "negative": []},
        "description": {"positive": [], "negative": []},
        "pattern_suggestion_threshold": 10,
    }
    job = {"title": "Software Engineer", "company": "Acme", "location": None, "description": None}
    ok, reason = apply_rules(job, rules)
    assert not ok
    assert "required" in reason


def test_apply_rules_require_any_passes():
    rules = {
        "title": {"require_any": ["head", "director", "vp"], "positive": [], "negative": []},
        "company": {"positive": [], "negative": []},
        "location": {"positive": [], "negative": []},
        "description": {"positive": [], "negative": []},
        "pattern_suggestion_threshold": 10,
    }
    job = {"title": "Head of Engineering", "company": "Acme", "location": None, "description": None}
    ok, _ = apply_rules(job, rules)
    assert ok


def test_apply_rules_none_fields_dont_crash():
    job = {"title": None, "company": None, "location": None, "description": None}
    ok, _ = apply_rules(job, SAMPLE_RULES)
    assert ok


def test_load_rules_missing_file_returns_defaults():
    rules = load_rules("/nonexistent/path/rules.yaml")
    assert "title" in rules
    assert "pattern_suggestion_threshold" in rules


def test_save_and_load_rules_roundtrip():
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
        path = f.name
    try:
        save_rules(SAMPLE_RULES, path)
        loaded = load_rules(path)
        assert loaded["title"]["negative"] == SAMPLE_RULES["title"]["negative"]
        assert loaded["pattern_suggestion_threshold"] == 10
    finally:
        os.unlink(path)
