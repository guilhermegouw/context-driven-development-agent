# CDD Agent

**LLM-agnostic AI coding assistant with structured workflows and background execution**

[![Version](https://img.shields.io/badge/version-0.0.4-blue.svg)](https://github.com/guilhermegouw/context-driven-development-agent)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## What is CDD Agent?

CDD Agent is a **terminal-based AI coding assistant** that lets you use **any LLM provider** - Anthropic (Claude), OpenAI (GPT), or custom endpoints - without vendor lock-in. It implements structured Context-Driven Development workflows while giving you complete control over your tools and configuration.

**Unlike vendor-specific tools** (Claude Code, Cursor), CDD Agent gives you:
- 🔄 Freedom to choose and switch LLM providers
- 🎯 Structured workflows that maintain context
- 🏠 Local configuration and complete control
- 💰 No subscription lock-in
- ⚡ Background bash execution for long-running tasks
- 🔐 OAuth support for convenient authentication

---

## ✨ What's New in v0.0.4

### 🚀 Background Bash Execution
Run long-running commands without blocking your workflow:
- Start processes in background and continue chatting
- Monitor output in real-time
- Interrupt or check status anytime
- Perfect for tests, builds, servers, and watch processes

### 🔐 OAuth Authentication
Convenient OAuth 2.0 authentication flow:
- Browser-based authorization
- Create API keys through OAuth
- Automatic token management
- **Note:** Zero-cost access restricted to official Claude Code

### ⚡ Performance Improvements
- Lazy imports for faster startup
- Optimized tool execution
- Efficient context loading

### 🛠️ Enhanced Tools
- Background process management
- Improved error handling
- Better streaming output

---

## Current Status: v0.0.4 (Beta)

This is a **beta release** with core features functional and production-ready for daily use.

### ✅ Core Features

**Multi-Provider Architecture:**
- Anthropic (Claude Haiku, Sonnet, Opus)
- OpenAI (GPT-4o, GPT-4, GPT-3.5)
- Custom endpoints (local models, proxies, alternative providers)

**Beautiful TUI:**
- Textual-based split-pane interface
- Token-by-token streaming responses
- Syntax-highlighted code blocks
- Interactive tool approval

**Advanced Tools:**
- File operations: `read_file`, `write_file`, `edit_file`
- Code search: `glob_files` (pattern matching), `grep_files` (regex)
- Shell execution: `run_bash` with output capture
- **Background execution:** Run long commands without blocking

**Safety & Context:**
- Tool approval system (paranoid/balanced/trusting modes)
- Hierarchical context loading (global → project)
- Security warnings for dangerous operations
- Context from CDD.md or CLAUDE.md files

**Authentication:**
- Interactive setup wizard
- OAuth 2.0 support for API key creation
- Environment variable overrides
- Multi-provider configuration

### 🔜 Coming Soon (v0.1.x)

- Further performance optimization (<200ms startup)
- Enhanced git integration with commit preview
- Specialized CDD workflow agents (Socrates, Planner, Executor)
- Plugin system for custom tools

See [ROADMAP.md](ROADMAP.md) for the full development plan.

---

## 📦 Installation

```bash
pip install cdd-agent
```

**Requirements:**
- Python 3.10 or higher
- API keys for your chosen LLM provider(s)

**From source:**
```bash
git clone https://github.com/guilhermegouw/context-driven-development-agent.git
cd context-driven-development-agent
poetry install
poetry run cdd-agent --help
```

---

## 🚀 Quick Start

### 1. Configure your LLM provider

**Interactive Setup (Recommended):**
```bash
# Setup wizard with provider selection
cdd-agent auth setup

# OAuth authentication (creates API key via browser)
cdd-agent auth oauth

# Choose provider: anthropic, openai, or custom
```

**Manual Configuration:**
```bash
# Set environment variables
export ANTHROPIC_API_KEY="your-api-key"
export OPENAI_API_KEY="your-api-key"
```

### 2. Verify your configuration

```bash
# Check configured providers
cdd-agent auth status

# Test API credentials
cdd-agent auth test anthropic
```

### 3. Start coding

```bash
# Interactive TUI mode (default)
cdd-agent chat

# With custom approval mode
cdd-agent chat --approval paranoid    # Ask for every tool execution
cdd-agent chat --approval balanced    # Auto-approve safe tools (default)
cdd-agent chat --approval trusting    # Remember approvals per session

# Choose provider and model
cdd-agent chat --provider anthropic --model mid
cdd-agent chat --provider openai --model big

# Simple streaming mode (no TUI)
cdd-agent chat --simple

# Single-shot execution
cdd-agent chat "Explain this codebase" --no-stream
```

### 4. Set up context files (optional but recommended)

```bash
# Global preferences (applies to all projects)
mkdir -p ~/.cdd
cat > ~/.cdd/CDD.md << 'EOF'
# Global Context

## Coding Style
- Always use type hints in Python
- Prefer functional programming style
- Write comprehensive docstrings

## Testing
- Use pytest for all tests
- Aim for >80% code coverage
EOF

# Project context (specific to this project)
cat > CDD.md << 'EOF'
# Project Context

## Architecture
This is a Flask web application with PostgreSQL backend.

## Tech Stack
- Python 3.11
- Flask 3.0
- SQLAlchemy ORM
- PostgreSQL 15

## Development
- Use virtual environment
- Run migrations before testing
EOF

# The agent automatically loads this context
cdd-agent chat  # Context loaded from both files
```

---

## 🎯 Features

### Multi-Provider Support

Switch between providers anytime without changing your workflow:

```bash
# Use Claude for complex reasoning
cdd-agent chat --provider anthropic --model big "Refactor this codebase"

# Use GPT for quick queries
cdd-agent chat --provider openai --model small "Fix syntax errors"

# Use custom endpoint for local models
cdd-agent auth setup  # Choose "custom" and enter your endpoint
```

**Supported Providers:**
- **Anthropic:** Claude 4.5 Haiku, Sonnet, Opus
- **OpenAI:** GPT-4o, GPT-4o-mini, GPT-3.5
- **Custom:** Any OpenAI-compatible API (Ollama, LM Studio, etc.)

### Model Tier Abstraction

Configure models by **purpose** instead of specific versions:

```json
{
  "models": {
    "small": "claude-3-5-haiku-20241022",      // Fast, cheap
    "mid": "claude-sonnet-4-5-20250929",       // Balanced
    "big": "claude-opus-4-20250514"            // Maximum capability
  }
}
```

Benefits:
- Update model versions in one place
- Switch providers without code changes
- Cost optimization based on task complexity

### Background Bash Execution

Run long commands without blocking your workflow:

```bash
# In chat, the AI can run commands in background:
> "Run the test suite in background"

# AI executes:
# run_bash_background("pytest tests/")

# You can continue chatting while tests run
> "While tests run, explain the auth module"

# Check background status anytime:
> "Check if tests finished"

# AI executes:
# get_background_status(process_id)
```

**Available background tools:**
- `run_bash_background` - Start command in background
- `get_background_status` - Check if process is running
- `get_background_output` - Get process output
- `interrupt_background_process` - Stop a process
- `list_background_processes` - List all running processes

**Perfect for:**
- Test suites
- Build processes
- Development servers
- Watch processes
- Long-running scripts

### OAuth Authentication

Convenient browser-based authentication:

```bash
# Start OAuth flow
cdd-agent auth oauth

# Choose mode:
# - "api-key": Create permanent API key (recommended)
# - "max": OAuth tokens (restricted to Claude Code)

# Browser opens for authorization
# Paste code back to CLI
# Tokens/keys saved automatically
```

**Benefits:**
- No need to manually create API keys in console
- Secure browser-based authorization
- Automatic token management
- OAuth 2.0 with PKCE security

**Important:** Zero-cost API access (Claude Pro/Max) only works with official Claude Code application. Third-party apps like cdd-agent use regular API pricing.

### Hierarchical Context Loading

Load context from multiple sources with intelligent merging:

**Context Sources (in order of priority):**
1. Project context: `CDD.md` or `CLAUDE.md` at project root
2. Global context: `~/.cdd/CDD.md` or `~/.claude/CLAUDE.md`
3. System prompt: Built-in pair programming guidelines

**Features:**
- Automatic project root detection (.git, pyproject.toml, package.json)
- LLM-aware context merging (project overrides global)
- Caching for performance
- Disable with `--no-context` flag

**Use cases:**
- Global coding standards across all projects
- Project-specific architecture documentation
- Team conventions and preferences
- Technology stack information

### Security & Approval System

Three approval modes to control tool execution:

**Paranoid Mode:**
```bash
cdd-agent chat --approval paranoid
```
- Ask for approval on **every** tool execution
- Perfect for learning or critical operations
- See exactly what the AI wants to do

**Balanced Mode (Default):**
```bash
cdd-agent chat --approval balanced
```
- Auto-approve safe read-only tools (read_file, glob_files)
- Ask for approval on write operations
- Best balance of safety and convenience

**Trusting Mode:**
```bash
cdd-agent chat --approval trusting
```
- Remember approvals within session
- Minimal interruptions
- For experienced users

**Risk Classification:**
- 🟢 **SAFE:** Read-only operations (read_file, grep_files)
- 🟡 **MEDIUM:** File modifications (write_file, edit_file)
- 🔴 **HIGH:** Dangerous operations (run_bash, system commands)

---

## ⚙️ Configuration

### Configuration File

CDD Agent stores settings in `~/.cdd-agent/settings.json`:

```json
{
  "version": "1.0",
  "default_provider": "anthropic",
  "approval_mode": "balanced",
  "providers": {
    "anthropic": {
      "auth_token": "sk-ant-...",
      "base_url": "https://api.anthropic.com",
      "models": {
        "small": "claude-3-5-haiku-20241022",
        "mid": "claude-sonnet-4-5-20250929",
        "big": "claude-opus-4-20250514"
      },
      "default_model": "mid"
    },
    "openai": {
      "api_key": "sk-...",
      "base_url": "https://api.openai.com/v1",
      "models": {
        "small": "gpt-4o-mini",
        "mid": "gpt-4o",
        "big": "gpt-4o"
      }
    },
    "custom": {
      "auth_token": "optional",
      "base_url": "http://localhost:11434/v1",
      "provider_type": "anthropic",
      "models": {
        "small": "llama3",
        "mid": "codellama",
        "big": "mixtral"
      }
    }
  },
  "ui": {
    "stream_responses": true,
    "syntax_highlighting": true
  },
  "conversation": {
    "auto_save": true,
    "history_limit": 100
  }
}
```

### Environment Variables

Override settings with environment variables (highest priority):

```bash
# Authentication
export CDD_AUTH_TOKEN="your-key"
export ANTHROPIC_AUTH_TOKEN="your-key"
export OPENAI_API_KEY="your-key"

# Provider settings
export CDD_BASE_URL="https://custom-endpoint.com"
export ANTHROPIC_BASE_URL="https://api.anthropic.com"

# Approval mode
export CDD_APPROVAL_MODE="paranoid"
```

**Priority order:**
1. CLI flags (`--approval`, `--provider`)
2. Environment variables (`CDD_APPROVAL_MODE`)
3. Settings file (`~/.cdd-agent/settings.json`)
4. Defaults (balanced approval, anthropic provider)

---

## 🛠️ Available Tools

CDD Agent provides Claude Code-level tool capabilities:

### File Operations
- `read_file(path)` - Read file contents
- `write_file(path, content)` - Create or overwrite file
- `write_file_lines(path, line_number, content)` - Insert at specific line
- `edit_file(path, old_text, new_text)` - Replace text in file

### Code Search
- `glob_files(pattern, path)` - Find files by pattern (**.py, src/**/test_*.py)
- `grep_files(pattern, file_pattern, path)` - Search code with regex

### Shell Execution
- `run_bash(command)` - Execute shell command and capture output
- `run_bash_background(command)` - Run command in background
- `get_background_status(process_id)` - Check background process
- `get_background_output(process_id, lines)` - Get process output
- `interrupt_background_process(process_id)` - Stop background process
- `list_background_processes()` - List all background processes

### Git Operations
- `git_status()` - Show git status
- `git_diff(file)` - Show file diff

All tools include:
- Detailed descriptions for the LLM
- Type-safe argument validation
- Error handling and recovery
- Risk level classification
- User approval integration

---

## 📊 Comparison

| Feature | CDD Agent | Claude Code | Cursor | Copilot |
|---------|-----------|-------------|--------|---------|
| **Multi-Provider** | ✅ Any LLM | ❌ Claude only | ❌ OpenAI only | ❌ GitHub only |
| **Local Control** | ✅ Full | ⚠️ Limited | ⚠️ Limited | ❌ Cloud |
| **Background Execution** | ✅ Yes | ✅ Yes | ❌ No | ❌ No |
| **Tool Approval** | ✅ 3 modes | ⚠️ Basic | ❌ None | ❌ None |
| **Context Loading** | ✅ Hierarchical | ✅ Yes | ✅ Yes | ⚠️ Limited |
| **OAuth Support** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| **Custom Tools** | 🔜 v0.1.x | ❌ No | ❌ No | ❌ No |
| **Cost** | 💰 API usage | 💰 Subscription | 💰 Subscription | 💰 Subscription |
| **Open Source** | ✅ MIT | ❌ Proprietary | ❌ Proprietary | ❌ Proprietary |

---

## 🤝 Why Choose CDD Agent?

### The Problem

Existing AI coding assistants create **vendor lock-in**:
- Claude Code → Anthropic only (can't use GPT)
- Cursor → OpenAI only (can't use Claude)
- GitHub Copilot → Microsoft ecosystem only

**What happens when:**
- Your preferred model improves on a different platform?
- API pricing changes?
- You want to use local models?
- The service has an outage?

### The Solution

CDD Agent provides **freedom and flexibility**:

✅ **Provider Independence**
- Switch between Claude, GPT, or local models instantly
- No workflow changes when switching providers
- Use the best model for each task

✅ **No Lock-In**
- Your configuration is local and portable
- Open source - audit and modify the code
- No proprietary formats or cloud dependencies

✅ **Cost Control**
- Choose cheaper models for simple tasks
- Use local models for free inference
- Pay only for what you use

✅ **Future-Proof**
- Works with any OpenAI-compatible API
- Easy to add new providers
- Continuous improvement without breaking changes

### Who Should Use CDD Agent?

**Perfect for:**
- Developers who want **flexibility** in LLM choice
- Teams with **multiple LLM providers**
- Users of **local/custom models**
- Projects requiring **audit trails** and approval
- Anyone who values **open source** and **control**

**Not ideal for:**
- Users who prefer integrated IDE experience
- Teams standardized on a single vendor tool
- Those who want zero configuration

---

## 🗺️ Roadmap

### ✅ Completed

**v0.0.1** - Foundation
- Authentication system
- Multi-provider configuration
- CLI framework

**v0.0.2** - Basic Agent
- Agentic loop with tool execution
- TUI with split-pane interface
- Streaming responses

**v0.0.3** - Advanced Features
- Comprehensive tool suite
- Approval system
- Hierarchical context loading

**v0.0.4** - Background & OAuth (Current)
- Background bash execution
- OAuth 2.0 authentication
- Performance improvements

### 🚧 In Progress

**v0.1.0** - Performance & Polish
- Startup time <200ms (currently ~700ms)
- Enhanced git integration
- Improved error messages
- Plugin system foundation

### 🔜 Planned

**v0.2.0** - CDD Workflows
- Socrates agent (requirements gathering)
- Planner agent (architecture design)
- Executor agent (implementation)
- Workflow orchestration

**v0.3.0** - Team Features
- Shared context repositories
- Team configuration templates
- Collaborative workflows

**v1.0.0** - Production Ready
- Full CDD methodology implementation
- Comprehensive documentation
- Extensive testing
- Performance optimization

See [ROADMAP.md](ROADMAP.md) for detailed milestones and feature descriptions.

---

## 🧪 Development

### Tech Stack

- **Python 3.10+** - Modern Python features
- **Click** - CLI framework
- **Rich** - Terminal formatting
- **Textual** - TUI framework
- **Pydantic** - Configuration validation
- **Poetry** - Dependency management

### Project Structure

```
cdd-agent-cli/
├── src/cdd_agent/
│   ├── cli.py              # CLI entry point
│   ├── agent.py            # Main agent loop
│   ├── tools.py            # Tool registry
│   ├── auth.py             # Authentication
│   ├── config.py           # Configuration management
│   ├── oauth.py            # OAuth implementation
│   ├── tui.py              # Textual TUI
│   ├── ui.py               # Streaming UI
│   ├── approval.py         # Tool approval system
│   ├── context.py          # Context loading
│   ├── background_executor.py  # Background processes
│   └── utils/              # Utilities
├── tests/                  # Test suite
├── docs/                   # Documentation
└── pyproject.toml          # Project metadata
```

### Contributing

We welcome contributions! Here's how to get started:

1. **Check the roadmap:** See [ROADMAP.md](ROADMAP.md) for planned features
2. **Open an issue:** Discuss your idea before implementing
3. **Fork and code:** Follow existing code style
4. **Add tests:** Ensure your changes are tested
5. **Submit PR:** Include description and test results

**Good first issues:**
- Add new tool implementations
- Improve error messages
- Add provider-specific optimizations
- Enhance documentation

### Running Tests

```bash
# Install dev dependencies
poetry install

# Run full test suite
poetry run pytest

# Run with coverage
poetry run pytest --cov=cdd_agent

# Run specific test
poetry run pytest tests/test_tools.py -v
```

### Code Quality

```bash
# Format code
poetry run black src/ tests/

# Type checking
poetry run mypy src/

# Linting
poetry run ruff check src/
```

---

## 📚 Documentation

- **[ROADMAP.md](ROADMAP.md)** - Development roadmap and milestones
- **[OAUTH_IMPLEMENTATION.md](OAUTH_IMPLEMENTATION.md)** - OAuth implementation details
- **[OAUTH_LIMITATION.md](OAUTH_LIMITATION.md)** - OAuth restrictions and limitations
- **[OAUTH_TESTING.md](OAUTH_TESTING.md)** - OAuth testing guide

---

## 🐛 Troubleshooting

### Common Issues

**"No configuration found"**
```bash
# Run setup wizard
cdd-agent auth setup
```

**"API error: 401 Unauthorized"**
```bash
# Check API key
cdd-agent auth test

# Verify environment variables
echo $ANTHROPIC_API_KEY
```

**"OAuth: This credential is only authorized for Claude Code"**
- Choose "api-key" mode instead of "max" when running `cdd-agent auth oauth`
- Zero-cost access only works with official Claude Code application

**Slow startup time**
- Already improved from ~2s to ~700ms
- Further optimization planned for v0.1.0

### Debug Mode

```bash
# Enable debug logging
export CDD_LOG_LEVEL=DEBUG
cdd-agent chat

# Check logs
cdd-agent logs show
```

### Getting Help

1. Check documentation files in the repo
2. Search [existing issues](https://github.com/guilhermegouw/context-driven-development-agent/issues)
3. Open a new issue with:
   - CDD Agent version (`cdd-agent --version`)
   - Python version (`python --version`)
   - Error message and logs
   - Steps to reproduce

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

**In short:** Use it, modify it, distribute it. Just keep the license notice.

---

## 🙏 Acknowledgments

- Inspired by [Claude Code](https://claude.ai/code) and [Cursor](https://cursor.sh)
- Built on the [Context-Driven Development](https://github.com/guilhermegouw/context-driven-documentation) methodology
- Powered by amazing open-source libraries (Click, Rich, Textual, Pydantic)

---

## 💬 Community

- **Issues:** [GitHub Issues](https://github.com/guilhermegouw/context-driven-development-agent/issues)
- **Discussions:** [GitHub Discussions](https://github.com/guilhermegouw/context-driven-development-agent/discussions)
- **Author:** [@guilhermegouw](https://github.com/guilhermegouw)

---

**Built by developers, for developers.**
**No vendor lock-in. Your code, your choice.**

*CDD Agent - Because your tools should work for you, not lock you in.*
