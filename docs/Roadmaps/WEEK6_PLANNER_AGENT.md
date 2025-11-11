# Week 6: Planner Agent - Implementation Plan

**Objective:** Implement the Planner Agent that generates detailed implementation plans from refined ticket specifications.

**Status:** 📋 Planning Phase
**Estimated Time:** ~6 hours
**Dependencies:** Week 5 (Socrates Agent, YAML parser)

---

## Background

The Planner Agent is the second agent in the CDD workflow:

```
Spec → Plan → Execute

Week 5: Socrates refines specs
Week 6: Planner generates implementation plans ← WE ARE HERE
Week 7: Executor implements the code
```

The Planner Agent:
1. Reads a refined ticket spec (output of Socrates)
2. Analyzes requirements and context
3. Generates a step-by-step implementation plan
4. Estimates complexity and identifies dependencies
5. Saves plan.md in the ticket directory
6. Auto-exits when plan is complete

---

## Implementation Plan

### Step 1: Create Plan Data Model (30 min)

**File:** `src/cdd_agent/utils/plan_model.py`

Create data structures for implementation plans:

```python
@dataclass
class PlanStep:
    """Single implementation step."""
    number: int
    title: str
    description: str
    complexity: str  # "simple", "medium", "complex"
    estimated_time: str  # "15 min", "1 hour", "2 hours"
    dependencies: list[int]  # Step numbers this depends on
    files_affected: list[str]  # Expected files to change

@dataclass
class ImplementationPlan:
    """Complete implementation plan."""
    ticket_slug: str
    ticket_title: str
    ticket_type: str
    overview: str  # High-level approach
    steps: list[PlanStep]
    total_complexity: str  # Overall: simple/medium/complex
    total_estimated_time: str  # "4 hours", "1 day"
    risks: list[str]  # Potential risks/challenges

    def to_markdown(self) -> str:
        """Convert plan to markdown format."""
        # Generate formatted plan.md content

    @classmethod
    def from_markdown(cls, content: str) -> "ImplementationPlan":
        """Parse plan from markdown file."""
        # Parse existing plan.md
```

**Key Features:**
- Structured plan representation
- Markdown roundtrip (save/load)
- Complexity estimation
- Dependency tracking

---

### Step 2: Implement PlannerAgent (2.5 hours)

**File:** `src/cdd_agent/agents/planner.py`

Core agent implementation:

```python
class PlannerAgent(BaseAgent):
    """Generates implementation plans from refined specs.

    The agent:
    1. Loads refined spec from Socrates
    2. Analyzes requirements and context
    3. Generates step-by-step plan via LLM
    4. Structures plan with dependencies
    5. Saves plan.md
    6. Auto-exits when complete
    """

    def __init__(self, target_path: Path, session, provider_config, tool_registry):
        super().__init__(target_path, session, provider_config, tool_registry)
        self.name = "Planner"
        self.description = "Generate implementation plans"

        self.spec: Optional[TicketSpec] = None
        self.plan: Optional[ImplementationPlan] = None
        self.plan_path: Optional[Path] = None

    def initialize(self) -> str:
        """Load spec and start planning."""
        # 1. Load ticket spec
        self.spec = parse_ticket_spec(self.target_path)

        # 2. Check if spec is complete
        if not self.spec.is_complete():
            return "⚠️  Spec is incomplete. Run /socrates first."

        # 3. Check if plan already exists
        self.plan_path = self.target_path.parent / "plan.md"
        if self.plan_path.exists():
            # Load existing plan
            self.plan = ImplementationPlan.from_markdown(
                self.plan_path.read_text()
            )
            return f"Plan already exists. Loaded {len(self.plan.steps)} steps."

        # 4. Generate plan (LLM call)
        self.plan = await self._generate_plan()

        # 5. Save plan
        self.plan_path.write_text(self.plan.to_markdown())

        # 6. Mark complete
        self.mark_complete()

        return self._format_plan_summary()

    async def process(self, user_input: str) -> str:
        """Process user refinement requests."""
        # User can ask for plan modifications
        # "Add a step for error handling"
        # "Break down step 3 into smaller steps"

        # Use LLM to understand request and update plan

    def finalize(self) -> str:
        """Save final plan and show summary."""
        if self.plan:
            self.plan_path.write_text(self.plan.to_markdown())

        return f"✅ Plan saved: {self.plan_path}"

    async def _generate_plan(self) -> ImplementationPlan:
        """Use LLM to generate implementation plan."""
        # Build prompt with spec context
        prompt = self._build_planning_prompt()

        # Call LLM
        response = self.session.general_agent.run(
            message="Generate implementation plan",
            system_prompt=prompt
        )

        # Parse LLM response into structured plan
        plan = self._parse_plan_response(response)

        return plan

    def _build_planning_prompt(self) -> str:
        """Build LLM prompt for plan generation."""
        return f"""You are an expert software architect creating \
implementation plans.

Given this ticket specification:

Title: {self.spec.title}
Type: {self.spec.type}
Description: {self.spec.description}

Acceptance Criteria:
{self._format_criteria()}

Technical Notes: {self.spec.technical_notes}

Create a detailed implementation plan with:
1. High-level approach overview
2. Step-by-step implementation tasks
3. Complexity estimate for each step (simple/medium/complex)
4. Time estimates (15min/30min/1hr/2hr/4hr)
5. File paths that will be affected
6. Dependencies between steps
7. Potential risks or challenges

Format as JSON with this structure:
{{
  "overview": "...",
  "steps": [
    {{
      "number": 1,
      "title": "...",
      "description": "...",
      "complexity": "simple",
      "estimated_time": "30 min",
      "dependencies": [],
      "files_affected": ["path/to/file.py"]
    }}
  ],
  "total_complexity": "medium",
  "total_estimated_time": "4 hours",
  "risks": ["..."]
}}"""
```

