# CDD Agent Phase 2: Complete Implementation Roadmap

**Vision:** Transform CDD Agent into a complete CDD workflow tool with conversational agents (Socrates, Planner, Executor) accessible via unified slash command interface in chat mode.

**Timeline:** 8-9 weeks (70-85 hours total)
**Current Status:** Phase 1 Complete ✅ (16 tools, approval system, context loading, background execution)
**Next Release:** v0.2.0 (CDD Workflow Integration)

---

## 🎯 Strategic Goals

### **Core Principles**
1. **Chat-First Experience** - Everything happens in `cdd-agent chat` via slash commands
2. **Provider Independence** - Works with any LLM (Anthropic, OpenAI, custom)
3. **Deterministic Workflows** - Code enforces agent boundaries and state transitions
4. **Resumability** - All progress tracked in files (progress.yaml)
5. **Terminal Excellence** - Beautiful TUI with Rich, streaming responses

### **What We're Building**

```
Mechanical Layer (File Generation):
  /init              → Initialize CDD project structure
  /new               → Create ticket/doc from templates

Intelligence Layer (AI Agents):
  /socrates          → Fill spec.yaml through Socratic dialogue
  /plan              → Generate plan.md from spec.yaml
  /exec              → Implement code from plan.md

Utility Layer:
  /status            → Show ticket progress
  /list              → List all tickets
  /help              → Command reference
```

---

## 📋 Phase 2 Breakdown

### **Week 4: Foundation - Mechanical Layer (12-15 hours)**

**Goal:** Build file generation commands (`/init`, `/new`) and slash command infrastructure

#### **4.1 Shared Logic Layer (6 hours)**

**Create:** `src/cdd_agent/mechanical/`

```python
src/cdd_agent/mechanical/
├── __init__.py
├── init.py              # initialize_project()
├── new_ticket.py        # create_new_ticket(), create_new_documentation()
└── templates/           # Template files
    ├── feature-ticket-template.yaml
    ├── bug-ticket-template.yaml
    ├── spike-ticket-template.yaml
    ├── feature-plan-template.md
    ├── bug-plan-template.md
    ├── spike-plan-template.md
    ├── constitution-template.md
    ├── guide-doc-template.md
    └── feature-doc-template.md
```

**Tasks:**

- [ ] **Port `initialize_project()` from CDD POC** (2h)
  - Input: `path: str, force: bool = False`
  - Output: `dict` with created items
  - Behavior:
    - Validates path (refuses /, /usr, /home, etc.)
    - Detects git root (uses `git rev-parse --show-toplevel`)
    - Creates directory structure:
      ```
      specs/tickets/
      docs/features/
      docs/guides/
      .cdd/templates/
      .cdd/config.yaml
      CLAUDE.md
      ```
    - Installs templates from package
    - Idempotent (safe to run multiple times)

- [ ] **Port `create_new_ticket()` from CDD POC** (2h)
  - Input: `ticket_type: str, name: str`
  - Output: `dict` with ticket_path, normalized_name, overwritten
  - Behavior:
    - Normalizes name ("User Auth" → "user-auth")
    - Finds git root
    - Loads template from `.cdd/templates/{type}-ticket-template.yaml`
    - Populates `[auto-generated]` dates
    - Creates `specs/tickets/{type}-{name}/spec.yaml`
    - Prompts on overwrite conflicts

- [ ] **Port `create_new_documentation()` from CDD POC** (1h)
  - Input: `doc_type: str, name: str`
  - Output: `dict` with file_path, normalized_name, overwritten
  - Behavior:
    - Creates `docs/guides/{name}.md` or `docs/features/{name}.md`
    - Uses templates from `.cdd/templates/`

- [ ] **Bundle templates with package** (1h)
  - Copy templates from CDD POC to `src/cdd_agent/mechanical/templates/`
  - Ensure templates load via `importlib.resources` (Python 3.9+)
  - Test template installation

**Success Criteria:**
- ✅ `initialize_project()` creates full directory structure
- ✅ `create_new_ticket()` creates spec.yaml from template
- ✅ `create_new_documentation()` creates markdown from template
- ✅ All functions have proper error handling
- ✅ Git validation works (refuses non-git repos)

---

#### **4.2 Slash Command Router (4 hours)**

**Create:** `src/cdd_agent/slash_commands.py`

```python
class SlashCommandRouter:
    """Routes slash commands to handlers in chat mode"""

    def __init__(self, session):
        self.session = session
        self.commands = {
            "/init": InitCommand(session),
            "/new": NewCommand(session),
            "/socrates": SocratesCommand(session),
            "/plan": PlanCommand(session),
            "/exec": ExecCommand(session),
            "/help": HelpCommand(session),
            "/status": StatusCommand(session),
            "/list": ListCommand(session),
        }

    def parse(self, user_input: str) -> tuple[str | None, str]:
        """Parse slash command and arguments"""
        if not user_input.startswith("/"):
            return None, ""

        parts = user_input.split(maxsplit=1)
        command = parts[0]
        args = parts[1] if len(parts) > 1 else ""
        return command, args

    async def handle(self, command: str, args: str) -> str | None:
        """Execute command, return response or None if agent takes over"""
        handler = self.commands.get(command)
        if handler:
            return await handler.execute(args)
        else:
            return self._unknown_command(command)
```

