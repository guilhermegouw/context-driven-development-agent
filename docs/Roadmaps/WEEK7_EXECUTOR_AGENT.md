# Week 7: Executor Agent - Implementation Plan

**Objective:** Implement the Executor Agent that autonomously executes implementation plans.

**Status:** 📋 Planning Phase
**Estimated Time:** ~8 hours
**Dependencies:** Week 5 (Socrates), Week 6 (Planner)

---

## Background

The Executor Agent is the final agent in the CDD workflow:

```
Spec → Plan → Execute

Week 5: Socrates refines specs
Week 6: Planner generates plans
Week 7: Executor implements the code ← WE ARE HERE
```

The Executor Agent:
1. Loads refined spec and implementation plan
2. Executes steps in order (respecting dependencies)
3. Uses LLM to generate code for each step
4. Runs tests and verifies implementation
5. Auto-exits when all steps complete
6. Handles errors and allows manual intervention

---

## Implementation Plan

### Step 1: Execution State Model (45 min)

**File:** `src/cdd_agent/utils/execution_state.py`

Create data structures for tracking execution progress:

```python
@dataclass
class StepExecution:
    """Execution state for a single step."""
    step_number: int
    status: str  # "pending", "in_progress", "completed", "failed"
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)

@dataclass
class ExecutionState:
    """Overall execution state."""
    ticket_slug: str
    current_step: int
    step_executions: dict[int, StepExecution]
    started_at: str
    completed_at: Optional[str] = None
    status: str = "in_progress"  # "in_progress", "completed", "failed"

    def to_json(self) -> str:
        """Save state to JSON."""

    @classmethod
    def from_json(cls, json_str: str) -> "ExecutionState":
        """Load state from JSON."""

    def save(self, path: Path):
        """Save to execution-state.json."""

    @classmethod
    def load(cls, path: Path) -> Optional["ExecutionState"]:
        """Load from execution-state.json."""
```

**Key Features:**
- Track per-step execution status
- Resume capability (save/load state)
- File tracking for rollback
- Error capture

---

### Step 2: Implement ExecutorAgent (4 hours)

**File:** `src/cdd_agent/agents/executor.py`

Core agent implementation:

