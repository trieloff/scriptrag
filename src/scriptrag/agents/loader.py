"""Agent loader module - re-exports from split modules for backward compatibility."""

from scriptrag.agents.agent_loader import AgentLoader
from scriptrag.agents.agent_spec import AgentSpec
from scriptrag.agents.markdown_agent_analyzer import MarkdownAgentAnalyzer

__all__ = ["AgentLoader", "AgentSpec", "MarkdownAgentAnalyzer"]