**Command Classes:**

```python
class BaseSlashCommand:
    """Base class for slash commands"""
    def __init__(self, session):
        self.session = session

    async def execute(self, args: str) -> str | None:
        """Execute command, return response or None"""
        raise NotImplementedError

class InitCommand(BaseSlashCommand):
    async def execute(self, args: str) -> str:
        # Parse --force flag
        force = "--force" in args

        # Call mechanical layer
        from cdd_agent.mechanical.init import initialize_project
        result = initialize_project(".", force)

        # Format success message
        return self._format_success(result)

class NewCommand(BaseSlashCommand):
    async def execute(self, args: str) -> str:
        # Parse: /new feature user-auth
        #        /new documentation guide getting-started
        parts = args.split(maxsplit=2)

        if len(parts) < 2:
            return self._usage_error()

        ticket_type = parts[0]
        name = parts[1]

        if ticket_type == "documentation":
            doc_type = parts[1]
            doc_name = parts[2] if len(parts) > 2 else ""
            from cdd_agent.mechanical.new_ticket import create_new_documentation
            result = create_new_documentation(doc_type, doc_name)
        else:
            from cdd_agent.mechanical.new_ticket import create_new_ticket
            result = create_new_ticket(ticket_type, name)

        return self._format_success(result)

class HelpCommand(BaseSlashCommand):
    async def execute(self, args: str) -> str:
        return """
📋 CDD Agent Slash Commands

**Project Setup:**
  /init [--force]              Initialize CDD project structure

**Ticket Creation:**
  /new feature <name>          Create feature ticket
  /new bug <name>              Create bug ticket
  /new spike <name>            Create research spike
  /new documentation guide <name>    Create guide documentation
  /new documentation feature <name>  Create feature docs

**CDD Workflow:**
  /socrates <ticket>           Fill specification (Socratic dialogue)
  /plan <ticket>               Generate implementation plan
  /exec <ticket>               Execute implementation

**Utilities:**
  /status [ticket]             Show ticket progress
  /list                        List all tickets
  /help                        Show this help

**Tips:**
- All work happens in this chat - no terminal switching!
- Type /init to get started
- Agents (Socrates, Planner, Executor) take over conversation
- Type 'exit' while in agent mode to return to chat
"""
```

**Tasks:**

- [ ] **Implement SlashCommandRouter** (1.5h)
  - Parse slash commands from user input
  - Route to appropriate handler
  - Handle unknown commands gracefully

- [ ] **Implement InitCommand** (0.5h)
  - Call `initialize_project()`
  - Format Rich success message
  - Handle errors with helpful messages

- [ ] **Implement NewCommand** (1h)
  - Parse ticket type and name
  - Call `create_new_ticket()` or `create_new_documentation()`
  - Format Rich success message
  - Handle name conflicts (prompt user)

- [ ] **Implement HelpCommand** (0.5h)
  - Show all available commands
  - Include usage examples
  - Format with Rich markdown

- [ ] **Implement StatusCommand stub** (0.5h)
  - Placeholder for Week 8
  - Returns "Coming soon" for now

**Success Criteria:**
- ✅ `/init` creates project structure in chat
- ✅ `/new feature user-auth` creates ticket
- ✅ `/new documentation guide api` creates docs
- ✅ `/help` shows formatted command list
- ✅ Unknown commands show helpful error

---

#### **4.3 Chat Session Integration (2 hours)**

**Modify:** `src/cdd_agent/tui.py` or create `src/cdd_agent/chat_session.py`

```python
class ChatSession:
    """Manages chat conversation with agent switching"""

    def __init__(self, provider, tools, approval_system):
        self.provider = provider
        self.tools = tools
        self.approval_system = approval_system

        # Agent management
        self.current_agent = None  # None = general chat mode
        self.slash_router = SlashCommandRouter(self)

        # Conversation state
        self.messages = []
        self.context = None  # Loaded from CLAUDE.md

    def switch_to_agent(self, agent_class, target_path):
        """Switch from general chat to specialized agent"""
        self.current_agent = agent_class(
            provider=self.provider,
            tools=self.tools,
            target_path=target_path,
            session=self
        )

        # Agent sends initial message
        initial_msg = self.current_agent.initialize()
        self.display(initial_msg)

    def exit_agent(self):
        """Return from agent to general chat"""
        if self.current_agent:
            completion_msg = self.current_agent.finalize()
            self.display(completion_msg)
            self.current_agent = None

    async def process_input(self, user_input: str):
        """Main input processing loop"""

        # Special commands
        if user_input.lower() in ["exit", "quit"] and self.current_agent:
            self.exit_agent()
            return

        # Check for slash command
        command, args = self.slash_router.parse(user_input)

        if command:
            # Execute slash command
            response = await self.slash_router.handle(command, args)

            if response:
                self.display(response)
            # If response is None, agent took over (Socrates/Planner/Executor)

        elif self.current_agent:
            # Agent is active - send to agent
            response = await self.current_agent.process(user_input)
            self.display(response)

            # Check if agent completed
            if self.current_agent.is_done():
                self.exit_agent()

        else:
            # General chat mode - send to LLM
            response = await self.send_to_llm(user_input)
            self.display(response)
```

