# Custom Insight Agents

This directory is a placeholder for custom insight agents defined by users. Custom agents are stored in the Git repository under `insight-agents/` and loaded by the Content Extractor.

## Purpose

This directory exists in the package structure to:

1. Provide a clear separation between built-in and custom agents
2. Allow for testing infrastructure
3. Enable future features like agent validation tools

## Custom Agent Location

Custom agents should be placed in your Git repository:

```text
your-screenplay-project/
├── scripts/
│   └── pilot.fountain
├── insight-agents/        # Custom agents go here
│   ├── my_custom_agent.md
│   └── genre_analysis.md
└── .scriptrag/
    └── config.yaml
```

## Creating Custom Agents

To create a custom agent:

1. Create a markdown file in `insight-agents/` in your repo
2. Follow the agent format (see parent CLAUDE.md)
3. Test the agent with `scriptrag agent validate <name>`
4. Commit to version control

## Custom Agent Ideas

- **Genre-Specific Analysis**: Horror tension, comedy beats, action pacing
- **Character Arcs**: Track character development across scenes
- **World Building**: Extract world details for fantasy/sci-fi
- **Production Notes**: Identify budget implications, location needs
- **Director's Vision**: Extract visual style, camera directions

## Best Practices

1. **Start Simple**: Begin with basic extraction, iterate
2. **Test Thoroughly**: Use diverse scenes to test robustness
3. **Document Well**: Include examples in your agent file
4. **Share Back**: Consider contributing useful agents to built-in set

## Agent Development Workflow

```bash
# Create new agent
echo "---
name: my_agent
property: my_property
description: What this agent does
version: 1.0
---" > insight-agents/my_agent.md

# Edit agent
$EDITOR insight-agents/my_agent.md

# Validate agent
scriptrag agent validate my_agent

# Test on a scene
scriptrag agent run my_agent <scene-hash>

# Commit when ready
git add insight-agents/my_agent.md
git commit -m "Add custom agent for X analysis"
```
