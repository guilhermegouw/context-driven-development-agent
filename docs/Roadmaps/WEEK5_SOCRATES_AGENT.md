# Week 5: Socrates Agent Implementation

**Status:** 🔜 Planning Complete, Ready to Implement
**Estimated Time:** 6-8 hours
**Dependencies:** Tasks 1-4 ✅
**Date:** 2025-11-09

---

## Objective

Implement the **Socrates Agent** - a specialized agent that refines ticket specifications through Socratic dialogue, asking clarifying questions to uncover requirements, edge cases, and implementation details.

---

## Background

### The Socratic Method

Socrates refined thinking through questions, not answers. The Socrates Agent applies this method to software specifications:

**Traditional approach:**
```
User: "Build a login feature"
AI: "I'll build a login feature with email and password"
→ Missing: OAuth? 2FA? Password reset? Session duration? etc.
```

**Socratic approach:**
```
User: "Build a login feature"
Socrates: "What authentication methods should we support?"
User: "Email and password for now"
Socrates: "Should we plan for OAuth integration later?"
User: "Yes, Google and GitHub"
Socrates: "What about password requirements? Length, complexity?"
User: "Minimum 8 characters, one number, one special char"
...
```

Result: Complete, well-thought-out specification before writing code.

---

## Architecture Design

### Component Structure

```
src/cdd_agent/
├── agents/
│   ├── __init__.py          # [MODIFIED] Export SocratesAgent
│   ├── test_agent.py        # ✅ Already exists
│   └── socrates.py          # NEW - Socrates implementation
├── slash_commands/
│   ├── __init__.py          # [MODIFIED] Register SocratesCommand
│   ├── socrates_command.py  # NEW - /socrates handler
│   └── ...
└── utils/                   # NEW - Shared utilities
    ├── __init__.py
    └── yaml_parser.py       # YAML spec parsing
```

---

## Detailed Implementation Plan

### Step 1: Create YAML Parser Utility (30 min)

**File:** `src/cdd_agent/utils/yaml_parser.py`

**Purpose:** Parse and update ticket spec.yaml files.

**Implementation:**
```python
"""YAML parsing utilities for ticket specifications."""

from pathlib import Path
from typing import Any, Dict
import yaml


class SpecParseError(Exception):
    """Raised when spec.yaml cannot be parsed."""
    pass


def load_spec(spec_path: Path) -> Dict[str, Any]:
    """Load ticket specification from YAML file.

    Args:
        spec_path: Path to spec.yaml

    Returns:
        Parsed specification dictionary

    Raises:
        SpecParseError: If file not found or invalid YAML
    """
    if not spec_path.exists():
        raise SpecParseError(f"Spec not found: {spec_path}")

    try:
        with open(spec_path, 'r') as f:
            spec = yaml.safe_load(f)

        if not isinstance(spec, dict):
            raise SpecParseError("Spec must be a YAML dictionary")

        return spec

    except yaml.YAMLError as e:
        raise SpecParseError(f"Invalid YAML: {e}")


def save_spec(spec_path: Path, spec: Dict[str, Any]):
    """Save ticket specification to YAML file.

    Args:
        spec_path: Path to spec.yaml
        spec: Specification dictionary to save
    """
    with open(spec_path, 'w') as f:
        yaml.dump(spec, f, default_flow_style=False, sort_keys=False)


def get_spec_field(spec: Dict[str, Any], field: str, default: Any = None) -> Any:
    """Get field from spec with default value.

    Args:
        spec: Specification dictionary
        field: Field name (supports nested: "metadata.status")
        default: Default value if field not found

    Returns:
        Field value or default
    """
    keys = field.split('.')
    value = spec

    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default

    return value


def set_spec_field(spec: Dict[str, Any], field: str, value: Any):
    """Set field in spec (creates nested dicts as needed).

    Args:
        spec: Specification dictionary
        field: Field name (supports nested: "metadata.status")
        value: Value to set
    """
    keys = field.split('.')
    current = spec

    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]

    current[keys[-1]] = value
```

---

### Step 2: Implement SocratesAgent (3 hours)

**File:** `src/cdd_agent/agents/socrates.py`

**Purpose:** Socratic dialogue agent for ticket refinement.

**Key Features:**
- Analyzes current spec state
- Asks targeted questions to fill gaps
- Updates spec based on responses
- Tracks progress (questions asked, fields refined)
- Auto-exits when spec is complete

