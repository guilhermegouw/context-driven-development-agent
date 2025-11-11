# Task 4: Chat Session Integration

**Status:** 🔜 Planning Complete, Ready to Implement
**Estimated Time:** 2-3 hours
**Dependencies:** Task 1 ✅, Task 2 ✅, Task 3 ✅
**Date:** 2025-11-09

---

## Objective

Create a `ChatSession` class that manages conversation state and enables agent switching, allowing users to seamlessly transition between general chat mode and specialized CDD agents (Socrates, Planner, Executor).

---

## Background

### Current State (After Tasks 1-3)
- ✅ Mechanical layer: `initialize_project()`, `create_new_ticket()`, `create_new_documentation()`
- ✅ Slash commands: `/init`, `/new`, `/help`
- ✅ Commands execute and return immediately

### Problem
We can create tickets and documentation, but we can't:
- Switch to specialized agents for ticket refinement (Socrates)
- Generate implementation plans (Planner)
- Execute autonomous coding (Executor)
- Maintain conversation state across agent transitions

### Solution
Create a session management layer that:
1. Tracks conversation state (general chat vs agent mode)
2. Manages agent lifecycle (activate, process, deactivate)
3. Handles transitions between modes
4. Provides context to agents (current ticket, project state)

---

## Architecture Design

### Component Structure

```
src/cdd_agent/
├── session/
│   ├── __init__.py          # Module exports
│   ├── chat_session.py      # Main ChatSession class
│   └── base_agent.py        # BaseAgent abstract class
├── agents/                  # Future: Specialized agents
│   ├── __init__.py
│   ├── socrates.py          # Week 5
│   ├── planner.py           # Week 6
│   └── executor.py          # Week 7
└── cli.py                   # [MODIFIED] Use ChatSession
```

### State Machine

```
┌─────────────────┐
│  General Chat   │ ←──────────────────┐
│   (no agent)    │                     │
└────────┬────────┘                     │
         │                              │
         │ /socrates <ticket>           │ exit
         │ /plan <ticket>               │
         │ /exec <ticket>               │
         │                              │
         ↓                              │
┌─────────────────┐                     │
│   Agent Mode    │                     │
│ (Socrates/      │────────────────────┘
│  Planner/       │
│  Executor)      │
└─────────────────┘
```

---

## Detailed Implementation Plan

### Step 1: Create BaseAgent Abstract Class (45 min)

**File:** `src/cdd_agent/session/base_agent.py`

**Purpose:** Abstract base class that all CDD agents inherit from.

**Interface:**
```python
from abc import ABC, abstractmethod
from typing import Optional
from pathlib import Path


class AgentError(Exception):
    """Raised when agent operations fail."""
    pass


class BaseAgent(ABC):
    """Base class for all CDD agents (Socrates, Planner, Executor).

    Lifecycle:
    1. __init__() - Create agent instance
    2. initialize() - Called when agent activates (returns greeting)
    3. process() - Called for each user message
    4. is_done() - Check if agent has completed its task
    5. finalize() - Called when agent deactivates (returns summary)
    """

    def __init__(
        self,
        target_path: Path,
        session: "ChatSession",
        provider_config,
        tool_registry,
    ):
        """Initialize agent.

        Args:
            target_path: Path to ticket/doc being worked on
            session: Parent ChatSession instance
            provider_config: LLM provider configuration
            tool_registry: Available tools for agent
        """
        self.target_path = target_path
        self.session = session
        self.provider_config = provider_config
        self.tool_registry = tool_registry

        # Agent state
        self.conversation_history = []
        self._is_complete = False

        # Agent metadata
        self.name: str = ""  # e.g., "Socrates", "Planner"
        self.description: str = ""  # e.g., "Refine ticket requirements"
        self.prompt_template: str = ""  # System prompt for agent

    @abstractmethod
    def initialize(self) -> str:
        """Called when agent is activated.

        Returns:
            Initial greeting message to display

        Example:
            "Hello! I'm Socrates. Let's refine your ticket requirements."
        """
        pass

    @abstractmethod
    async def process(self, user_input: str) -> str:
        """Process user message while agent is active.

        Args:
            user_input: User's message

        Returns:
            Agent's response
        """
        pass

    def is_done(self) -> bool:
        """Check if agent has completed its task.

        Returns:
            True if agent should exit automatically
        """
        return self._is_complete

    def finalize(self) -> str:
        """Called when agent is deactivated.

        Returns:
            Completion summary message

        Example:
            "✅ Specification updated: specs/tickets/feature-auth/spec.yaml"
        """
        return f"✅ {self.name} completed"

    def mark_complete(self):
        """Mark agent as complete (will exit automatically)."""
        self._is_complete = True

    def load_target(self) -> dict:
        """Load target file (ticket spec, doc, etc.).

        Returns:
            Parsed content (YAML or markdown)

        Raises:
            AgentError: If target file not found or invalid
        """
        if not self.target_path.exists():
            raise AgentError(f"Target not found: {self.target_path}")

        # Implementation depends on file type
        # For now, just read as text
        return {"content": self.target_path.read_text()}

    def save_target(self, content: str):
        """Save changes to target file.

        Args:
            content: Updated content to write
        """
        self.target_path.write_text(content)
```

