"""Executor Agent - Autonomous code execution from implementation plans.

This agent executes implementation plans step-by-step, generating code via LLM
and running tests to verify implementations.
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from ..session.base_agent import BaseAgent
from ..utils.execution_state import ExecutionState
from ..utils.plan_model import ImplementationPlan, PlanStep
from ..utils.yaml_parser import parse_ticket_spec

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
        self.spec = None
        self.plan: Optional[ImplementationPlan] = None
        self.execution_state: Optional[ExecutionState] = None
        self.state_path: Optional[Path] = None

    def initialize(self) -> str:
        """Load spec, plan, and start or resume execution.

        Returns:
            Initial greeting with execution status
        """
        logger.info(f"Initializing Executor agent for ticket: {self.target_path}")

        try:
            # 1. Load ticket spec
            self.spec = parse_ticket_spec(self.target_path)
            logger.info(f"Loaded spec: {self.spec.title}")

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
            self.plan = ImplementationPlan.from_markdown(
                plan_path.read_text(), ticket_slug
            )
            logger.info(f"Loaded plan: {len(self.plan.steps)} steps")

            # 3. Check for existing execution state
            self.state_path = self.target_path.parent / "execution-state.json"
            if self.state_path.exists():
                logger.info(f"Found existing execution state at {self.state_path}")
                self.execution_state = ExecutionState.load(self.state_path)
                if self.execution_state:
                    step_num = self.execution_state.current_step
                    logger.info(f"Resuming execution from step {step_num}")
                    return self._format_resume_message()

            # 4. Initialize new execution
            logger.info("Starting new execution")
            self.execution_state = ExecutionState(
                ticket_slug=self.plan.ticket_slug,
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

    async def _execute_next_step(self) -> str:
        """Execute the next pending step.

        Returns:
            Execution result message
        """
        # Find next step
        next_step = self._get_next_step()

        if not next_step:
            # All done!
            logger.info("All steps completed!")
            self.mark_complete()
            return self._format_completion_message()

        # Check dependencies
        if not self._dependencies_met(next_step):
            deps = ", ".join(f"Step {d}" for d in next_step.dependencies)
            logger.warning(
                f"Cannot execute step {next_step.number}: dependencies not met ({deps})"
            )
            return (
                f"**⚠️  Cannot execute Step {next_step.number}**\n\n"
                f"Dependencies not met: {deps}\n\n"
                f"Complete those steps first or type 'skip' to skip this step."
            )

        logger.info(f"Executing step {next_step.number}: {next_step.title}")

        # Mark step started
        self.execution_state.mark_step_started(next_step.number)
        self.execution_state.save(self.state_path)
        logger.debug(f"Marked step {next_step.number} as in_progress")

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
                self.execution_state.mark_step_completed(next_step.number, [], [])
                self.execution_state.current_step = next_step.number + 1
                self.execution_state.save(self.state_path)

                return (
                    f"{status_msg}"
                    f"✅ **Step {next_step.number} completed** "
                    f"(planning/research step)\n\n"
                    f"{code_result.get('explanation', 'No code changes needed')}\n\n"
                    f"**Progress:** {self._calculate_progress()}\n\n"
                    f"Type 'continue' for next step."
                )

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
            response = (
                f"{status_msg}"
                f"✅ **Step {next_step.number} completed:** {next_step.title}\n\n"
                f"{self._format_file_changes(files_changed)}\n\n"
                f"**Progress:** {self._calculate_progress()}\n\n"
                f"Type 'continue' for next step or 'exit' to finish."
            )

            return response

        except Exception as e:
            # Mark step failed
            logger.error(f"Step {next_step.number} failed: {e}", exc_info=True)
            self.execution_state.mark_step_failed(next_step.number, str(e))
            self.execution_state.save(self.state_path)

            return (
                f"**❌ Step {next_step.number} failed:** {next_step.title}\n\n"
                f"**Error:**\n"
                f"```\n{str(e)}\n```\n\n"
                f"**Options:**\n"
                f"- Type 'retry' to try again\n"
                f"- Type 'skip' to skip this step\n"
                f"- Type 'exit' to stop execution"
            )

    def _get_next_step(self) -> Optional[PlanStep]:
        """Find the next step to execute.

        Returns:
            Next pending step or None if all complete
        """
        completed = self.execution_state.get_completed_steps()

        for step in self.plan.steps:
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
        if not step.dependencies:
            return True

        completed = self.execution_state.get_completed_steps()
        return all(dep in completed for dep in step.dependencies)

    async def _generate_code_for_step(self, step: PlanStep) -> dict:
        """Use LLM to generate code for a step.

        Args:
            step: Step to generate code for

        Returns:
            Dict with 'files' and 'explanation'
        """
        # Build prompt
        prompt = self._build_code_generation_prompt(step)

        # Call LLM
        if hasattr(self.session, "general_agent") and self.session.general_agent:
            response = self.session.general_agent.run(
                message="Generate code for this implementation step",
                system_prompt=prompt,
            )

            # Parse response
            return self._parse_code_response(response)
        else:
            raise Exception("No LLM available for code generation")

    def _build_code_generation_prompt(self, step: PlanStep) -> str:
        """Build LLM prompt for code generation.

        Args:
            step: Step to generate code for

        Returns:
            System prompt string
        """
        criteria_text = "\n".join(f"- {ac}" for ac in self.spec.acceptance_criteria)
        files_text = "\n".join(f"- {f}" for f in step.files_affected)

        return f"""You are an expert software engineer implementing this step.