**Tasks:**

- [ ] **Create ChatSession class** (1h)
  - Agent switching logic
  - Slash command routing integration
  - State management (general chat vs agent mode)

- [ ] **Integrate with TUI** (0.5h)
  - Replace current message handling
  - Add agent mode indicator in UI
  - Show current ticket in status bar

- [ ] **Add exit command handling** (0.5h)
  - Type "exit" to leave agent mode
  - Confirmation prompt if work incomplete

**Success Criteria:**
- ✅ Slash commands work in chat mode
- ✅ `/init` and `/new` execute successfully
- ✅ Error messages display properly
- ✅ Chat session state persists across commands

---

#### **4.4 BaseAgent Architecture (3 hours)**

**Create:** `src/cdd_agent/agents/base.py`

```python
class BaseAgent:
    """Base class for specialized agents (Socrates, Planner, Executor)"""

    def __init__(self, provider, tools, target_path, session):
        self.provider = provider
        self.tools = tools
        self.target_path = Path(target_path)
        self.session = session

        # Agent state
        self.messages = []
        self.is_complete = False
        self.system_prompt = self.load_system_prompt()

        # Context
        self.context = self.load_context()

    def load_system_prompt(self) -> str:
        """Load agent-specific prompt from markdown file"""
        prompt_name = self.__class__.__name__.lower().replace("agent", "")
        prompt_path = Path(__file__).parent / "prompts" / f"{prompt_name}.md"

        if prompt_path.exists():
            return prompt_path.read_text()
        else:
            raise FileNotFoundError(f"System prompt not found: {prompt_path}")

    def load_context(self) -> dict:
        """Load agent-specific context files"""
        # Base implementation - override in subclasses
        context = {}

        # Load CLAUDE.md (all agents need this)
        claude_md = self._find_claude_md()
        if claude_md:
            context["project"] = claude_md.read_text()

        return context

    def initialize(self) -> str:
        """Called when agent first takes over - returns initial message"""
        raise NotImplementedError

    async def process(self, user_input: str) -> str:
        """Process user input, return agent response"""
        raise NotImplementedError

    def is_done(self) -> bool:
        """Check if agent has completed its task"""
        return self.is_complete

    def finalize(self) -> str:
        """Called when exiting agent - returns completion message"""
        raise NotImplementedError

    async def call_llm(self, user_message: str) -> str:
        """Call LLM with agent's system prompt and conversation history"""
        # Add user message
        self.messages.append({"role": "user", "content": user_message})

        # Call provider
        response = await self.provider.create_message(
            system=self.system_prompt,
            messages=self.messages,
            tools=self.get_tool_schemas()
        )

        # Add assistant message
        self.messages.append({"role": "assistant", "content": response})

        return response

    def get_tool_schemas(self) -> list:
        """Return tool schemas for this agent (override in subclasses)"""
        return []
```

**Tasks:**

- [ ] **Implement BaseAgent class** (2h)
  - System prompt loading from markdown
  - Context loading (CLAUDE.md, etc.)
  - LLM conversation management
  - Tool execution framework

- [ ] **Create prompts directory** (0.5h)
  ```
  src/cdd_agent/agents/prompts/
  ├── socrates.md      # Week 5
  ├── planner.md       # Week 6
  └── executor.md      # Week 7
  ```

- [ ] **Write stub agents for testing** (0.5h)
  - TestAgent that echoes input
  - Verify agent switching works

**Success Criteria:**
- ✅ BaseAgent loads system prompt from file
- ✅ BaseAgent manages conversation state
- ✅ BaseAgent calls LLM correctly
- ✅ Subclasses can override tool sets

---

#### **Week 4 Deliverables**

- ✅ `/init` command works in chat
- ✅ `/new` command creates tickets/docs
- ✅ `/help` shows all commands
- ✅ Slash command router integrated
- ✅ BaseAgent architecture ready
- ✅ Chat session manages agent switching
- ✅ Tests for mechanical layer

**Testing Strategy:**
- Unit tests for `initialize_project()`, `create_new_ticket()`
- Integration tests for slash commands
- Manual testing in chat mode
- Template validation tests

---

### **Week 5: Socrates Agent (15-18 hours)**

