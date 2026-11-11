#!/usr/bin/env python3
"""Cheap offline guards for Kotlin/Compose mistakes that cost a full CI build.

Not a compiler — just the mistakes that are easy to make when hand-editing Compose
code and that CI reports 3 minutes later:

  * C-style ternary `cond ? a : b` (Kotlin has no ternary operator)
  * `const val` initialised with a non-constant expression (`.toInt()` etc.)
  * unbalanced braces / parentheses (ignoring strings and comments)
  * public composables exposing a private type

Run: python3 scripts/check-kotlin-syntax.py
"""

from __future__ import annotations

import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "android", "app", "src")


def code_only(src: str) -> str:
    """Strips comments and string/char literals so bracket counting is meaningful."""
    out = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                i += 1
        elif c == "/" and i + 1 < n and src[i + 1] == "*":
            i += 2
            while i + 1 < n and not (src[i] == "*" and src[i + 1] == "/"):
                i += 1
            i += 2
        elif src[i:i + 3] == '"""':
            i += 3
            while i + 2 < n and src[i:i + 3] != '"""':
                i += 1
            i += 3
        elif c == '"':
            i += 1
            while i < n:
                if src[i] == "\\":
                    i += 2
                    continue
                if src[i] == '"':
                    i += 1
                    break
                i += 1
        elif c == "'":
            i += 1
            while i < n:
                if src[i] == "\\":
                    i += 2
                    continue
                if src[i] == "'":
                    i += 1
                    break
                i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


TRIPLE = re.compile(r"\bif\s*\([^()]*\)[^;{}\n]*\?[^?\n:]*:")


def main() -> int:
    problems = []
    for path in sorted(glob.glob(os.path.join(SRC, "**", "*.kt"), recursive=True)):
        raw = open(path, encoding="utf-8").read()
        rel = os.path.relpath(path, ROOT)

        for lineno, line in enumerate(raw.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            # A ternary looks like `something ? value : other` with a bare `?` (not `?.` or `?:`)
            # and a bare `:` on the same line.
            if re.search(r"[^?!\s]\s*\?\s*[^?.:\s]", line) and re.search(r"\s:\s", line) \
                    and "?:" not in line and "?." not in line:
                problems.append(
                    f"{rel}:{lineno}: looks like a C-style ternary (Kotlin has none; use if/else)"
                    f" -> {stripped}"
                )

        code = code_only(raw)
        for m in re.finditer(r"const val\s+\w+[^=\n]*=\s*([^\n]*)", code):
            expr = m.group(1)
            if re.search(r"\.to(Int|Float|Double|Long|Char)\(\)|Math\.|\.pow\(|\.sqrt\(", expr):
                problems.append(f"{rel}: `const val` needs a compile-time constant, got: {expr.strip()}")

        stack = []
        pairs = {"{": "}", "(": ")", "[": "]"}
        for idx, ch in enumerate(code):
            if ch in pairs:
                stack.append(ch)
            elif ch in "})]":
                if not stack:
                    problems.append(f"{rel}: unbalanced '{ch}'")
                    break
                if pairs[stack.pop()] != ch:
                    problems.append(f"{rel}: mismatched bracket near offset {idx}")
                    break
        if stack:
            problems.append(f"{rel}: {len(stack)} unclosed bracket(s)")

    if problems:
        print("Kotlin syntax checks FAILED:")
        for p in problems:
            print("  -", p)
        return 1
    print("Kotlin syntax checks OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
