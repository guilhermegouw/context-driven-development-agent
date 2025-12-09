# CDD Agent Features

A comprehensive list of all features available in CDD Agent.

---

## Multi-Provider LLM Support

### Anthropic Integration
Support for Claude models including Haiku, Sonnet, and Opus variants. Full API compatibility with streaming responses.

### OpenAI Integration
Support for GPT-4o, GPT-4o-mini, and GPT-3.5 models through the OpenAI API.

### Custom Endpoints
Connect to any OpenAI-compatible API including Ollama, LM Studio, or self-hosted models. Enables local inference without cloud dependencies.

### Model Tier Abstraction
Configure models by purpose (small/mid/big) instead of specific versions. Switch providers without workflow changes and optimize costs based on task complexity.

---

## Authentication & Configuration

### Interactive Setup Wizard
Guided setup process via `cdd-agent auth setup` for configuring providers and API keys.

### OAuth 2.0 Authentication
Browser-based authorization flow with PKCE security. Create API keys through OAuth without manually visiting provider consoles.

### Environment Variable Overrides
Override any configuration setting via environment variables (e.g., `ANTHROPIC_API_KEY`, `CDD_APPROVAL_MODE`).

### Multi-Provider Configuration
Store credentials for multiple providers simultaneously. Switch between them with CLI flags.

### Settings File
Persistent configuration stored in `~/.cdd-agent/settings.json` with version tracking and provider-specific settings.

---

## Terminal User Interface (TUI)

### Split-Pane Interface
Textual-based TUI with separate panes for input, output, and status information.

### Token-by-Token Streaming
Real-time streaming of LLM responses for a responsive ChatGPT-like experience.

### Syntax Highlighting
Code blocks rendered with proper syntax highlighting for improved readability.

### Interactive Tool Approval
Visual prompts for approving or rejecting tool executions with context about the operation.

### Simple Mode
Alternative `--simple` flag for basic streaming output without the full TUI.

---

## File Operations Tools

### read_file
Read contents of any file with path validation and error handling.

### write_file
Create new files or overwrite existing ones with specified content.

### write_file_lines
Insert content at a specific line number within a file.

### edit_file
Find and replace text within files using old_text/new_text matching.

---

## Code Search Tools

### glob_files
Find files matching glob patterns (e.g., `**/*.py`, `src/**/test_*.js`). Useful for discovering project structure.

### grep_files
Search file contents using regex patterns. Filter by file pattern and path for targeted searches.

---

## Shell Execution Tools

### run_bash
Execute shell commands synchronously and capture output. Includes timeout handling and error reporting.

### run_bash_background
Start long-running commands without blocking the chat session. Returns a process ID for tracking.

### get_background_status
Check if a background process is still running or has completed.

### get_background_output
Retrieve output from a background process, optionally limiting to recent lines.

### interrupt_background_process
Stop a running background process by its ID.

### list_background_processes
View all active background processes with their status and IDs.

---

## Git Operations Tools

### git_status
Display current git repository status including staged, modified, and untracked files.

### git_diff
Show differences for specific files or the entire working directory.

---

## Safety & Approval System

### Paranoid Mode
Requires explicit approval for every tool execution. Ideal for learning or critical operations.

### Balanced Mode (Default)
Auto-approves safe read-only operations. Asks for approval on write operations and shell commands.

### Trusting Mode
Remembers approvals within the session for minimal interruptions. Suited for experienced users.

### Risk Classification
Tools categorized as Safe (read-only), Medium (file modifications), or High (shell execution) with appropriate warnings.

---

## Context Loading System

### Project Context
Automatically loads `CDD.md` or `CLAUDE.md` from the project root to provide project-specific information to the LLM.

### Global Context
Loads user preferences from `~/.cdd/CDD.md` or `~/.claude/CLAUDE.md` that apply across all projects.

### Hierarchical Merging
Project context takes priority over global context, with intelligent merging of preferences.

### Auto-Detection
Finds project root by looking for `.git`, `pyproject.toml`, `package.json`, or other markers.

### Context Caching
Caches loaded context for performance. Disable with `--no-context` flag when needed.

---

## CDD Workflow Agents

### Socrates Agent
Specialized agent for requirements gathering through Socratic questioning. Helps clarify and refine project specifications.

### Planner Agent
Designs architecture and creates implementation plans from specifications. Outputs structured markdown plans.

### Executor Agent
Implements features according to plans. Tracks execution state and handles step-by-step implementation.

### Writer Agent
Generates documentation based on code and specifications. Creates feature docs, guides, and technical documentation.

---

## Slash Commands

### /init
Initialize CDD structure in a project, creating necessary directories and configuration files.

### /new
Create a new ticket (feature, bug, enhancement, or spike) using templates.

### /plan
Generate an implementation plan from a specification using the Planner agent.

### /exec
Execute a plan step-by-step using the Executor agent with state tracking.

### /socrates
Start a Socratic dialogue session for requirements gathering.

### /clear
Clear the current conversation history.

### /help
Display available commands and usage information.

---

## Template System

### Feature Tickets
YAML-based templates for defining new features with structured fields.

### Bug Tickets
Templates for bug reports with reproduction steps and expected behavior.

### Enhancement Tickets
Templates for improvements to existing functionality.

### Spike Tickets
Templates for research and exploration tasks.

### Plan Templates
Markdown templates for implementation plans with task breakdowns.

### Documentation Templates
Templates for feature docs, guides, and constitution files.

---

## Performance Optimizations

### Lazy Loading
Deferred import of heavy dependencies for faster CLI startup (~700ms target).

### Efficient Streaming
Token-by-token streaming with minimal buffering for responsive output.

### Context Caching
Cached context loading to avoid repeated file reads.

---

## Developer Experience

### Make Commands
`make install`, `make test`, `make format`, `make lint`, `make qa` for streamlined development.

### Pre-commit Hooks
Automatic quality checks before commits via git hooks.

### Debug Logging
Configurable log levels via `CDD_LOG_LEVEL` environment variable.

### Test Coverage
Pytest with coverage reporting via `make test-cov`.

---

## CLI Options

### Provider Selection
`--provider anthropic|openai|custom` to choose LLM provider per session.

### Model Selection
`--model small|mid|big` to choose model tier based on task needs.

### Approval Mode
`--approval paranoid|balanced|trusting` to set tool approval behavior.

### Streaming Control
`--simple` for basic output, `--no-stream` for single-shot execution.

### Context Control
`--no-context` to disable automatic context loading.
