from typing import Any


def score_job(job: dict, scoring_config: dict[str, Any]) -> tuple[int, list[str]]:
    """
    Score a job against the scoring section of rules.yaml.
    Returns (total_score, reasons) where reasons are human-readable match explanations.
    """
    total = 0
    reasons: list[str] = []

    for field, keywords in scoring_config.items():
        if not isinstance(keywords, dict):
            continue
        text = (job.get(field) or "").lower()
        for keyword, points in keywords.items():
            if not isinstance(points, (int, float)):
                continue
            if str(keyword).lower() in text:
                total += int(points)
                reasons.append(f"+{points}: '{keyword}' in {field}")

    for rule in scoring_config.get("absence_penalties", []):
        fields = rule.get("fields", [])
        keywords = rule.get("keywords", [])
        penalty = rule.get("penalty", 0)
        combined = " ".join((job.get(f) or "").lower() for f in fields)
        if not any(str(kw).lower() in combined for kw in keywords):
            total += int(penalty)
            reasons.append(f"{penalty}: no salary info in {', '.join(fields)}")

    return total, reasons


def validate_scoring(
    jobs: list[dict], scoring_config: dict[str, Any]
) -> list[dict]:
    """
    For each keyword in scoring_config, compute match rates across applied/saved
    vs rejected jobs.
    Returns list of dicts: {field, keyword, points, applied_matches,
    rejected_matches, signal_strength}.
    Only rows with at least one match are returned.
    signal_strength = applied_rate - rejected_rate (positive = good predictor).
    """
    applied = [j for j in jobs if j.get("status") in ("applied", "saved")]
    rejected = [j for j in jobs if j.get("status") == "rejected"]
    n_applied = len(applied)
    n_rejected = len(rejected)

    results = []
    for field, keywords in scoring_config.items():
        if not isinstance(keywords, dict):
            continue
        for keyword, points in keywords.items():
            kw_lower = str(keyword).lower()
            applied_matches = sum(
                1 for j in applied if kw_lower in (j.get(field) or "").lower()
            )
            rejected_matches = sum(
                1 for j in rejected if kw_lower in (j.get(field) or "").lower()
            )
            if applied_matches == 0 and rejected_matches == 0:
                continue
            applied_rate = applied_matches / n_applied if n_applied else 0.0
            rejected_rate = rejected_matches / n_rejected if n_rejected else 0.0
            results.append(
                {
                    "field": field,
                    "keyword": keyword,
                    "points": points,
                    "applied_matches": applied_matches,
                    "rejected_matches": rejected_matches,
                    "signal_strength": round(applied_rate - rejected_rate, 2),
                }
            )

    results.sort(key=lambda r: r["signal_strength"], reverse=True)
    return results