**Goal:** Implement Socrates agent for requirements gathering through Socratic dialogue

#### **5.1 Socrates System Prompt (3 hours)**

**Create:** `src/cdd_agent/agents/prompts/socrates.md`

**Port from CDD POC:** `.claude/commands/socrates.md`

**Key Sections:**
- Persona definition (curious, collaborative, context-aware)
- Mission (create comprehensive specs through dialogue)
- Context loading workflow (CLAUDE.md → spec → templates)
- Progressive clarification pattern
- Scope boundaries (requirements only, not implementation)
- Wrap-up flow (show summary → get approval → write file)

**Adaptations for CDD Agent:**
- Remove Claude Code-specific instructions (view command, etc.)
- Use tool names from CDD Agent (read_file, write_file)
- Update file paths to match our structure
- Add exit handling ("type 'exit' to return to chat")

**Tasks:**

- [ ] **Port and adapt Socrates prompt** (2h)
  - Copy base content from CDD POC
  - Update tool references
  - Update file path patterns
  - Test prompt with test conversations

- [ ] **Add CDD Agent specific instructions** (1h)
  - Session management (exit to return to chat)
  - Tool approval handling
  - Progress indication
  - Error recovery

**Success Criteria:**
- ✅ Prompt defines clear Socrates persona
- ✅ Context loading workflow is clear
- ✅ Progressive clarification pattern explained
- ✅ Scope boundaries well-defined
- ✅ Wrap-up flow detailed

---

#### **5.2 SocratesAgent Implementation (10 hours)**

**Create:** `src/cdd_agent/agents/socrates.py`

```python
class SocratesAgent(BaseAgent):
    """Requirements gathering specialist using Socratic method"""

    def __init__(self, provider, tools, target_path, session):
        super().__init__(provider, tools, target_path, session)

        # Socrates-specific state
        self.spec_sections = {}
        self.template_structure = self._load_template()
        self.approval_received = False

    def get_tool_schemas(self) -> list:
        """Socrates has READ-ONLY tools"""
        allowed_tools = [
            "read_file",
            "list_files",
            "glob_files",
            "grep_files"
        ]
        return [t for t in self.tools if t.name in allowed_tools]

    def load_context(self) -> dict:
        """Load Socrates-specific context"""
        context = super().load_context()

        # Load target spec file (may be empty or partial)
        spec_file = self.target_path / "spec.yaml"
        if spec_file.exists():
            context["spec"] = spec_file.read_text()

        # Load appropriate template
        ticket_type = self._infer_ticket_type()
        template_path = self._find_template(ticket_type)
        if template_path:
            context["template"] = template_path.read_text()

        # Look for related work
        context["related"] = self._find_related_work()

        return context

    def initialize(self) -> str:
        """Socrates introduction"""
        return f"""
👋 Hey! I'm Socrates. Let me load context before we start...

📚 Context loaded:

**Project:** {self._summarize_project()}
**Working on:** {self.target_path.name}
**Template structure:** {self._summarize_template()}
**Related context:** {self._summarize_related()}

**Key insights:**
{self._generate_insights()}

Now I can ask smart, targeted questions. Ready?
"""

    async def process(self, user_input: str) -> str:
        """Process user response in Socratic dialogue"""

        # Check for special commands
        if user_input.lower() == "summary":
            return self._show_summary()

        if user_input.lower() == "approve" and self.approval_received:
            await self._write_spec()
            self.is_complete = True
            return "✅ Saved spec.yaml! Type 'exit' to return to chat."

        # Regular dialogue - call LLM
        response = await self.call_llm(user_input)

        # Check if Socrates is showing final summary
        if "Does this look good?" in response or "Should I save" in response:
            self.approval_received = True

        return response

    async def _write_spec(self):
        """Write completed spec to spec.yaml"""
        spec_file = self.target_path / "spec.yaml"

        # Call write_file tool
        # (Tool execution happens through approval system)
        await self.execute_tool("write_file", {
            "file_path": str(spec_file),
            "content": self._format_spec_yaml()
        })

    def finalize(self) -> str:
        """Completion message"""
        if self.is_complete:
            return f"""
✅ Specification complete!

**File:** {self.target_path / 'spec.yaml'}

**Next steps:**
  /plan {self.target_path.name}    Generate implementation plan

Type any message to return to general chat.
"""
        else:
            return "⚠️ Specification incomplete. Progress saved."
```

**Tasks:**

- [ ] **Implement core SocratesAgent class** (3h)
  - Initialize with target path
  - Load context (CLAUDE.md, spec, template)
  - Manage conversation state

- [ ] **Implement context loading** (2h)
  - `load_context()` - Load CLAUDE.md, spec.yaml, template
  - `_infer_ticket_type()` - Detect feature/bug/spike from path
  - `_find_template()` - Locate template file
  - `_find_related_work()` - Search for similar tickets