**Implementation:**
```python
"""Socrates Agent - Refine ticket specifications through dialogue."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from ..session.base_agent import BaseAgent, AgentError
from ..utils.yaml_parser import load_spec, save_spec, get_spec_field, set_spec_field


class SocratesAgent(BaseAgent):
    """Refines ticket specifications through Socratic dialogue.

    The Socrates Agent:
    1. Analyzes the current ticket specification
    2. Identifies gaps, ambiguities, and missing details
    3. Asks clarifying questions (one at a time)
    4. Updates the spec based on user responses
    5. Continues until specification is complete

    Philosophy:
    - Ask questions, don't make assumptions
    - One question at a time (focused dialogue)
    - Build understanding progressively
    - Uncover edge cases and requirements
    """

    def __init__(self, target_path: Path, session, provider_config, tool_registry):
        """Initialize Socrates Agent."""
        super().__init__(target_path, session, provider_config, tool_registry)
        self.name = "Socrates"
        self.description = "Refine ticket requirements through dialogue"

        # Conversation state
        self.spec: Optional[Dict[str, Any]] = None
        self.questions_asked: List[str] = []
        self.current_focus: str = "overview"  # overview, requirements, edge_cases, etc.

        # Progress tracking
        self.refinement_areas = [
            "overview",
            "requirements",
            "acceptance_criteria",
            "edge_cases",
            "technical_notes",
        ]
        self.current_area_index = 0

    def initialize(self) -> str:
        """Greet user and start refinement."""
        try:
            # Load spec
            self.spec = load_spec(self.target_path)

            ticket_id = get_spec_field(self.spec, "metadata.ticket_id", "unknown")
            ticket_type = get_spec_field(self.spec, "metadata.ticket_type", "unknown")

            return (
                f"Hello! I'm **{self.name}**, here to help refine your ticket.\n\n"
                f"**Ticket:** `{ticket_id}`\n"
                f"**Type:** `{ticket_type}`\n\n"
                f"I'll ask questions to understand your requirements fully. "
                f"Let's explore this together through dialogue.\n\n"
                f"**Current specification:**\n"
                f"```yaml\n{self._format_spec_preview()}\n```\n\n"
                f"Let's start with the big picture. "
                f"{self._generate_next_question()}"
            )

        except Exception as e:
            raise AgentError(f"Failed to load spec: {e}")

    async def process(self, user_input: str) -> str:
        """Process user response and ask next question.

        Args:
            user_input: User's answer to previous question

        Returns:
            Next question or completion message
        """
        # Record the conversation
        self.conversation_history.append({
            "question": self.questions_asked[-1] if self.questions_asked else None,
            "answer": user_input,
        })

        # Update spec based on response
        self._update_spec_from_response(user_input)

        # Save progress
        save_spec(self.target_path, self.spec)

        # Check if current area is complete
        if self._is_current_area_complete():
            self.current_area_index += 1

            # Check if all areas complete
            if self.current_area_index >= len(self.refinement_areas):
                self.mark_complete()
                return (
                    f"✅ Excellent! I believe we have a solid specification now.\n\n"
                    f"**Summary of refinements:**\n"
                    f"- Questions asked: {len(self.questions_asked)}\n"
                    f"- Areas covered: {', '.join(self.refinement_areas)}\n\n"
                    f"The specification has been updated. "
                    f"You can now use `/plan` to generate an implementation plan."
                )

        # Generate next question
        next_question = self._generate_next_question()

        return (
            f"Great! I've updated the spec.\n\n"
            f"**Next question:** {next_question}"
        )

    def finalize(self) -> str:
        """Return completion summary."""
        return (
            f"✅ **Specification refined: `{self.target_path}`**\n\n"
            f"- Total questions: {len(self.questions_asked)}\n"
            f"- Refinement areas covered: {len(self.refinement_areas)}\n\n"
            f"The ticket is ready for planning. Use `/plan` to continue."
        )

    def _format_spec_preview(self) -> str:
        """Format spec for display (abbreviated)."""
        if not self.spec:
            return "No spec loaded"

        # Show key fields only
        preview = {
            "metadata": get_spec_field(self.spec, "metadata", {}),
            "description": get_spec_field(self.spec, "description", ""),
        }

        import yaml
        return yaml.dump(preview, default_flow_style=False)[:200] + "..."

    def _generate_next_question(self) -> str:
        """Generate the next clarifying question based on spec state."""
        current_area = self.refinement_areas[self.current_area_index]

        # Simple question generation (could be enhanced with LLM)
        if current_area == "overview":
            q = "What is the primary goal of this feature? What problem does it solve?"

        elif current_area == "requirements":
            q = "What are the must-have requirements? What should users be able to do?"

        elif current_area == "acceptance_criteria":
            q = "How will we know this is done correctly? What defines success?"

        elif current_area == "edge_cases":
            q = "What edge cases should we consider? What could go wrong?"

        elif current_area == "technical_notes":
            q = "Any technical constraints or preferences? (libraries, patterns, etc.)"

        else:
            q = "Anything else we should consider?"

        self.questions_asked.append(q)
        self.current_focus = current_area

        return q

    def _update_spec_from_response(self, response: str):
        """Update spec based on user response to current question."""
        # Simple implementation: append to current area
        current_area = self.current_focus

        # Get existing content
        existing = get_spec_field(self.spec, current_area, "")

        # Append new content
        if existing:
            updated = f"{existing}\n\n{response}"
        else:
            updated = response

        # Save to spec
        set_spec_field(self.spec, current_area, updated)

    def _is_current_area_complete(self) -> bool:
        """Check if current refinement area has enough detail."""
        # Simple heuristic: ask 1 question per area
        # In production, would use LLM to determine completeness
        return len(self.conversation_history) >= self.current_area_index + 1
```