```python
class ExecutorAgent(BaseAgent):
    """Executes implementation plans autonomously.

    The agent:
    1. Loads spec and plan
    2. Executes steps in dependency order
    3. Uses LLM to generate code
    4. Runs tests after each step
    5. Handles errors and retries
    6. Auto-exits when complete
    """

    def __init__(self, target_path: Path, session, provider_config, tool_registry):
        super().__init__(target_path, session, provider_config, tool_registry)
        self.name = "Executor"
        self.description = "Execute implementation plans autonomously"

        self.spec = None
        self.plan: Optional[ImplementationPlan] = None
        self.execution_state: Optional[ExecutionState] = None
        self.state_path: Optional[Path] = None

    def initialize(self) -> str:
        """Load spec, plan, and start execution."""
        # 1. Load ticket spec
        self.spec = parse_ticket_spec(self.target_path)

        # 2. Load implementation plan
        plan_path = self.target_path.parent / "plan.md"
        if not plan_path.exists():
            return "⚠️  No plan found. Run /plan first."

        self.plan = ImplementationPlan.from_markdown(
            plan_path.read_text(),
            self.target_path.parent.name
        )

        # 3. Check for existing execution state
        self.state_path = self.target_path.parent / "execution-state.json"
        if self.state_path.exists():
            self.execution_state = ExecutionState.load(self.state_path)
            return self._format_resume_message()

        # 4. Initialize new execution
        self.execution_state = ExecutionState(
            ticket_slug=self.plan.ticket_slug,
            current_step=1,
            step_executions={},
            started_at=datetime.now().isoformat()
        )

        return self._format_start_message()

    async def process(self, user_input: str) -> str:
        """Execute next step or handle user commands."""
        user_input = user_input.strip().lower()

        # Handle commands
        if user_input in ["skip", "s"]:
            return self._skip_current_step()

        if user_input in ["retry", "r"]:
            return await self._retry_current_step()

        if user_input in ["status", "st"]:
            return self._format_status()

        # Execute next step
        if user_input in ["continue", "c", "next", "n", ""]:
            return await self._execute_next_step()

        # Default: execute next step
        return await self._execute_next_step()

    async def _execute_next_step(self) -> str:
        """Execute the next pending step."""
        # Find next step to execute
        next_step = self._get_next_step()

        if not next_step:
            # All done!
            self.mark_complete()
            return self._format_completion_message()

        # Check dependencies
        if not self._dependencies_met(next_step):
            return f"⚠️  Cannot execute Step {next_step.number}: dependencies not met"

        # Execute step
        step_exec = StepExecution(
            step_number=next_step.number,
            status="in_progress",
            started_at=datetime.now().isoformat()
        )
        self.execution_state.step_executions[next_step.number] = step_exec
        self.execution_state.save(self.state_path)

        try:
            # Use LLM to generate code for this step
            code_changes = await self._generate_code_for_step(next_step)

            # Apply code changes
            files_changed = self._apply_code_changes(code_changes)

            # Run tests (if test step or after implementation)
            if "test" in next_step.title.lower() or next_step.number > 1:
                test_result = self._run_tests()
                if not test_result["passed"]:
                    raise Exception(f"Tests failed: {test_result['error']}")

            # Mark step complete
            step_exec.status = "completed"
            step_exec.completed_at = datetime.now().isoformat()
            step_exec.files_created = files_changed["created"]
            step_exec.files_modified = files_changed["modified"]
            self.execution_state.current_step = next_step.number + 1
            self.execution_state.save(self.state_path)

            # Format response
            response = f"""**✅ Step {next_step.number} completed:** {next_step.title}

**Files changed:**
{self._format_file_list(files_changed)}

**Progress:** {self._calculate_progress()}

Type 'continue' for next step or 'exit' to finish.
"""
            return response

        except Exception as e:
            # Mark step failed
            step_exec.status = "failed"
            step_exec.error = str(e)
            self.execution_state.save(self.state_path)

            return f"""**❌ Step {next_step.number} failed:** {next_step.title}

**Error:**
```
{str(e)}
```

Options:
- Type 'retry' to try again
- Type 'skip' to skip this step
- Type 'exit' to stop execution
"""

    async def _generate_code_for_step(self, step: PlanStep) -> dict:
        """Use LLM to generate code for a step.

        Returns dict with:
        - files: {path: content}
        - explanation: str
        """
        # Build context-rich prompt
        prompt = self._build_code_generation_prompt(step)

        # Call LLM
        response = self.session.general_agent.run(
            message="Generate code for this step",
            system_prompt=prompt
        )

        # Parse response (extract code blocks)
        code_changes = self._parse_code_response(response)

        return code_changes

    def finalize(self) -> str:
        """Save final state and return summary."""
        if self.execution_state:
            self.execution_state.status = "completed"
            self.execution_state.completed_at = datetime.now().isoformat()
            self.execution_state.save(self.state_path)

        completed = sum(
            1 for e in self.execution_state.step_executions.values()
            if e.status == "completed"
        )
        total = len(self.plan.steps)

        return f"""**✅ Executor completed**

**Execution Summary:**
- Steps completed: {completed}/{total}
- Total time: {self._calculate_duration()}
- Files modified: {self._count_files_modified()}

**Next:** Review changes and commit
"""
```

**Key Features:**
- Step-by-step execution
- Dependency checking
- LLM code generation
- Test running
- Error handling
- Resume capability
- User commands (skip, retry, status)

---

### Step 3: Create /exec Slash Command (30 min)

**File:** `src/cdd_agent/slash_commands/exec_command.py`

```python
class ExecCommand(BaseSlashCommand):
    """Activate Executor agent to implement a plan.

    Usage:
        /exec <ticket-slug>
        /exec feature-user-auth
    """

    name = "exec"
    description = "Execute implementation plan autonomously"
    usage = "/exec <ticket-slug>"

    async def execute(self, args: str) -> str:
        # 1. Validate args
        # 2. Resolve ticket spec path
        # 3. Check session
        # 4. Switch to Executor agent
```

---

### Step 4: Code Generation and Parsing (1.5 hours)

**Implement in:** `src/cdd_agent/agents/executor.py`

```python
def _build_code_generation_prompt(self, step: PlanStep) -> str:
    """Build prompt for code generation."""
    return f"""You are an expert software engineer implementing this step:

**Ticket:** {self.spec.title}
**Step {step.number}:** {step.title}

**Description:** {step.description}

**Files to modify:** {', '.join(step.files_affected)}

**Acceptance Criteria:**
{self._format_criteria()}

**Technical Context:**
{self.spec.technical_notes}

Generate the code needed for this step. For each file:

1. Show the complete file content or specific changes
2. Include necessary imports
3. Add appropriate error handling
4. Follow best practices
5. Add docstrings and comments

Format your response as:

```python:path/to/file.py
# Complete file content here
```

Explain your implementation choices briefly.
"""

def _parse_code_response(self, response: str) -> dict:
    """Parse LLM response to extract code blocks.

    Returns:
        {
            "files": {
                "path/to/file.py": "content",
                ...
            },
            "explanation": "..."
        }
    """
    # Extract code blocks with file paths
    # Pattern: ```lang:path/to/file
    # content
    # ```

    import re

    files = {}
    pattern = r"```\w*:([^\n]+)\n(.*?)```"
    matches = re.findall(pattern, response, re.DOTALL)

    for path, content in matches:
        files[path.strip()] = content.strip()

    # Extract explanation (text outside code blocks)
    explanation = re.sub(r"```.*?```", "", response, flags=re.DOTALL).strip()

    return {
        "files": files,
        "explanation": explanation
    }

