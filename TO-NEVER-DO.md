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