**Key Design Decisions:**
- Lifecycle methods mirror slash command pattern (initialize/process/finalize)
- `is_done()` allows agents to auto-exit when task complete
- `target_path` gives agent context (which ticket/doc they're working on)
- Access to session allows agents to reference project state

---

### Step 2: Create ChatSession Class (60 min)

**File:** `src/cdd_agent/session/chat_session.py`

**Purpose:** Manage conversation state and agent switching.

**Implementation:**
```python
from typing import Optional, Type
from pathlib import Path

from rich.console import Console

from .base_agent import BaseAgent
from ..slash_commands import get_router, setup_commands

console = Console()


class ChatSession:
    """Manages chat conversation with agent switching.

    Modes:
    - General chat: User talks to LLM with tools (no specialized agent)
    - Agent mode: Specialized agent (Socrates/Planner/Executor) takes over

    Usage:
        session = ChatSession(agent, provider_config, tool_registry)

        # In chat loop
        result = await session.process_input(user_input)
        console.print(result)
    """

    def __init__(self, agent, provider_config, tool_registry):
        """Initialize chat session.

        Args:
            agent: General-purpose Agent instance (for non-agent mode)
            provider_config: LLM provider configuration
            tool_registry: Available tools
        """
        self.general_agent = agent  # For regular chat (existing Agent class)
        self.provider_config = provider_config
        self.tool_registry = tool_registry

        # Agent management
        self.current_agent: Optional[BaseAgent] = None  # Active CDD agent
        self.slash_router = get_router()

        # Initialize slash commands if needed
        if not self.slash_router._commands:
            setup_commands(self.slash_router)

        # Session state
        self.context = None  # Loaded from CDD.md (future)
        self.current_ticket = None  # Track active ticket

    def is_in_agent_mode(self) -> bool:
        """Check if a specialized agent is active.

        Returns:
            True if Socrates/Planner/Executor is active
        """
        return self.current_agent is not None

    def get_current_agent_name(self) -> Optional[str]:
        """Get name of active agent.

        Returns:
            Agent name or None if in general chat
        """
        if self.current_agent:
            return self.current_agent.name
        return None

    def switch_to_agent(
        self,
        agent_class: Type[BaseAgent],
        target_path: Path,
    ) -> str:
        """Switch from general chat to specialized agent.

        Args:
            agent_class: Agent class to instantiate (SocratesAgent, etc.)
            target_path: Path to ticket/doc to work on

        Returns:
            Agent's initial greeting message

        Raises:
            RuntimeError: If already in agent mode
        """
        if self.current_agent:
            raise RuntimeError(
                f"Already in {self.current_agent.name} mode. "
                f"Type 'exit' to leave agent mode first."
            )

        # Create agent instance
        self.current_agent = agent_class(
            target_path=target_path,
            session=self,
            provider_config=self.provider_config,
            tool_registry=self.tool_registry,
        )

        # Track current ticket
        self.current_ticket = target_path

        # Get agent's initial message
        greeting = self.current_agent.initialize()

        return f"\n[bold cyan]──── Entering {self.current_agent.name} Mode ────[/bold cyan]\n\n{greeting}"

    def exit_agent(self) -> str:
        """Return from agent mode to general chat.

        Returns:
            Agent's completion message

        Raises:
            RuntimeError: If not in agent mode
        """
        if not self.current_agent:
            raise RuntimeError("Not in agent mode")

        # Get agent's final message
        completion = self.current_agent.finalize()
        agent_name = self.current_agent.name

        # Clear agent
        self.current_agent = None
        self.current_ticket = None

        return (
            f"{completion}\n\n"
            f"[bold cyan]──── Exiting {agent_name} Mode ────[/bold cyan]\n\n"
            f"Back in general chat. Type /help to see available commands."
        )

    async def process_input(self, user_input: str) -> tuple[str, bool]:
        """Process user input (main entry point).

        Args:
            user_input: User's message

        Returns:
            Tuple of (response_message, should_exit_session)

        Flow:
        1. Check for exit command (if in agent mode)
        2. Check for slash command
        3. Route to active agent or general chat
        """
        user_input = user_input.strip()

        # Handle exit command (only in agent mode)
        if user_input.lower() in ["exit", "quit"] and self.current_agent:
            response = self.exit_agent()
            return response, False

        # Check for slash command
        if self.slash_router.is_slash_command(user_input):
            try:
                response = await self.slash_router.execute(user_input)

                # Check if command switched to agent mode
                # (Future: commands like /socrates will call switch_to_agent)

                return response, False

            except Exception as e:
                return f"[red]Error executing command: {e}[/red]", False

        # Route to active agent or general chat
        if self.current_agent:
            # Agent mode - send to specialized agent
            response = await self.current_agent.process(user_input)

            # Check if agent completed automatically
            if self.current_agent.is_done():
                completion = self.exit_agent()
                response = f"{response}\n\n{completion}"

            return response, False

        else:
            # General chat mode - this will be handled by caller
            # Return indicator that general agent should process
            return None, False

    def get_status(self) -> dict:
        """Get current session status.

        Returns:
            Status dictionary with mode, agent, ticket info
        """
        return {
            "mode": "agent" if self.current_agent else "general",
            "agent_name": self.get_current_agent_name(),
            "current_ticket": str(self.current_ticket) if self.current_ticket else None,
        }
```

**Key Features:**
- Clean separation: general chat vs agent mode
- Agent lifecycle management (activate, process, deactivate)
- Exit handling with proper cleanup
- Status tracking for UI integration

---

### Step 3: Create Module Initialization (10 min)

**File:** `src/cdd_agent/session/__init__.py`

```python
"""Session management for CDD Agent.

This module provides conversation state management and agent switching:
- ChatSession: Manages conversation and agent transitions
- BaseAgent: Abstract base for specialized agents (Socrates, Planner, Executor)

Usage:
    from cdd_agent.session import ChatSession

    session = ChatSession(agent, provider_config, tool_registry)
    response, should_exit = await session.process_input(user_input)
"""

from .base_agent import BaseAgent, AgentError
from .chat_session import ChatSession

__all__ = [
    "ChatSession",
    "BaseAgent",
    "AgentError",
]
```

---

### Step 4: Integrate with CLI (30 min)

**File:** `src/cdd_agent/cli.py` (MODIFIED)

**Changes Required:**

1. **Import ChatSession:**
```python
from .session import ChatSession
```

2. **Modify `_run_interactive_chat()` to use ChatSession:**
```python
def _run_interactive_chat(agent: "Agent", ui: "StreamingUI", system: str, no_stream: bool):
    """Run interactive chat loop with session management.

    Args:
        agent: General-purpose Agent instance
        ui: UI instance
        system: System prompt
        no_stream: Whether to disable streaming
    """
    from .session import ChatSession
    from rich.markdown import Markdown

    # Create chat session
    session = ChatSession(
        agent=agent,
        provider_config=agent.provider_config,
        tool_registry=agent.tool_registry,
    )

    _get_console().print("[dim]Type /help for commands, 'exit' to leave agent mode, Ctrl+D to quit[/dim]\n")

    while True:
        try:
            # Show prompt (indicate agent mode if active)
            if session.is_in_agent_mode():
                agent_name = session.get_current_agent_name()
                ui.show_prompt(f"[{agent_name}]>")
            else:
                ui.show_prompt(">")

            # Get user input
            user_input = input()

            # Handle empty input
            if not user_input.strip():
                continue

            # Process through session
            import asyncio
            response, should_exit = asyncio.run(session.process_input(user_input))

            # If response is None, it's general chat - use existing agent
            if response is None:
                _get_console().print()  # Blank line before response

                if no_stream:
                    response = agent.run(user_input, system_prompt=system)
                    _get_console().print(Markdown(response))
                else:
                    event_stream = agent.stream(user_input, system_prompt=system)
                    ui.stream_response(event_stream)

                _get_console().print()  # Blank line after response
            else:
                # Slash command or agent response
                _get_console().print()
                _get_console().print(Markdown(response))
                _get_console().print()

        except KeyboardInterrupt:
            _get_console().print("\n[dim]Use 'exit' to leave agent mode or Ctrl+D to quit[/dim]")
            continue
        except EOFError:
            break
```

**Key Changes:**
- Wrap Agent in ChatSession
- Show agent name in prompt when in agent mode
- Route through session.process_input()
- Handle None response (general chat fallback)

---

### Step 5: Create Stub Agent for Testing (15 min)

**File:** `src/cdd_agent/agents/__init__.py`

```python
"""Specialized CDD agents.

Agents:
- SocratesAgent (Week 5): Refine ticket requirements through dialogue
- PlannerAgent (Week 6): Generate implementation plans
- ExecutorAgent (Week 7): Execute autonomous coding

For Week 4, we create a TestAgent for integration testing.
"""

# Future exports (Week 5-7)
# from .socrates import SocratesAgent
# from .planner import PlannerAgent
# from .executor import ExecutorAgent

__all__ = []
```

**File:** `src/cdd_agent/agents/test_agent.py` (for testing)

```python
"""Test agent for integration testing."""

from pathlib import Path

from ..session.base_agent import BaseAgent


class TestAgent(BaseAgent):
    """Simple test agent for validating session integration."""

    def __init__(self, target_path: Path, session, provider_config, tool_registry):
        super().__init__(target_path, session, provider_config, tool_registry)
        self.name = "TestAgent"
        self.description = "Simple test agent"
        self.message_count = 0

    def initialize(self) -> str:
        """Return greeting."""
        return (
            f"Hello! I'm {self.name}. I'm working on: {self.target_path}\n\n"
            f"Send me 3 messages, then I'll automatically exit.\n"
            f"Or type 'exit' to leave early."
        )

    async def process(self, user_input: str) -> str:
        """Echo user input and count messages."""
        self.message_count += 1

        response = f"[Message {self.message_count}/3] You said: {user_input}"

        # Auto-complete after 3 messages
        if self.message_count >= 3:
            self.mark_complete()
            response += "\n\n✅ Mission accomplished! Exiting..."

        return response

    def finalize(self) -> str:
        """Return completion message."""
        return (
            f"✅ {self.name} processed {self.message_count} messages.\n"
            f"Target file: {self.target_path}"
        )
```

---

## Testing Strategy

### Unit Tests

**File:** `test_chat_session.py`

**Test Coverage:**

1. **ChatSession Tests (8 tests)**
   - ✅ Session initialization
   - ✅ Agent mode detection
   - ✅ Switch to agent (activation)
   - ✅ Exit agent (deactivation)
   - ✅ Process input in general mode
   - ✅ Process input in agent mode
   - ✅ Exit command handling
   - ✅ Status reporting

2. **BaseAgent Tests (5 tests)**
   - ✅ Agent initialization
   - ✅ Lifecycle methods (initialize, process, finalize)
   - ✅ Auto-completion (is_done)
   - ✅ Target file loading
   - ✅ TestAgent behavior

3. **Integration Tests (4 tests)**
   - ✅ Full flow: general → agent → exit → general
   - ✅ Slash commands work in both modes
   - ✅ Auto-exit when agent completes
   - ✅ Error handling (switch while in agent mode)

---

## Success Criteria

- ✅ `ChatSession` manages conversation state
- ✅ `BaseAgent` provides clean interface for future agents
- ✅ Agent switching works (activate/deactivate)
- ✅ `exit` command returns from agent mode
- ✅ Slash commands continue to work
- ✅ Session state persists across commands
- ✅ UI shows agent mode in prompt
- ✅ All tests pass
- ✅ Quality checks pass (Black, Ruff)

---

## Files to Create/Modify

### New Files (5)
1. `src/cdd_agent/session/__init__.py`
2. `src/cdd_agent/session/base_agent.py`
3. `src/cdd_agent/session/chat_session.py`
4. `src/cdd_agent/agents/__init__.py`
5. `src/cdd_agent/agents/test_agent.py` (for testing)
6. `test_chat_session.py` (test suite)

### Modified Files (1)
1. `src/cdd_agent/cli.py` (integrate ChatSession)

---

## Estimated Timeline

| Step | Task | Time |
|------|------|------|
| 1 | Create BaseAgent class | 45 min |
| 2 | Create ChatSession class | 60 min |
| 3 | Create module __init__.py | 10 min |
| 4 | Integrate with CLI | 30 min |
| 5 | Create test agent | 15 min |
| 6 | Write test suite | 30 min |
| 7 | Run tests and quality checks | 15 min |
| 8 | Documentation | 15 min |
| **Total** | | **~3 hours** |

---

## Next Steps After Task 4

With session management complete:
- ✅ Task 1-3: Mechanical layer and slash commands
- ✅ Task 4: Session management (this task)
- 🔜 **Week 5:** Implement SocratesAgent
  - Ticket refinement through Socratic dialogue
  - `/socrates <ticket>` command
- 🔜 **Week 6:** Implement PlannerAgent
  - Implementation plan generation
  - `/plan <ticket>` command
- 🔜 **Week 7:** Implement ExecutorAgent
  - Autonomous code execution
  - `/exec <ticket>` command

---

**Task 4 Status:** 🔜 **READY TO IMPLEMENT**

Plan approved and documented. Ready to begin implementation.
