"""Bible alias extraction using LLM for ScriptRAG."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime

from scriptrag.config import ScriptRAGSettings, get_logger
from scriptrag.parser.bible_parser import ParsedBible

logger = get_logger(__name__)


class BibleAliasExtractor:
    """Handles extraction of character aliases from bible documents using LLM."""

    def __init__(self, settings: ScriptRAGSettings) -> None:
        """Initialize alias extractor.

        Args:
            settings: Configuration settings
        """
        self.settings = settings

    async def extract_aliases(self, parsed_bible: ParsedBible) -> dict | None:
        """Use an LLM to extract canonical+aliases JSON from bible text.

        Returns None if LLM isn't configured. The expected return:
        {
          "version": 1,
          "extracted_at": "ISO8601",
          "characters": [
            {"canonical": "JANE SMITH", "aliases": ["JANE", "MS. SMITH"], ...},
            ...
          ]
        }

        Args:
            parsed_bible: Parsed bible data

        Returns:
            Extracted alias map or None if LLM not configured
        """
        settings = self.settings
        if (
            not settings.llm_model
            and not settings.llm_provider
            and not settings.llm_api_key
        ):
            return None

        try:
            from scriptrag.utils import get_default_llm_client

            client = await get_default_llm_client()

            # Concatenate relevant chunks into a single prompt context (bounded)
            # Keep it lightweight: headings + first N chars (configurable)
            chunks_text = []
            limit = self.settings.bible_llm_context_limit
            total = 0
            for ch in parsed_bible.chunks:
                frag = f"# {ch.heading or ''}\n\n{ch.content}\n\n"
                if total + len(frag) > limit:
                    remaining = max(0, limit - total)
                    if remaining > 0:
                        frag = frag[:remaining]
                    else:
                        break
                chunks_text.append(frag)
                total += len(frag)

            system = (
                "You extract canonical character names and their aliases "
                "from a screenplay bible. "
                "Return strict JSON with fields: version (1), "
                "extracted_at (ISO8601), characters (list of objects). "
                "Each object has: canonical (UPPERCASE string), "
                "aliases (list of UPPERCASE strings). "
                "Exclude generic nouns; dedupe and uppercase all outputs."
            )
            user = (
                "Extract character canonical names and aliases from the "
                "following notes. "
                "Focus on sections describing characters or naming "
                "variations.\n\n" + "\n".join(chunks_text)
            )
            resp = await client.complete(
                messages=[{"role": "user", "content": user}],
                system=system,
                temperature=0.0,
                max_tokens=800,
            )
            text = resp.text.strip() if hasattr(resp, "text") else str(resp)
            # Try to parse as JSON; if the model wrapped in code fences, strip them
            text = re.sub(
                r"^```json\s*|```$",
                "",
                text.strip(),
                flags=re.IGNORECASE | re.MULTILINE,
            )
            data = json.loads(text)

            # Basic validation/normalization
            chars = []
            for entry in data.get("characters", []) or []:
                canonical = (entry.get("canonical") or "").strip().upper()
                aliases = [
                    (a or "").strip().upper() for a in (entry.get("aliases") or []) if a
                ]
                if canonical:
                    # dedupe while preserving order
                    unique_aliases = list(dict.fromkeys([a for a in aliases if a]))
                    # Ensure canonical not duplicated in aliases
                    unique_aliases = [a for a in unique_aliases if a != canonical]
                    chars.append({"canonical": canonical, "aliases": unique_aliases})

            return {
                "version": 1,
                "extracted_at": datetime.utcnow().isoformat() + "Z",
                "characters": chars,
            }
        except Exception as e:  # pragma: no cover
            logger.debug(f"LLM alias extraction failed: {e}")
            return None

    def attach_alias_map_to_script(
        self, conn: sqlite3.Connection, script_id: int, alias_map: dict
    ) -> None:
        """Store alias map under scripts.metadata['bible']['characters'].

        Args:
            conn: Database connection
            script_id: ID of the script
            alias_map: Extracted alias mapping
        """
        cur = conn.execute("SELECT metadata FROM scripts WHERE id = ?", (script_id,))
        row = cur.fetchone()
        try:
            meta = json.loads(row[0]) if row and row[0] else {}
        except Exception:  # pragma: no cover
            meta = {}
        # Store under dotted key to match index/analyzer consumers
        meta["bible.characters"] = alias_map
        conn.execute(
            (
                "UPDATE scripts SET metadata = ?, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = ?"
            ),
            (json.dumps(meta), script_id),
        )

    def attach_aliases_to_characters(
        self, conn: sqlite3.Connection, script_id: int, alias_map: dict
    ) -> None:
        """If 'aliases' column exists, update characters' aliases by canonical match.

        Args:
            conn: Database connection
            script_id: ID of the script
            alias_map: Extracted alias mapping
        """
        # Check schema for aliases column
        try:
            has_aliases = False
            for row in conn.execute("PRAGMA table_info(characters)"):
                if (row[1] if isinstance(row, tuple) else row["name"]) == "aliases":
                    has_aliases = True
                    break
            if not has_aliases:
                return

            # Build canonical->aliases
            canonical_to_aliases: dict[str, list[str]] = {}
            for entry in alias_map.get("characters") or []:
                canonical = (entry.get("canonical") or "").strip().upper()
                aliases = [
                    (a or "").strip().upper() for a in (entry.get("aliases") or []) if a
                ]
                if canonical:
                    canonical_to_aliases[canonical] = sorted(dict.fromkeys(aliases))

            if not canonical_to_aliases:
                return

            # Fetch character IDs and names for this script
            for row in conn.execute(
                "SELECT id, name FROM characters WHERE script_id = ?", (script_id,)
            ):
                cid = row[0]
                name = (row[1] or "").strip().upper()
                if name in canonical_to_aliases:
                    conn.execute(
                        "UPDATE characters SET aliases = ? WHERE id = ?",
                        (json.dumps(canonical_to_aliases[name]), cid),
                    )
        except Exception as e:  # pragma: no cover
            logger.debug(f"Skipping character alias attachment: {e}")