def _apply_code_changes(self, code_changes: dict) -> dict:
    """Apply code changes to filesystem.

    Returns:
        {
            "created": [list of new files],
            "modified": [list of modified files]
        }
    """
    created = []
    modified = []

    base_path = Path.cwd()

    for file_path, content in code_changes["files"].items():
        full_path = base_path / file_path

        # Create parent directories
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Track create vs modify
        if full_path.exists():
            modified.append(file_path)
        else:
            created.append(file_path)

        # Write file
        full_path.write_text(content)

    return {
        "created": created,
        "modified": modified
    }

def _run_tests(self) -> dict:
    """Run tests and return results.

    Returns:
        {
            "passed": bool,
            "output": str,
            "error": Optional[str]
        }
    """
    # Try common test commands
    test_commands = [
        "poetry run pytest",
        "pytest",
        "python -m pytest",
        "npm test",
        "cargo test"
    ]

    for cmd in test_commands:
        try:
            result = subprocess.run(
                cmd.split(),
                capture_output=True,
                text=True,
                timeout=30
            )
            return {
                "passed": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None
            }
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    # No test framework found
    return {
        "passed": True,  # Assume pass if no tests
        "output": "No test framework found",
        "error": None
    }
```

---

### Step 5: Testing (2 hours)

**File:** `test_executor_agent.py`

Test coverage:

```python
# Execution State Tests (4 tests)
def test_step_execution_creation()
def test_execution_state_creation()
def test_state_to_json()
def test_state_save_load()

# Executor Agent Tests (6 tests)
async def test_executor_initialization_with_plan()
async def test_executor_initialization_no_plan()
async def test_executor_step_execution()
async def test_executor_dependency_checking()
async def test_executor_error_handling()
async def test_executor_finalization()

# Code Generation Tests (3 tests)
async def test_code_generation_prompt()
async def test_code_response_parsing()
async def test_code_application()

# Slash Command Tests (2 tests)
async def test_exec_command_usage()
async def test_exec_command_activation()

# Integration Test (1 test)
async def test_full_workflow_socrates_planner_executor()
```

**Total: 16 tests**

---

## Success Criteria

- ✅ ExecutorAgent loads spec and plan
- ✅ Step-by-step execution with dependency checking
- ✅ LLM code generation works
- ✅ Code parsing and file writing
- ✅ Test running integration
- ✅ Error handling and retry
- ✅ Resume capability (save/load state)
- ✅ /exec command activates agent
- ✅ Auto-exit when complete
- ✅ All tests pass
- ✅ Quality checks pass

---

## Time Estimate

| Task | Estimated Time |
|------|---------------|
| Execution state model | 45 min |
| ExecutorAgent implementation | 4 hours |
| /exec slash command | 30 min |
| Code generation/parsing | 1.5 hours |
| Testing | 2 hours |
| Quality checks & fixes | 30 min |
| **Total** | **~9 hours** |

---

## Known Limitations (By Design)

1. **No rollback mechanism** - Failed steps must be manually fixed (future: git integration)
2. **Simple test detection** - Tries common commands, may miss custom setups
3. **No interactive debugging** - Agent generates code but doesn't debug failures iteratively
4. **Single-threaded** - Steps execute sequentially (intentional for simplicity)
5. **LLM-dependent** - No heuristic fallback for code generation (too complex)

---

## Files to Create/Modify

### Create
- `src/cdd_agent/utils/execution_state.py`
- `src/cdd_agent/agents/executor.py`
- `src/cdd_agent/slash_commands/exec_command.py`
- `test_executor_agent.py`
- `docs/WEEK7_EXECUTOR_AGENT.md` (this file)
- `docs/WEEK7_COMPLETION_SUMMARY.md`

### Modify
- `src/cdd_agent/agents/__init__.py`
- `src/cdd_agent/slash_commands/__init__.py`
- `src/cdd_agent/utils/__init__.py`

---

**Ready to implement!** Waiting for approval to proceed. 🚀

---

*Note: This is the final agent in the CDD workflow. After Week 7, we'll have a complete Spec → Plan → Execute pipeline!*
