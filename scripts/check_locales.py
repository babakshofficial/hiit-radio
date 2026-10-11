#!/usr/bin/env python3
"""Ensure all locale files expose the same STRINGS keys (run from repo root)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from locales import SUPPORTED, get_strings

def main():
    base = set(get_strings("en").keys())
    errors = []
    for lang in SUPPORTED:
        keys = set(get_strings(lang).keys())
        missing = base - keys
        extra = keys - base
        if missing:
            errors.append(f"{lang}: missing {len(missing)} keys, e.g. {sorted(missing)[:5]}")
        if extra:
            errors.append(f"{lang}: extra {len(extra)} keys, e.g. {sorted(extra)[:5]}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"OK: {len(base)} keys across {len(SUPPORTED)} locales")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
