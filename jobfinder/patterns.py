import re

STOP_WORDS = {
    "of", "the", "a", "and", "or", "for", "in", "at", "to", "is",
    "with", "you", "we", "be", "your", "our", "an", "on", "as", "by",
    "are", "was", "has", "have", "it", "its", "this", "that", "from",
}


def analyze_patterns(jobs: list[dict], existing_rules: dict, top_n: int = 10) -> dict:
    """
    jobs: list of dicts with keys: title, company, status ('saved' | 'rejected')
    existing_rules: current rules dict (to exclude already-known terms)
    Returns {"positive_suggestions": [...], "negative_suggestions": [...]}
    or {"positive_suggestions": [], "negative_suggestions": []} if insufficient data.
    """
    positives = [j for j in jobs if j.get("status") == "saved"]
    negatives = [j for j in jobs if j.get("status") == "rejected"]

    if not positives or not negatives:
        return {"positive_suggestions": [], "negative_suggestions": []}

    existing_terms = _collect_existing_terms(existing_rules)

    suggestions_pos = []
    suggestions_neg = []

    for field in ("title", "company"):
        pos_freq = _term_frequencies(positives, field)
        neg_freq = _term_frequencies(negatives, field)
        all_terms = set(pos_freq) | set(neg_freq)

        for term in all_terms:
            if term in existing_terms:
                continue
            score = pos_freq.get(term, 0.0) - neg_freq.get(term, 0.0)
            entry = {"term": term, "score": round(score, 4), "source": field}
            if score > 0:
                suggestions_pos.append(entry)
            elif score < 0:
                suggestions_neg.append(entry)

    suggestions_pos.sort(key=lambda x: x["score"], reverse=True)
    suggestions_neg.sort(key=lambda x: x["score"])

    return {
        "positive_suggestions": suggestions_pos[:top_n],
        "negative_suggestions": suggestions_neg[:top_n],
    }


def _tokenize(text: str | None) -> list[str]:
    if not text:
        return []
    tokens = re.split(r"[^a-zA-Z]+", text.lower())
    return [t for t in tokens if t and len(t) >= 3 and t not in STOP_WORDS]


def _term_frequencies(jobs: list[dict], field: str) -> dict[str, float]:
    counts: dict[str, int] = {}
    total = len(jobs)
    if total == 0:
        return {}
    for job in jobs:
        for token in _tokenize(job.get(field)):
            counts[token] = counts.get(token, 0) + 1
    return {term: count / total for term, count in counts.items()}


def _collect_existing_terms(rules: dict) -> set[str]:
    terms: set[str] = set()
    for field in ("title", "company", "location", "description"):
        field_rules = rules.get(field, {})
        for key in ("positive", "negative", "require_any"):
            for term in field_rules.get(key, []):
                for token in _tokenize(term):
                    terms.add(token)
    return terms
