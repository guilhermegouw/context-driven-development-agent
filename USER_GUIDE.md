# CDD Agent User Guide

Welcome to CDD Agent - your LLM-agnostic AI coding assistant with structured workflows!

## Table of Contents

1. [Getting Started](#getting-started)
2. [Basic Usage](#basic-usage)
3. [Chat Interface](#chat-interface)
4. [Authentication](#authentication)
5. [Tools & Capabilities](#tools--capabilities)
6. [Keyboard Shortcuts](#keyboard-shortcuts)
7. [Advanced Features](#advanced-features)
8. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Installation

```bash
pip install cdd-agent
```

### First-Time Setup

Before using CDD Agent, you need to configure your LLM provider:

```bash
cdd-agent auth setup
```

This interactive setup will guide you through:
- Choosing your provider (Anthropic, OpenAI, or custom)
- Entering your API key
- Configuring model mappings (small/mid/big tiers)

Your settings are stored in `~/.cdd-agent/settings.json`

---

## Basic Usage

### Start a Chat Session

```bash
cdd-agent chat
```

This opens the beautiful TUI (Text User Interface) where you can interact with the AI agent.

### Quick Question (Single Message)

```bash
cdd-agent chat "What files are in this directory?"
```

### Use Simple Streaming UI

If you prefer a simpler interface without the full TUI:

```bash
cdd-agent chat --simple
```

### Choose a Different Model

```bash
cdd-agent chat --model small   # Faster, cheaper
cdd-agent chat --model mid     # Balanced (default)
cdd-agent chat --model big     # Most capable
```

---

## Chat Interface

### TUI Mode (Default)

The TUI provides a split-pane interface with:

**Top Area: Chat History**
- See all your messages and the agent's responses
- Messages are beautifully formatted with markdown support
- Automatic scrolling to latest message

**Middle Area: Status Window (appears during processing)**
- 💭 Thinking indicators with animated dots
- 🔧 Tool usage notifications
- ✓ Tool completion confirmations
- Shows last 3 events in a scrolling window

**Bottom Area: Input Box**
- Type your messages here
- Press **Enter** to send
- Multi-line input coming soon!

### What You'll See

When the agent is working, you'll see:

1. **💭 Thinking...** - The agent is processing your request
2. **🔧 Using tool: read_file** - The agent is reading a file
3. **✓ read_file completed** - Tool execution succeeded
4. **Robot Panel** - Agent's response streams in word-by-word!

### Example Session

```
You: Read pyproject.toml and summarize this project

💭 Iteration 1/25.
🔧 Using tool: read_file
✓ read_file completed

Robot:
Based on the pyproject.toml file, this is CDD Agent - an AI coding
assistant with structured Context-Driven Development workflows...
[response continues streaming in real-time]
```

---

## Authentication

### View Current Configuration

```bash
cdd-agent auth status
```

Shows:
- Configured providers
- Default provider
- Model mappings
- API key status (masked for security)

### Switch Default Provider

```bash
cdd-agent auth set-default openai
```

### Test Your Authentication

```bash
cdd-agent auth test
cdd-agent auth test --provider anthropic
```

Makes a small API call to verify your credentials are working.

### Reconfigure

Just run setup again to change settings:

```bash
cdd-agent auth setup
```

---

## Tools & Capabilities

The agent has powerful tools at its disposal:

### 1. Read Files

The agent can read any file in your project:

```
You: Read src/main.py and explain what it does
```

### 2. Write Files

The agent can create or modify files:

```
You: Create a new file called hello.py with a simple hello world program
```

### 3. List Files

The agent can explore your project structure:

```
You: Show me all Python files in this directory
```

### 4. Run Bash Commands

The agent can execute shell commands:

```
You: Run pytest and show me the results
```

**Security Note**: The agent will execute commands with your user permissions. Always review what it's doing!

### Example: Complex Multi-Tool Task

```
You: Read all Python files in src/, analyze the code structure,
     and create a ARCHITECTURE.md file documenting the design
```

The agent will:
1. Use `list_files` to find Python files
2. Use `read_file` multiple times to read each file
3. Analyze the structure
4. Use `write_file` to create ARCHITECTURE.md
5. Stream the results to you in real-time!

---

## Keyboard Shortcuts

### TUI Mode

| Shortcut | Action |
|----------|--------|
| `Enter` | Send message |
| `Ctrl+C` | Quit application |
| `Ctrl+L` | Clear conversation history |
| `Ctrl+N` | Start new conversation |
| `F1` | Show help |

### Slash Commands

Type these in the input box:

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/clear` | Clear conversation history |
| `/new` | Start fresh conversation |
| `/quit` | Exit the application |

---

## Advanced Features

### Custom System Prompts

Add context or instructions that apply to the entire conversation:

```bash
cdd-agent chat --system "You are a Python expert. Always suggest best practices."
```

### Use Custom LLM Endpoints

During `auth setup`, choose "custom" provider and enter:
- Base URL (e.g., `http://localhost:8000/v1` for local LLM)
- API key (if needed)
- Model names for small/mid/big tiers

This works with:
- OpenAI-compatible APIs
- Local LLM servers (Ollama, LM Studio, vLLM)
- Custom proxy servers

### Environment Variables

Override settings with environment variables:

```bash
# Override API key
export ANTHROPIC_API_KEY="sk-ant-..."
cdd-agent chat

# Override base URL
export OPENAI_BASE_URL="http://localhost:8000/v1"
cdd-agent chat --provider openai
```

### Working Directory Context

The agent knows your current working directory:

```bash
cd /path/to/my/project
cdd-agent chat "Analyze this project structure"
```

The agent will work within that directory context.

---

## Troubleshooting

### "No configuration found"

**Problem**: You haven't set up authentication yet.

**Solution**:
```bash
cdd-agent auth setup
```

### "Authentication failed"

**Problem**: Invalid API key or network issues.

**Solutions**:
1. Check your API key is correct: `cdd-agent auth status`
2. Test connection: `cdd-agent auth test`
3. Reconfigure: `cdd-agent auth setup`

### "Max iterations reached"

**Problem**: Task is very complex and agent ran out of thinking cycles.

**Explanation**: The agent has 25 iterations to complete a task. Each tool use + thinking counts as an iteration.

**Solutions**:
- Break your request into smaller parts
- Be more specific in your instructions
- The limit is configurable in future versions

### Tool Execution Errors

**Problem**: "Permission denied" or "File not found"

**Solutions**:
- Check file paths are correct
- Ensure you have permissions
- Use absolute paths if relative paths fail

### Response Quality Issues

**Try**:
- Use a bigger model: `--model big`
- Add system prompt with more context: `--system "Context: ..."`
- Break complex tasks into steps
- Be more specific in your requests

### Terminal Display Issues

**Problem**: Colors or formatting look wrong

**Solutions**:
- Try simple mode: `cdd-agent chat --simple`
- Check terminal supports colors
- Update terminal emulator

---

## Tips & Best Practices

### 1. Be Specific

❌ "Fix the code"
✅ "Read main.py and fix the syntax error on line 42"

### 2. Provide Context

❌ "Add a feature"
✅ "Read the existing auth.py and add Google OAuth support following the same pattern"

### 3. Let the Agent Explore

✅ "Analyze this codebase and suggest improvements"

The agent can use tools to explore and understand your project.

### 4. Iterative Development

Start broad, then refine:
1. "What does this project do?"
2. "Show me the main entry point"
3. "Explain the authentication flow"
4. "Add rate limiting to the API"

### 5. Verify Important Changes

For critical code:
```
You: Read the changes you just made to main.py and explain what they do
```

---

## Getting Help

### In the Application

- Press `F1` in TUI mode
- Type `/help` in chat
- Use `cdd-agent --help` for CLI options

### Documentation

- **README**: Project overview and quick start
- **CLAUDE.md**: Development guidelines and architecture
- **This Guide**: Complete user documentation

### Issues & Feedback

Found a bug or have a suggestion?

Report it at: https://github.com/guilhermegouw/context-driven-development-agent/issues

---

## What's Next?

Now that you know the basics, try:

1. ✨ Ask the agent to analyze your current project
2. 🔧 Have it help refactor some code
3. 📝 Generate documentation for your codebase
4. 🧪 Write tests with the agent's help
5. 🚀 Build something amazing!

**Happy coding with CDD Agent!** 🤖

---

*Generated with love by the CDD Agent team*
*Version: 0.0.2*
