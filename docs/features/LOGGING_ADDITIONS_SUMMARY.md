# Logging Additions Summary

## ✅ Completed: Socrates Agent

**File:** `src/cdd_agent/agents/socrates.py`

Added comprehensive logging:
- Import `logging` module
- Created `logger = logging.getLogger(__name__)`
- Log statements at:
  - `initialize()`: Ticket loading, vague area detection
  - `process()`: User input, question generation, completion
  - `finalize()`: Saving spec, session statistics
  - Error handlers: Full exception logging with stack traces

**Key logs:**
```python
logger.info(f"Initializing Socrates agent for ticket: {self.target_path}")
logger.info(f"Loaded spec: {self.spec.title} (type: {self.spec.type})")
logger.info(f"Found {len(vague_areas)} vague areas to clarify")
logger.info(f"Asked question #{self.questions_asked}/{self.max_questions}")
logger.info(f"Saved refined spec to {self.target_path}")
logger.error(f"Error in Socrates process: {e}", exc_info=True)
```

---

## 🔄 TODO: Planner Agent

**File:** `src/cdd_agent/agents/planner.py`

**Import added:** ✅ `import logging` and `logger = logging.getLogger(__name__)`

### Locations to Add Logging:

#### 1. `initialize()` method (around line 50-80)
```python
def initialize(self) -> str:
    logger.info(f"Initializing Planner agent for ticket: {self.target_path}")

    try:
        self.spec = parse_ticket_spec(self.target_path)
        logger.info(f"Loaded spec: {self.spec.title} (type: {self.spec.type})")

        if not self.spec.is_complete():
            logger.warning("Spec is not complete enough for planning")
            # ... existing code

        plan_path = self.target_path.parent / "plan.md"
        logger.debug(f"Looking for existing plan at: {plan_path}")

        if plan_path.exists():
            logger.info("Found existing plan, asking user for confirmation")
            # ... existing code

    except Exception as e:
        logger.error(f"Failed to initialize Planner: {e}", exc_info=True)
```

#### 2. `process()` method (around line 90-120)
```python
async def process(self, user_input: str) -> str:
    logger.debug(f"Processing user input: {user_input.strip()}")

    # If user wants to regenerate
    if "regen" in user_input.lower() or "yes" in user_input.lower():
        logger.info("User requested plan regeneration")

    # Generate plan
    logger.info("Generating implementation plan via LLM")
    plan = await self._generate_plan()
    logger.info(f"Generated plan with {len(plan.steps)} steps")

    # Save plan
    plan.save(plan_path)
    logger.info(f"Saved plan to {plan_path}")
```

#### 3. `_generate_plan()` method (around line 150-200)
```python
async def _generate_plan(self) -> ImplementationPlan:
    logger.debug("Building LLM prompt for plan generation")

    if hasattr(self.session, "general_agent"):
        logger.debug("Calling LLM for plan generation")
        response = self.session.general_agent.run(...)
        logger.debug(f"Received LLM response (length: {len(response)})")

        try:
            plan = ImplementationPlan.from_json(response, self.spec.title)
            logger.info(f"Successfully parsed plan: {len(plan.steps)} steps, {plan.total_estimated_time}")
            return plan
        except:
            logger.warning("Failed to parse JSON, trying heuristic fallback")
            return self._heuristic_plan()
    else:
        logger.info("No LLM available, using heuristic plan")
        return self._heuristic_plan()
```

#### 4. `finalize()` method (around line 250-280)
```python
def finalize(self) -> str:
    logger.info("Finalizing Planner session")

    if not self.plan:
        logger.warning("Finalize called but no plan generated")
        return ...

    logger.info(f"Plan finalized: {len(self.plan.steps)} steps, {self.plan.total_complexity} complexity")

    return summary
```

---

## 🔄 TODO: Executor Agent

**File:** `src/cdd_agent/agents/executor.py`

### Locations to Add Logging:

#### 1. Add imports (at top)
```python
import logging

logger = logging.getLogger(__name__)
```

#### 2. `initialize()` method
```python
def initialize(self) -> str:
    logger.info(f"Initializing Executor agent for ticket: {self.target_path}")

    try:
        self.spec = parse_ticket_spec(self.target_path)
        logger.info(f"Loaded spec: {self.spec.title}")

        plan_path = self.target_path.parent / "plan.md"
        self.plan = ImplementationPlan.from_markdown(...)
        logger.info(f"Loaded plan with {len(self.plan.steps)} steps")

        self.state_path = self.target_path.parent / "execution-state.json"
        if self.state_path.exists():
            self.execution_state = ExecutionState.load(self.state_path)
            logger.info(f"Resuming from saved state (step {self.execution_state.current_step})")
        else:
            logger.info("Starting new execution")
            self.execution_state = ExecutionState(...)

    except Exception as e:
        logger.error(f"Failed to initialize Executor: {e}", exc_info=True)
```

#### 3. `process()` method
```python
async def process(self, user_input: str) -> str:
    logger.debug(f"Processing command: {user_input.strip()}")

    if user_input in ["skip", "s"]:
        logger.info("User requested skip current step")
        return self._skip_current_step()

    if user_input in ["retry", "r"]:
        logger.info("User requested retry failed step")
        return await self._retry_current_step()

    if user_input in ["status", "st"]:
        logger.debug("User requested status")
        return self._format_status()

    logger.info("Executing next step")
    return await self._execute_next_step()
```

