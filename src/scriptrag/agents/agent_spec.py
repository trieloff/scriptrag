"""Agent specification class for markdown-based agent definitions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import frontmatter
from markdown_it import MarkdownIt


class AgentSpec:
    """Represents a parsed agent specification from markdown."""

    def __init__(
        self,
        name: str,
        description: str,
        version: str,
        requires_llm: bool,
        context_query: str,
        output_schema: dict[str, Any],
        analysis_prompt: str,
    ) -> None:
        """Initialize an agent specification.

        Args:
            name: Agent name (derived from filename)
            description: Agent description
            version: Agent version
            requires_llm: Whether the agent requires an LLM
            context_query: SQL query for context
            output_schema: JSON schema for output validation
            analysis_prompt: Prompt template for LLM
        """
        self.name = name
        self.description = description
        self.version = version
        self.requires_llm = requires_llm
        self.context_query = context_query
        self.output_schema = output_schema
        self.analysis_prompt = analysis_prompt

    @classmethod
    def from_markdown(cls, markdown_path: Path) -> AgentSpec:
        """Load an agent specification from a markdown file.

        Args:
            markdown_path: Path to the markdown file

        Returns:
            Parsed AgentSpec instance

        Raises:
            ValueError: If the markdown file is invalid
        """
        if not markdown_path.exists():
            raise ValueError(f"Agent specification not found: {markdown_path}")

        # Parse the markdown file with frontmatter
        with markdown_path.open(encoding="utf-8") as f:
            post = frontmatter.load(f)

        # Extract metadata from frontmatter
        metadata = post.metadata
        if not metadata:
            raise ValueError(f"No frontmatter found in {markdown_path}")

        # Agent name is always derived from filename
        agent_name = markdown_path.stem

        # Check for required fields
        required_fields = ["description", "version"]
        for field in required_fields:
            if field not in metadata:
                raise ValueError(f"Missing required field '{field}' in frontmatter")

        # Extract code blocks from content using proper markdown parser
        code_blocks = cls._extract_code_blocks(post.content)

        # Find context query block (SQL)
        context_query = ""
        for block in code_blocks:
            if block["lang"] == "sql":
                context_query = block["content"]
                break

        # Find output schema block (JSON)
        output_schema = {}
        for block in code_blocks:
            if block["lang"] == "json":
                try:
                    output_schema = json.loads(block["content"])
                    break
                except json.JSONDecodeError:
                    continue

        if not output_schema:
            raise ValueError("No valid JSON schema found in code blocks")

        # The full content becomes the analysis prompt
        analysis_prompt = post.content

        return cls(
            name=agent_name,
            description=metadata["description"],
            version=str(metadata["version"]),  # Ensure version is string
            requires_llm=metadata.get("requires_llm", True),
            context_query=context_query,
            output_schema=output_schema,
            analysis_prompt=analysis_prompt,
        )

    @staticmethod
    def _extract_code_blocks(content: str) -> list[dict[str, str]]:
        """Extract code blocks from markdown content using proper parser.

        Args:
            content: Markdown content

        Returns:
            List of code blocks with language and content
        """
        # Use markdown-it-py to parse the markdown
        md = MarkdownIt()
        tokens = md.parse(content)

        code_blocks = []
        for token in tokens:
            if token.type == "fence" and token.content:
                # Extract language from info string (e.g., "json" from "```json")
                lang = token.info.strip() if token.info else ""
                code_blocks.append({"lang": lang, "content": token.content.rstrip()})

        return code_blocks