**Key Features:**
- LLM-powered plan generation
- JSON parsing for structured output
- Plan refinement via dialogue
- Auto-exit after generation
- Heuristic fallback for basic plans

---

### Step 3: Create /plan Slash Command (30 min)

**File:** `src/cdd_agent/slash_commands/plan_command.py`

```python
class PlanCommand(BaseSlashCommand):
    """Activate Planner agent to generate implementation plan.

    Usage:
        /plan <ticket-slug>
        /plan feature-user-auth
    """

    name = "plan"
    description = "Generate implementation plan for ticket"
    usage = "/plan <ticket-slug>"

    async def execute(self, args: str) -> str:
        # 1. Validate args
        if not args.strip():
            return "Usage: /plan <ticket-slug>"

        # 2. Resolve ticket spec path (reuse from SocratesCommand)
        ticket_slug = args.strip()
        spec_path = self._resolve_ticket_spec(ticket_slug)

        # 3. Check session
        if not self.session:
            return "Error: No active session"

        # 4. Check not already in agent mode
        if self.session.is_in_agent_mode():
            return "Error: Already in agent mode. Type 'exit' first."

        # 5. Switch to Planner agent
        from ..agents import PlannerAgent

        greeting = self.session.switch_to_agent(PlannerAgent, spec_path)
        return greeting
```

**Features:**
- Same ticket resolution as `/socrates`
- Session integration
- Error handling

---

### Step 4: Plan Markdown Template (45 min)

**Implement in:** `src/cdd_agent/utils/plan_model.py`

```python
def to_markdown(self) -> str:
    """Convert plan to markdown."""
    md = f"""# Implementation Plan: {self.ticket_title}

**Ticket:** `{self.ticket_slug}`
**Type:** {self.ticket_type}
**Complexity:** {self.total_complexity}
**Estimated Time:** {self.total_estimated_time}

---

## Overview

{self.overview}

---

## Implementation Steps

"""

    for step in self.steps:
        md += f"""### Step {step.number}: {step.title}

**Description:** {step.description}

**Complexity:** {step.complexity}
**Estimated Time:** {step.estimated_time}
**Dependencies:** {', '.join(f'Step {d}' for d in step.dependencies) or 'None'}

**Files Affected:**
{self._format_files(step.files_affected)}

---

"""

    if self.risks:
        md += f"""## Risks & Considerations

{self._format_risks()}

---

"""

    md += f"""## Execution

To execute this plan:

```bash
/exec {self.ticket_slug}
```

---

*Generated by Planner Agent on {datetime.now().strftime('%Y-%m-%d')}*
"""

    return md
```

**Example plan.md Output:**

