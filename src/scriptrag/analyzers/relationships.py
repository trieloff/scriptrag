"""Character relationships analyzer using Bible aliases.

This analyzer derives per-scene character presence, co-presence, and speaking
relationships based on an alias map authored in the Script Bible and stored in
scripts.metadata (DB). It performs exact, case-insensitive, word-boundary
matching with support for multi-word aliases and punctuation (dots, hyphens).

It does NOT use any fuzzy matching/NER.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from scriptrag.analyzers.base import BaseSceneAnalyzer
from scriptrag.config import get_logger, get_settings

logger = get_logger(__name__)


def _normalize_speaker(raw: str) -> str:
    """Normalize a dialogue speaker line to uppercase canonical-ish form.

    Rules:
    - Uppercase
    - Strip trailing parentheticals like "(CONT'D)", "(O.S.)", etc.
    - Trim whitespace
    """
    # Remove trailing parentheticals
    cleaned = re.sub(r"\s*\([^)]*\)\s*$", "", raw or "")
    return cleaned.strip().upper()


def _build_alias_index(
    bible_characters: dict[str, Any] | None,
) -> tuple[dict[str, str], set[str]]:
    """Build a mapping alias->canonical and set of canonicals.

    Input format (stored in scripts.metadata):
    {
      "version": 1,
      "extracted_at": "ISO8601",
      "characters": [
        {"canonical": "JANE SMITH", "aliases": ["JANE", "MS. SMITH"], ...},
        ...
      ]
    }
    """
    alias_to_canonical: dict[str, str] = {}
    canonicals: set[str] = set()
    if not bible_characters:
        return alias_to_canonical, canonicals

    chars = bible_characters.get("characters") or []
    for entry in chars:
        canonical = (entry.get("canonical") or "").strip().upper()
        if not canonical:
            continue
        canonicals.add(canonical)
        for alias in entry.get("aliases") or []:
            a = (alias or "").strip().upper()
            if not a:
                continue
            alias_to_canonical[a] = canonical
        # Ensure canonical maps to itself as a fallback
        alias_to_canonical.setdefault(canonical, canonical)

    return alias_to_canonical, canonicals


def _compile_alias_patterns(aliases: list[str]) -> list[tuple[re.Pattern[str], str]]:
    """Compile case-insensitive, word-boundary-like regex for each alias.

    We consider boundaries as transitions to/from non-alphanumeric to avoid
    partial matches (e.g., BOB != BOBBIN). Periods and hyphens are treated
    as non-alphanumerics (boundaries).
    """
    patterns: list[tuple[re.Pattern[str], str]] = []
    for alias in aliases:
        # Escape alias literally
        escaped = re.escape(alias)
        # Custom boundary: not preceded/followed by [A-Za-z0-9]
        pattern = rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])"
        patterns.append((re.compile(pattern, re.IGNORECASE), alias))
    return patterns


@dataclass
class _AliasIndex:
    alias_to_canonical: dict[str, str]
    canonicals: set[str]
    patterns: list[tuple[re.Pattern[str], str]]


class CharacterRelationshipsAnalyzer(BaseSceneAnalyzer):
    """Derive per-scene character relationships from Bible aliases.

    Reads a script-level alias map (authored in the Script Bible) and computes
    per-scene presence, co-presence, and speaking edges using exact, case-
    insensitive, word-boundary alias matching. No fuzzy matching is used.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Create a relationships analyzer.

        Args:
        
            config: Optional configuration. Supports key "bible_characters" to
                inject a pre-parsed alias map for tests.
        """
        super().__init__(config)
        # Set by AnalyzeCommand when available; used to find script file_path
        self.script: Any | None = None
        # Optional direct alias map injection for tests: config["bible_characters"]
        self._index: _AliasIndex | None = None

    @property
    def name(self) -> str:
        """Return analyzer name for registration."""
        return "relationships"

    async def initialize(self) -> None:  # pragma: no cover - trivial
        """Initialize analyzer from provided config if available."""
        # Preload alias index if provided via config, else read from DB lazily
        provided = self.config.get("bible_characters") if self.config else None
        if provided:
            alias_to_canonical, canonicals = _build_alias_index(provided)
            patterns = _compile_alias_patterns(list(alias_to_canonical.keys()))
            self._index = _AliasIndex(alias_to_canonical, canonicals, patterns)

    def _ensure_index_from_db(self) -> None:
        """Load alias index from DB scripts.metadata if not already loaded."""
        if self._index is not None:
            return
        # Need script to know which file we're analyzing
        source_file: str | None = None
        script_obj = self.script
        if script_obj is not None and hasattr(script_obj, "metadata"):
            meta = cast(dict[str, Any], script_obj.metadata)
            source_file = meta.get("source_file")
        if not source_file:
            logger.info("Relationships analyzer: no script source_file; skipping.")
            self._index = _AliasIndex({}, set(), [])
            return

        try:
            settings = get_settings()
            db_path = settings.database_path
            with sqlite3.connect(str(db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.execute(
                    "SELECT metadata FROM scripts WHERE file_path = ?",
                    (str(Path(source_file).resolve()),),
                )
                row = cur.fetchone()
                bible_chars: dict[str, Any] | None = None
                if row and row["metadata"]:
                    try:
                        meta = json.loads(row["metadata"]) or {}
                        # Prefer dotted key; fall back to nested structure
                        bible_chars = meta.get("bible.characters")
                        if not bible_chars:
                            bible = meta.get("bible") or {}
                            bible_chars = bible.get("characters")
                    except Exception:  # pragma: no cover
                        bible_chars = None

                alias_to_canonical, canonicals = _build_alias_index(bible_chars)
                patterns = _compile_alias_patterns(list(alias_to_canonical.keys()))
                self._index = _AliasIndex(alias_to_canonical, canonicals, patterns)
        except Exception as e:  # pragma: no cover
            logger.info(f"Relationships analyzer: DB load failed: {e}")
            self._index = _AliasIndex({}, set(), [])

    async def analyze(self, scene: dict[str, Any]) -> dict[str, Any]:
        """Analyze a scene to produce relationships metadata.

        Returns an empty dict when no alias map is available.
        """
        # Ensure alias index is ready
        if self._index is None:
            self._ensure_index_from_db()

        if not self._index or not self._index.alias_to_canonical:
            # No-op when no bible map
            return {}

        # Collect speaking characters (normalize speakers via alias map)
        speaking_set: set[str] = set()
        for d in scene.get("dialogue") or []:
            speaker = _normalize_speaker(d.get("character", ""))
            # Map speaker via alias table if known; else skip
            canonical = self._resolve_alias(speaker)
            if canonical:
                speaking_set.add(canonical)

        # Collect mentions in heading + action lines via alias patterns
        present_set: set[str] = set(speaking_set)
        text_blobs: list[str] = []
        if scene.get("heading"):
            text_blobs.append(scene["heading"])
        for line in scene.get("action") or []:
            text_blobs.append(line)
        mentions = self._scan_mentions("\n".join(text_blobs))
        present_set.update(mentions)

        if not present_set:
            return {}

        # Build co-presence pairs (unordered, unique, sorted)
        present_list = sorted(present_set)
        co_pairs: list[list[str]] = []
        for i in range(len(present_list)):
            for j in range(i + 1, len(present_list)):
                co_pairs.append([present_list[i], present_list[j]])

        # Build speaking edges (speaker -> every other present character)
        speaking_edges: set[tuple[str, str]] = set()
        for speaker in sorted(speaking_set):
            for other in sorted(present_set):
                if other != speaker:
                    speaking_edges.add((speaker, other))

        return {
            "present": present_list,
            "speaking": sorted(speaking_set),
            "co_presence_pairs": [list(p) for p in co_pairs],
            "speaking_edges": [list(e) for e in sorted(speaking_edges)],
            "stats": {
                "present_count": len(present_set),
                "speaking_count": len(speaking_set),
            },
        }

    def _resolve_alias(self, name_or_alias: str) -> str | None:
        # Exact, case-insensitive match of alias keys
        key = name_or_alias.strip().upper()
        return self._index.alias_to_canonical.get(key) if self._index else None

    def _scan_mentions(self, text: str) -> set[str]:
        """Scan text for alias matches and return set of canonical names."""
        found: set[str] = set()
        if not self._index:
            return found
        for pattern, alias in self._index.patterns:
            if pattern.search(text):
                canonical = self._index.alias_to_canonical.get(alias)
                if canonical:
                    found.add(canonical)
        return found
