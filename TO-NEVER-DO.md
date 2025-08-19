# TO-NEVER-DO: ScriptRAG Anti-Patterns and Non-Goals

This document explicitly defines what ScriptRAG will **NEVER** do. These are intentional design decisions to maintain project focus, respect screenwriter autonomy, and preserve creative integrity.

## 🚫 Core Non-Goals: Respecting Writer Autonomy

### 1. **NEVER Auto-Correct Fountain Formatting**

ScriptRAG will NEVER automatically "fix" or modify a writer's screenplay formatting. We parse and analyze, but we respect the writer's creative choices and formatting decisions.

**Why:** Writers often use unconventional formatting for creative effect. What looks like an "error" might be an intentional stylistic choice. ScriptRAG is an analysis tool, not a formatting enforcer.

### 2. **NEVER Modify Creative Content Without Explicit User Action**

The tool will NEVER:

- Automatically rewrite dialogue to be "better"
- Suggest character name changes
- Alter scene descriptions for "clarity"
- Change action lines for "pacing"
- Modify any creative content without explicit user-initiated action

**Why:** ScriptRAG respects writer autonomy. We provide insights and analysis, not unsolicited creative changes.

### 3. **NEVER Act as a Screenplay Quality Judge**

ScriptRAG will NEVER:

- Rate scripts on a quality scale
- Provide "good/bad" judgments on creative choices
- Implement scoring systems for dialogue or structure
- Compare scripts to determine which is "better"

**Why:** Quality is subjective in creative work. Our role is to provide objective analysis and data, not subjective judgments.

### 4. **NEVER Enforce Screenplay "Rules" or Conventions**

The tool will NEVER:

- Force adherence to three-act structure
- Require specific page counts for acts
- Enforce "rules" like "no camera directions"
- Mandate formatting conventions beyond basic Fountain syntax

**Why:** Screenwriting "rules" are guidelines, not laws. Innovation comes from breaking conventions.

### 5. **NEVER Implement Proprietary Screenplay Formats**

ScriptRAG will NEVER support:

- Final Draft's .fdx format (proprietary)
- Celtx's proprietary formats
- WriterDuet's proprietary formats
- Any closed-source, proprietary screenplay format

**Why:** We're committed to open standards. Fountain is open, human-readable, and version-control friendly.

## 🚫 Technical Anti-Patterns

### **NEVER Store or Transmit Scripts to External Services Without Explicit Consent**

The tool will NEVER:

- Automatically upload scripts to cloud services
- Send script content to analytics services
- Share script data with third parties
- Use script content for model training without explicit opt-in

**Why:** Scripts are valuable intellectual property. Privacy and ownership must be absolute.

### **NEVER Implement "AI Writing" Features**

ScriptRAG will NEVER:

- Generate entire scenes from prompts
- Write dialogue for characters
- Create plot outlines from themes
- Finish incomplete scripts automatically

**Why:** We're an analysis tool, not a writing tool. Writers write; we analyze what they've written.

### **NEVER Make Subjective Style Decisions**

The tool will NEVER:

- Convert between dialogue styles (e.g., formal to casual)
- "Modernize" dated language
- Adjust tone or voice
- Standardize character speech patterns

**Why:** Style is the writer's domain. Every character's voice is intentional.

## 🚫 Scope Boundaries

### **NEVER Become a Production Management Tool**

ScriptRAG will NEVER include:

- Shooting schedule generation
- Budget calculation
- Location scouting features
- Casting suggestions
- Production logistics

**Why:** We focus on script analysis, not production. There are specialized tools for production management.

### **NEVER Implement Social Features**

The tool will NEVER:

- Create writer social networks
- Implement script sharing platforms
- Add commenting/collaboration features
- Build screenplay marketplaces

**Why:** ScriptRAG is a local-first, privacy-focused analysis tool. Social features compromise privacy and shift focus from core functionality.

### **NEVER Require Online Connectivity for Core Features**

All essential ScriptRAG features must work offline. We will NEVER:

- Require internet for basic parsing
- Gate features behind online authentication
- Make cloud sync mandatory
- Require online validation for local analysis