```markdown
# Implementation Plan: User Authentication

**Ticket:** `feature-user-auth`
**Type:** feature
**Complexity:** medium
**Estimated Time:** 6 hours

---

## Overview

Implement a user authentication system with email/password and OAuth
support. The implementation will consist of creating database models,
API endpoints, authentication middleware, and frontend components.

---

## Implementation Steps

### Step 1: Create User Model

**Description:** Create SQLAlchemy User model with fields for email,
hashed password, OAuth provider info, and timestamps.

**Complexity:** simple
**Estimated Time:** 30 min
**Dependencies:** None

**Files Affected:**
- `src/models/user.py` (new)
- `src/database/migrations/001_users.py` (new)

---

### Step 2: Implement Password Hashing

**Description:** Add bcrypt utilities for password hashing and
verification with proper salt rounds.

**Complexity:** simple
**Estimated Time:** 30 min
**Dependencies:** Step 1

**Files Affected:**
- `src/auth/password.py` (new)
- `requirements.txt` (bcrypt dependency)

---

### Step 3: Create Registration Endpoint

**Description:** Implement POST /api/auth/register endpoint with
validation, duplicate checking, and password hashing.

**Complexity:** medium
**Estimated Time:** 1 hour
**Dependencies:** Step 1, Step 2

**Files Affected:**
- `src/api/auth.py` (new)
- `src/api/__init__.py` (register blueprint)

---

### Step 4: Create Login Endpoint

**Description:** Implement POST /api/auth/login with credential
validation and JWT token generation.

**Complexity:** medium
**Estimated Time:** 1 hour
**Dependencies:** Step 2

**Files Affected:**
- `src/api/auth.py` (update)
- `src/auth/jwt.py` (new)

---

### Step 5: Implement OAuth Integration

**Description:** Add OAuth handlers for Google and GitHub using
authlib, with callback routes and user creation.

**Complexity:** complex
**Estimated Time:** 2 hours
**Dependencies:** Step 1

**Files Affected:**
- `src/auth/oauth.py` (new)
- `src/api/auth.py` (update)
- `config.py` (OAuth credentials)

---

### Step 6: Add Authentication Middleware

**Description:** Create middleware to verify JWT tokens and attach
user to request context.

**Complexity:** medium
**Estimated Time:** 45 min
**Dependencies:** Step 4

**Files Affected:**
- `src/middleware/auth.py` (new)
- `src/api/__init__.py` (register middleware)

---

### Step 7: Write Tests

**Description:** Comprehensive test coverage for registration,
login, OAuth, and protected routes.

**Complexity:** medium
**Estimated Time:** 1.5 hours
**Dependencies:** All previous steps

**Files Affected:**
- `tests/test_auth.py` (new)
- `tests/test_oauth.py` (new)

---

## Risks & Considerations

- **OAuth configuration complexity:** Setting up OAuth apps with
  Google/GitHub requires external configuration

- **Session management:** Need to decide on token storage strategy
  (localStorage vs httpOnly cookies)

- **Password reset flow:** Not included in initial spec, may need
  to add later

---

## Execution

To execute this plan:

```bash
/exec feature-user-auth
```

---

*Generated by Planner Agent on 2025-11-09*
```

---

### Step 5: Testing (2 hours)

**File:** `test_planner_agent.py`

Test coverage:

```python
# Plan Model Tests (5 tests)
def test_plan_step_creation()
def test_implementation_plan_creation()
def test_plan_to_markdown()
def test_plan_from_markdown()
def test_markdown_roundtrip()

# Planner Agent Tests (5 tests)
async def test_planner_initialization_complete_spec()
async def test_planner_initialization_incomplete_spec()
async def test_planner_initialization_existing_plan()
async def test_plan_generation()
async def test_planner_finalization()

# Slash Command Tests (3 tests)
async def test_plan_command_usage()
async def test_plan_command_activation()
async def test_plan_command_errors()

# Integration Tests (2 tests)
async def test_full_workflow_socrates_to_planner()
async def test_plan_refinement_dialogue()
```

