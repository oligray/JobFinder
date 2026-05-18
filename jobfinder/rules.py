from typing import Any
import yaml

_DEFAULT_RULES: dict = {
    "title":       {"require_any": [], "positive": [], "negative": []},
    "company":     {"positive": [], "negative": []},
    "location":    {"positive": [], "negative": []},
    "description": {"positive": [], "negative": []},
    "pattern_suggestion_threshold": 10,
    "job_boards": [],
    "search_pages_per_board": 3,
}


def load_rules(path: str = "rules.yaml") -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return _merge_defaults(data)
    except FileNotFoundError:
        return _merge_defaults({})


def save_rules(rules: dict[str, Any], path: str = "rules.yaml") -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(rules, f, default_flow_style=False, allow_unicode=True)


def apply_rules(job: dict, rules: dict) -> tuple[bool, str]:
    """
    Returns (should_include, reason).
    job keys: title, company, location, description (all may be None).
    """
    for field in ("title", "company", "location", "description"):
        text = job.get(field) or ""
        field_rules = rules.get(field, {})
        ok, reason = _check_field(text, field_rules, field)
        if not ok:
            return False, reason

    return True, ""


def _check_field(text: str, field_rules: dict, field_name: str) -> tuple[bool, str]:
    lower = text.lower()

    for term in field_rules.get("negative", []):
        if term.lower() in lower:
            return False, f"Excluded: {field_name} matches '{term}'"

    require_any = field_rules.get("require_any", [])
    if require_any and not any(t.lower() in lower for t in require_any):
        return False, f"Excluded: {field_name} does not match any required term"

    return True, ""


def _merge_defaults(data: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for field in ("title", "company", "location", "description"):
        defaults = _DEFAULT_RULES.get(field, {}).copy()
        incoming = data.get(field, {}) or {}
        defaults.update(incoming)
        result[field] = defaults
    result["pattern_suggestion_threshold"] = data.get(
        "pattern_suggestion_threshold",
        _DEFAULT_RULES["pattern_suggestion_threshold"]
    )
    result["job_boards"] = data.get("job_boards", _DEFAULT_RULES["job_boards"])
    result["search_pages_per_board"] = data.get(
        "search_pages_per_board",
        _DEFAULT_RULES["search_pages_per_board"]
    )
    return result
