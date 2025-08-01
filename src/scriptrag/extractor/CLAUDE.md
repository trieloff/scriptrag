# Content Extractor Component

This directory contains the content extraction system that analyzes scenes using LLMs and Insight Agents to extract semantic information.

## Architecture Role

The Content Extractor is an **Actor** in the FMC architecture. It:

- Receives parsed scenes from the Fountain Parser (through a channel)
- Reads from Built-in and Custom Insight Agents (Places)
- Communicates with LLM API (through a channel)
- Outputs structured metadata to the Embedding Generator

## Key Responsibilities

1. **Load and Execute Insight Agents**
   - Discover agents in `insight-agents/` directory
   - Parse agent markdown files
   - Execute agent prompts against scenes

2. **LLM Integration**
   - Support both OpenAI REST API and Claude Code SDK
   - Handle structured output (JSON mode)
   - Manage rate limits and retries

3. **Metadata Aggregation**
   - Combine results from multiple agents
   - Validate against JSON schemas
   - Handle conflicts and merge strategies

## Implementation Guidelines

```python
from typing import List, Dict, Any, Optional
from pathlib import Path
import json

from ..models import Scene, ExtractedMetadata
from ..agents import InsightAgent
from ..llm import LLMClient
from ..exceptions import ExtractionError


class ContentExtractor:
    """Extract semantic information from scenes using LLMs."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        agents_dir: Optional[Path] = None
    ):
        self.llm = llm_client or LLMClient()
        self.agents_dir = agents_dir or Path("insight-agents")
        self.agents = self._load_agents()

    def extract(self, scene: Scene) -> ExtractedMetadata:
        """Extract metadata from a scene using all agents.

        Args:
            scene: Parsed scene object

        Returns:
            Aggregated metadata from all agents

        Raises:
            ExtractionError: If extraction fails
        """
        metadata = ExtractedMetadata()

        for agent in self.agents:
            try:
                result = self._run_agent(agent, scene)
                metadata.merge(agent.property_name, result)
            except Exception as e:
                self.logger.warning(
                    f"Agent {agent.name} failed: {e}",
                    agent=agent.name,
                    scene=scene.content_hash
                )

        return metadata

    def _run_agent(
        self,
        agent: InsightAgent,
        scene: Scene
    ) -> Dict[str, Any]:
        """Execute a single agent against a scene."""
        # Build context from agent's SQL query
        context = self._build_context(agent, scene)

        # Construct prompt
        prompt = agent.build_prompt(scene, context)

        # Call LLM with structured output
        response = self.llm.complete(
            prompt,
            response_format={"type": "json_object"},
            schema=agent.output_schema
        )

        # Validate response
        return agent.validate_output(response)
```

## Insight Agent Integration

### Agent Discovery

```python
def _load_agents(self) -> List[InsightAgent]:
    """Discover and load all insight agents."""
    agents = []

    # Load built-in agents
    builtin_dir = Path(__file__).parent / "builtin_agents"
    agents.extend(self._load_agents_from_dir(builtin_dir))

    # Load custom agents
    if self.agents_dir.exists():
        agents.extend(self._load_agents_from_dir(self.agents_dir))

    return agents
```

### Agent Execution Flow

1. Parse agent markdown file
2. Execute context SQL query
3. Build prompt with scene + context
4. Call LLM with JSON schema
5. Validate response
6. Merge into metadata

## LLM Client Abstraction

```python
class LLMClient:
    """Abstract LLM client supporting multiple providers."""

    def __init__(self, provider: str = "auto"):
        if provider == "auto":
            self.provider = self._detect_provider()
        else:
            self.provider = provider

    def _detect_provider(self) -> str:
        """Detect if running in Claude Code or use OpenAI."""
        if self._in_claude_code():
            return "claude_sdk"
        return "openai"

    def complete(
        self,
        prompt: str,
        response_format: Optional[Dict] = None,
        schema: Optional[Dict] = None
    ) -> str:
        """Get completion from LLM."""
        if self.provider == "claude_sdk":
            return self._claude_complete(prompt, schema)
        else:
            return self._openai_complete(prompt, response_format)
```

## Metadata Aggregation

```python
class MetadataAggregator:
    """Aggregate results from multiple agents."""

    def merge(
        self,
        base: ExtractedMetadata,
        property_name: str,
        value: Any
    ) -> ExtractedMetadata:
        """Merge new property into metadata."""
        if property_name in base:
            # Handle conflicts
            if isinstance(value, list):
                base[property_name].extend(value)
            elif isinstance(value, dict):
                base[property_name].update(value)
            else:
                # Last write wins for scalars
                base[property_name] = value
        else:
            base[property_name] = value

        return base
```

## Error Handling

1. **Agent Failures**: Log and continue with other agents
2. **LLM Errors**: Retry with exponential backoff
3. **Validation Errors**: Skip invalid data with warning
4. **Network Issues**: Cache and retry queue

## Performance Optimizations

1. **Parallel Agent Execution**: Run independent agents concurrently
2. **LLM Batching**: Batch multiple scenes in one request
3. **Response Caching**: Cache LLM responses by content hash
4. **Agent Priority**: Run critical agents first

## Testing

Key test scenarios:

- Mock LLM responses for deterministic tests
- Agent loading and validation
- Schema validation
- Error recovery
- Performance under load

## Integration Points

- **Input from**: Fountain Parser (via channel)
- **Output to**: Embedding Generator (via channel)
- **Reads from**: Built-in/Custom Insight Agents (Places)
- **Communicates with**: LLM API (via channel)

## Configuration

```yaml
extractor:
  llm_provider: "auto"  # auto, openai, claude_sdk
  openai_api_key: "${OPENAI_API_KEY}"
  model: "gpt-4-turbo-preview"
  temperature: 0.3
  max_retries: 3
  agents_dir: "./insight-agents"
  parallel_agents: true
  cache_responses: true
```
