#!/usr/bin/env python3
"""Offline sanity checks for the Android resources and strings.

Catches the failures that only show up deep inside `:app:mergeDebugResources`
(otherwise a 3-minute CI round trip):

  * duplicate resource names in a strings file  ("Found item String/x more than one time")
  * XML that does not parse
  * a name present in `values/` but missing from `values-fa/` (and vice versa)
  * placeholder-argument mismatches between locales (%1$s vs %2$s)
  * `R.string.*` keys referenced from Kotlin that no longer exist

Run:  python3 scripts/check-android-resources.py
Exit: 0 = clean, 1 = problems found.
"""

from __future__ import annotations

import collections
import glob
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "android", "app", "src", "main", "res")
KOTLIN = os.path.join(ROOT, "android", "app", "src", "main", "java")

LOCALES = ["values", "values-fa"]


def parse_strings(path: str) -> collections.Counter:
    """Returns a Counter of resource names; also validates the XML."""
    raw = open(path, encoding="utf-8").read()
    ET.fromstring(raw)  # raises on malformed XML
    return collections.Counter(re.findall(r'<string name="([^"]+)"', raw))


def body_of(raw: str, name: str) -> str:
    m = re.search(r'<string name="%s"[^>]*>(.*?)</string>' % re.escape(name), raw, re.S)
    return m.group(1) if m else ""


def main() -> int:
    problems: list[str] = []

    counters: dict[str, collections.Counter] = {}
    raws: dict[str, str] = {}
    for loc in LOCALES:
        path = os.path.join(RES, loc, "strings.xml")
        if not os.path.exists(path):
            problems.append(f"missing strings file: {path}")
            continue
        try:
            counters[loc] = parse_strings(path)
        except ET.ParseError as exc:
            problems.append(f"{loc}/strings.xml is not valid XML: {exc}")
            counters[loc] = collections.Counter()
        raws[loc] = open(path, encoding="utf-8").read()

    for loc, counter in counters.items():
        for name, count in counter.items():
            if count > 1:
                problems.append(f"{loc}/strings.xml: '{name}' declared {count} times")

    if len(counters) == len(LOCALES):
        a, b = counters[LOCALES[0]], counters[LOCALES[1]]
        for name in sorted(set(a) - set(b)):
            problems.append(f"'{name}' exists in {LOCALES[0]} but not in {LOCALES[1]}")
        for name in sorted(set(b) - set(a)):
            problems.append(f"'{name}' exists in {LOCALES[1]} but not in {LOCALES[0]}")
        for name in sorted(set(a) & set(b)):
            pa = sorted(re.findall(r"%(\d)\$[sdf]", body_of(raws[LOCALES[0]], name)))
            pb = sorted(re.findall(r"%(\d)\$[sdf]", body_of(raws[LOCALES[1]], name)))
            if pa != pb:
                problems.append(f"placeholder mismatch in '{name}': {pa} vs {pb}")

    known = set().union(*counters.values()) if counters else set()
    referenced: set[str] = set()
    for path in glob.glob(os.path.join(KOTLIN, "**", "*.kt"), recursive=True):
        referenced |= set(re.findall(r"R\.string\.(\w+)", open(path, encoding="utf-8").read()))
    for name in sorted(referenced - known):
        problems.append(f"R.string.{name} is used in Kotlin but not declared")

    if problems:
        print("Android resource checks FAILED:")
        for p in problems:
            print("  -", p)
        return 1

    print(f"Android resource checks OK ({len(known)} strings, "
          f"{len(referenced)} referenced, locales: {', '.join(LOCALES)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