---

### Step 3: Create /socrates Slash Command (45 min)

**File:** `src/cdd_agent/slash_commands/socrates_command.py`

**Purpose:** Handler for `/socrates` command.

**Implementation:**
```python
"""Socrates slash command - Refine ticket specifications."""

from pathlib import Path

from .base import BaseSlashCommand, CommandError


class SocratesCommand(BaseSlashCommand):
    """Refine ticket specification through Socratic dialogue.

    Usage:
        /socrates <ticket>
        /socrates feature-user-auth
        /socrates bug-login-error
    """

    def __init__(self):
        """Initialize command metadata."""
        super().__init__()
        self.name = "socrates"
        self.description = "Refine ticket through Socratic dialogue"
        self.usage = "<ticket>"
        self.examples = [
            "/socrates feature-user-auth",
            "/socrates bug-login-error",
            "/socrates spike-database-research",
        ]

    def validate_args(self, args: str) -> bool:
        """Validate arguments (ticket name required)."""
        return bool(args.strip())

    async def execute(self, args: str) -> str:
        """Execute Socrates refinement.

        Args:
            args: Ticket name (e.g., "feature-user-auth")

        Returns:
            Agent activation message (switches to Socrates mode)
        """
        from ..agents.socrates import SocratesAgent
        from ..session import ChatSession

        ticket_name = args.strip()

        # Find ticket spec file
        # Try with and without type prefix
        possible_paths = [
            Path(f"specs/tickets/{ticket_name}/spec.yaml"),
            Path(f"specs/tickets/feature-{ticket_name}/spec.yaml"),
            Path(f"specs/tickets/bug-{ticket_name}/spec.yaml"),
            Path(f"specs/tickets/spike-{ticket_name}/spec.yaml"),
            Path(f"specs/tickets/enhancement-{ticket_name}/spec.yaml"),
        ]

        target_path = None
        for path in possible_paths:
            if path.exists():
                target_path = path
                break

        if not target_path:
            return (
                f"❌ Ticket not found: `{ticket_name}`\n\n"
                f"**Searched locations:**\n"
                + "\n".join(f"  - {p}" for p in possible_paths) +
                f"\n\nCreate a ticket first using `/new ticket <type> <name>`"
            )

        # Get session from context (passed during setup)
        # For now, return instruction message
        # In practice, this would call session.switch_to_agent()

        return (
            f"🎭 **Starting Socratic dialogue for:** `{target_path}`\n\n"
            f"*Note: This command will switch to Socrates agent mode.*\n"
            f"*(Integration pending - requires session context)*"
        )
```

---

### Step 4: Register Command and Agent (15 min)

**Modify:** `src/cdd_agent/slash_commands/__init__.py`

```python
# Add import
from .socrates_command import SocratesCommand

# Update setup_commands()
def setup_commands(router: SlashCommandRouter) -> None:
    # ... existing commands ...
    router.register(SocratesCommand())
```

**Modify:** `src/cdd_agent/agents/__init__.py`

```python
from .test_agent import TestAgent
from .socrates import SocratesAgent

__all__ = [
    "TestAgent",
    "SocratesAgent",
]
```

---

### Step 5: Enable Session Context in Commands (30 min)

**Challenge:** Slash commands need access to ChatSession to call `switch_to_agent()`.

**Solution:** Pass session during command initialization.

**Modify:** `src/cdd_agent/slash_commands/base.py`

```python
class BaseSlashCommand(ABC):
    def __init__(self, session=None):
        # ... existing code ...
        self.session = session  # NEW: Reference to ChatSession
```

**Modify:** `src/cdd_agent/session/chat_session.py`

```python
def __init__(self, agent, provider_config, tool_registry):
    # ... existing code ...

    # Initialize slash commands WITH session context
    if not self.slash_router._commands:
        from ..slash_commands import setup_commands_with_session
        setup_commands_with_session(self.slash_router, self)
```

**Update:** `src/cdd_agent/slash_commands/__init__.py`

```python
def setup_commands_with_session(router: SlashCommandRouter, session) -> None:
    """Register commands with session context."""
    router.register(InitCommand())
    router.register(NewCommand())
    router.register(HelpCommand())
    router.register(SocratesCommand(session))  # Pass session
```

