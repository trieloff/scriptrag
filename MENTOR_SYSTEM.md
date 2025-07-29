# ScriptRAG Pluggable Mentors System

## Overview

The Pluggable Mentors System provides automated screenplay analysis and feedback based on
established screenwriting methodologies. Mentors are rule-based analyzers that query the
script database, apply domain-specific logic through LLM processing, and provide structured
feedback to writers.

## Architecture

### Core Components

```text
mentors/
├── core/
│   ├── mentor_base.py      # Base mentor class and interfaces
│   ├── mentor_runner.py    # Execution engine for mentors
│   └── mentor_registry.py  # Discovery and registration system
├── builtin/
│   ├── save_the_cat.md     # Save the Cat methodology
│   ├── heros_journey.md    # Hero's Journey structure
│   ├── three_act.md        # Traditional three-act structure
│   └── character_arc.md    # Character development analysis
└── custom/                 # User-defined mentor files
    └── [user_mentors].md
```

### Mentor File Format

Each mentor is defined as a Markdown file with YAML frontmatter:

```yaml
---
name: "Save the Cat"
version: "1.0"
author: "Blake Snyder Methodology"
description: "Analyzes screenplay structure against Save the Cat beat sheet"
triggers:
  - "script_updated"
  - "manual_request"
requirements:
  - "scenes"
  - "characters"
  - "page_count"
output_mode: "notes"  # or "verdict"
---

# Save the Cat Analysis

## Methodology

This mentor analyzes your screenplay against Blake Snyder's Save the Cat structure...

## Analysis Rules

### Opening Image (Page 1)
Query the database for scenes on pages 1-2 and check for:
- Visual establishment of tone
- Character introduction context
- World establishment

### Inciting Incident (Pages 12-15)
Query scenes in this range for:
- Life-changing event for protagonist
- Clear story catalyst
- Stakes establishment

## LLM Prompt Template

Analyze the following screenplay data against Save the Cat structure:

**Scenes:** {scenes_data}
**Characters:** {characters_data}
**Current Page Count:** {page_count}

Based on Save the Cat methodology, evaluate:
1. Beat timing and placement
2. Character development alignment
3. Structural integrity

Provide specific, actionable feedback.
```

### Data Flow

```text
1. Trigger Event → Mentor Runner
2. Load Mentor Definition → Parse YAML + Markdown
3. Execute Database Queries → Fetch Relevant Data
4. Format LLM Prompt → Include Context + Rules
5. Process Through LLM → Apply Mentor Logic
6. Generate Output → Notes or Pass/Fail Verdict
7. Store Results → Link to Script Version
```

## Database Schema Extensions

### Mentor Results Table

```sql
CREATE TABLE mentor_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    script_id INTEGER NOT NULL,
    mentor_name TEXT NOT NULL,
    mentor_version TEXT NOT NULL,
    execution_timestamp DATETIME NOT NULL,
    trigger_type TEXT NOT NULL,  -- 'manual', 'script_updated', etc.
    output_mode TEXT NOT NULL,   -- 'notes' or 'verdict'
    result_data JSON NOT NULL,   -- Structured mentor output
    status TEXT NOT NULL,        -- 'success', 'error', 'warning'
    FOREIGN KEY (script_id) REFERENCES scripts(id)
);

CREATE INDEX idx_mentor_results_script ON mentor_results(script_id);
CREATE INDEX idx_mentor_results_mentor ON mentor_results(mentor_name);
```

### Query Context Helper

```sql
-- Example query for scene structure analysis
SELECT
    s.page_number,
    s.scene_type,
    s.location,
    s.time_of_day,
    s.content,
    GROUP_CONCAT(c.name) as characters_present
FROM scenes s
LEFT JOIN scene_characters sc ON s.id = sc.scene_id
LEFT JOIN characters c ON sc.character_id = c.id
WHERE s.script_id = ?
    AND s.page_number BETWEEN ? AND ?
GROUP BY s.id
ORDER BY s.sequence_number;
```

## API Design

### Mentor Base Class

```python
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Literal
from pydantic import BaseModel

class MentorConfig(BaseModel):
    name: str
    version: str
    author: str
    description: str
    triggers: List[str]
    requirements: List[str]
    output_mode: Literal["notes", "verdict"]

class MentorResult(BaseModel):
    mentor_name: str
    status: Literal["success", "error", "warning"]
    output_mode: Literal["notes", "verdict"]
    verdict: Literal["pass", "fail"] | None = None
    notes: List[str] = []
    recommendations: List[str] = []
    score: float | None = None
    execution_time: float

class BaseMentor(ABC):
    def __init__(self, config: MentorConfig, content: str):
        self.config = config
        self.content = content

    @abstractmethod
    async def analyze(self, script_id: int, context: Dict[str, Any]) -> MentorResult:
        """Execute mentor analysis against script data."""
        pass

    @abstractmethod
    def get_required_data(self, script_id: int) -> Dict[str, Any]:
        """Query database for required analysis data."""
        pass
```

### Mentor Runner

