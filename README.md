# CDD Agent

**LLM-agnostic AI coding assistant with structured CDD (Context-Driven Development) workflows**

---

## What is CDD Agent?

CDD Agent is a terminal-based AI coding assistant that lets you use **any LLM provider** - Anthropic (Claude), OpenAI (GPT), or custom endpoints - without vendor lock-in. It implements the Context-Driven Development workflow: **Spec → Plan → Execute**, creating a virtuous cycle where development generates documentation that provides perfect context for AI assistance.

**Unlike vendor-specific tools** (Claude Code, Cursor), CDD Agent gives you:
- Freedom to choose your LLM provider
- Structured workflows that maintain context
- Local configuration and control
- No subscription lock-in

---

## Current Status: v0.0.1 (Experimental)

This is an **early experimental release**. Currently functional:
- Multi-provider configuration (Anthropic, OpenAI, custom endpoints)
- Authentication system with credential management
- CLI interface for setup and testing
- Model tier abstraction (small/mid/big)

**Coming soon:**
- Conversational agent loop
- Tool execution system
- Specialized CDD workflow agents (Socrates, Planner, Executor)
- Rich terminal UI with streaming responses

See [ROADMAP.md](ROADMAP.md) for the full development plan.

---

## Installation

```bash
pip install cdd-agent
```

**Requirements:**
- Python 3.10 or higher
- API keys for your chosen LLM provider(s)

---

## Quick Start

### 1. Configure your LLM provider

```bash
# Interactive setup wizard
cdd-agent auth setup

# Or set environment variables
export CDD_ANTHROPIC_API_KEY="your-api-key"
export CDD_OPENAI_API_KEY="your-api-key"
```

### 2. Verify your configuration

```bash
# Check configured providers
cdd-agent auth status

# Test API credentials
cdd-agent auth test
```

### 3. Start coding (coming in v0.1.0)

```bash
# Interactive conversation mode
cdd-agent chat

# CDD workflow modes
cdd-agent socrates  # Spec generation
cdd-agent plan      # Task planning
cdd-agent execute   # Implementation
```

---

## Features

### Multi-Provider Support
- **Anthropic**: Claude Haiku, Sonnet, Opus
- **OpenAI**: GPT-4o, GPT-4, GPT-3.5
- **Custom**: Any OpenAI-compatible endpoint (local models, proxies, alternative providers)

### Model Tier Abstraction
Configure models by tier instead of specific versions:
- **Small**: Fast, cheap operations (file searches, quick queries)
- **Mid**: Balanced performance (general coding, planning)
- **Big**: Maximum capability (complex reasoning, refactoring)

### Secure Configuration
- Local settings file: `~/.cdd-agent/settings.json`
- Environment variable overrides
- No telemetry or data collection
- Your code stays on your machine

---

## Configuration

CDD Agent uses a local configuration file at `~/.cdd-agent/settings.json`:

```json
{
  "providers": {
    "anthropic": {
      "api_key": "your-key",
      "models": {
        "small": "claude-haiku-4-5-20250929",
        "mid": "claude-sonnet-4-5-20250929",
        "big": "claude-opus-4-5-20250929"
      }
    },
    "openai": {
      "api_key": "your-key",
      "models": {
        "small": "gpt-4o-mini",
        "mid": "gpt-4o",
        "big": "gpt-4o"
      }
    }
  },
  "default_provider": "anthropic"
}
```

**Environment variables** (override settings file):
- `CDD_ANTHROPIC_API_KEY`
- `CDD_OPENAI_API_KEY`
- `CDD_CUSTOM_ENDPOINT`
- `CDD_DEFAULT_PROVIDER`

---

## Why CDD Agent?

### The Problem
Existing AI coding assistants lock you into a single vendor:
- Claude Code → Anthropic only
- Cursor → OpenAI only
- GitHub Copilot → GitHub/OpenAI only

### The Solution
CDD Agent provides:
- **Provider freedom**: Switch between Claude, GPT, or local models anytime
- **No lock-in**: Your workflows work with any LLM
- **Local control**: Configuration stays on your machine
- **Structured workflows**: CDD methodology keeps AI assistance contextual and effective

---

## Development

CDD Agent is built with:
- **Python 3.10+** for developer productivity
- **Click** for CLI framework
- **Rich** for beautiful terminal UI
- **Pydantic** for configuration management
- **Poetry** for dependency management

### Contributing

This is an early-stage project! Contributions welcome:
1. Check [ROADMAP.md](ROADMAP.md) for planned features
2. Open an issue to discuss your idea
3. Submit a PR with tests

### Running from source

```bash
git clone https://github.com/guilhermegouw/context-driven-development-agent.git
cd context-driven-development-agent
poetry install
poetry run cdd-agent --help
```

---

## Roadmap

**v0.0.x**: Foundation (auth, config, CLI) ✅
**v0.1.x**: Basic agent loop (conversation, tool execution)
**v0.2.x**: CDD workflows (Socrates, Planner, Executor)
**v0.3.x**: Rich TUI and streaming
**v1.0.0**: Stable API, full CDD workflow

See [ROADMAP.md](ROADMAP.md) for detailed milestones.

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## About Context-Driven Development

CDD Agent implements the Context-Driven Development methodology, where development creates documentation that provides perfect context for AI assistance. Learn more: [Context-Driven Documentation Framework](https://github.com/guilhermegouw/context-driven-documentation)

---

**Built by developers, for developers. No vendor lock-in. Your code, your choice.**