**Why:** Writers work everywhere - planes, cabins, coffee shops with bad wifi. Local-first is non-negotiable.

### **NEVER Collect Telemetry Without Explicit Opt-In**

The tool will NEVER:

- Automatically collect usage statistics
- Track script content or metadata
- Monitor writing patterns
- Share any data without explicit, informed consent

**Why:** Privacy is paramount. Writers must have complete control over their data.

## 🚫 Never Use These Technologies

### 1. **Docker / Containerization**

**Decision**: ScriptRAG will NEVER use Docker, containers, or any form of
containerization technology.

**Rationale**:

- Modern Python tooling (uv/uvx) provides all needed functionality
- No need for containerization overhead
- Simpler deployment and development workflow
- Native Python packaging is sufficient

**Use Instead**:

- `uv` for dependency management
- `uvx` for global tool installation
- Native Python virtual environments
- System package managers for external dependencies

### 2. **Legacy Python Tooling**

While we're transitioning away from these, they should not be reintroduced:

- `pip` (use `uv` instead)
- `virtualenv` (use `uv venv` instead)
- `poetry` (use `uv` instead)
- `pipenv` (use `uv` instead)

### 3. **Real-time Collaboration Features**

**Decision**: ScriptRAG will NOT implement real-time collaborative editing or
multi-user features.

**Rationale**:

- Git provides superior version control and collaboration
- Real-time collaboration adds unnecessary complexity
- Writers prefer asynchronous workflows with clear ownership
- Merge conflicts are better handled through git

**Features explicitly rejected**:

- Multi-writer bible access and editing
- Change tracking and approval workflows
- Writer room integration features
- Producer oversight and approval systems
- Real-time collaborative editing
- User authentication and permissions systems

**Use Instead**:

- Git-based workflow with database export/import
- Standard git branching and merging
- Pull requests for review workflows
- File-based formats that support clean merges

### 4. **Visualization and Export Formats**

**Decision**: ScriptRAG will NOT generate visualizations or complex export formats.

**Rationale**:

- Focus on core analysis capabilities
- Visualization adds complexity without core value
- Export to simple, text-based formats only
- Let other tools handle visualization

**Features explicitly rejected**:

- PDF series bible document generation
- Character relationship charts/graphs
- Timeline visualization graphics
- World map and location guides
- Mentor result visualization and trends
- Visual trend analysis
- Script export functionality from MCP server (pointless in MCP context)

**Use Instead**:

- Plain text and markdown exports
- Git-friendly structured data formats (JSON, YAML)
- Let users create visualizations with external tools

## 📝 Implementation Guidelines

When implementing new features, ask:

1. Does this respect writer autonomy?
2. Does this make subjective creative decisions?
3. Does this require modifying the writer's content?
4. Does this judge or rate creative work?
5. Does this compromise privacy or require online connectivity?

If the answer to ANY of these is "yes" or "maybe", the feature belongs in this TO-NEVER-DO list.

## 🎯 What ScriptRAG DOES Do

For clarity, ScriptRAG DOES:

- Parse and analyze Fountain format screenplays
- Extract structured data (scenes, characters, dialogue)
- Provide objective metrics and visualizations
- Enable powerful search and query capabilities
- Integrate with version control (Git)
- Respect writer privacy and autonomy
- Work entirely offline
- Preserve creative intent

## 💡 Philosophy

> "A computer should never touch the creative aspects of a screenplay. That's the writer's domain, and it's sacred." - ScriptRAG Design Principle #1

This document is not about limitations - it's about focus. By clearly defining what we won't do, we can excel at what we choose to do: providing writers with powerful, respectful, privacy-focused analysis tools that enhance their understanding of their own work without ever presuming to judge or modify it.

## 📝 How to Update This List

This list should only be updated when:

1. A technology or approach is explicitly rejected by project maintainers
2. The decision aligns with our core philosophy of respecting writer autonomy
3. A clear alternative has been identified (when applicable)
4. The decision is considered permanent

---

*Last Updated: 2025-08-19*
*"Sometimes knowing what NOT to do is as important as knowing what to do."*