```python
class MentorRunner:
    def __init__(self, db_session, llm_client):
        self.db = db_session
        self.llm = llm_client
        self.registry = MentorRegistry()

    async def run_mentor(self, mentor_name: str, script_id: int,
                        trigger: str = "manual") -> MentorResult:
        """Execute a specific mentor against a script."""

    async def run_all_mentors(self, script_id: int,
                             trigger: str = "script_updated") -> List[MentorResult]:
        """Run all applicable mentors for a script."""

    async def get_mentor_history(self, script_id: int,
                                mentor_name: str = None) -> List[MentorResult]:
        """Retrieve historical mentor results."""
```

## CLI Integration

### New Commands

```bash
# Run specific mentor
uv run scriptrag mentor run --mentor "save_the_cat" --script-id 123

# Run all mentors
uv run scriptrag mentor run-all --script-id 123

# List available mentors
uv run scriptrag mentor list

# View mentor results
uv run scriptrag mentor results --script-id 123 --mentor "save_the_cat"

# Install custom mentor
uv run scriptrag mentor install --file custom_mentor.md

# Validate mentor definition
uv run scriptrag mentor validate --file new_mentor.md
```

## Built-in Mentors

### 1. Save the Cat (save_the_cat.md)

- Blake Snyder's 15-beat structure
- Page count validation
- Character arc alignment
- Genre-specific requirements

### 2. Hero's Journey (heros_journey.md)

- Joseph Campbell's monomyth structure
- Character transformation tracking
- Mythic elements identification
- Archetypal character analysis

### 3. Three-Act Structure (three_act.md)

- Classical dramatic structure
- Plot point identification
- Pacing analysis
- Conflict escalation tracking

### 4. Character Arc Analysis (character_arc.md)

- Protagonist development
- Supporting character consistency
- Dialogue authenticity
- Character motivation alignment

## Configuration

### Settings Integration

```python
class MentorSettings(BaseModel):
    enabled: bool = True
    auto_run_on_update: bool = True
    custom_mentors_path: str = "mentors/custom"
    llm_model: str = "gpt-4"
    max_concurrent_mentors: int = 3
    cache_results: bool = True
    cache_duration_hours: int = 24

class ScriptRAGSettings(BaseSettings):
    # ... existing settings ...
    mentors: MentorSettings = MentorSettings()
```

## Triggers and Automation

### Trigger Types

- **manual_request**: User-initiated analysis
- **script_updated**: Automatic run when script changes
- **scheduled**: Periodic analysis (future)
- **milestone**: Run at specific story milestones

### Integration Points

- CLI command execution
- Script parsing completion
- Database update events
- MCP server endpoints

## Output Formats

### Notes Mode

```json
{
    "mentor_name": "save_the_cat",
    "status": "success",
    "output_mode": "notes",
    "notes": [
        "Opening Image effectively establishes the mundane world",
        "Inciting Incident occurs too late (page 18 vs recommended page 12-15)",
        "Midpoint lacks sufficient tension escalation"
    ],
    "recommendations": [
        "Consider moving the apartment fire scene earlier",
        "Add character stakes before the discovery scene",
        "Strengthen the protagonist's emotional low point"
    ],
    "score": 7.5
}
```

### Verdict Mode

```json
{
    "mentor_name": "three_act",
    "status": "success",
    "output_mode": "verdict",
    "verdict": "fail",
    "notes": [
        "Act 1 exceeds recommended length (35 pages vs 25-30)",
        "Act 2 lacks clear midpoint"
    ],
    "score": 4.2
}
```

## Implementation Strategy

### Phase 1: Core Infrastructure

1. Mentor base classes and interfaces
2. File parsing and validation system
3. Database schema extensions
4. Basic CLI commands

### Phase 2: Built-in Mentors

1. Save the Cat mentor implementation
2. Three-Act structure mentor
3. LLM integration and prompt engineering
4. Result storage and retrieval

### Phase 3: Advanced Features

1. Hero's Journey and Character Arc mentors
2. Custom mentor installation system
3. Automated triggers and scheduling
4. MCP server integration

### Phase 4: Enhancement

1. Mentor result visualization
2. Historical trend analysis
3. Collaborative mentor sharing
4. Advanced query optimization

## Testing Strategy

### Unit Tests

- Mentor file parsing validation
- Database query correctness
- LLM prompt generation
- Result formatting and storage

### Integration Tests

- End-to-end mentor execution
- CLI command functionality
- Database transaction integrity
- Error handling and recovery

### Test Mentors

- Simple rule-based mentors for testing
- Mock LLM responses for consistent testing
- Performance benchmarks for large scripts

## Security Considerations

- Validate mentor file content and structure
- Sanitize user-provided mentor definitions
- Limit LLM query complexity and rate
- Secure mentor result data storage
- Audit mentor execution history

## Future Enhancements

- **Collaborative Mentors**: Community-shared mentor definitions
- **Learning Mentors**: Self-improving mentors based on feedback
- **Visual Analytics**: Graphical mentor result dashboards
- **Genre-Specific Mentors**: Horror, comedy, drama-specific analysis
- **Real-time Feedback**: Live mentor suggestions during writing

---

*"The way to get started is to quit talking and begin doing."* - Walt Disney
