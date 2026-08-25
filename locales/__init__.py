"""Locale registry for the HiiT Radio bot.

Each locale module exposes a flat ``STRINGS`` dict keyed by message id.
``get_strings`` returns a merged dict so a missing key in any locale falls
back to Persian instead of raising.
"""

from importlib import import_module

SUPPORTED = ("fa", "en", "fr", "es", "ru", "it")
DEFAULT_LANG = "fa"

STRINGS = {
    lang: import_module(f"{__name__}.{lang}").STRINGS for lang in SUPPORTED
}

# Telegram language_code -> supported locale. Keys are lowercase, without the
# region suffix (which is stripped before lookup).
_ALIASES = {
    "fa": "fa",
    "per": "fa",
    "fas": "fa",
    "prs": "fa",  # Dari
    "en": "en",
    "eng": "en",
    "fr": "fr",
    "fra": "fr",
    "fre": "fr",
    "es": "es",
    "spa": "es",
    "ca": "es",  # Catalan speakers get Spanish rather than Persian
    "gl": "es",
    "ru": "ru",
    "rus": "ru",
    "be": "ru",
    "uk": "ru",
    "kk": "ru",
    "it": "it",
    "ita": "it",
}

_MERGED_CACHE = {}


def normalize_lang(code):
    """Map a Telegram ``language_code`` to a supported locale, else ``None``."""
    if not code:
        return None
    base = str(code).strip().lower().replace("_", "-").split("-")[0]
    if not base:
        return None
    if base in SUPPORTED:
        return base
    return _ALIASES.get(base)


def get_strings(lang):
    """Return the string table for ``lang``, backfilled with Persian defaults."""
    resolved = normalize_lang(lang) or DEFAULT_LANG
    cached = _MERGED_CACHE.get(resolved)
    if cached is None:
        merged = dict(STRINGS[DEFAULT_LANG])
        merged.update(STRINGS[resolved])
        cached = _MERGED_CACHE[resolved] = merged
    return cached


def get(lang, key, default=""):
    """Look up a single key with locale fallback."""
    return get_strings(lang).get(key, default)


def missing_keys(lang):
    """Keys present in the default locale but absent from ``lang``."""
    resolved = normalize_lang(lang) or DEFAULT_LANG
    return sorted(set(STRINGS[DEFAULT_LANG]) - set(STRINGS[resolved]))


__all__ = [
    "SUPPORTED",
    "DEFAULT_LANG",
    "STRINGS",
    "get_strings",
    "get",
    "normalize_lang",
    "missing_keys",
]
