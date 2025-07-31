# ScriptRAG To-Never-Do List

This document explicitly lists technologies, patterns, and approaches that are
NOT to be used in the ScriptRAG project. These decisions are final and should
not be revisited.

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

## 📝 How to Update This List

This list should only be updated when:

1. A technology is explicitly rejected by project maintainers
2. A clear alternative has been identified
3. The decision is considered permanent

## 🎯 Purpose

This document serves to:

- Prevent wasted effort on rejected approaches
- Guide contributors away from non-viable solutions
- Maintain project focus on chosen technologies
- Document architectural decisions clearly

---

*"Sometimes knowing what NOT to do is as important as knowing what to do."*