- [ ] **Implement dialogue management** (3h)
  - `initialize()` - Show loaded context
  - `process()` - Handle user responses
  - Progressive clarification logic
  - Approval detection

- [ ] **Implement spec writing** (2h)
  - `_write_spec()` - Format and write spec.yaml
  - `_format_spec_yaml()` - Convert conversation to YAML
  - Tool execution with approval

**Success Criteria:**
- ✅ Socrates loads context intelligently
- ✅ Socrates asks progressive questions
- ✅ Socrates stays in scope (requirements only)
- ✅ Socrates shows summary before saving
- ✅ Socrates writes valid spec.yaml
- ✅ Socrates handles errors gracefully

---

#### **5.3 /socrates Slash Command (2 hours)**

**Create command handler in:** `src/cdd_agent/slash_commands.py`

```python
class SocratesCommand(BaseSlashCommand):
    async def execute(self, args: str) -> None:
        """Launch Socrates agent"""

        if not args:
            return "❌ Usage: /socrates <ticket-path>"

        # Validate ticket exists
        ticket_path = self._resolve_ticket_path(args)

        if not ticket_path.exists():
            return f"❌ Ticket not found: {args}\n" \
                   f"💡 Create it first: /new feature {args}"

        # Switch to Socrates agent
        from cdd_agent.agents.socrates import SocratesAgent

        self.session.switch_to_agent(
            agent_class=SocratesAgent,
            target_path=ticket_path
        )

        # Agent takes over - return None
        return None
```

**Tasks:**

- [ ] **Implement SocratesCommand** (1h)
  - Parse ticket path argument
  - Validate ticket exists
  - Switch session to Socrates agent

- [ ] **Add ticket path resolution** (0.5h)
  - Support shortcuts: `feature-user-auth` → `specs/tickets/feature-user-auth/`
  - Support full paths
  - Search from git root

- [ ] **Add helpful error messages** (0.5h)
  - Ticket doesn't exist → suggest `/new`
  - No spec.yaml → offer to create
  - Clear usage examples

**Success Criteria:**
- ✅ `/socrates feature-user-auth` launches agent
- ✅ Path resolution works (shortcuts + full paths)
- ✅ Error messages are helpful
- ✅ Agent mode activates correctly

---

#### **5.4 Integration & Testing (3 hours)**

**Tasks:**

- [ ] **End-to-end workflow test** (1h)
  ```bash
  /init
  /new feature user-auth
  /socrates feature-user-auth
  [Complete dialogue]
  [Verify spec.yaml written]
  ```

- [ ] **Unit tests for SocratesAgent** (1h)
  - Context loading
  - Template detection
  - Spec formatting
  - Tool restrictions (read-only)

- [ ] **Error handling tests** (0.5h)
  - Missing template
  - Invalid spec.yaml
  - Tool execution failures

- [ ] **Documentation** (0.5h)
  - Update README with Socrates workflow
  - Add examples to help text
  - Document common issues

**Success Criteria:**
- ✅ Full workflow works end-to-end
- ✅ Tests cover core functionality
- ✅ Error cases handled gracefully
- ✅ Documentation updated

---

#### **Week 5 Deliverables**

- ✅ SocratesAgent fully functional
- ✅ `/socrates` command launches agent
- ✅ Context loading works (CLAUDE.md + template + related)
- ✅ Socratic dialogue pattern implemented
- ✅ spec.yaml written correctly
- ✅ Exit back to chat works
- ✅ Tests passing (>80% coverage)
- ✅ Documentation updated

---

### **Week 6: Planner Agent (15-18 hours)**

**Goal:** Implement Planner agent for autonomous implementation planning

#### **6.1 Planner System Prompt (3 hours)**

**Create:** `src/cdd_agent/agents/prompts/planner.md`

**Port from CDD POC:** `.claude/commands/plan.md`

**Key Sections:**
- Persona (senior architect, autonomous, pragmatic)
- Decision-making framework (90% autonomous, 1-3 questions max)
- Codebase analysis with depth limits
- Plan structure (steps, effort estimates, decisions)
- Confirmation flow (show overview → generate plan)

**Adaptations:**
- Update tool names
- Add depth limits enforcement
- Clarify effort estimation methodology
- Add resumability instructions

**Tasks:**

- [ ] **Port Planner prompt** (2h)
- [ ] **Add CDD Agent specific sections** (1h)
  - Tool approval integration
  - Progress indication
  - Plan validation

---

#### **6.2 PlannerAgent Implementation (10 hours)**

**Create:** `src/cdd_agent/agents/planner.py`

