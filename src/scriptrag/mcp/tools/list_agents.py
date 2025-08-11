"""MCP tool for listing analysis agents."""

from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from scriptrag.agents.loader import AgentLoader
from scriptrag.config import get_logger
from scriptrag.mcp.models import AgentInfo
from scriptrag.mcp.server import mcp
from scriptrag.mcp.utils import AsyncAPIWrapper, format_error_response

logger = get_logger(__name__)


class ListAgentsInput(BaseModel):
    """Input for listing agents."""

    category: str | None = Field(None, description="Filter by agent category")
    builtin_only: bool = Field(False, description="Show only built-in agents")


class ListAgentsOutput(BaseModel):
    """Output from listing agents."""

    success: bool
    agents: list[AgentInfo]
    categories: list[str]
    total_count: int
    message: str | None = None


@mcp.tool()
async def scriptrag_list_agents(
    category: str | None = None,
    builtin_only: bool = False,
    ctx: Context | None = None,
) -> ListAgentsOutput:
    """List available analysis agents.

    Args:
        category: Filter by agent category
        builtin_only: Show only built-in agents
        ctx: MCP context

    Returns:
        List of available agents with their capabilities
    """
    try:
        if ctx:
            filters = []
            if category:
                filters.append(f"category={category}")
            if builtin_only:
                filters.append("builtin_only=true")
            filter_str = f" with {', '.join(filters)}" if filters else ""
            await ctx.info(f"Listing agents{filter_str}")

        # Use Agent Loader to get agents
        loader = AgentLoader()
        wrapper = AsyncAPIWrapper()

        # Load all agents
        all_agents = await wrapper.run_sync(loader.load_all_agents)

        # Convert to MCP models and apply filters
        agent_infos = []
        categories_set = set()

        for agent in all_agents:
            agent_category = getattr(agent, "category", "general")
            is_builtin = getattr(agent, "is_builtin", False)

            # Apply filters
            if category and agent_category != category:
                continue
            if builtin_only and not is_builtin:
                continue

            categories_set.add(agent_category)

            agent_infos.append(
                AgentInfo(
                    name=agent.name,
                    category=agent_category,
                    description=getattr(agent, "description", ""),
                    is_builtin=is_builtin,
                    parameters=getattr(agent, "parameters", None),
                )
            )

        categories = sorted(categories_set)
        total_count = len(agent_infos)

        if ctx:
            await ctx.info(
                f"Found {total_count} agents in {len(categories)} categories"
            )

        return ListAgentsOutput(
            success=True,
            agents=agent_infos,
            categories=categories,
            total_count=total_count,
            message=f"Found {total_count} agents",
        )

    except Exception as e:
        logger.error("Failed to list agents", error=str(e))
        error_response = format_error_response(e, "scriptrag_list_agents")
        return ListAgentsOutput(
            success=False,
            agents=[],
            categories=[],
            total_count=0,
            message=error_response["message"],
        )
