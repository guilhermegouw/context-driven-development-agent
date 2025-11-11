# Project Constitution

> This file serves as the foundational context for all AI-assisted development in this project.

## Project Overview

**Project:** CDD Agent

**Purpose:** LLM-agnostic AI coding assistant that provides structured CDD (Context-Driven Development) workflows without vendor lock-in

**Target Users:**
- Solo developers working on side projects
- Professional developers in companies
- Development teams seeking structured AI-assisted workflows

**Business Domain:** Software development tools / AI-assisted coding

**Core Value Proposition:** Enables the CDD workflow (Spec → Plan → Execute) with any LLM provider, creating a virtuous cycle where development generates documentation that provides perfect context for AI assistance. Unlike vendor-specific tools (Claude Code, Cursor), CDD Agent gives developers freedom to choose their LLM provider while maintaining structured, context-rich development workflows.

## Architecture & Design Patterns

**Architecture Type:** Monolithic CLI (single Python package)

**Design Patterns:**
- **Provider Pattern**: Separate implementations per LLM vendor (AnthropicProvider, OpenAIProvider, CustomProvider) for clear separation of concerns and strong typing
- **Tool Registry Pattern**: Decorator-based tool registration with auto-schema generation for extensibility
- **Configuration-Driven Design**: Settings file with environment variable overrides for flexibility across deployment contexts

**Code Organization:**
Layer-based structure organized by technical responsibility:
```
src/cdd_agent/
├── auth.py       # Authentication layer
├── config.py     # Configuration management
├── agent.py      # Agent orchestration loop
├── agents/       # Specialized agents (Socrates, Planner, Executor)
├── tools.py      # Tool registry and execution
└── cli.py        # CLI commands and interface
```

**Key Architectural Decisions:**
- **Multi-provider pattern over generic adapter**: Chose separate provider implementations for maintainability, type safety, and clear API handling. Each provider owns its format translation rather than a complex generic adapter.
- **Python over TypeScript**: Selected for developer productivity (primary language expertise). Future performance needs would drive migration to Go (superior for CLI tools) rather than TypeScript.
- **Layer-based organization**: Chose technical layers over feature-based modules for predictable navigation and clear separation of infrastructure vs domain logic.

**Integration Points:**
- Anthropic API (Claude models)
- OpenAI API (GPT models)
- Custom LLM endpoints (proxies, local servers, alternative providers)

## Technology Stack & Constraints

**Primary Language:** Python 3.10+

**Framework:** Click (CLI framework), Rich (terminal UI and streaming)

**Database:** None (file-based configuration in `~/.cdd-agent/settings.json`)

**Deployment:** PyPI package distribution (`pip install cdd-agent`)

**Key Dependencies:**
- Click 8.1.7+ - CLI framework for command structure
- Rich 13.7+ - Terminal UI, markdown rendering, streaming responses
- Anthropic 0.40+ - Claude API client
- OpenAI 1.55+ - GPT API client
- Pydantic 2.10+ - Data validation and settings management
- PyYAML 6.0+ - YAML parsing for specs and config
- httpx 0.27+ - HTTP client for custom endpoints

**Version Constraints:**
- Minimum Python 3.10 (required for modern type hints and pattern matching)
- Poetry for dependency management
- Compatible with PyPI packaging standards

**Performance Requirements:**
- **Startup time**: Target <100ms for instant feel, acceptable up to 500ms for CLI responsiveness
- **Streaming**: Token-by-token streaming for smooth ChatGPT-like UX
- **Tool execution**: Configurable timeout (user-defined based on command complexity)
- **Memory**: Efficient conversation history management (avoid memory bloat on long sessions)

**Security Requirements:**
- **Settings file permissions**: Implement optional enforcement (chmod 600) with "dangerously skip" flag following Claude Code pattern
- **API key storage**: Local filesystem only (`~/.cdd-agent/settings.json`), with environment variable override option
- **Tool execution approval**: Flexible flow with three modes:
  - Always ask (safest, for paranoid mode)
  - Auto-approve read-only, ask for writes (balanced default)
  - Remember approvals per session (convenience mode)
- **Command injection prevention**: Sanitize bash tool inputs, validate file paths, warn on dangerous operations

## Development Standards

**Code Style:**
- Black formatter (88 character line length)
- Ruff linter (enforcing E, F, I, N, W rule sets)
- Type hints encouraged (mypy configured but not enforcing untyped defs for pragmatism)

**Testing Standards:**
- Pytest framework with async support
- Coverage target: As high as reasonable (pragmatic over dogmatic - focus on critical paths)
- Test scope: Everything (core logic + CLI commands + agent behaviors)
- Integration tests: Mocked LLM responses (avoid API costs, ensure reproducibility)
- Coverage reporting: `pytest-cov` with term-missing output

**Code Review Process:**
- All changes via GitHub Pull Requests (even for solo work initially - builds good habits)
- PR must pass CI checks (Black, Ruff, pytest, mypy)
- Self-review checklist: functionality, tests, documentation, edge cases
- Ready for external contributors from day one

**Definition of Done:**
- Code written and follows style guidelines (Black + Ruff passing)
- Tests written and passing (pytest green)
- Type hints added where reasonable (mypy passing)
- Documentation updated (README, docstrings, ROADMAP if needed)
- CI checks passing (all quality gates green)
- PR reviewed and approved (self-review initially, external review when contributors arrive)

**Quality Gates:**
- Black formatting check (zero tolerance for style violations)
- Ruff linting (must pass all enabled rules)
- Pytest suite (all tests passing, no skipped critical tests)
- Mypy type checking (warnings acceptable, errors must be resolved)

## Team Conventions

**Naming Conventions:**
- Files: `snake_case.py` (e.g., `agent_loop.py`)
- Functions/variables: `snake_case` (e.g., `execute_tool`, `user_message`)
- Classes: `PascalCase` (e.g., `AnthropicProvider`, `ToolRegistry`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_TIMEOUT`, `MAX_RETRIES`)
- CLI commands: `kebab-case` (e.g., `cdd-agent auth setup`)

**Branching Strategy:**
- Feature branches: `feature/short-description` (e.g., `feature/streaming-ui`)
- Bug fixes: `fix/issue-description` (e.g., `fix/auth-token-validation`)
- Main branch: `main` (or `master` - currently using `master`)
- Always branch from main, merge back via PR

**Commit Message Format:**
Conventional Commits specification:
- `feat: add streaming response UI with Rich`
- `fix: resolve API key validation error`
- `docs: update README with installation steps`
- `refactor: simplify provider abstraction`
- `test: add integration tests for auth flow`
- `chore: update dependencies to latest versions`

**Workflow:**
GitHub Flow (feature branch → PR → review → merge):
1. Create feature branch from `main`
2. Develop feature with frequent commits
3. Run local checks (Black, Ruff, pytest)
4. Push branch and open PR
5. CI runs automated checks
6. Self-review (or peer review when contributors arrive)
7. Merge to `main` after approval
8. Delete feature branch

**Communication:**
- **GitHub Issues**: Feature requests, bug reports, task tracking
- **GitHub Discussions**: Questions, ideas, community support (when community grows)
- **Pull Requests**: Code review, implementation discussion
- **ROADMAP.md**: Project direction, phase planning, progress tracking

---
*Generated by CDD Framework - Learn more: https://github.com/guilhermegouw/context-driven-documentation*
