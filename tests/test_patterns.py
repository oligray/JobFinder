from jobfinder.patterns import analyze_patterns, _tokenize, _term_frequencies


def _make_jobs(saved_titles, declined_titles):
    jobs = []
    for t in saved_titles:
        jobs.append({"title": t, "company": "Acme", "status": "saved"})
    for t in declined_titles:
        jobs.append({"title": t, "company": "Acme", "status": "declined"})
    return jobs


EMPTY_RULES = {
    "title": {"require_any": [], "positive": [], "negative": []},
    "company": {"positive": [], "negative": []},
    "location": {"positive": [], "negative": []},
    "description": {"positive": [], "negative": []},
}


def test_returns_empty_with_no_data():
    result = analyze_patterns([], EMPTY_RULES)
    assert result["positive_suggestions"] == []
    assert result["negative_suggestions"] == []


def test_returns_empty_with_only_one_status():
    jobs = _make_jobs(["Head of Engineering", "VP Engineering"], [])
    result = analyze_patterns(jobs, EMPTY_RULES)
    assert result["positive_suggestions"] == []


def test_positive_suggestion_for_accepted_term():
    saved = ["Head of Platform Engineering", "Director of Platform", "VP of Platform Engineering"]
    rejected = ["Senior Sales Engineer", "Data Science Director", "Engineering Manager Games"]
    jobs = _make_jobs(saved, rejected)
    result = analyze_patterns(jobs, EMPTY_RULES)
    pos_terms = [s["term"] for s in result["positive_suggestions"]]
    assert "platform" in pos_terms


def test_negative_suggestion_for_rejected_term():
    saved = ["Head of Engineering", "VP of Engineering", "Director of Engineering"]
    rejected = ["Senior Sales Engineer", "Sales Director", "Sales Manager"]
    jobs = _make_jobs(saved, rejected)
    result = analyze_patterns(jobs, EMPTY_RULES)
    neg_terms = [s["term"] for s in result["negative_suggestions"]]
    assert "sales" in neg_terms


def test_existing_rules_excluded_from_suggestions():
    rules = {
        "title": {"require_any": [], "positive": ["platform engineer"], "negative": []},
        "company": {"positive": [], "negative": []},
        "location": {"positive": [], "negative": []},
        "description": {"positive": [], "negative": []},
    }
    saved = ["Head of Platform Engineering", "VP Platform", "Director Platform"]
    rejected = ["Junior Sales Engineer", "Intern Sales", "Sales Lead"]
    jobs = _make_jobs(saved, rejected)
    result = analyze_patterns(jobs, rules)
    pos_terms = [s["term"] for s in result["positive_suggestions"]]
    assert "platform" not in pos_terms


def test_tokenize_removes_stop_words():
    tokens = _tokenize("Head of Engineering")
    assert "of" not in tokens
    assert "head" in tokens
    assert "engineering" in tokens


def test_tokenize_removes_short_tokens():
    tokens = _tokenize("VP of AI")
    assert "ai" not in tokens
    assert "vp" not in tokens


def test_tokenize_none_returns_empty():
    assert _tokenize(None) == []


def test_term_frequencies_sum_to_relative():
    jobs = [
        {"title": "Platform Engineering", "status": "saved"},
        {"title": "Platform Director", "status": "saved"},
    ]
    freqs = _term_frequencies(jobs, "title")
    assert freqs["platform"] == 1.0
    assert freqs["engineering"] == 0.5
    assert freqs["director"] == 0.5


def test_scores_are_bounded():
    saved = ["Platform Engineering"] * 5
    rejected = ["Sales Engineer"] * 5
    jobs = _make_jobs(saved, rejected)
    result = analyze_patterns(jobs, EMPTY_RULES)
    for s in result["positive_suggestions"]:
        assert -1.0 <= s["score"] <= 1.0
    for s in result["negative_suggestions"]:
        assert -1.0 <= s["score"] <= 1.0
