# CDD Agent Roadmap

**Vision**: Build a monetizable, LLM-agnostic AI coding assistant with structured CDD workflows.

**Time Budget**: 10-15 hours/week (nights & weekends)
**Target**: Monetizable MVP in 8 weeks (60-120 hours total)

---

## ✅ Phase 0: Foundation (COMPLETED)

**Status**: ✅ Done
**Time Invested**: ~8-10 hours

### Deliverables
- [x] Poetry project setup with PyPI metadata
- [x] Package structure (`src/cdd_agent/`)
- [x] Configuration management (`config.py`)
- [x] Authentication system (`auth.py`)
- [x] CLI with auth commands (`cli.py`)
- [x] Comprehensive README
- [x] MIT License
- [x] Multi-provider support (Anthropic, OpenAI, custom)
- [x] Model tier abstraction (small/mid/big)
- [x] Environment variable overrides

### What Users Can Do Now
```bash
pip install cdd-agent  # (after publishing)
cdd-agent auth setup   # Configure providers
cdd-agent auth status  # View configuration
cdd-agent auth test    # Validate credentials
```

---

## 🚀 Phase 1: Basic Agent Loop (Weeks 1-2)

**Goal**: Create a working conversational AI agent
**Time Estimate**: 20-30 hours
**Status**: 🔜 Next Up

### Week 1: Core Agent Loop (10-15 hours)

#### Tasks
- [ ] Create `agent.py` with minimal conversation loop
  - Message history management
  - LLM API integration (Anthropic SDK)
  - Tool use detection and execution
  - Iteration loop until completion
- [ ] Implement `ToolRegistry` in `tools.py`
  - Auto-generate tool schemas from Python functions
  - Tool registration decorator
  - Tool execution with error handling
- [ ] Add 3 basic tools:
  - `read_file(path: str)` - Read file contents
  - `write_file(path: str, content: str)` - Write to file
  - `run_bash(command: str)` - Execute shell commands
- [ ] Create `cdd-agent chat` command
  - Non-streaming mode (simple text output)
  - Basic error handling

#### Success Criteria
```bash
cdd-agent chat "Read src/main.py and summarize it"
# Should: read the file, send to LLM, return summary

cdd-agent chat "Create a hello.py file that prints Hello World"
# Should: use write_file tool, create the file
```

### Week 2: LLM Provider Abstraction (10-15 hours)

#### Tasks
- [ ] Create `LLMProvider` interface in `providers.py`
  - Abstract base class for all providers
  - Methods: `create_message()`, `stream_message()`
- [ ] Implement `AnthropicProvider`
  - Use existing Anthropic SDK
  - Tool use support
  - Streaming support
- [ ] Implement `OpenAIProvider`
  - Translate Anthropic tool format to OpenAI
  - Handle response differences
  - Streaming support
- [ ] Add provider selection to chat command
  - `--provider` flag
  - Read from config default
  - Environment variable override

#### Success Criteria
```bash
# Use Claude
cdd-agent chat "Write a Python function to calculate factorial"

# Use GPT
cdd-agent chat --provider openai "Same task"

# Use custom provider
export CDD_PROVIDER=custom
cdd-agent chat "Same task"
```

#### Deliverable: Working Agent
- Can have conversations with any configured LLM
- Can execute basic file and shell tools
- Provider-agnostic architecture
- Ready for UI improvements

---

## 🎨 Phase 2: UX & Polish (Weeks 3-4)

**Goal**: Beautiful terminal UX with streaming responses
**Time Estimate**: 20-30 hours

### Week 3: Streaming UI (10-15 hours)

#### Tasks
- [ ] Create `ui.py` with Rich streaming components
  - Live markdown rendering
  - Syntax highlighting for code blocks
  - Tool execution progress indicators
  - Spinner for LLM thinking time
- [ ] Update `agent.py` for streaming
  - Stream LLM responses token-by-token
  - Update UI in real-time
  - Handle tool use in streaming mode
- [ ] Add conversation display
  - Color-coded messages (user vs assistant)
  - Formatted tool executions
  - Pretty error messages
- [ ] Improve chat command UX
  - Multi-line input support
  - `/help`, `/clear`, `/quit` commands
  - Ctrl+C graceful exit

#### Success Criteria
- Responses stream in real-time (like ChatGPT)
- Code blocks have syntax highlighting
- Tool executions show progress
- Beautiful, polished terminal experience

### Week 4: Conversation Management (10-15 hours)

#### Tasks
- [ ] Implement conversation persistence
  - Save conversations to `~/.cdd-agent/conversations/`
  - JSON format with metadata (date, provider, model, cost)
  - Auto-save after each message
- [ ] Add conversation commands
  - `cdd-agent conversations list` - Show all conversations
  - `cdd-agent conversations show <id>` - Display conversation
  - `cdd-agent conversations resume <id>` - Continue conversation
  - `cdd-agent conversations delete <id>` - Remove conversation
