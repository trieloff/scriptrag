"""Query specification and header parser for .sql files.

Parses leading SQL comments describing query metadata:
- ``-- name: <query_name>``
- ``-- description: <one-line description>``
- ``-- param: <name> <type> <required|optional> [default=<value>]``
  ``[help="text"] [choices=a|b|c]``
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

ParamType = Literal["str", "int", "float", "bool"]


@dataclass
class ParamSpec:
    """Parameter specification for a query.

    Defines the name, type, requirement, and optional metadata for a
    single parameter consumed by a SQL query.
    """

    name: str
    type: ParamType
    required: bool
    default: Any | None = None
    help: str | None = None
    choices: list[str] | None = None


@dataclass
class QuerySpec:
    """Parsed query specification loaded from a .sql file."""

    name: str
    description: str
    params: list[ParamSpec]
    sql: str
    source_path: Path


_NAME_RE = re.compile(r"^--\s*name:\s*(?P<name>.+?)\s*$", re.IGNORECASE)
_DESC_RE = re.compile(r"^--\s*description:\s*(?P<desc>.+?)\s*$", re.IGNORECASE)
_PARAM_RE = re.compile(
    r"^--\s*param:\s*(?P<name>\w+)\s+"
    r"(?P<type>str|int|float|bool)\s+"
    r"(?P<req>required|optional)"
    r"(?P<extras>.*)$",
    re.IGNORECASE,
)
_DEFAULT_RE = re.compile(r"\bdefault=([^\s]+)")
_HELP_RE = re.compile(r'\bhelp="([^"]*)"')
_CHOICES_RE = re.compile(r"\bchoices=([^\s]+)")


def parse_query_file(path: Path) -> QuerySpec:
    """Parse a .sql file into a QuerySpec using the header comment block."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    header: list[str] = []
    body_start = 0

    for idx, line in enumerate(lines):
        if line.strip().startswith("--") or not line.strip():
            header.append(line)
        else:
            body_start = idx
            break

    name: str | None = None
    desc: str = ""
    params: list[ParamSpec] = []

    for h in header:
        m = _NAME_RE.match(h)
        if m:
            name = m.group("name").strip()
            continue
        m = _DESC_RE.match(h)
        if m:
            desc = m.group("desc").strip()
            continue
        m = _PARAM_RE.match(h)
        if m:
            pname = m.group("name").strip()
            ptype = m.group("type").lower()
            req = m.group("req").lower() == "required"
            extras = m.group("extras") or ""

            default: Any | None = None
            help_text: str | None = None
            choices: list[str] | None = None

            dm = _DEFAULT_RE.search(extras)
            if dm:
                raw = dm.group(1)
                default = _cast_default(raw, ptype)

            hm = _HELP_RE.search(extras)
            if hm:
                help_text = hm.group(1)

            cm = _CHOICES_RE.search(extras)
            if cm:
                choices = cm.group(1).split("|")

            params.append(
                ParamSpec(
                    name=pname,
                    type=ptype,  # type: ignore[arg-type]
                    required=req,
                    default=default,
                    help=help_text,
                    choices=choices,
                )
            )

    if name is None:
        # Fallback to filename stem if name missing
        name = path.stem

    sql = "\n".join(lines[body_start:]).strip()

    return QuerySpec(
        name=name,
        description=desc,
        params=params,
        sql=sql,
        source_path=path,
    )


def _cast_default(raw: str, ptype: str) -> Any:
    if ptype == "int":
        return int(raw)
    if ptype == "float":
        return float(raw)
    if ptype == "bool":
        return _parse_bool(raw)
    # str
    # Strip surrounding quotes if present
    if (raw.startswith('"') and raw.endswith('"')) or (
        raw.startswith("'") and raw.endswith("'")
    ):
        return raw[1:-1]
    return raw


def _parse_bool(v: str | bool | int) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return v != 0
    s = str(v).strip().lower()
    return s in {"1", "true", "yes", "y", "on"}
