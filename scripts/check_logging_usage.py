"""Pre-commit check: enforce unified logging usage.

Fails if code uses the standard logging module directly or bypasses
the project's get_logger utility, except in the central config module.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


# Files allowed to use stdlib logging directly
ALLOWLIST = {
    SRC / "scriptrag" / "config" / "logging.py",
}


PATTERNS: dict[str, re.Pattern[str]] = {
    "logging.getLogger": re.compile(r"\blogging\.getLogger\s*\("),
    "structlog.get_logger": re.compile(r"\bstructlog\.get_logger\s*\("),
    "direct logging call": re.compile(
        r"\blogging\.(info|debug|warning|error|exception|critical)\s*\("
    ),
    "import logging": re.compile(r"^\s*(import logging|from logging import )", re.M),
}


def is_python_file(path: Path) -> bool:
    """Return True if the path looks like a Python source file under src."""
    return path.suffix == ".py" and (SRC in path.parents or path.parent == SRC)


def should_skip(path: Path) -> bool:
    """Return True for files excluded from this check.

    Excludes tests, docs, notebooks, and the central logging config.
    """
    rel = path.relative_to(ROOT)
    if path in ALLOWLIST:
        return True
    parts = set(rel.parts)
    return "tests" in parts or "docs" in parts or "notebooks" in parts


def main() -> int:
    """Scan for disallowed logging usage and report any offenders."""
    offenders: list[tuple[Path, str, int, str]] = []

    for path in SRC.rglob("*.py"):
        if should_skip(path):
            continue

        text = path.read_text(encoding="utf-8", errors="ignore")

        for label, pattern in PATTERNS.items():
            for m in pattern.finditer(text):
                # capture line no
                line_no = text.count("\n", 0, m.start()) + 1
                line = text.splitlines()[line_no - 1].rstrip()
                offenders.append((path, label, line_no, line))

    if offenders:
        print("Found disallowed logging usage:")
        for path, label, line_no, line in offenders:
            print(f"- {label}: {path.relative_to(ROOT)}:{line_no}: {line}")
        print(
            "\nUse `from scriptrag.config import get_logger` and "
            "`logger = get_logger(__name__)`."
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