**Total: 15 tests**

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────┐
│  User: /plan feature-user-auth                  │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│  PlanCommand                                     │
│  - Resolve ticket slug                           │
│  - Validate session                              │
│  - Switch to PlannerAgent                        │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│  PlannerAgent.initialize()                       │
│  - Load spec.yaml (from Socrates)                │
│  - Check completeness                            │
│  - Check existing plan                           │
│  - Generate plan (LLM)                           │
│  - Save plan.md                                  │
│  - Mark complete                                 │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│  Plan Generation (LLM)                           │
│  ┌─────────────────────────────────────────┐    │
│  │ System Prompt:                          │    │
│  │ - Ticket spec (title, description, AC)  │    │
│  │ - Technical notes                       │    │
│  │ - Request JSON plan structure           │    │
│  └─────────────────────────────────────────┘    │
│                                                  │
│  ┌─────────────────────────────────────────┐    │
│  │ LLM Response (JSON):                    │    │
│  │ {                                       │    │
│  │   "overview": "...",                    │    │
│  │   "steps": [...],                       │    │
│  │   "total_complexity": "medium",         │    │
│  │   "risks": [...]                        │    │
│  │ }                                       │    │
│  └─────────────────────────────────────────┘    │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│  ImplementationPlan                              │
│  - Parse JSON → structured data                  │
│  - Convert to markdown                           │
│  - Save to specs/tickets/<slug>/plan.md          │
└─────────────────────────────────────────────────┘
```

---

## Example Usage Flow

```bash
# Step 1: Create and refine ticket
> /new ticket feature User Authentication
✅ Created: specs/tickets/feature-user-authentication/

> /socrates feature-user-authentication
[Socrates dialogue refines spec...]
✅ Spec refined and saved

# Step 2: Generate plan
> /plan feature-user-authentication

──── Entering Planner Mode ────

**Hello! I'm the Planner.**

Analyzing specification: User Authentication

Generating implementation plan...

**Implementation Plan Created:**

📋 **Overview:** 7-step implementation
⏱️  **Estimated Time:** 6 hours
🔧 **Complexity:** Medium

**Steps:**
1. Create User Model (30 min)
2. Implement Password Hashing (30 min)
3. Create Registration Endpoint (1 hour)
4. Create Login Endpoint (1 hour)
5. Implement OAuth Integration (2 hours)
6. Add Authentication Middleware (45 min)
7. Write Tests (1.5 hours)

**Plan saved to:**
`specs/tickets/feature-user-authentication/plan.md`

✅ Ready for execution! Use `/exec feature-user-authentication`

──── Exiting Planner Mode ────

# Step 3: Execute (Week 7)
> /exec feature-user-authentication
[Executor implements the plan...]
```

---

## Success Criteria

- ✅ PlannerAgent loads refined specs
- ✅ Plan generation via LLM works
- ✅ Structured plan with steps, complexity, time estimates
- ✅ Dependency tracking between steps
- ✅ File paths identified per step
- ✅ Markdown output is readable and well-formatted
- ✅ Plan saved to ticket directory
- ✅ /plan command activates agent
- ✅ Auto-exit after plan generation
- ✅ All tests pass
- ✅ Quality checks pass (Black, Ruff)

---

## Time Estimate

| Task | Estimated Time |
|------|---------------|
| Plan data model | 30 min |
| PlannerAgent implementation | 2.5 hours |
| /plan slash command | 30 min |
| Markdown template | 45 min |
| Testing | 2 hours |
| Quality checks & fixes | 30 min |
| **Total** | **~6.5 hours** |

---

## Dependencies

**Requires from Week 5:**
- ✅ `TicketSpec` and YAML parser
- ✅ `BaseAgent` class
- ✅ Session management
- ✅ Slash command infrastructure

**Provides for Week 7:**
- `ImplementationPlan` model
- `plan.md` files in ticket directories
- Foundation for ExecutorAgent

---

## Files to Create/Modify

### Create
- `src/cdd_agent/utils/plan_model.py` (Plan data structures)
- `src/cdd_agent/agents/planner.py` (PlannerAgent)
- `src/cdd_agent/slash_commands/plan_command.py` (/plan command)
- `test_planner_agent.py` (Test suite)
- `docs/WEEK6_PLANNER_AGENT.md` (This file)
- `docs/WEEK6_COMPLETION_SUMMARY.md` (After completion)

### Modify
- `src/cdd_agent/agents/__init__.py` (Export PlannerAgent)
- `src/cdd_agent/slash_commands/__init__.py` (Register /plan)
- `src/cdd_agent/utils/__init__.py` (Export plan models)

---

## Notes

1. **JSON Parsing:** LLM responses may need validation/sanitization
2. **Heuristic Fallback:** If LLM fails, create basic linear plan
3. **Plan Refinement:** User can ask for modifications after initial generation
4. **Dependency Validation:** Check for circular dependencies
5. **Time Estimates:** Calibrate based on complexity levels

---

**Ready to implement!** Waiting for approval to proceed. 🚀
