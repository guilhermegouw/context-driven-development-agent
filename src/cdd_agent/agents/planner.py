"""Planner Agent - Generate implementation plans from refined specs.

This agent creates detailed, step-by-step implementation plans for tickets
that have been refined by the Socrates Agent.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from ..session.base_agent import BaseAgent
from ..utils.plan_model import ImplementationPlan, PlanStep
from ..utils.yaml_parser import parse_ticket_spec

if TYPE_CHECKING:
    from ..session.chat_session import ChatSession

logger = logging.getLogger(__name__)


class PlannerAgent(BaseAgent):
    """Generates implementation plans from refined ticket specifications.

    The agent:
    1. Loads refined spec (from Socrates)
    2. Checks spec completeness
    3. Generates step-by-step plan via LLM
    4. Saves plan.md to ticket directory
    5. Auto-exits when complete

    Example Session:
        [Planner]> Analyzing specification...
        Generated 7-step implementation plan.
        Estimated time: 6 hours
        Plan saved to: specs/tickets/feature-auth/plan.md
    """

    def __init__(
        self,
        target_path: Path,
        session: "ChatSession",
        provider_config: Any,
        tool_registry: Any,
    ):
        """Initialize Planner agent.

        Args:
            target_path: Path to ticket spec.yaml file
            session: Parent ChatSession instance
            provider_config: LLM provider configuration
            tool_registry: Available tools for agent
        """
        super().__init__(target_path, session, provider_config, tool_registry)

        self.name = "Planner"
        self.description = "Generate implementation plans from refined specs"

        # Agent state
        self.spec = None
        self.plan: Optional[ImplementationPlan] = None
        self.plan_path: Optional[Path] = None

    def initialize(self) -> str:
        """Load spec and generate implementation plan.

        Returns:
            Initial greeting with plan summary
        """
        logger.info(f"Initializing Planner agent for ticket: {self.target_path}")

        try:
            # 1. Load ticket spec
            self.spec = parse_ticket_spec(self.target_path)
            logger.info(f"Loaded spec: {self.spec.title} (type: {self.spec.type})")

            # 2. Check if spec is complete
            if not self.spec.is_complete():
                vague_areas = self.spec.get_vague_areas()
                vague_count = len(vague_areas)
                logger.warning(f"Spec incomplete ({vague_count} vague areas)")
                slug_hint = self.spec.title.lower().replace(" ", "-")
                return (
                    "**⚠️  Specification is incomplete**\n\n"
                    "The ticket spec needs more detail before planning.\n\n"
                    "**Issues:**\n"
                    + "\n".join(f"- {area}" for area in vague_areas)
                    + "\n\n"
                    f"Please run `/socrates {slug_hint}` "
                    f"to refine the specification first."
                )

            # 3. Check if plan already exists
            self.plan_path = self.target_path.parent / "plan.md"
            logger.debug(f"Checking for existing plan at: {self.plan_path}")

            if self.plan_path.exists():
                # Load existing plan
                logger.info("Found existing plan, loading it")
                content = self.plan_path.read_text()
                ticket_slug = self.target_path.parent.name
                self.plan = ImplementationPlan.from_markdown(content, ticket_slug)
                steps_count = len(self.plan.steps)
                logger.info(f"Loaded plan: {steps_count} steps")

                return (
                    f"**Hello! I'm the Planner.**\n\n"
                    f"A plan already exists for this ticket.\n\n"
                    f"**Existing Plan:**\n"
                    f"- Steps: {len(self.plan.steps)}\n"
                    f"- Complexity: {self.plan.total_complexity}\n"
                    f"- Estimated Time: {self.plan.total_estimated_time}\n\n"
                    f"You can:\n"
                    f"- Type 'regenerate' to create a new plan\n"
                    f"- Type 'exit' to keep the existing plan\n"
                    f"- Ask me to modify specific steps"
                )

            # 4. Generate new plan
            logger.info("No existing plan found, will generate new plan")
            greeting = (
                f"**Hello! I'm the Planner.**\n\n"
                f"Analyzing specification: *{self.spec.title}*\n\n"
                f"Generating implementation plan...\n\n"
            )

            # This will be displayed before the plan generation
            return greeting

        except Exception as e:
            logger.error(f"Failed to initialize Planner: {e}", exc_info=True)
            return (
                f"**Error loading ticket specification:**\n\n"
                f"```\n{str(e)}\n```\n\n"
                f"Please check that `{self.target_path}` exists and is valid."
            )

    async def process(self, user_input: str) -> str:
        """Process user input for plan generation or modification.

        Args:
            user_input: User's message

        Returns:
            Response or generated plan
        """
        logger.debug(f"Processing user input: {user_input.strip()}")
        user_input = user_input.strip().lower()

        # Handle regeneration request
        if user_input == "regenerate" and self.plan_path and self.plan_path.exists():
            # Generate new plan
            logger.info("User requested plan regeneration")
            self.plan = await self._generate_plan()
            self.plan_path.write_text(self.plan.to_markdown())
            logger.info(f"Regenerated and saved plan to {self.plan_path}")
            self.mark_complete()
            return self._format_plan_summary()

        # If no plan exists yet, generate it now
        if not self.plan:
            logger.info("Generating implementation plan")
            try:
                self.plan = await self._generate_plan()
                logger.info(f"Generated plan with {len(self.plan.steps)} steps")

                # Save plan
                self.plan_path = self.target_path.parent / "plan.md"
                self.plan_path.write_text(self.plan.to_markdown())
                logger.info(f"Saved plan to {self.plan_path}")

                # Mark complete
                self.mark_complete()

                return self._format_plan_summary()

            except Exception as e:
                logger.error(f"Error generating plan: {e}", exc_info=True)
                return (
                    f"**Error generating plan:**\n\n"
                    f"```\n{str(e)}\n```\n\n"
                    f"Please try again or type 'exit' to leave."
                )

        # Plan exists, handle modification requests
        # TODO: Implement plan modification via LLM
        return (
            "Plan modification not yet implemented. "
            "Type 'regenerate' to create a new plan or 'exit' to finish."
        )

    def finalize(self) -> str:
        """Save final plan and return completion summary.

        Returns:
            Completion message with statistics
        """
        logger.info("Finalizing Planner session")

        if not self.plan:
            logger.warning("Finalize called but no plan generated")
            return "**Planner session ended** (no plan generated)"

        try:
            # Ensure plan is saved
            if self.plan_path:
                self.plan_path.write_text(self.plan.to_markdown())
                logger.info(f"Ensured plan is saved to {self.plan_path}")

            logger.info(
                f"Plan finalized: {len(self.plan.steps)} steps, "
                f"{self.plan.total_complexity} complexity, "
                f"{self.plan.total_estimated_time} time"
            )

            summary = (
                f"**✅ Planner completed**\n\n"
                f"**Implementation plan saved to:**\n"
                f"`{self.plan_path}`\n\n"
                f"**Plan Summary:**\n"
                f"- Steps: {len(self.plan.steps)}\n"
                f"- Complexity: {self.plan.total_complexity}\n"
                f"- Estimated Time: {self.plan.total_estimated_time}\n\n"
            )

            if self.plan.risks:
                summary += f"**Risks Identified:** {len(self.plan.risks)}\n\n"

            summary += f"**Ready for execution!** Use `/exec {self.plan.ticket_slug}`\n"

            return summary

        except Exception as e:
            logger.error(f"Error finalizing Planner: {e}", exc_info=True)
            return (
                f"**⚠️  Planner completed with errors**\n\n"
                f"Error saving plan: {str(e)}\n\n"
                f"Plan may not have been saved to `{self.plan_path}`"
            )

    async def _generate_plan(self) -> ImplementationPlan:
        """Generate implementation plan using LLM.

        Returns:
            Generated ImplementationPlan

        Raises:
            Exception: If plan generation fails
        """
        logger.debug("Building LLM prompt for plan generation")
        # Build LLM prompt
        prompt = self._build_planning_prompt()

        # Call LLM
        try:
            if hasattr(self.session, "general_agent") and self.session.general_agent:
                logger.debug("Calling LLM for plan generation")
                response = self.session.general_agent.run(
                    message="Generate implementation plan",
                    system_prompt=prompt,
                )
                logger.debug(f"Received LLM response (length: {len(response)})")

                # Parse JSON response
                ticket_slug = self.target_path.parent.name
                plan = ImplementationPlan.from_json(
                    response,
                    ticket_slug=ticket_slug,
                    ticket_title=self.spec.title,
                    ticket_type=self.spec.type,
                )
                logger.info(f"Successfully parsed LLM plan: {len(plan.steps)} steps")

                return plan
            else:
                # Fallback: Generate basic heuristic plan
                logger.info("No LLM available, using heuristic plan")
                return self._generate_heuristic_plan()

        except Exception as e:
            # Fallback on error
            logger.warning(
                f"LLM plan generation failed ({e}), falling back to heuristic"
            )
            return self._generate_heuristic_plan()

    def _build_planning_prompt(self) -> str:
        """Build LLM prompt for plan generation.

        Returns:
            System prompt for LLM
        """
        ac_text = "\n".join(f"- {ac}" for ac in self.spec.acceptance_criteria)

        return f"""You are an expert software architect creating \