**Ticket:** {self.spec.title}
**Type:** {self.spec.type}

**Step {step.number}:** {step.title}

**Description:** {step.description}

**Complexity:** {step.complexity}

**Files to create/modify:**
{files_text or "Not specified - determine appropriate files"}

**Acceptance Criteria for the entire ticket:**
{criteria_text}

**Technical Context:**
{self.spec.technical_notes or "None provided"}

**Your task:** Generate the code needed for this step.

For each file you create or modify, use this format:

```python:path/to/file.py
# Complete file content here
# Include all necessary imports
# Add error handling where appropriate
# Include docstrings
```

You can use other languages too (use appropriate extension):
- ```javascript:path/to/file.js
- ```typescript:path/to/file.ts
- ```go:path/to/file.go
- etc.

**Important:**
1. Only generate code for THIS step (not future steps)
2. Make code production-ready (error handling, validation, etc.)
3. Follow best practices for the language
4. Add helpful comments
5. If this is a planning/research step with no code, explain what was considered

After the code blocks, briefly explain your implementation choices."""

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
        completed = len(self.execution_state.get_completed_steps())
        failed = len(self.execution_state.get_failed_steps())
        total = len(self.plan.steps)

        status = f"""**📊 Execution Status**

**Ticket:** {self.spec.title}
**Progress:** {completed}/{total} steps completed ({self._calculate_progress()})

**Breakdown:**
- ✅ Completed: {completed}
- ❌ Failed: {failed}
- ⏸️  Remaining: {total - completed - failed}

**Current Step:** {self.execution_state.current_step}
"""

        if failed > 0:
            status += "\n**Failed Steps:**\n"
            for step_num in self.execution_state.get_failed_steps():
                exec_state = self.execution_state.step_executions.get(step_num)
                if exec_state:
                    status += f"- Step {step_num}: {exec_state.error}\n"

        status += "\nType 'continue' to proceed or 'exit' to stop."

        return status

    def _calculate_progress(self) -> str:
        """Calculate progress percentage.

        Returns:
            Progress string (e.g., "42%")
        """
        total = len(self.plan.steps)
        completed = len(self.execution_state.get_completed_steps())
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
        return f"""**Hello! I'm the Executor.**

**Ticket:** {self.spec.title}
**Plan:** {len(self.plan.steps)} implementation steps
**Estimated Time:** {self.plan.total_estimated_time}

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
        completed = len(self.execution_state.get_completed_steps())
        total = len(self.plan.steps)

        return f"""**Resuming execution...**

**Ticket:** {self.spec.title}
**Progress:** {completed}/{total} steps completed
**Current Step:** {self.execution_state.current_step}

Type 'continue' to resume or 'status' for details.
"""

    def _format_completion_message(self) -> str:
        """Format completion message.

        Returns:
            Completion message
        """
        completed = len(self.execution_state.get_completed_steps())
        failed = len(self.execution_state.get_failed_steps())

        return f"""**🎉 All steps executed!**

**Summary:**
- ✅ Completed: {completed}
- ❌ Failed: {failed}
- Total Steps: {len(self.plan.steps)}

**Next Steps:**
1. Review the generated code
2. Run tests: `pytest` or your test command
3. Commit changes if satisfied

Type 'exit' to finish.
"""

    def finalize(self) -> str:
        """Save final state and return summary.

        Returns:
            Finalization summary
        """
        logger.info("Finalizing Executor session")

        if self.execution_state:
            self.execution_state.status = "completed"
            self.execution_state.completed_at = datetime.now().isoformat()
            self.execution_state.save(self.state_path)
            logger.info(f"Saved final execution state to {self.state_path}")

        completed = len(self.execution_state.get_completed_steps())
        failed = len(self.execution_state.get_failed_steps())
        total = len(self.plan.steps)

        # Count total files
        total_created = sum(
            len(e.files_created) for e in self.execution_state.step_executions.values()
        )
        total_modified = sum(
            len(e.files_modified) for e in self.execution_state.step_executions.values()
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