```python
class PlannerAgent(BaseAgent):
    """Autonomous implementation planning specialist"""

    def __init__(self, provider, tools, target_path, session):
        super().__init__(provider, tools, target_path, session)

        # Planner-specific state
        self.spec = self._load_spec()
        self.codebase_analysis = {}
        self.decisions = []
        self.plan_approved = False

        # Analysis limits
        self.max_files_analyzed = 10
        self.max_glob_searches = 3
        self.max_analysis_time = 30  # seconds

    def get_tool_schemas(self) -> list:
        """Planner has READ + ANALYSIS tools"""
        allowed_tools = [
            "read_file",
            "list_files",
            "glob_files",
            "grep_files",
            "git_status",
            "git_log",
            "git_diff"
        ]
        return [t for t in self.tools if t.name in allowed_tools]

    def load_context(self) -> dict:
        """Load Planner-specific context"""
        context = super().load_context()

        # Load spec.yaml (required)
        spec_file = self.target_path / "spec.yaml"
        if not spec_file.exists():
            raise FileNotFoundError(
                f"spec.yaml not found. Run: /socrates {self.target_path.name}"
            )

        context["spec"] = self._load_spec()

        # Load plan template
        ticket_type = self._infer_ticket_type()
        template_path = self._find_plan_template(ticket_type)
        if template_path:
            context["plan_template"] = template_path.read_text()

        return context

    def initialize(self) -> str:
        """Planner introduction"""
        return f"""
📋 Got it! I'll create the implementation plan.

**Loading context...**

📚 Context loaded:
- Spec: {self.target_path / 'spec.yaml'}
- Project: {self._summarize_project()}
- Template: {self._plan_template_name()}

**Starting codebase analysis** (limited to {self.max_files_analyzed} files)...
"""

    async def process(self, user_input: str) -> str:
        """Process planner workflow"""

        # State machine: analyze → confirm → generate → done

        if self.state == "analyzing":
            # Planner asks 1-3 clarifying questions
            response = await self.call_llm(user_input)

            if self._analysis_complete():
                self.state = "confirming"
                return self._show_plan_overview()

            return response

        elif self.state == "confirming":
            # Show plan overview, get approval
            if user_input.lower() in ["yes", "y", "looks good", "approve"]:
                self.state = "generating"
                return await self._generate_plan()
            elif user_input.lower() == "no":
                return "What would you like to change?"
            else:
                response = await self.call_llm(user_input)
                return response

        elif self.state == "generating":
            # Plan generated, write file
            await self._write_plan()
            self.is_complete = True
            return "✅ Plan saved! Type 'exit' to return to chat."

    async def _generate_plan(self) -> str:
        """Generate detailed plan.md"""
        # Calls LLM to populate plan template
        prompt = self._build_plan_generation_prompt()
        plan_content = await self.call_llm(prompt)

        self.plan_content = plan_content
        return f"📋 Plan generated! Review:\n\n{plan_content[:500]}..."

    async def _write_plan(self):
        """Write plan.md to ticket folder"""
        plan_file = self.target_path / "plan.md"

        await self.execute_tool("write_file", {
            "file_path": str(plan_file),
            "content": self.plan_content
        })
```

**Tasks:**

- [ ] **Implement PlannerAgent core** (3h)
  - Spec loading and validation
  - State machine (analyze → confirm → generate)
  - Plan template integration

- [ ] **Implement codebase analysis** (3h)
  - Pattern detection with depth limits
  - Similar feature detection
  - Technology stack analysis
  - Respect max files/searches/time limits

- [ ] **Implement autonomous decisions** (2h)
  - Decision framework (when to ask vs decide)
  - Track decisions made
  - Generate 1-3 questions max

- [ ] **Implement plan generation** (2h)
  - Template population
  - Effort estimation
  - Step breakdown with validation criteria
  - Format as markdown

**Success Criteria:**
- ✅ Loads and parses spec.yaml
- ✅ Analyzes codebase within limits
- ✅ Makes autonomous decisions (90%+)
- ✅ Asks 1-3 clarifying questions only
- ✅ Generates detailed plan.md
- ✅ Respects analysis depth limits

---

#### **6.3 /plan Slash Command (2 hours)**

Similar to Socrates command implementation.

---

#### **6.4 Integration & Testing (3 hours)**

**Tasks:**

- [ ] **End-to-end test** (1h)
  ```bash
  /init
  /new feature user-auth
  /socrates feature-user-auth
  [Complete spec]
  /plan feature-user-auth
  [Review plan]
  [Verify plan.md written]
  ```

- [ ] **Unit tests** (1h)
  - Spec parsing
  - Codebase analysis limits
  - Decision tracking
  - Plan formatting

- [ ] **Documentation** (1h)
  - Update README
  - Add planning examples
  - Document effort estimation

---

#### **Week 6 Deliverables**

- ✅ PlannerAgent functional
- ✅ `/plan` command works
- ✅ Autonomous decision making (90%+)
- ✅ Codebase analysis with depth limits
- ✅ plan.md generation
- ✅ Tests passing
- ✅ Documentation updated

---

### **Week 7: Executor Agent (18-20 hours)**

**Goal:** Implement Executor agent for step-by-step code implementation

#### **7.1 Executor System Prompt (3 hours)**