**Update:** `src/cdd_agent/slash_commands/socrates_command.py`

```python
class SocratesCommand(BaseSlashCommand):
    def __init__(self, session=None):
        super().__init__(session)
        # ... metadata ...

    async def execute(self, args: str) -> str:
        # ... find ticket ...

        if not self.session:
            raise CommandError("Session not available")

        # Switch to Socrates agent
        from ..agents.socrates import SocratesAgent
        greeting = self.session.switch_to_agent(SocratesAgent, target_path)
        return greeting
```

---

## Testing Strategy

### Unit Tests

**File:** `test_socrates_agent.py`

**Test Coverage:**

1. **YAML Parser Tests (5 tests)**
   - ✅ Load valid spec
   - ✅ Handle missing file
   - ✅ Handle invalid YAML
   - ✅ Get/set nested fields
   - ✅ Save spec

2. **SocratesAgent Tests (8 tests)**
   - ✅ Initialization with valid spec
   - ✅ Generate first question
   - ✅ Process user response
   - ✅ Update spec fields
   - ✅ Progress through refinement areas
   - ✅ Auto-complete when done
   - ✅ Finalize message
   - ✅ Handle malformed spec

3. **SocratesCommand Tests (4 tests)**
   - ✅ Find ticket by name
   - ✅ Find ticket with type prefix
   - ✅ Error on missing ticket
   - ✅ Switch to agent mode

4. **Integration Test (1 test)**
   - ✅ Full workflow: create ticket → /socrates → dialogue → refined spec

---

## Success Criteria

- ✅ SocratesAgent asks relevant questions
- ✅ Spec is updated based on responses
- ✅ `/socrates <ticket>` switches to agent mode
- ✅ Agent auto-exits when refinement complete
- ✅ User can type 'exit' to leave early
- ✅ Refined spec is saved to spec.yaml
- ✅ All tests pass
- ✅ Quality checks pass (Black, Ruff)

---

## Example Session

```bash
> /new ticket feature User Authentication
✅ Created: specs/tickets/feature-user-authentication/spec.yaml

> /socrates feature-user-authentication

──── Entering Socrates Mode ────

Hello! I'm Socrates, here to help refine your ticket.

Ticket: `feature-user-authentication`
Type: `feature`

Current specification:
```yaml
metadata:
  ticket_id: feature-user-authentication
  ticket_type: feature
  status: draft
description: ""
...
```

I'll ask questions to understand your requirements fully.

Let's start with the big picture. What is the primary goal of this feature?
What problem does it solve?

[Socrates]> Users need to securely log in to access their accounts

Great! I've updated the spec.

Next question: What authentication methods should we support?
(Email/password, OAuth, SSO, etc.)?

[Socrates]> Email and password initially, but design for OAuth later

Excellent. I've noted that.

Next question: What are the password requirements?
(Length, complexity, special characters?)

[Socrates]> Minimum 8 characters, one uppercase, one number, one special character

Perfect. Moving on.

Next question: How will we know this is done correctly?
What defines a successful login?

[Socrates]> User provides correct credentials and receives a session token valid for 24 hours

Great insight!

Next question: What edge cases should we consider?
(Failed attempts, account lockout, expired sessions?)

[Socrates]> Lock account after 5 failed attempts, send password reset email

Excellent! I believe we have a solid specification now.

Summary of refinements:
- Questions asked: 5
- Areas covered: overview, requirements, acceptance_criteria, edge_cases, technical_notes

The specification has been updated. You can now use `/plan` to generate
an implementation plan.

✅ Specification refined: `specs/tickets/feature-user-authentication/spec.yaml`

──── Exiting Socrates Mode ────

Back in general chat.

> /plan feature-user-authentication
(Planner agent - Week 6)
```

---

## Estimated Timeline

| Step | Task | Time |
|------|------|------|
| 1 | YAML parser utility | 30 min |
| 2 | SocratesAgent implementation | 3 hours |
| 3 | /socrates slash command | 45 min |
| 4 | Register command and agent | 15 min |
| 5 | Session context integration | 30 min |
| 6 | Write test suite | 2 hours |
| 7 | Run tests and quality checks | 30 min |
| 8 | Documentation | 30 min |
| **Total** | | **~8 hours** |

---

## Future Enhancements (Not in Scope for Week 5)

1. **LLM-powered question generation** - Use LLM to analyze spec and generate targeted questions
2. **Smart completion detection** - Use LLM to determine when spec is complete
3. **Multiple question styles** - Open-ended, multiple choice, yes/no
4. **Spec validation** - Check for completeness, ambiguity, conflicts
5. **Resume capability** - Continue refinement from where it left off

---

**Week 5 Status:** 🔜 **READY TO IMPLEMENT**

Plan approved and documented. Ready to begin implementation.
