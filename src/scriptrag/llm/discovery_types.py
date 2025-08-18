"""Type definitions for model discovery."""

from typing import TypedDict


class GitHubModelInfo(TypedDict, total=False):
    """Type for GitHub API model information."""

    id: str
    name: str
    friendly_name: str
    context_window: int
    max_output_tokens: int


class GitHubModelsResponse(TypedDict, total=False):
    """Type for GitHub Models API response."""

    data: list[GitHubModelInfo]
