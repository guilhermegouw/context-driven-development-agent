#!/usr/bin/env python3
"""Quick script to add comprehensive logging to Planner and Executor agents."""

import re
from pathlib import Path


# Logging statements to add at key points
LOGGING_ADDITIONS = {
    "planner.py": [
        {
            "after": "from typing import TYPE_CHECKING, Any, Optional",
            "add": "\nimport logging",
        },
        {
            "after": "if TYPE_CHECKING:\n    from ..session.chat_session import ChatSession",
            "add": "\n\nlogger = logging.getLogger(__name__)",
        },
        {
            "after": "    def initialize(self) -> str:",
            "add": '\n        logger.info(f"Initializing Planner agent for ticket: {self.target_path}")',
        },
        {
            "search": r"self\.spec = parse_ticket_spec\(self\.target_path\)",
            "add_after": '\n        logger.info(f"Loaded spec: {self.spec.title} (type: {self.spec.type})")',
        },
        {
            "search": r"if not self\.spec\.is_complete\(\):",
            "add_after": '\n            logger.warning("Spec is not complete, cannot generate plan")',
        },
        {
            "search": r'plan_path = self\.target_path\.parent / "plan\.md"',
            "add_after": '\n        logger.debug(f"Looking for existing plan at: {plan_path}")',
        },
        {
            "search": r"plan = await self\._generate_plan\(\)",
            "add_before": '        logger.info("Generating implementation plan via LLM")\n        ',
        },
        {
            "search": r"plan\.save\(plan_path\)",
            "add_after": '\n        logger.info(f"Saved plan to {plan_path} ({len(plan.steps)} steps)")',
        },
        {
            "search": r"except Exception as e:",
            "add_after": '\n            logger.error(f"Error in Planner: {e}", exc_info=True)',
        },
    ],
    "executor.py": [
        {
            "after": "from pathlib import Path",
            "add": "\nimport logging",
        },
        {
            "after": "if TYPE_CHECKING:\n    from ..session.chat_session import ChatSession",
            "add": "\n\nlogger = logging.getLogger(__name__)",
        },
        {
            "after": "    def initialize(self) -> str:",
            "add": '\n        logger.info(f"Initializing Executor agent for ticket: {self.target_path}")',
        },
        {
            "search": r"self\.plan = ImplementationPlan\.from_markdown",
            "add_after": '\n            logger.info(f"Loaded plan: {len(self.plan.steps)} steps")',
        },
        {
            "search": r"self\.execution_state = ExecutionState\.load\(self\.state_path\)",
            "add_after": '\n                logger.info(f"Resuming from saved state (step {self.execution_state.current_step})")',
        },
        {
            "search": r"self\.execution_state = ExecutionState\(",
            "add_before": '        logger.info("Starting new execution")\n        ',
        },
        {
            "search": r"async def process\(self, user_input: str\) -> str:",
            "add_after": '\n        logger.debug(f"Processing command: {user_input.strip()}")',
        },
        {
            "search": r"return self\._skip_current_step\(\)",
            "add_before": '            logger.info("User requested skip current step")\n            ',
        },
        {
            "search": r"return await self\._retry_current_step\(\)",
            "add_before": '            logger.info("User requested retry failed step")\n            ',
        },
        {
            "search": r"return self\._format_status\(\)",
            "add_before": '            logger.debug("User requested status")\n            ',
        },
        {
            "search": r"return await self\._execute_next_step\(\)",
            "add_before": '        logger.info("Executing next step")\n        ',
        },
        {
            "search": r"# All done!",
            "add_after": '\n            logger.info("All steps completed!")',
        },
        {
            "search": r"response = self\.session\.general_agent\.run\(",
            "add_before": '            logger.debug(f"Generating code for step {step.number} via LLM")\n            ',
        },
        {
            "search": r"files_changed = self\._apply_code_changes\(code_result\)",
            "add_after": "\n            logger.info(f\"Applied code changes: {len(files_changed.get('created', []))} created, {len(files_changed.get('modified', []))} modified\")",
        },
        {
            "search": r"self\.execution_state\.save\(self\.state_path\)",
            "add_after": '\n            logger.debug("Saved execution state")',
        },
        {
            "search": r"except Exception as e:",
            "add_after": '\n            logger.error(f"Error in Executor: {e}", exc_info=True)',
        },
    ],
}


def add_logging_to_file(filepath: Path, additions: list):
    """Add logging statements to a file."""
    print(f"\n📝 Processing {filepath.name}...")

    content = filepath.read_text()
    original_content = content
    modifications = 0

    for addition in additions:
        if "after" in addition:
            # Simple string replacement
            if addition["after"] in content:
                content = content.replace(
                    addition["after"], addition["after"] + addition["add"]
                )
                modifications += 1
                print(f"  ✓ Added after: {addition['after'][:50]}...")

        elif "search" in addition:
            # Regex search and add before/after
            pattern = addition["search"]
            matches = list(re.finditer(pattern, content))

            if matches:
                # Work backwards to preserve positions
                for match in reversed(matches):
                    pos = match.start()
                    if "add_before" in addition:
                        content = content[:pos] + addition["add_before"] + content[pos:]
                        modifications += 1
                    elif "add_after" in addition:
                        end_pos = match.end()
                        content = (
                            content[:end_pos]
                            + addition["add_after"]
                            + content[end_pos:]
                        )
                        modifications += 1

                print(
                    f"  ✓ Modified {len(matches)} occurrence(s) of: {pattern[:40]}..."
                )

    if modifications > 0:
        filepath.write_text(content)
        print(f"  ✅ Made {modifications} modifications to {filepath.name}")
    else:
        print(f"  ⚠️  No modifications made to {filepath.name}")

    return modifications


def main():
    """Add logging to Planner and Executor agents."""
    agents_dir = Path("src/cdd_agent/agents")

    if not agents_dir.exists():
        print(f"❌ Directory not found: {agents_dir}")
        print("   Run this script from the project root!")
        return

    total_mods = 0

    for filename, additions in LOGGING_ADDITIONS.items():
        filepath = agents_dir / filename
        if filepath.exists():
            mods = add_logging_to_file(filepath, additions)
            total_mods += mods
        else:
            print(f"⚠️  File not found: {filepath}")

    print(f"\n{'='*60}")
    print("✅ Logging additions complete!")
    print(f"   Total modifications: {total_mods}")
    print(f"{'='*60}")
    print("\n📋 Next steps:")
    print("1. Review the changes in planner.py and executor.py")
    print("2. Run: poetry run black src/cdd_agent/agents/")
    print("3. Run: poetry run ruff check src/cdd_agent/agents/")
    print("4. Test: poetry run cdd-agent chat --verbose")
    print("5. Check logs: tail -f ~/.cdd-agent/logs/*.log")


if __name__ == "__main__":
    main()
