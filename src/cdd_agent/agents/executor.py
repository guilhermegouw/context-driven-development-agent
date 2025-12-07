"""Executor Agent - Autonomous code execution from implementation plans.

This agent executes implementation plans step-by-step, generating code via LLM
and running tests to verify implementations.

Key Features:
- Uses direct LLM call for code generation (no tool loop)
- Loads project context from CDD.md/CLAUDE.md
- Reads existing files before modifying them
- Generates complete file content with proper merging instructions
"""

import logging
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import Optional
from typing import TypedDict
from typing import cast

from ..session.base_agent import BaseAgent
from ..utils.execution_state import ExecutionState
from ..utils.plan_model import ImplementationPlan
from ..utils.plan_model import PlanStep
from ..utils.yaml_parser import parse_ticket_spec


class TicketSpec(TypedDict, total=False):
    title: str
    type: str
    acceptance_criteria: list[str]
    technical_notes: str


if TYPE_CHECKING:
    from ..session.chat_session import ChatSession

logger = logging.getLogger(__name__)


class ExecutorAgent(BaseAgent):
    """Executes implementation plans autonomously.

    The agent:
    1. Loads refined spec and implementation plan
    2. Executes steps in dependency order
    3. Uses LLM to generate code for each step
    4. Runs tests after changes
    5. Handles errors with retry/skip options
    6. Auto-exits when all steps complete

    Example Session:
        [Executor]> Executing Step 1: Create User Model
        ✅ Step 1 completed (3 files created)
        Progress: 1/7 steps (14%)

        [Executor]> Executing Step 2: Add Authentication...
    """

    def __init__(
        self,
        target_path: Path,
        session: "ChatSession",
        provider_config: Any,
        tool_registry: Any,
    ):
        """Initialize Executor agent.

        Args:
            target_path: Path to ticket spec.yaml file
            session: Parent ChatSession instance
            provider_config: LLM provider configuration
            tool_registry: Available tools for agent
        """
        super().__init__(target_path, session, provider_config, tool_registry)

        self.name = "Executor"
        self.description = "Execute implementation plans autonomously"

        # Agent state
        self.spec: Optional[TicketSpec] = None
        self.plan: Optional[ImplementationPlan] = None
        self.execution_state: Optional[ExecutionState] = None
        self.state_path: Optional[Path] = None

        # Project context (loaded once during initialize)
        self.project_context: str = ""
        self.codebase_structure: str = ""

    def initialize(self) -> str:
        """Load spec, plan, and start or resume execution.

        Returns:
            Initial greeting with execution status
        """
        logger.info(f"Initializing Executor agent for ticket: {self.target_path}")

        try:
            # 1. Load ticket spec
            spec_parsed = parse_ticket_spec(self.target_path)
            self.spec = cast(TicketSpec, spec_parsed)
            if not self.spec:
                raise ValueError("Failed to parse ticket spec")
            logger.info(
                f"Loaded spec: {self._safe_attr(self.spec, 'title', 'Unknown')}"
            )

            # 2. Load implementation plan
            plan_path = self.target_path.parent / "plan.md"
            logger.debug(f"Looking for plan at: {plan_path}")

            if not plan_path.exists():
                logger.warning(f"No plan found at {plan_path}")
                return (
                    "**⚠️  No implementation plan found**\n\n"
                    f"Please run `/plan {self.target_path.parent.name}` "
                    f"to generate a plan first."
                )

            ticket_slug = self.target_path.parent.name
            self.plan = cast(
                ImplementationPlan,
                ImplementationPlan.from_markdown(plan_path.read_text(), ticket_slug),
            )
            if not self.plan:
                raise ValueError("Failed to load implementation plan")
            logger.info(f"Loaded plan: {self._safe_len(self.plan.steps)} steps")

            # 3. Check for existing execution state
            self.state_path = self.target_path.parent / "execution-state.json"
            if self.state_path.exists():
                logger.info(f"Found existing execution state at {self.state_path}")
                self.execution_state = ExecutionState.load(self.state_path)
                if self.execution_state:
                    step_num = self._safe_attr(self.execution_state, "current_step", 1)
                    logger.info(f"Resuming execution from step {step_num}")
                    return self._format_resume_message()

            # 4. Initialize new execution
            logger.info("Starting new execution")
            self.execution_state = ExecutionState(
                ticket_slug=self._safe_attr(self.plan, "ticket_slug", ticket_slug),
                current_step=1,
                step_executions={},
                started_at=datetime.now().isoformat(),
            )

            return self._format_start_message()

        except Exception as e:
            logger.error(f"Failed to initialize Executor: {e}", exc_info=True)
            return (
                f"**Error initializing Executor:**\n\n"
                f"```\n{str(e)}\n```\n\n"
                f"Please check the ticket and plan."
            )

    async def process(self, user_input: str) -> str:
        """Execute steps or handle user commands.

        Args:
            user_input: User command or empty for next step

        Returns:
            Step execution result or command response
        """
        logger.debug(f"Processing command: {user_input.strip()}")
        user_input = user_input.strip().lower()

        # Handle special commands
        if user_input in ["skip", "s"]:
            logger.info("User requested skip current step")
            return self._skip_current_step()

        if user_input in ["retry", "r"]:
            logger.info("User requested retry failed step")
            return await self._retry_current_step()

        if user_input in ["status", "st"]:
            logger.debug("User requested status")
            return self._format_status()

        # Default: execute next step
        logger.info("Executing next step")
        return await self._execute_next_step()

    def _safe_call(
        self, obj: Any, method_name: str, *args: Any, default: Any = None
    ) -> Any:
        """Safely call a method on an object.

        Handles potential None or attribute errors.

        Args:
            obj: The object to call method on
            method_name: Name of the method to call
            *args: Arguments to pass to the method
            default: Value to return if method cannot be called

        Returns:
            Result of method call or default value
        """
        try:
            if obj is None:
                return default
            method = getattr(obj, method_name)
            return method(*args)
        except (AttributeError, TypeError, Exception):
            return default

    def _is_yolo_mode(self) -> bool:
        """Check if execution is in YOLO mode (auto-continue).

        Returns:
            True if in YOLO mode, False otherwise
        """
        try:
            # Multi-step safety for nested attribute access
            if not hasattr(self, "session"):
                return False

            # Safe general_agent retrieval
            general_agent = self._safe_call(
                self.session, "getattr", "general_agent", default=None
            )
            if not general_agent:
                return False

            # Safe execution_mode retrieval
            execution_mode = self._safe_call(
                general_agent, "getattr", "execution_mode", default=None
            )
            if not execution_mode:
                return False

            # Call is_yolo method with safety
            return bool(self._safe_call(execution_mode, "is_yolo", default=False))

        except Exception as e:
            logger.warning(f"Error checking YOLO mode: {e}")
            return False

    async def _execute_next_step(self) -> str:
        """Execute the next pending step.

        In YOLO mode, automatically continues to the next step after success.
        In NORMAL/PLAN mode, pauses and waits for user to type 'continue'.
        On failure, ALWAYS stops and reports the error (regardless of mode).

        Returns:
            Execution result message
        """
        # Validate execution context
        if not self.plan or not self.execution_state or not self.state_path:
            return "**Error: Incomplete execution context**"

        # Collect all step results for YOLO mode
        all_results: list[str] = []

        while True:
            # Find next step
            next_step = self._get_next_step()

            if not next_step:
                # All done!
                logger.info("All steps completed!")

                # Safely mark execution complete and get completion message
                if self.execution_state and self.state_path:
                    self.execution_state.status = "completed"
                    self.execution_state.completed_at = datetime.now().isoformat()
                    try:
                        self.execution_state.save(self.state_path)
                    except Exception as e:
                        logger.error(f"Failed to save completion state: {e}")

                completion_msg = self._format_completion_message()

                if all_results:
                    all_results.append(completion_msg)
                    return "\n\n---\n\n".join(all_results)
                return completion_msg

            # Check dependencies
            if not self._dependencies_met(next_step):
                deps = ", ".join(f"Step {d}" for d in next_step.dependencies)
                logger.warning(
                    f"Cannot execute step {next_step.number}: "
                    f"dependencies not met ({deps})"
                )
                error_msg = (
                    f"**⚠️  Cannot execute Step {next_step.number}**\n\n"
                    f"Dependencies not met: {deps}\n\n"
                    f"Complete those steps first or type 'skip' to skip this step."
                )
                if all_results:
                    all_results.append(error_msg)
                    return "\n\n---\n\n".join(all_results)
                return error_msg

            logger.info(f"Executing step {next_step.number}: {next_step.title}")

            # Mark step started with safety
            if not self.execution_state or not self.state_path:
                logger.error(
                    f"Cannot mark step {next_step.number} as started: Missing state"
                )
                return "Error: Invalid execution state"

            try:
                self.execution_state.mark_step_started(next_step.number)
                self.execution_state.save(self.state_path)
                logger.debug(f"Marked step {next_step.number} as in_progress")
            except Exception as e:
                logger.error(f"Failed to mark step {next_step.number}: {e}")

            status_msg = (
                f"**🔄 Executing Step {next_step.number}:** {next_step.title}\n\n"
                f"**Description:** {next_step.description}\n\n"
                f"Generating code...\n\n"
            )

            try:
                # Generate code for this step
                logger.debug(f"Generating code for step {next_step.number} via LLM")
                code_result = await self._generate_code_for_step(next_step)

                if not code_result["files"]:
                    # No code generated - possibly a planning/research step
                    logger.info(f"Step {next_step.number} completed (no code changes)")
                    self._safe_state_op("mark_step_completed", next_step.number, [], [])
                    self.execution_state.current_step = next_step.number + 1
                    self.execution_state.save(self.state_path)

                    explanation = code_result.get(
                        "explanation", "No code changes needed"
                    )
                    step_result = (
                        f"{status_msg}"
                        f"✅ **Step {next_step.number} completed** "
                        f"(planning/research step)\n\n"
                        f"{explanation}\n\n"
                        f"**Progress:** {self._calculate_progress()}"
                    )

                    # YOLO mode: continue to next step
                    if self._is_yolo_mode():
                        all_results.append(step_result)
                        logger.info("YOLO mode: auto-continuing to next step")
                        continue
                    else:
                        return step_result + "\n\nType 'continue' for next step."

                # Apply code changes
                logger.debug(f"Applying code changes for step {next_step.number}")
                files_changed = self._apply_code_changes(code_result)
                logger.info(
                    f"Applied code changes: {len(files_changed['created'])} created, "
                    f"{len(files_changed['modified'])} modified"
                )

                # Mark step completed
                self.execution_state.mark_step_completed(
                    next_step.number,
                    files_changed["created"],
                    files_changed["modified"],
                )
                self.execution_state.current_step = next_step.number + 1
                self.execution_state.save(self.state_path)
                logger.debug("Saved execution state")

                logger.info(f"Step {next_step.number} completed successfully")

                # Format response
                step_result = (
                    f"{status_msg}"
                    f"✅ **Step {next_step.number} completed:** {next_step.title}\n\n"
                    f"{self._format_file_changes(files_changed)}\n\n"
                    f"**Progress:** {self._calculate_progress()}"
                )

                # YOLO mode: auto-continue to next step
                if self._is_yolo_mode():
                    all_results.append(step_result)
                    logger.info("YOLO mode: auto-continuing to next step")
                    continue
                else:
                    return (
                        step_result
                        + "\n\nType 'continue' for next step or 'exit' to finish."
                    )

            except Exception as e:
                # Mark step failed - ALWAYS stop on failure, even in YOLO mode
                logger.error(f"Step {next_step.number} failed: {e}", exc_info=True)
                self.execution_state.mark_step_failed(next_step.number, str(e))
                self.execution_state.save(self.state_path)

                error_msg = (
                    f"**❌ Step {next_step.number} failed:** {next_step.title}\n\n"
                    f"**Error:**\n"
                    f"```\n{str(e)}\n```\n\n"
                    f"**Options:**\n"
                    f"- Type 'retry' to try again\n"
                    f"- Type 'skip' to skip this step\n"
                    f"- Type 'exit' to stop execution"
                )

                # If we had previous successful steps, include them
                if all_results:
                    all_results.append(error_msg)
                    return "\n\n---\n\n".join(all_results)
                return error_msg

    def _get_next_step(self) -> Optional[PlanStep]:
        """Find the next step to execute.

        Returns:
            Next pending step or None if all complete
        """
        # Early return checks
        if not self.execution_state or not self.plan:
            return None

        completed = self.execution_state.get_completed_steps()

        # Safely iterate through steps
        for step in self.plan.steps or []:
            if step.number not in completed:
                return step

        return None

    def _dependencies_met(self, step: PlanStep) -> bool:
        """Check if step dependencies are met.

        Args:
            step: Step to check

        Returns:
            True if all dependencies completed
        """
        # Early return if no execution state
        if not self.execution_state:
            return False

        # If no dependencies, always return True
        if not step.dependencies:
            return True

        # Safely get completed steps
        completed = self.execution_state.get_completed_steps()
        if not completed:
            return False

        # Check dependencies
        return all(dep in completed for dep in step.dependencies)

    async def _generate_code_for_step(self, step: PlanStep) -> dict:
        """Use LLM to generate code for a step.

        Uses direct LLM call (no tool loop) with full project context.

        Args:
            step: Step to generate code for

        Returns:
            Dict with 'files' and 'explanation'
        """
        # Load project context if not already loaded
        if not self.project_context:
            self.project_context = self._load_project_context()
            self.codebase_structure = self._scan_codebase_structure()

        # Read existing files that will be modified
        existing_files = self._read_existing_files(step.files_affected)

        # Build prompts
        system_prompt = self._build_code_generation_system_prompt()
        user_message = self._build_code_generation_request(step, existing_files)

        # Direct LLM call - no tools
        if hasattr(self.session, "general_agent") and self.session.general_agent:
            agent = self.session.general_agent
            model = agent.provider_config.get_model(agent.model_tier)

            logger.info(f"Calling LLM for code generation (model: {model})")

            response = agent.client.messages.create(
                model=model,
                max_tokens=8192,  # More tokens for code generation
                messages=[{"role": "user", "content": user_message}],
                system=system_prompt,
            )

            # Extract text response
            response_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    response_text += block.text
                elif isinstance(block, dict) and "text" in block:
                    response_text += block["text"]

            logger.debug(f"LLM response length: {len(response_text)} chars")

            # Parse response
            return self._parse_code_response(response_text)
        else:
            raise Exception("No LLM available for code generation")

    def _load_project_context(self) -> str:
        """Load project context from CDD.md or CLAUDE.md."""
        for filename in ["CDD.md", "CLAUDE.md"]:
            path = Path.cwd() / filename
            if path.exists():
                try:
                    content = path.read_text(encoding="utf-8")
                    if len(content) > 6000:
                        content = content[:6000] + "\n\n[... truncated ...]"
                    logger.info(f"Loaded project context from {filename}")
                    return content
                except Exception as e:
                    logger.error(f"Failed to read {filename}: {e}")
        return ""

    def _scan_codebase_structure(self) -> str:
        """Scan codebase structure using tree command."""
        try:
            result = subprocess.run(
                [
                    "tree",
                    "-L",
                    "3",
                    "-I",
                    "__pycache__|.git|.venv|*.pyc",
                    "--noreport",
                    str(Path.cwd()),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                output = result.stdout
                if len(output) > 3000:
                    lines = output.split("\n")[:100]
                    output = "\n".join(lines) + "\n[... truncated ...]"
                return output
        except Exception as e:
            logger.warning(f"tree command failed: {e}")
        return ""

    def _read_existing_files(self, file_paths: list[str]) -> dict[str, str]:
        """Read content of existing files that will be modified.

        Args:
            file_paths: List of file paths from the plan

        Returns:
            Dict mapping path -> content for existing files
        """
        existing = {}
        base_path = Path.cwd()

        for file_path in file_paths:
            full_path = base_path / file_path
            if full_path.exists():
                try:
                    content = full_path.read_text(encoding="utf-8")
                    # Truncate very large files
                    if len(content) > 10000:
                        content = content[:10000] + "\n\n# [... file truncated ...]"
                    existing[file_path] = content
                    logger.debug(
                        f"Read existing file: {file_path} ({len(content)} chars)"
                    )
                except Exception as e:
                    logger.warning(f"Could not read {file_path}: {e}")

        return existing

    def _build_code_generation_system_prompt(self) -> str:
        """Build system prompt for code generation."""
        return f"""You are an expert software engineer implementing code changes.

## PROJECT CONTEXT

{self.project_context if self.project_context else "No project context file found."}

## CODEBASE STRUCTURE

```
{self.codebase_structure if self.codebase_structure else "Structure not available"}
```

## CRITICAL RULES

1. **For EXISTING files**: Output the COMPLETE file content with your changes integrated
   - Do NOT output just a snippet or just the new code
   - Include ALL existing code plus your additions/modifications
   - Preserve all existing functionality

2. **For NEW files**: Output the complete new file content

3. **Output format**: Use code blocks with file path:
   ```python:src/path/to/file.py
   # Complete file content here
   ```

# Match the code style, imports, and patterns used in the project
4. **Follow existing patterns**

5. **Be precise**: Only modify what's needed for this specific step"""

    def _build_code_generation_request(
        self, step: PlanStep, existing_files: dict[str, str]
    ) -> str:
        """Build user message for code generation.

        Args:
            step: Step to implement
            existing_files: Dict of existing file contents

        Returns:
            User message string
        """
        # Early returns for edge cases
        if not self.spec:
            return "Error: No spec available for code generation"

        criteria_text = "\n".join(
            f"- {ac}"
            for ac in self._safe_attr(self.spec, "acceptance_criteria", []) or []
        )
        files_text = "\n".join(f"- {f}" for f in step.files_affected)

        # Include existing file contents
        existing_section = ""
        if existing_files:
            existing_section = "\n## EXISTING FILES TO MODIFY\n\n"
            existing_section += (
                "**IMPORTANT: These files already exist. "
                "Output the COMPLETE file with your changes integrated.**\n\n"
            )
            for path, content in existing_files.items():
                existing_section += (
                    f"### `{path}` (EXISTING - include ALL content "
                    f"with modifications)\n\n```python\n{content}\n```\n\n"
                )

        new_files = [f for f in step.files_affected if f not in existing_files]
        new_section = ""
        if new_files:
            new_section = "\n## NEW FILES TO CREATE\n\n"
            for path in new_files:
                new_section += f"- `{path}` (create new file)\n"

        return f"""## TASK

Implement Step {step.number}: **{step.title}**

**Description:** {step.description}

**Files to work on:**
{files_text}
{existing_section}{new_section}
## TICKET CONTEXT

**Title:** {self._safe_attr(self.spec, 'title', 'Untitled')}
**Type:** {self._safe_attr(self.spec, 'type', 'Unspecified')}

**Acceptance Criteria:**
{criteria_text}

**Technical Notes:**
{self._safe_attr(self.spec, 'technical_notes', 'None provided')}

## INSTRUCTIONS

1. Generate the code needed for THIS step only
2. For existing files: output COMPLETE file content with changes integrated
3. For new files: output complete new file content
4. Use the format: ```python:path/to/file.py

After the code, briefly explain what you changed."""

    def _parse_code_response(self, response: str) -> dict:
        """Parse LLM response to extract code blocks.

        Args:
            response: LLM response text

        Returns:
            Dict with 'files' (dict of path->content) and 'explanation'
        """
        logger.debug(f"Parsing code response (length: {len(response)})")
        files = {}

        # Pattern: ```lang:path/to/file
        # content
        # ```
        pattern = r"```[\w]*:([^\n]+)\n(.*?)```"
        matches = re.findall(pattern, response, re.DOTALL)
        logger.debug(f"Found {len(matches)} code blocks")

        for path, content in matches:
            clean_path = path.strip()
            clean_content = content.strip()
            files[clean_path] = clean_content

        logger.info(f"Parsed {len(files)} files from code response")

        # Extract explanation (text outside code blocks)
        explanation = re.sub(r"```.*?```", "", response, flags=re.DOTALL).strip()

        # Clean up explanation (remove excessive newlines)
        explanation = re.sub(r"\n{3,}", "\n\n", explanation)

        return {"files": files, "explanation": explanation}

    def _apply_code_changes(self, code_result: dict) -> dict:
        """Apply code changes to filesystem.

        Args:
            code_result: Dict with 'files' mapping path to content

        Returns:
            Dict with 'created' and 'modified' file lists
        """
        files = code_result.get("files", {})
        logger.info(f"Applying code changes to {len(files)} files")

        created = []
        modified = []

        base_path = Path.cwd()

        for file_path, content in files.items():
            full_path = base_path / file_path
            logger.debug(f"Writing file: {full_path}")

            # Create parent directories if needed
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Track create vs modify
            if full_path.exists():
                modified.append(file_path)
                logger.info(f"Modified: {file_path}")
            else:
                created.append(file_path)
                logger.info(f"Created: {file_path}")

            # Write file
            full_path.write_text(content)

        return {"created": created, "modified": modified}

    def _skip_current_step(self) -> str:
        """Skip the current step.

        Returns:
            Status message
        """
        assert self.execution_state is not None, "Execution state must be initialized"
        assert self.state_path is not None, "State path must be initialized"

        next_step = self._get_next_step()

        if not next_step:
            logger.debug("No step to skip - all steps completed")
            return "No step to skip - all steps completed!"

        logger.info(f"Skipping step {next_step.number}: {next_step.title}")

        # Mark as completed (even though skipped)
        self.execution_state.mark_step_completed(next_step.number, [], [])
        self.execution_state.current_step = next_step.number + 1
        self.execution_state.save(self.state_path)

        return (
            f"⏭️  **Skipped Step {next_step.number}:** {next_step.title}\n\n"
            f"**Progress:** {self._calculate_progress()}\n\n"
            f"Type 'continue' for next step."
        )

    async def _retry_current_step(self) -> str:
        """Retry the last failed step.

        Returns:
            Retry result message
        """
        assert self.execution_state is not None, "Execution state must be initialized"
        assert self.state_path is not None, "State path must be initialized"
        assert self.plan is not None, "Plan must be initialized"

        # Find last failed step
        failed = self.execution_state.get_failed_steps()

        if not failed:
            logger.debug("No failed steps to retry")
            return "No failed steps to retry."

        # Get the step
        step_num = failed[-1]  # Retry most recent failure
        logger.info(f"Retrying failed step {step_num}")
        step = next((s for s in self.plan.steps if s.number == step_num), None)

        if not step:
            logger.error(f"Cannot find step {step_num} for retry")
            return f"Cannot find step {step_num}"

        # Reset step to pending
        self.execution_state.current_step = step_num
        if step_num in self.execution_state.step_executions:
            del self.execution_state.step_executions[step_num]
        self.execution_state.save(self.state_path)
        logger.debug(f"Reset step {step_num} to pending state")

        # Execute
        return await self._execute_next_step()

    def _format_status(self) -> str:
        """Format current execution status.

        Returns:
            Status message
        """
        # Safety checks
        if not self.execution_state or not self.plan or not self.spec:
            return "Execution state is incomplete. Please initialize first."

        # Safe attribute access
        completed = self._safe_len(self.execution_state.get_completed_steps())
        failed = self._safe_len(self.execution_state.get_failed_steps())
        total = self._safe_len(self.plan.steps)

        status = f"""**📊 Execution Status**

**Ticket:** {self._safe_attr(self.spec, 'title', 'Untitled')}
**Progress:** {completed}/{total} steps completed ({self._calculate_progress()})

**Breakdown:**
- ✅ Completed: {completed}
- ❌ Failed: {failed}
- ⏸️  Remaining: {max(0, total - completed - failed)}

**Current Step:** {self._safe_attr(self.execution_state, 'current_step', 'N/A')}
"""

        if failed > 0:
            status += "\n**Failed Steps:**\n"
            for step_num in self._safe_call(
                self.execution_state, "get_failed_steps", default=[]
            ):
                # Safely retrieve execution state
                exec_state = self._safe_call(
                    self.execution_state, "getattr", "step_executions", default={}
                ).get(step_num)

                # Safely extract error
                if exec_state:
                    error_msg = self._safe_attr(exec_state, "error", "Unknown error")
                    status += f"- Step {step_num}: {error_msg}\n"

        status += "\nType 'continue' to proceed or 'exit' to stop."

        return status

    def _calculate_progress(self) -> str:
        """Calculate progress percentage.

        Returns:
            Progress string (e.g., "42%")
        """
        if not self.plan or not self.execution_state:
            return "0/0 steps (0%)"

        total = self._safe_len(self.plan.steps)
        completed = self._safe_len(self.execution_state.get_completed_steps())

        # Prevent division by zero
        percent = (completed / total * 100) if total > 0 else 0
        return f"{completed}/{total} steps ({percent:.0f}%)"

    def _format_file_changes(self, files_changed: dict) -> str:
        """Format file changes for display.

        Args:
            files_changed: Dict with 'created' and 'modified' lists

        Returns:
            Formatted string
        """
        parts = []

        if files_changed["created"]:
            parts.append("**Files Created:**")
            for file in files_changed["created"]:
                parts.append(f"- `{file}`")

        if files_changed["modified"]:
            parts.append("**Files Modified:**")
            for file in files_changed["modified"]:
                parts.append(f"- `{file}`")

        return "\n".join(parts) if parts else "No files changed"

    def _format_start_message(self) -> str:
        """Format initial execution message.

        Returns:
            Start message
        """
        # Safety checks
        if not self.spec or not self.plan:
            return "**Error: Incomplete execution context**"

        yolo_hint = ""
        if self._is_yolo_mode():
            yolo_hint = (
                "\n🚀 **YOLO MODE ACTIVE** - Steps will execute automatically!\n"
            )
        else:
            yolo_hint = (
                "\n💡 *Tip: Switch to YOLO mode (Shift+Tab) for auto-execution*\n"
            )

        return f"""**Hello! I'm the Executor.**

**Ticket:** {self._safe_attr(self.spec, 'title', 'Untitled')}
**Plan:** {self._safe_len(self.plan.steps)} implementation steps
**Estimated Time:** {self._safe_attr(self.plan, 'total_estimated_time', 'Unknown')}
{yolo_hint}
I'll execute the implementation plan step-by-step.

**Available Commands:**
- Press Enter or type 'continue' to execute next step
- Type 'status' to see progress
- Type 'skip' to skip current step
- Type 'retry' to retry failed step
- Type 'exit' to stop execution

Ready to begin! Type 'continue' or press Enter to start.
"""

    def _format_resume_message(self) -> str:
        """Format resume message for existing execution.

        Returns:
            Resume message
        """
        # Safety checks
        if not self.spec or not self.plan or not self.execution_state:
            return "**Error: Cannot resume incomplete execution**"

        completed = self._safe_len(self.execution_state.get_completed_steps())
        total = self._safe_len(self.plan.steps)

        return f"""**Resuming execution...**

**Ticket:** {self._safe_attr(self.spec, 'title', 'Untitled')}
**Progress:** {completed}/{total} steps completed
**Current Step:** {self._safe_attr(self.execution_state, 'current_step', 'Unknown')}

Type 'continue' to resume or 'status' for details.
"""

    def _format_completion_message(self) -> str:
        """Format completion message.

        Returns:
            Completion message
        """
        # Safety checks
        if not self.execution_state or not self.plan:
            return "**Error: Execution context is incomplete**"

        completed = self._safe_len(self.execution_state.get_completed_steps())
        failed = self._safe_len(self.execution_state.get_failed_steps())
        total = self._safe_len(self.plan.steps)

        return f"""**🎉 All steps executed!**

**Summary:**
- ✅ Completed: {completed}
- ❌ Failed: {failed}
- Total Steps: {total}

**Next Steps:**
1. Review the generated code
2. Run tests: `pytest` or your test command
3. Commit changes if satisfied

Type 'exit' to finish.
"""

    def _safe_attr(self, obj: Any, attr_name: str, default: Any = None) -> Any:
        """Safely get an attribute from an object.

        Args:
            obj: The object to get the attribute from
            attr_name: The name of the attribute
            default: The default value to return if attribute doesn't exist

        Returns:
            The attribute value or default
        """
        return getattr(obj, attr_name, default)

    def _safe_len(self, obj: Optional[Any]) -> int:
        """Safely get length of an object, returning 0 if None.

        Args:
            obj: Object to get length of

        Returns:
            Length of the object or 0
        """
        return len(obj) if obj is not None else 0

    def _safe_state_op(self, operation: str, *args: Any, default: Any = None) -> Any:
        """Safely perform an operation on execution state.

        Args:
            operation: Name of method to call
            *args: Arguments to pass to the method
            default: Value to return if operation fails

        Returns:
            Result of operation or default
        """
        if not self.execution_state or not self.state_path:
            logger.warning(f"Cannot perform {operation}: Missing state")
            return default

        try:
            method = getattr(self.execution_state, operation)
            result = method(*args)

            # Save state after operation if it modifies state
            if operation in [
                "mark_step_started",
                "mark_step_completed",
                "mark_step_failed",
            ]:
                self.execution_state.save(self.state_path)

            return result
        except Exception as e:
            logger.error(f"Error performing {operation}: {e}")
            return default

    def finalize(self) -> str:
        """Save final state and return summary.

        Returns:
            Finalization summary
        """
        logger.info("Finalizing Executor session")

        # Early return if no execution state
        if not self.execution_state or not self.plan or not self.state_path:
            logger.warning("No execution state to finalize")
            return "**❗ Execution state is incomplete**"

        # Safe updates
        self.execution_state.status = "completed"
        self.execution_state.completed_at = datetime.now().isoformat()
        self.execution_state.save(self.state_path)
        logger.info(f"Saved final execution state to {self.state_path}")

        completed = self._safe_len(self.execution_state.get_completed_steps())
        failed = self._safe_len(self.execution_state.get_failed_steps())
        total = self._safe_len(self.plan.steps)

        # Count total files with safety checks
        total_created = sum(
            self._safe_len(e.files_created)
            for e in (self.execution_state.step_executions or {}).values()
        )
        total_modified = sum(
            self._safe_len(e.files_modified)
            for e in (self.execution_state.step_executions or {}).values()
        )

        logger.info(
            f"Execution complete: {completed}/{total} steps completed, "
            f"{failed} failed, {total_created} files created, {total_modified} modified"
        )

        summary = f"""**✅ Executor completed**

**Execution Summary:**
- Steps completed: {completed}/{total}
- Steps failed: {failed}
- Files created: {total_created}
- Files modified: {total_modified}

**Execution state saved to:**
`{self.state_path}`

**Next:** Review changes and test your implementation!
"""

        return summary
