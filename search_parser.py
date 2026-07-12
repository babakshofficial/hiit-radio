"""Parse /search genre:lofi style commands."""

import json
import os
import re

_MAPPINGS_PATH = os.path.join(os.path.dirname(__file__), "search_mappings.json")


def _load_mappings():
    try:
        with open(_MAPPINGS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return {"genre": {}, "mood": {}, "decade": {}}


def parse_search_command(text):
    """Parse '/search genre:lofi mood:chill' or 'genre:lofi'.

    Returns list of (category, key, itunes_query) or empty list.
    """
    text = (text or "").strip()
    if text.startswith("/search"):
        text = text[len("/search"):].strip()

    mappings = _load_mappings()
    results = []
    for match in re.finditer(r"(genre|mood|decade):(\w+)", text, re.IGNORECASE):
        cat, key = match.group(1).lower(), match.group(2).lower()
        query = mappings.get(cat, {}).get(key)
        if query:
            results.append((cat, key, query))
    return results


def format_search_help():
    mappings = _load_mappings()
    cat_labels = {"genre": "ژانر", "mood": "حالت", "decade": "دهه"}
    lines = [
        "دستورات جستجو:",
        "/search genre:lofi",
        "/search mood:workout",
        "/search decade:80s",
        "",
        "دسته‌بندی‌های موجود:",
    ]
    for cat, items in mappings.items():
        label = cat_labels.get(cat, cat)
        keys = ", ".join(sorted(items.keys())[:8])
        if len(items) > 8:
            keys += ", ..."
        lines.append(f"  {label}: {keys}")
    return "\n".join(lines)