- [ ] Add token counting and cost estimation
  - Track input/output tokens per message
  - Calculate cost per provider/model
  - Display running total
- [ ] Add `/save`, `/load`, `/new` slash commands
  - In-conversation management
  - Named conversations (optional)

#### Success Criteria
```bash
# Start conversation
cdd-agent chat "Help me build a web app"
# ... conversation happens, auto-saved ...

# List conversations
cdd-agent conversations list
# Shows: ID, Date, Provider, Messages, Cost

# Resume later
cdd-agent conversations resume abc123
# Continues where you left off
```

#### Deliverable: Production-Ready Chat
- Beautiful streaming UI
- Persistent conversation history
- Token/cost tracking
- Professional terminal experience

---

## 🛠️ Phase 3: Advanced Tools & CDD Integration (Weeks 5-6)

**Goal**: Integrate CDD workflow and advanced tools
**Time Estimate**: 20-30 hours

### Week 5: Advanced Tools (10-15 hours)

#### Tasks
- [ ] Add search/grep tools
  - `grep_files(pattern: str, path: str)` - Search in files
  - `find_files(pattern: str, path: str)` - Find files by name
  - `list_directory(path: str)` - List directory contents
- [ ] Add git tools
  - `git_status()` - Show git status
  - `git_diff(file: str)` - Show file changes
  - `git_commit(message: str, files: list)` - Commit changes
- [ ] Add codebase mapping tool
  - `map_codebase(path: str)` - Generate file tree
  - Include file counts, sizes, languages
  - Respect .gitignore patterns
- [ ] Implement tool approval flow
  - Ask before executing destructive commands
  - Auto-approve safe operations (read-only)
  - Remember approvals for session
  - Security warnings for dangerous operations

#### Success Criteria
```bash
cdd-agent chat "Find all Python files with 'TODO' comments"
# Uses grep_files + find_files

cdd-agent chat "Refactor all authentication code to use new API"
# Multi-file changes with approval flow
```

### Week 6: CDD Workflow Integration (10-15 hours)

#### Tasks
- [ ] Port Socrates agent
  - Load `socrates.md` prompt from your existing CDD framework
  - Implement as specialized agent mode
  - `cdd-agent socrates <spec-file>` command
  - Guided conversation for spec creation
- [ ] Port Plan generator
  - Load `plan.md` prompt
  - `cdd-agent plan <spec-file>` command
  - Generate implementation plans from specs
  - Save to `plan.md` in ticket folder
- [ ] Add context loading
  - Read `CLAUDE.md` / `CDD.md` files
  - Include in system prompt automatically
  - Hierarchical loading (global → project → ticket)
- [ ] Create `cdd-agent exec <ticket>` command
  - Load spec + plan as context
  - Execute implementation with full context
  - Track progress in ticket folder

#### Success Criteria
```bash
# CDD workflow works standalone
cdd-agent socrates specs/tickets/feature-auth/spec.yaml
# Guided conversation, builds spec

cdd-agent plan specs/tickets/feature-auth/spec.yaml
# Generates detailed plan

cdd-agent exec specs/tickets/feature-auth
# Implements based on spec + plan
```

#### Deliverable: CDD-Powered Agent
- All your existing CDD agents work
- Context management from CLAUDE.md
- Structured workflow (spec → plan → exec)
- Advanced tools for complex refactors
- Security via approval flow

---

## 💰 Phase 4: Monetization & Launch (Weeks 7-8)

**Goal**: Prepare for market and launch
**Time Estimate**: 20-30 hours

### Week 7: Cloud Integration (10-15 hours)

#### Tasks
- [ ] Add usage tracking/analytics
  - Log API calls, tokens, costs
  - Store locally in SQLite
  - Optional telemetry (opt-in)
- [ ] Implement license key validation
  - Support for free tier (50 conversations/month)
  - Pro tier ($10-15/month) - unlimited
  - Validate keys against backend API
- [ ] Add cloud conversation sync (optional)
  - Sync conversations to cloud storage
  - Access from multiple machines
  - End-to-end encryption
- [ ] Create update mechanism
  - Check for new versions on startup
  - `cdd-agent update` command
  - Notify users of new features

#### Monetization Tiers
```
FREE:
- Unlimited usage with own API keys
- Local conversations only
- Community support
- Open source core

PRO ($10-15/month):
- Cloud conversation sync
- Usage analytics dashboard
- Priority support
- Early access to features

ENTERPRISE ($500+/month):
- On-premise deployment
- Custom model fine-tuning
- SLA support
- Team features
```

### Week 8: Documentation & Launch (10-15 hours)

#### Tasks
- [ ] Comprehensive documentation
  - Installation guide
  - Configuration examples
  - CDD workflow tutorial
  - API reference for custom tools
  - Video demos
