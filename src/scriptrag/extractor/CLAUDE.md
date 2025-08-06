# Content Extractor Component

This directory contains the content extraction system that analyzes scenes using LLMs and Insight Agents to extract semantic information.

## Architecture Role

The Content Extractor is a **processing component** that:

- Receives parsed scenes from the Fountain Parser
- Reads from Built-in and Custom Insight Agents
- Communicates with LLM API
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

## Insight Agent Integration

### Agent Execution Flow

1. Parse agent markdown file
2. Execute context SQL query
3. Build prompt with scene + context
4. Call LLM with JSON schema
5. Validate response
6. Merge into metadata

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

- **Input from**: Fountain Parser
- **Output to**: Embedding Generator
- **Reads from**: Built-in/Custom Insight Agents
- **Communicates with**: LLM API

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
