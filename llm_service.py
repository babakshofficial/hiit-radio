"""LLM-powered song recommendations from download history."""

import json
import logging
import os
import re
import time

import aiohttp

logger = logging.getLogger(__name__)

DISCOVER_CACHE_TTL = 3600
_discover_cache = {}


def is_configured():
    return bool(os.getenv("LLM_API_KEY", "").strip() and os.getenv("LLM_API_BASE", "").strip())


def _normalize_key(title, artist):
    return (
        (title or "").strip().lower(),
        (artist or "").strip().lower(),
    )


def _history_keys(history):
    keys = set()
    for row in history or []:
        if row.get("title"):
            keys.add(_normalize_key(row["title"], row.get("artist")))
    return keys


def _format_history(history):
    lines = []
    for row in history:
        title = (row.get("title") or "").strip()
        if not title:
            continue
        artist = (row.get("artist") or "").strip()
        album = (row.get("album") or "").strip()
        parts = [title]
        if artist:
            parts.append(artist)
        if album:
            parts.append(f"album:{album}")
        lines.append(" - ".join(parts))
    return "\n".join(lines)


def _parse_recommendations(content, limit):
    content = (content or "").strip()
    if not content:
        return []

    data = None
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

    if data is None:
        return []

    if isinstance(data, dict):
        for key in ("recommendations", "songs", "tracks", "items", "results"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            return []

    if not isinstance(data, list):
        return []

    recs = []
    for item in data:
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or item.get("track") or item.get("name") or "").strip()
        artist = (item.get("artist") or item.get("performer") or "").strip()
        if title:
            recs.append({"title": title, "artist": artist})
        if len(recs) >= limit:
            break
    return recs


def get_cached_recommendations(user_id):
    entry = _discover_cache.get(str(user_id))
    if not entry:
        return None
    if time.time() - entry["ts"] > DISCOVER_CACHE_TTL:
        _discover_cache.pop(str(user_id), None)
        return None
    return entry["recs"]


def set_cached_recommendations(user_id, recs):
    _discover_cache[str(user_id)] = {"ts": time.time(), "recs": recs}


async def recommend_songs(history, user_id=None, limit=10):
    """Return (list of {title, artist} dicts, usage_meta) or (None, usage_meta) on failure."""
    model = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()
    usage = {
        "model": model,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "success": False,
        "recommendations_count": 0,
    }
    if not is_configured():
        return None, usage

    api_base = os.getenv("LLM_API_BASE", "").rstrip("/")
    api_key = os.getenv("LLM_API_KEY", "").strip()

    history_text = _format_history(history)
    if not history_text:
        usage["success"] = True
        return [], usage

    system_prompt = (
        "You are a music recommendation assistant. "
        "Given a user's recent download history, suggest new songs they would enjoy. "
        "Do not recommend songs already in their history. "
        "Mix artists they like with similar discoveries. "
        "Respond with ONLY valid JSON in this exact shape: "
        '{"recommendations": [{"title": "Song Name", "artist": "Artist Name"}, ...]} '
        f"Include exactly {limit} recommendations."
    )
    user_prompt = (
        f"Download history (most recent first):\n{history_text}\n\n"
        f"Recommend {limit} songs as JSON."
    )

    url = f"{api_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.8,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=60) as resp:
                body = await resp.text()
                if resp.status != 200:
                    logger.error(f"LLM API {resp.status}: {body[:500]}")
                    return None, usage
                data = json.loads(body)
    except Exception as e:
        logger.error(f"LLM request failed: {e}", exc_info=True)
        return None, usage

    api_usage = data.get("usage") or {}
    usage["prompt_tokens"] = api_usage.get("prompt_tokens", 0) or 0
    usage["completion_tokens"] = api_usage.get("completion_tokens", 0) or 0
    usage["total_tokens"] = api_usage.get("total_tokens", 0) or (
        usage["prompt_tokens"] + usage["completion_tokens"]
    )

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        logger.error("LLM response missing choices/message")
        return None, usage

    recs = _parse_recommendations(content, limit)
    if not recs:
        logger.error(f"LLM returned no parseable recommendations: {content[:300]}")
        return None, usage

    known = _history_keys(history)
    filtered = []
    seen = set()
    for rec in recs:
        key = _normalize_key(rec["title"], rec.get("artist"))
        if key in known or key in seen:
            continue
        seen.add(key)
        filtered.append(rec)
    result = filtered[:limit]
    usage["success"] = True
    usage["recommendations_count"] = len(result)
    return result, usage