- [ ] Create landing page
  - Features overview
  - Pricing table
  - Demo videos/GIFs
  - Sign up for Pro tier
- [ ] Set up payment processing
  - Stripe integration
  - License key generation API
  - Customer portal
- [ ] Publish to PyPI
  - `poetry publish`
  - Version 1.0.0 release
- [ ] Launch!
  - Product Hunt
  - Hacker News Show HN
  - Reddit (r/python, r/programming)
  - Twitter/X announcement
  - Email beta users

#### Success Criteria
- Published on PyPI: `pip install cdd-agent`
- Landing page live with pricing
- Payment processing working
- 10+ beta users signed up
- First paying customer ($10/month)

#### Deliverable: Launched Product
- Publicly available on PyPI
- Monetization infrastructure
- Marketing materials
- Active user base
- $100+ MRR target

---

## 🔮 Phase 5: Growth & Features (Months 3-6)

**Post-Launch Improvements**

### Month 3: Polish & Feedback
- [ ] User feedback implementation
- [ ] Bug fixes and stability
- [ ] Performance optimizations
- [ ] Documentation improvements
- **Goal**: 100 active users

### Month 4: Advanced Features
- [ ] Full Textual TUI (split panes, file tree)
- [ ] Multi-agent orchestration
- [ ] Codebase embeddings for semantic search
- [ ] VS Code extension
- **Goal**: 500 active users, $500 MRR

### Month 5: Team Features
- [ ] Shared conversation libraries
- [ ] Team analytics
- [ ] SSO/SAML for enterprise
- [ ] Custom tool marketplace
- **Goal**: First enterprise customer

### Month 6: Ecosystem
- [ ] MCP (Model Context Protocol) support
- [ ] Plugin system for community tools
- [ ] Integration marketplace
- [ ] Mobile companion app
- **Goal**: $2000 MRR, sustainable business

---

## 🎯 Success Metrics

### Week 6 (MVP)
- ✅ Working CLI that can read/write/execute code
- ✅ Streaming responses with beautiful UI
- ✅ LLM-agnostic (Claude & GPT)
- ✅ CDD workflow integrated
- ✅ 10 beta users testing

### Week 8 (Launch)
- ✅ Published to PyPI
- ✅ Landing page + pricing
- ✅ Payment processing
- ✅ First paying customer
- ✅ $100 MRR

### Month 3 (Traction)
- ✅ 100 active users
- ✅ $500 MRR
- ✅ Positive user reviews
- ✅ Low churn rate (<10%)

### Month 6 (Sustainable)
- ✅ 500+ active users
- ✅ $2000+ MRR
- ✅ 1-2 enterprise customers
- ✅ Active community
- ✅ Profitable (covering costs + runway)

---

## 🚧 Risks & Mitigations

### Risk: Burnout from Scope Creep
**Mitigation**:
- Stick to week-by-week plan religiously
- Ship "embarrassingly simple" MVP at week 6
- Use feature flags for incomplete features
- Say no to non-essential features

### Risk: Competition from Well-Funded Tools
**Mitigation**:
- Focus on niche: CDD workflow users
- Emphasize open source + self-hosting
- Build community early (Discord, GitHub)
- Compete on workflow, not features

### Risk: LLM API Changes
**Mitigation**:
- Abstract provider interface from day 1 (✅ done)
- Write integration tests against live APIs
- Version lock dependencies
- Support multiple LLM versions

### Risk: Monetization Resistance
**Mitigation**:
- Keep core open source forever
- Only charge for cloud services
- Generous free tier (unlimited with own keys)
- Transparent pricing

---

## 📊 Progress Tracking

**Current Phase**: Phase 0 ✅ (Foundation Complete)
**Next Phase**: Phase 1 🔜 (Basic Agent Loop)
**Hours Invested**: 8-10 hours
**Hours Remaining to MVP**: 60-90 hours
**Target MVP Date**: 6-8 weeks from now

**Last Updated**: 2025-11-03

---

## 🎓 Key Learnings

### What We Learned from Gemini CLI
- Tool registry pattern with auto-schema generation
- Streaming UI is essential for good UX
- Context management is critical for large codebases
- React + Ink for terminal is powerful but complex (we chose Rich for Python)

### What We Learned from Claude Code
- Settings.json pattern with env overrides
- Model tier abstraction (small/mid/big)
- Custom commands as markdown files
- Slash commands for in-conversation controls

### Our Unique Approach
- **LLM-agnostic from day one** (Gemini CLI is Gemini-first)
- **Python ecosystem** (more accessible than TypeScript)
- **CDD workflow built-in** (unique value proposition)
- **Simpler architecture** (easier to understand and modify)

---

**Next Step**: Start Week 1 - Build the core agent loop! 🚀