implementation plans.

Given this ticket specification:

**Title:** {self.spec.title}
**Type:** {self.spec.type}

**Description:**
{self.spec.description}

**Acceptance Criteria:**
{ac_text or "None specified"}

**Technical Notes:**
{self.spec.technical_notes or "None provided"}

Create a detailed implementation plan with:
1. High-level approach overview (2-3 sentences)
2. Step-by-step implementation tasks (5-10 steps)
3. Complexity estimate for each step (simple/medium/complex)
4. Time estimates (15min/30min/1hr/2hr/4hr)
5. File paths that will be affected
6. Dependencies between steps (by step number)
7. Potential risks or challenges

**IMPORTANT:** Respond ONLY with valid JSON in this exact structure:

{{
  "overview": "Brief description of the implementation approach",
  "steps": [
    {{
      "number": 1,
      "title": "Step title",
      "description": "Detailed description of what to do",
      "complexity": "simple",
      "estimated_time": "30 min",
      "dependencies": [],
      "files_affected": ["path/to/file.py"]
    }}
  ],
  "total_complexity": "medium",
  "total_estimated_time": "4 hours",
  "risks": ["Risk description 1", "Risk description 2"]
}}

Do not include any text outside the JSON structure."""

    def _generate_heuristic_plan(self) -> ImplementationPlan:
        """Generate basic plan using heuristics (fallback).

        Returns:
            Basic ImplementationPlan
        """
        logger.info(f"Generating heuristic plan for ticket type: {self.spec.type}")
        ticket_slug = self.target_path.parent.name

        # Create simple linear plan based on ticket type
        steps = []

        if self.spec.type == "feature":
            steps = [
                PlanStep(
                    number=1,
                    title="Design data models and schemas",
                    description=(
                        f"Design and implement data models for {self.spec.title}"
                    ),
                    complexity="medium",
                    estimated_time="1 hour",
                    dependencies=[],
                    files_affected=["src/models/"],
                ),
                PlanStep(
                    number=2,
                    title="Implement core logic",
                    description=f"Implement main functionality for {self.spec.title}",
                    complexity="medium",
                    estimated_time="2 hours",
                    dependencies=[1],
                    files_affected=["src/"],
                ),
                PlanStep(
                    number=3,
                    title="Add API endpoints or interfaces",
                    description="Create public API or user interface",
                    complexity="medium",
                    estimated_time="1 hour",
                    dependencies=[2],
                    files_affected=["src/api/", "src/ui/"],
                ),
                PlanStep(
                    number=4,
                    title="Write tests",
                    description="Comprehensive test coverage",
                    complexity="medium",
                    estimated_time="1.5 hours",
                    dependencies=[3],
                    files_affected=["tests/"],
                ),
                PlanStep(
                    number=5,
                    title="Update documentation",
                    description="Add or update relevant documentation",
                    complexity="simple",
                    estimated_time="30 min",
                    dependencies=[4],
                    files_affected=["README.md", "docs/"],
                ),
            ]
        elif self.spec.type == "bug":
            steps = [
                PlanStep(
                    number=1,
                    title="Reproduce and diagnose issue",
                    description="Reproduce bug and identify root cause",
                    complexity="medium",
                    estimated_time="1 hour",
                    dependencies=[],
                    files_affected=[],
                ),
                PlanStep(
                    number=2,
                    title="Implement fix",
                    description="Fix the identified issue",
                    complexity="medium",
                    estimated_time="1 hour",
                    dependencies=[1],
                    files_affected=["src/"],
                ),
                PlanStep(
                    number=3,
                    title="Add regression test",
                    description="Add test to prevent future regressions",
                    complexity="simple",
                    estimated_time="30 min",
                    dependencies=[2],
                    files_affected=["tests/"],
                ),
                PlanStep(
                    number=4,
                    title="Verify fix",
                    description="Verify fix resolves the issue",
                    complexity="simple",
                    estimated_time="30 min",
                    dependencies=[3],
                    files_affected=[],
                ),
            ]
        else:  # refactor, chore, doc
            steps = [
                PlanStep(
                    number=1,
                    title="Plan refactoring approach",
                    description=f"Design refactoring strategy for {self.spec.title}",
                    complexity="simple",
                    estimated_time="30 min",
                    dependencies=[],
                    files_affected=[],
                ),
                PlanStep(
                    number=2,
                    title="Implement changes",
                    description="Execute the planned changes",
                    complexity="medium",
                    estimated_time="2 hours",
                    dependencies=[1],
                    files_affected=["src/"],
                ),
                PlanStep(
                    number=3,
                    title="Verify tests still pass",
                    description="Ensure no regressions",
                    complexity="simple",
                    estimated_time="30 min",
                    dependencies=[2],
                    files_affected=["tests/"],
                ),
            ]

        plan = ImplementationPlan(
            ticket_slug=ticket_slug,
            ticket_title=self.spec.title,
            ticket_type=self.spec.type,
            overview=f"Basic implementation plan for {self.spec.title}. "
            f"Generated using heuristic fallback.",
            steps=steps,
            total_complexity="medium",
            total_estimated_time=self._calculate_total_time(steps),
            risks=["This plan was generated using basic heuristics - review carefully"],
        )
        logger.info(
            f"Generated heuristic plan: {len(steps)} steps, {plan.total_estimated_time}"
        )
        return plan

    def _calculate_total_time(self, steps: list[PlanStep]) -> str:
        """Calculate total estimated time from steps.

        Args:
            steps: List of plan steps

        Returns:
            Total time estimate as string
        """
        total_minutes = 0

        for step in steps:
            time_str = step.estimated_time.lower()
            if "min" in time_str:
                minutes = int(time_str.split()[0])
                total_minutes += minutes
            elif "hour" in time_str:
                hours = float(time_str.split()[0])
                total_minutes += int(hours * 60)

        if total_minutes < 60:
            return f"{total_minutes} min"
        else:
            hours = total_minutes / 60
            if hours == int(hours):
                return f"{int(hours)} hours"
            else:
                return f"{hours:.1f} hours"

    def _format_plan_summary(self) -> str:
        """Format plan summary for display.

        Returns:
            Formatted summary string
        """
        if not self.plan:
            return "No plan generated"

        summary = f"""**Implementation Plan Created:**

📋 **Overview:** {len(self.plan.steps)}-step implementation
⏱️  **Estimated Time:** {self.plan.total_estimated_time}
🔧 **Complexity:** {self.plan.total_complexity.title()}

**Steps:**
"""

        for step in self.plan.steps:
            summary += f"{step.number}. {step.title} ({step.estimated_time})\n"

        summary += f"\n**Plan saved to:**\n`{self.plan_path}`\n\n"

        if self.plan.risks:
            summary += (
                f"⚠️  **{len(self.plan.risks)} risk(s) identified** "
                f"- review plan.md\n\n"
            )

        summary += f"✅ Ready for execution! Use `/exec {self.plan.ticket_slug}`"

        return summary