**Create:** `src/cdd_agent/agents/prompts/executor.md`

**Port from CDD POC:** `.claude/commands/exec.md`

**Key sections:**
- Plan-driven execution
- Progress tracking (progress.yaml)
- Quality gates (Black, Ruff, pytest)
- Error handling (interactive resolution)
- Resumability

---

#### **7.2 ExecutorAgent Implementation (12 hours)**

**Create:** `src/cdd_agent/agents/executor.py`

```python
class ExecutorAgent(BaseAgent):
    """Step-by-step implementation specialist"""

    def __init__(self, provider, tools, target_path, session):
        super().__init__(provider, tools, target_path, session)

        # Executor-specific state
        self.plan = self._load_plan()
        self.progress = self._load_or_create_progress()
        self.current_step = None
        self.quality_checks_enabled = True

    def get_tool_schemas(self) -> list:
        """Executor has ALL tools"""
        return self.tools  # All 16 tools available

    def load_context(self) -> dict:
        """Load Executor context"""
        context = super().load_context()

        # Load spec + plan (both required)
        spec_file = self.target_path / "spec.yaml"
        plan_file = self.target_path / "plan.md"

        if not spec_file.exists():
            raise FileNotFoundError("spec.yaml not found")
        if not plan_file.exists():
            raise FileNotFoundError("plan.md not found")

        context["spec"] = spec_file.read_text()
        context["plan"] = plan_file.read_text()

        # Load progress if exists
        progress_file = self.target_path / "progress.yaml"
        if progress_file.exists():
            context["progress"] = progress_file.read_text()

        return context

    def initialize(self) -> str:
        """Executor introduction"""
        if self.progress.has_completed_steps():
            return f"""
🚀 Resuming implementation from progress.yaml...

**Completed steps:** {self.progress.completed_count()}
**Remaining steps:** {self.progress.pending_count()}

Starting from step {self.progress.next_step_id()}...
"""
        else:
            return f"""
🚀 Starting implementation from plan.md...

**Total steps:** {self.plan.total_steps()}
**Estimated time:** {self.plan.total_effort()}

Let's begin with step 1...
"""

    async def process(self, user_input: str) -> str:
        """Execute implementation steps"""

        # Step execution loop
        while not self._all_steps_complete():
            step = self._get_next_step()

            # Mark step in progress
            self.progress.mark_in_progress(step.id)
            self._save_progress()

            # Execute step
            await self._execute_step(step)

            # Run quality checks
            if self.quality_checks_enabled:
                checks_passed = await self._run_quality_checks(step)

                if not checks_passed:
                    # Prompt user for action
                    return self._prompt_error_resolution()

            # Mark complete
            self.progress.mark_complete(step.id)
            self._save_progress()

        # All steps complete - validate acceptance criteria
        await self._validate_acceptance_criteria()

        self.is_complete = True
        return self._completion_report()

    async def _execute_step(self, step):
        """Execute single implementation step"""
        # Call LLM with step context
        prompt = f"Execute: {step.description}\n\nExpected outcome: {step.expected_outcome}"

        await self.call_llm(prompt)

        # LLM will use tools (write_file, edit_file, bash, etc.)
        # Tools execute through approval system

    async def _run_quality_checks(self, step) -> bool:
        """Run Black, Ruff, pytest on modified files"""
        files_touched = self.progress.get_files_touched(step.id)

        # Black formatting
        black_result = await self.execute_tool("bash", {
            "command": f"black {' '.join(files_touched)}"
        })

        # Ruff linting
        ruff_result = await self.execute_tool("bash", {
            "command": f"ruff check {' '.join(files_touched)}"
        })

        # Pytest (if step involves tests)
        if step.involves_tests:
            pytest_result = await self.execute_tool("bash", {
                "command": "pytest -xvs"
            })

            if pytest_result.failed:
                return False

        return True
```

**Tasks:**

- [ ] **Implement ExecutorAgent core** (4h)
  - Load plan.md and parse steps
  - Progress tracking with progress.yaml
  - Step execution loop

- [ ] **Implement progress management** (3h)
  - `progress.yaml` schema
  - Load/save progress
  - Resume from incomplete state
  - Track files touched per step

- [ ] **Implement quality gates** (3h)
  - Black formatting integration
  - Ruff linting integration
  - Pytest execution
  - Error detection and reporting

- [ ] **Implement error handling** (2h)
  - Interactive error resolution prompts
  - Retry logic
  - Skip step option
  - Stop implementation option

**Success Criteria:**
- ✅ Executes plan steps sequentially
- ✅ Tracks progress in progress.yaml
- ✅ Runs quality checks after each step
- ✅ Handles errors interactively
- ✅ Resumes from saved progress
- ✅ Validates acceptance criteria

---

#### **7.3 /exec Slash Command (2 hours)**

Similar pattern to Socrates/Planner commands.

---

#### **7.4 Integration & Testing (3 hours)**