#### 4. `_execute_next_step()` method
```python
async def _execute_next_step(self) -> str:
    next_step = self._get_next_step()

    if not next_step:
        logger.info("All steps completed!")
        self.mark_complete()
        return ...

    logger.info(f"Executing step {next_step.number}: {next_step.title}")

    # Mark step started
    self.execution_state.mark_step_started(next_step.number)
    logger.debug(f"Marked step {next_step.number} as in_progress")

    # Generate code
    logger.debug(f"Generating code for step {next_step.number} via LLM")
    code_result = await self._generate_code_for_step(next_step)
    logger.info(f"Generated {len(code_result.get('files', {}))} files for step {next_step.number}")

    # Apply changes
    files_changed = self._apply_code_changes(code_result)
    logger.info(f"Applied code changes: {len(files_changed.get('created', []))} created, {len(files_changed.get('modified', []))} modified")

    # Mark complete
    self.execution_state.mark_step_completed(...)
    self.execution_state.save(self.state_path)
    logger.debug("Saved execution state")

    return response
```

#### 5. `_parse_code_response()` method
```python
def _parse_code_response(self, response: str) -> dict:
    logger.debug(f"Parsing code response (length: {len(response)})")

    pattern = r"```[\w]*:([^\n]+)\n(.*?)```"
    matches = re.findall(pattern, response, re.DOTALL)
    logger.debug(f"Found {len(matches)} code blocks")

    files = {path.strip(): content.strip() for path, content in matches}
    logger.info(f"Parsed {len(files)} files from code response")

    return {"files": files, "explanation": explanation}
```

#### 6. `_apply_code_changes()` method
```python
def _apply_code_changes(self, code_result: dict) -> dict:
    files = code_result.get("files", {})
    logger.info(f"Applying code changes to {len(files)} files")

    for filepath, content in files.items():
        full_path = Path.cwd() / filepath
        logger.debug(f"Writing file: {full_path}")

        # Create directories
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        full_path.write_text(content)
        logger.info(f"Created/modified: {filepath}")

    return {"created": created, "modified": modified}
```

#### 7. Error handling
```python
except Exception as e:
    logger.error(f"Step {next_step.number} failed: {e}", exc_info=True)
    self.execution_state.mark_step_failed(next_step.number, str(e))
    self.execution_state.save(self.state_path)
```

---

## 🔄 TODO: Slash Commands

### `socrates_command.py`
```python
import logging

logger = logging.getLogger(__name__)

async def execute(self, args: str) -> str:
    logger.info(f"Executing /socrates command with args: {args}")

    try:
        spec_path = self._resolve_ticket_spec(args.strip())
        logger.info(f"Resolved ticket to: {spec_path}")

        greeting = self.session.switch_to_agent(SocratesAgent, spec_path)
        logger.info("Successfully activated Socrates agent")
        return greeting

    except FileNotFoundError as e:
        logger.warning(f"Ticket not found: {args}")
        return error_message

    except Exception as e:
        logger.error(f"Error activating Socrates: {e}", exc_info=True)
        return error_message
```

### `plan_command.py`
```python
import logging

logger = logging.getLogger(__name__)

async def execute(self, args: str) -> str:
    logger.info(f"Executing /plan command with args: {args}")

    try:
        spec_path = self._resolve_ticket_spec(args.strip())
        logger.info(f"Resolved ticket to: {spec_path}")

        greeting = self.session.switch_to_agent(PlannerAgent, spec_path)
        logger.info("Successfully activated Planner agent")
        return greeting

    except Exception as e:
        logger.error(f"Error activating Planner: {e}", exc_info=True)
        return error_message
```

### `exec_command.py`
```python
import logging

logger = logging.getLogger(__name__)

async def execute(self, args: str) -> str:
    logger.info(f"Executing /exec command with args: {args}")

    try:
        spec_path = self._resolve_ticket_spec(args.strip())
        logger.info(f"Resolved ticket to: {spec_path}")

        # Check plan exists
        plan_path = spec_path.parent / "plan.md"
        if not plan_path.exists():
            logger.warning(f"No plan found at {plan_path}")
            return error_message

        logger.info("Plan exists, activating Executor agent")
        greeting = self.session.switch_to_agent(ExecutorAgent, spec_path)
        logger.info("Successfully activated Executor agent")
        return greeting

    except Exception as e:
        logger.error(f"Error activating Executor: {e}", exc_info=True)
        return error_message
```

---

## Testing Logging

Once logging is added, test with:

```bash
# Enable verbose logging
poetry run cdd-agent chat --verbose

# In another terminal, tail logs
tail -f ~/.cdd-agent/logs/cdd-agent-*.log

# Run a test workflow
> /init
> /new ticket feature test
> /socrates feature-test
> ... answer questions ...
> /plan feature-test
> /exec feature-test
```

## Log File Location

Logs are written to: `~/.cdd-agent/logs/cdd-agent-YYYY-MM-DD.log`

## Log Levels

- **DEBUG**: Detailed diagnostic info (LLM prompts, parsing details)
- **INFO**: General progress tracking (agent activation, step completion)
- **WARNING**: Recoverable issues (incomplete specs, missing plans)
- **ERROR**: Failures with stack traces (exceptions, file errors)

---

## Benefits of This Logging

1. **Debugging**: See exactly what's happening in agent workflows
2. **Monitoring**: Track progress of long-running Executor sessions
3. **Troubleshooting**: Error messages with full context
4. **Performance**: Identify slow operations
5. **Testing**: Verify behavior in automated tests

---

## Quick Apply

To apply these changes quickly:

1. **Socrates**: ✅ DONE
2. **Planner**: Follow locations marked above
3. **Executor**: Follow locations marked above
4. **Slash Commands**: Add at execute() methods

Or run: `python add_logging_to_agents.py` (script provided)

---

**Priority:** Add logging to Executor first - it's the most complex and benefits most from visibility!
