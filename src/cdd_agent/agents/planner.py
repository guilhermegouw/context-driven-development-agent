"""Planner Agent - Generate implementation plans from refined specs.

This agent creates detailed, step-by-step implementation plans for tickets
that have been refined by the Socrates Agent.

Key Features:
- Loads project context from CDD.md/CLAUDE.md
- Scans actual codebase structure for accurate file paths
- Uses direct LLM call (no tool loop) for plan generation
- Validates generated plans against actual codebase
"""

import json
import logging
import subprocess
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

        # Context for planning (loaded during initialize)
        self.project_context: str = ""  # From CDD.md/CLAUDE.md
        self.codebase_structure: str = ""  # File tree
        self.relevant_files: dict[str, str] = {}  # path -> content snippets

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
        """Generate implementation plan using LLM with full project context.

        This method:
        1. Gathers project context (CDD.md, file structure, relevant files)
        2. Builds a comprehensive prompt with all context
        3. Makes a DIRECT LLM call (no tool loop)
        4. Parses and validates the JSON response

        Returns:
            Generated ImplementationPlan

        Raises:
            Exception: If plan generation fails
        """
        logger.info("Starting intelligent plan generation")

        # Step 1: Gather context
        logger.debug("Gathering project context...")
        self.project_context = self._load_project_context()
        self.codebase_structure = self._scan_codebase_structure()
        self.relevant_files = self._find_relevant_files()

        logger.info(
            f"Context gathered: {len(self.project_context)} chars project context, "
            f"{len(self.codebase_structure)} chars structure, "
            f"{len(self.relevant_files)} relevant files"
        )

        # Step 2: Build comprehensive prompt
        system_prompt = self._build_planning_prompt()
        user_message = self._build_planning_request()

        # Step 3: Make direct LLM call (no tools)
        try:
            if hasattr(self.session, "general_agent") and self.session.general_agent:
                agent = self.session.general_agent
                model = agent.provider_config.get_model(agent.model_tier)

                logger.info(f"Calling LLM directly for plan generation (model: {model})")

                # Direct API call - NO TOOLS
                response = agent.client.messages.create(
                    model=model,
                    max_tokens=4096,
                    messages=[{"role": "user", "content": user_message}],
                    system=system_prompt,
                    # No tools parameter - we want pure JSON output
                )

                # Extract text response
                response_text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        response_text += block.text
                    elif isinstance(block, dict) and "text" in block:
                        response_text += block["text"]

                logger.debug(f"LLM response length: {len(response_text)} chars")
                logger.debug(f"LLM response preview: {response_text[:500]}...")

                # Step 4: Parse JSON response
                ticket_slug = self.target_path.parent.name
                plan = self._parse_plan_response(
                    response_text,
                    ticket_slug=ticket_slug,
                )

                # Step 5: Validate plan
                validation_warnings = self._validate_plan(plan)
                if validation_warnings:
                    logger.warning(f"Plan validation warnings: {validation_warnings}")
                    # Add warnings to risks
                    plan.risks.extend(validation_warnings)

                logger.info(f"Successfully generated plan: {len(plan.steps)} steps")
                return plan

            else:
                logger.error("No LLM available for plan generation")
                raise RuntimeError(
                    "LLM not available. Please ensure you're authenticated with an LLM provider."
                )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            raise RuntimeError(
                f"LLM returned invalid JSON. Please try again.\nError: {e}"
            )
        except Exception as e:
            logger.error(f"Plan generation failed: {e}", exc_info=True)
            raise RuntimeError(f"Plan generation failed: {e}")

    def _build_planning_prompt(self) -> str:
        """Build comprehensive system prompt for plan generation.

        Includes project context, architecture patterns, and constraints.

        Returns:
            System prompt for LLM
        """
        return f'''You are an expert software architect creating implementation plans.

## YOUR ROLE

You create precise, actionable implementation plans that:
- Use ACTUAL file paths from the codebase (not generic paths)
- Follow the project's existing architecture and patterns
- Break work into clear, testable steps
- Identify real files that need modification

## PROJECT CONTEXT

{self.project_context if self.project_context else "No project context file (CDD.md/CLAUDE.md) found."}

## CODEBASE STRUCTURE

```
{self.codebase_structure}
```

## RELEVANT FILES

These files may need to be modified or referenced:
{self._format_relevant_files()}

## IMPORTANT GUIDELINES

1. **Use REAL paths** - Only reference files that exist in the codebase structure above
2. **Follow existing patterns** - Look at how similar features are implemented
3. **Be specific** - Don't say "update the config", say which config file
4. **Keep it focused** - Only include steps directly needed for this feature
5. **No time estimates** - The project doesn't use time estimates (per project guidelines)

## OUTPUT FORMAT

Respond with ONLY valid JSON (no markdown, no explanation):

{{
  "overview": "2-3 sentence description of the implementation approach",
  "steps": [
    {{
      "number": 1,
      "title": "Short step title",
      "description": "Detailed description of what to do and why",
      "complexity": "simple|medium|complex",
      "dependencies": [],
      "files_affected": ["actual/path/to/file.py"]
    }}
  ],
  "total_complexity": "simple|medium|complex",
  "risks": ["Potential risk or challenge"]
}}

Do NOT include:
- Markdown code blocks
- Explanatory text before or after the JSON
- Generic paths like "src/models/" - use actual paths
- Time estimates (not used in this project)
'''

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

    # =========================================================================
    # Context Gathering Methods (for intelligent planning)
    # =========================================================================

    def _load_project_context(self) -> str:
        """Load project context from CDD.md or CLAUDE.md.

        Returns:
            Project context content or empty string if not found
        """
        # Try CDD.md first (preferred), then CLAUDE.md (fallback)
        for filename in ["CDD.md", "CLAUDE.md"]:
            path = Path.cwd() / filename
            if path.exists():
                logger.info(f"Loading project context from {filename}")
                try:
                    content = path.read_text(encoding="utf-8")
                    # Truncate if too long (keep most important parts)
                    if len(content) > 8000:
                        logger.warning(f"{filename} is long ({len(content)} chars), truncating")
                        content = content[:8000] + "\n\n[... truncated ...]"
                    return content
                except Exception as e:
                    logger.error(f"Failed to read {filename}: {e}")
                    return ""

        logger.warning("No CDD.md or CLAUDE.md found in project root")
        return ""

    def _scan_codebase_structure(self) -> str:
        """Scan codebase structure using tree command.

        Returns:
            Tree output showing file structure
        """
        try:
            # Use tree command with reasonable depth and exclusions
            result = subprocess.run(
                [
                    "tree",
                    "-L", "4",  # 4 levels deep
                    "-I", "__pycache__|node_modules|.git|.venv|venv|*.pyc|.pytest_cache|.mypy_cache|dist|build|*.egg-info",
                    "--noreport",  # Don't show file count
                    str(Path.cwd())
                ],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                tree_output = result.stdout
                logger.info(f"Scanned codebase: {len(tree_output)} chars")

                # Truncate if too long
                if len(tree_output) > 4000:
                    lines = tree_output.split("\n")[:150]
                    tree_output = "\n".join(lines) + "\n[... truncated ...]"

                return tree_output
            else:
                logger.warning(f"tree command failed: {result.stderr}")
                return self._fallback_scan_structure()

        except FileNotFoundError:
            logger.warning("tree command not found, using fallback")
            return self._fallback_scan_structure()
        except subprocess.TimeoutExpired:
            logger.warning("tree command timed out")
            return self._fallback_scan_structure()
        except Exception as e:
            logger.error(f"Error scanning codebase: {e}")
            return self._fallback_scan_structure()

    def _fallback_scan_structure(self) -> str:
        """Fallback codebase scan using Python when tree is unavailable.

        Returns:
            Simple directory listing
        """
        output_lines = []
        root = Path.cwd()

        exclude_dirs = {
            "__pycache__", "node_modules", ".git", ".venv", "venv",
            ".pytest_cache", ".mypy_cache", "dist", "build"
        }

        def scan_dir(path: Path, prefix: str = "", depth: int = 0):
            if depth > 3:  # Max 4 levels
                return

            try:
                items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name))
                for i, item in enumerate(items):
                    if item.name.startswith(".") and item.name not in [".cdd"]:
                        continue
                    if item.name in exclude_dirs:
                        continue
                    if item.suffix == ".pyc":
                        continue

                    is_last = i == len(items) - 1
                    connector = "└── " if is_last else "├── "
                    output_lines.append(f"{prefix}{connector}{item.name}")

                    if item.is_dir():
                        extension = "    " if is_last else "│   "
                        scan_dir(item, prefix + extension, depth + 1)
            except PermissionError:
                pass

        output_lines.append(str(root.name))
        scan_dir(root)

        result = "\n".join(output_lines[:150])  # Limit lines
        logger.info(f"Fallback scan: {len(result)} chars")
        return result

    def _find_relevant_files(self) -> dict[str, str]:
        """Find files likely relevant to the spec based on keywords.

        Returns:
            Dict of file_path -> brief content description
        """
        relevant = {}

        if not self.spec:
            return relevant

        # Extract keywords from spec
        keywords = set()
        text_to_search = f"{self.spec.title} {self.spec.description}"

        # Common feature-related words to look for
        for word in text_to_search.lower().split():
            if len(word) > 3 and word.isalpha():
                keywords.add(word)

        # Also add specific tech terms
        tech_terms = ["cli", "command", "session", "chat", "agent", "tool", "config"]
        for term in tech_terms:
            if term in text_to_search.lower():
                keywords.add(term)

        logger.debug(f"Searching for files with keywords: {keywords}")

        # Search in src directory
        src_dir = Path.cwd() / "src"
        if not src_dir.exists():
            src_dir = Path.cwd()

        try:
            for py_file in src_dir.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue

                # Check if filename matches any keyword
                filename_lower = py_file.stem.lower()
                if any(kw in filename_lower for kw in keywords):
                    rel_path = py_file.relative_to(Path.cwd())
                    relevant[str(rel_path)] = f"Filename matches keywords"
                    continue

                # Quick scan of file content (first 50 lines)
                try:
                    with open(py_file, "r", encoding="utf-8") as f:
                        head = "".join(f.readline() for _ in range(50))

                    # Check for keyword matches in docstrings/comments
                    head_lower = head.lower()
                    matching_kw = [kw for kw in keywords if kw in head_lower]
                    if len(matching_kw) >= 2:  # At least 2 keyword matches
                        rel_path = py_file.relative_to(Path.cwd())
                        relevant[str(rel_path)] = f"Contains: {', '.join(matching_kw[:3])}"
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Error finding relevant files: {e}")

        # Limit to most relevant files
        if len(relevant) > 10:
            relevant = dict(list(relevant.items())[:10])

        logger.info(f"Found {len(relevant)} potentially relevant files")
        return relevant

    def _format_relevant_files(self) -> str:
        """Format relevant files for inclusion in prompt.

        Returns:
            Formatted string of relevant files
        """
        if not self.relevant_files:
            return "No specific files identified - refer to codebase structure above."

        lines = []
        for path, reason in self.relevant_files.items():
            lines.append(f"- `{path}` - {reason}")

        return "\n".join(lines)

    def _build_planning_request(self) -> str:
        """Build the user message containing the spec details.

        Returns:
            User message with spec information
        """
        ac_text = "\n".join(f"- {ac}" for ac in self.spec.acceptance_criteria)

        return f'''Please create an implementation plan for this feature:

## SPECIFICATION

**Title:** {self.spec.title}
**Type:** {self.spec.type}

**Description:**
{self.spec.description}

**Acceptance Criteria:**
{ac_text if ac_text else "None specified"}

**Technical Notes:**
{self.spec.technical_notes or "None provided"}

## YOUR TASK

Create a step-by-step implementation plan that:
1. Identifies the specific files that need to be created or modified
2. Describes what changes to make in each file
3. Orders steps logically with dependencies
4. Is realistic and actionable

Remember:
- Use ACTUAL file paths from the codebase structure
- Follow the project's existing patterns
- Output ONLY valid JSON'''

    def _parse_plan_response(self, response_text: str, ticket_slug: str) -> ImplementationPlan:
        """Parse LLM response into ImplementationPlan.

        Handles JSON extraction from potentially messy LLM output.

        Args:
            response_text: Raw LLM response
            ticket_slug: Ticket identifier

        Returns:
            Parsed ImplementationPlan

        Raises:
            json.JSONDecodeError: If JSON parsing fails
        """
        import re

        # Clean up response - remove markdown code blocks if present
        clean_text = response_text.strip()

        # Try to extract JSON from code blocks
        if "```" in clean_text:
            # Extract content between code blocks
            json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean_text, re.DOTALL)
            if json_match:
                clean_text = json_match.group(1)
            else:
                # Just strip the backticks
                clean_text = re.sub(r"```(?:json)?", "", clean_text).strip()

        # Parse JSON
        try:
            data = json.loads(clean_text)
        except json.JSONDecodeError:
            # Try to find JSON object in the text
            start = clean_text.find("{")
            end = clean_text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(clean_text[start:end])
            else:
                raise

        # Build steps
        steps = []
        for step_data in data.get("steps", []):
            steps.append(
                PlanStep(
                    number=step_data.get("number", len(steps) + 1),
                    title=step_data.get("title", "Untitled step"),
                    description=step_data.get("description", ""),
                    complexity=step_data.get("complexity", "medium"),
                    estimated_time=step_data.get("estimated_time", ""),
                    dependencies=step_data.get("dependencies", []),
                    files_affected=step_data.get("files_affected", []),
                )
            )

        return ImplementationPlan(
            ticket_slug=ticket_slug,
            ticket_title=self.spec.title,
            ticket_type=self.spec.type,
            overview=data.get("overview", ""),
            steps=steps,
            total_complexity=data.get("total_complexity", "medium"),
            total_estimated_time=data.get("total_estimated_time", ""),
            risks=data.get("risks", []),
        )

    def _validate_plan(self, plan: ImplementationPlan) -> list[str]:
        """Validate generated plan against codebase.

        Checks that file paths are reasonable and flags potential issues.

        Args:
            plan: Generated plan to validate

        Returns:
            List of warning messages (empty if valid)
        """
        warnings = []

        # Collect all file paths from steps
        all_paths = []
        for step in plan.steps:
            all_paths.extend(step.files_affected)

        # Check for generic/suspicious paths
        generic_patterns = [
            "src/models/",
            "src/api/",
            "src/ui/",
            "src/services/",
            "src/components/",
        ]

        for path in all_paths:
            # Check for generic paths
            for pattern in generic_patterns:
                if path == pattern or path.endswith("/"):
                    warnings.append(f"Generic path detected: '{path}' - may not exist")
                    break

            # Check if path exists (for existing files)
            if not path.endswith("/"):
                full_path = Path.cwd() / path
                # Only warn about existing files that don't exist
                # (new files are expected to not exist)
                if "create" not in path.lower() and "new" not in path.lower():
                    if not full_path.exists() and not any(
                        p in path for p in ["test_", "_test", "tests/"]
                    ):
                        # Check if parent directory exists
                        if not full_path.parent.exists():
                            warnings.append(
                                f"Path may not exist: '{path}' - parent directory not found"
                            )

        # Check for empty steps
        if not plan.steps:
            warnings.append("Plan has no steps!")

        # Check for very short plans on complex specs
        if len(plan.steps) < 2 and len(self.spec.acceptance_criteria) > 3:
            warnings.append(
                "Plan seems too simple for the spec complexity - review carefully"
            )

        return warnings