**Full workflow test:**
```bash
/init
/new feature user-auth
/socrates feature-user-auth
[Complete spec]
/plan feature-user-auth
[Generate plan]
/exec feature-user-auth
[Implement code]
[Verify all acceptance criteria met]
```

---

#### **Week 7 Deliverables**

- ✅ ExecutorAgent functional
- ✅ `/exec` command works
- ✅ Progress tracking with resumability
- ✅ Quality gates integrated
- ✅ Error handling works
- ✅ Full CDD workflow end-to-end
- ✅ Tests passing
- ✅ Documentation complete

---

### **Week 8: Utilities & Polish (10-12 hours)**

**Goal:** Add utility commands, error handling, and polish UX

#### **8.1 Utility Slash Commands (4 hours)**

**Implement:**

- [ ] **/status [ticket]** (2h)
  - Show ticket progress
  - Display completed/pending steps
  - Show acceptance criteria status
  - Estimate time remaining

- [ ] **/list** (1h)
  - List all tickets in specs/tickets/
  - Show status (empty/spec/plan/in-progress/done)
  - Filter by type (feature/bug/spike)

- [ ] **/resume [ticket]** (1h)
  - Resume incomplete ticket
  - Load last agent used
  - Continue from saved state

---

#### **8.2 Error Handling & Edge Cases (4 hours)**

**Improvements:**

- [ ] **Missing files handling** (1h)
  - CLAUDE.md missing → offer to create
  - Templates missing → suggest /init
  - spec.yaml missing → suggest /socrates

- [ ] **Invalid input handling** (1h)
  - Malformed ticket paths
  - Unknown ticket types
  - Empty arguments

- [ ] **Network/API errors** (1h)
  - LLM timeout handling
  - Rate limit errors
  - Retry with exponential backoff

- [ ] **File permission errors** (1h)
  - Read-only directories
  - Git conflicts
  - Concurrent access

---

#### **8.3 Documentation & Examples (4 hours)**

**Create:**

- [ ] **Complete README update** (2h)
  - Full workflow examples
  - Slash command reference
  - Troubleshooting guide

- [ ] **Tutorial/quickstart** (1h)
  - First project walkthrough
  - Common workflows
  - Best practices

- [ ] **Video/GIF demos** (1h)
  - Record workflow demos
  - Create animated GIFs
  - Upload to README

---

#### **Week 8 Deliverables**

- ✅ /status, /list, /resume commands
- ✅ Comprehensive error handling
- ✅ Complete documentation
- ✅ Demos and examples
- ✅ Ready for v0.2.0 release

---

## 🎯 Success Metrics

### **Week 4 Complete:**
- ✅ `/init` and `/new` work in chat
- ✅ Slash command router functional
- ✅ BaseAgent architecture ready
- ✅ Tests passing (>80% coverage)

### **Week 5 Complete:**
- ✅ `/socrates` creates complete specs
- ✅ Socratic dialogue works
- ✅ spec.yaml written correctly

### **Week 6 Complete:**
- ✅ `/plan` generates detailed plans
- ✅ Autonomous decision making
- ✅ plan.md follows template

### **Week 7 Complete:**
- ✅ `/exec` implements code
- ✅ Quality gates pass
- ✅ Progress tracked and resumable

### **Week 8 Complete:**
- ✅ Full CDD workflow functional
- ✅ Utility commands working
- ✅ Documentation complete
- ✅ Ready for production use

---

## 📊 Testing Strategy

### **Unit Tests** (src/cdd_agent/tests/)
- Mechanical layer functions
- Agent initialization
- Context loading
- Tool restrictions
- Progress management

### **Integration Tests**
- Full workflows (init → new → socrates → plan → exec)
- Agent switching
- File operations
- Error handling

### **Manual Testing Checklist**
- TUI displays correctly
- Slash commands autocomplete
- Agent mode switching smooth
- Error messages helpful
- Progress persists across sessions

---

## 🚀 Release Strategy

### **v0.2.0-alpha (End of Week 5)**
- `/init`, `/new`, `/socrates` functional
- Early adopter testing
- Gather feedback

### **v0.2.0-beta (End of Week 7)**
- Full workflow (init → socrates → plan → exec)
- Beta testing with community
- Bug fixes and polish

### **v0.2.0 (End of Week 8)**
- Production release
- Complete documentation
- PyPI publish
- Announcement

---

## 📝 Next Steps

**Immediate (This Session):**
1. Break down Week 4 into actionable tasks
2. Create task tracking (GitHub issues or TodoWrite)
3. Begin implementation of mechanical layer

**Week 4 Kickoff:**
1. Port `initialize_project()` from CDD POC
2. Port `create_new_ticket()` from CDD POC
3. Implement SlashCommandRouter
4. Integrate with chat session

---

**This roadmap represents ~75 hours of focused work over 8 weeks, delivering a complete CDD workflow system with chat-first UX and provider independence.**
