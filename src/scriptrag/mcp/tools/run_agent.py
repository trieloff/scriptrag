"""MCP tool for running analysis agents."""

from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from scriptrag.api.analyze import AnalyzeCommand
from scriptrag.config import get_logger, get_settings
from scriptrag.mcp.server import mcp
from scriptrag.mcp.utils import AsyncAPIWrapper, format_error_response

logger = get_logger(__name__)


class RunAgentInput(BaseModel):
    """Input for running an agent."""

    agent_name: str = Field(..., description="Name of the agent to run")
    scene_id: int | None = Field(None, description="Scene to analyze")
    script_id: int | None = Field(None, description="Script to analyze")
    custom_content: str | None = Field(None, description="Custom content to analyze")
    save_results: bool = Field(True, description="Save results to database")


class RunAgentOutput(BaseModel):
    """Output from running an agent."""

    success: bool
    agent_name: str
    results: dict
    analysis_id: int | None = None
    message: str


@mcp.tool()
async def scriptrag_run_agent(
    agent_name: str,
    scene_id: int | None = None,
    script_id: int | None = None,
    custom_content: str | None = None,
    save_results: bool = True,
    ctx: Context | None = None,
) -> RunAgentOutput:
    """Run a specific analysis agent on content.

    Args:
        agent_name: Name of the agent to run
        scene_id: Scene to analyze
        script_id: Script to analyze
        custom_content: Custom content to analyze
        save_results: Save results to database
        ctx: MCP context

    Returns:
        Analysis results from the agent
    """
    try:
        # Validate that at least one content source is provided
        if not any([scene_id, script_id, custom_content]):
            return RunAgentOutput(
                success=False,
                agent_name=agent_name,
                results={},
                message="Must provide either scene_id, script_id, or custom_content",
            )

        if ctx:
            target = "custom content"
            if scene_id:
                target = f"scene {scene_id}"
            elif script_id:
                target = f"script {script_id}"
            await ctx.info(f"Running agent '{agent_name}' on {target}")

        # Use Analyze Command to run the agent
        settings = get_settings()
        analyze_cmd = AnalyzeCommand(settings)
        wrapper = AsyncAPIWrapper()

        # Prepare analysis parameters
        analyze_params = {
            "agent_name": agent_name,
            "save_results": save_results,
        }

        if scene_id:
            analyze_params["scene_id"] = scene_id
        elif script_id:
            analyze_params["script_id"] = script_id
        elif custom_content:
            analyze_params["content"] = custom_content

        # Run the analysis
        analysis_result = await wrapper.run_sync(analyze_cmd.analyze, **analyze_params)

        if not analysis_result or analysis_result.get("error"):
            error_msg = (
                analysis_result.get("error", "Unknown error")
                if analysis_result
                else "Analysis failed"
            )
            return RunAgentOutput(
                success=False,
                agent_name=agent_name,
                results={},
                message=f"Agent execution failed: {error_msg}",
            )

        # Extract results
        results = analysis_result.get("results", {})
        analysis_id = analysis_result.get("analysis_id") if save_results else None

        if ctx:
            result_keys = list(results.keys())
            await ctx.info(
                f"Agent '{agent_name}' completed with {len(result_keys)} result fields"
            )

        return RunAgentOutput(
            success=True,
            agent_name=agent_name,
            results=results,
            analysis_id=analysis_id,
            message=f"Successfully ran agent '{agent_name}'",
        )

    except Exception as e:
        logger.error("Failed to run agent", error=str(e))
        error_response = format_error_response(e, "scriptrag_run_agent")
        return RunAgentOutput(
            success=False,
            agent_name=agent_name,
            results={},
            message=error_response["message"],
        )
