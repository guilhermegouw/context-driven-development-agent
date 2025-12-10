"""Commit slash command - Automated git commit with AI-generated messages.

This command analyzes staged changes and generates conventional commit messages,
with interactive choice selection for accept/edit/abort actions.
"""

import logging
import subprocess
from typing import Callable
from typing import Optional

from .base import BaseSlashCommand


logger = logging.getLogger(__name__)

# Type alias for choice callback
ChoiceCallback = Callable[[str, list, Optional[Callable]], None]


class CommitCommand(BaseSlashCommand):
    """Automated git commit with conventional commit message generation.

    This command:
    1. Analyzes staged changes via git diff --cached
    2. Generates a conventional commit message using the LLM
    3. Shows interactive choices: Accept, Edit, Abort
    4. Executes git commit when approved

    Usage:
        /commit           - Generate commit message for staged changes
        /commit --push    - Commit and push after approval
        /commit --abort   - Unstage all files
    """

    # Class-level pending commit state for TUI interaction
    _pending_commit: Optional["CommitCommand"] = None

    def __init__(self):
        """Initialize command metadata."""
        super().__init__()
        self.name = "commit"
        self.description = "Generate conventional commit message for staged changes"
        self.usage = "[--push] [--abort]"
        self.examples = [
            "/commit",
            "/commit --push",
            "/commit --abort",
        ]
        # State for commit flow
        self._current_message: str = ""
        self._staged_files: list[dict] = []  # List of {path, insertions, deletions}
        self._staged_diff: str = ""  # Keep diff for LLM context
        self._should_push: bool = False
        self._awaiting_choice: bool = False
        # Callback for showing choices in TUI
        self._choice_callback: Optional[ChoiceCallback] = None

    async def execute(self, args: str) -> str:
        """Execute the /commit command.

        Args:
            args: Command arguments (--push, --abort, or action response)

        Returns:
            Result message with commit status or formatted proposal
        """
        logger.info(f"Executing /commit command with args: {args}")

        args_lower = args.strip().lower()

        # Handle --abort flag
        if "--abort" in args_lower:
            return await self._handle_abort()

        # Handle --push flag
        if "--push" in args_lower:
            self._should_push = True
            args = args.replace("--push", "").replace("--Push", "").strip()

        # Handle user action responses (from TUI or text input)
        if self._awaiting_choice and args.strip():
            return await self._handle_action(args.strip())

        # Start fresh commit flow
        return await self._start_commit_flow()

    async def _start_commit_flow(self) -> str:
        """Start the commit flow by analyzing staged changes."""
        # Check if there are staged changes
        if not self._has_staged_changes():
            return (
                "**No staged changes found.**\n\n"
                "Use `git add <files>` to stage changes first, then run `/commit`."
            )

        # Get staged file list with stats
        self._staged_files = self._get_staged_files_with_stats()
        if not self._staged_files:
            return "**Error:** Failed to get staged file information."

        # Get diff for LLM context (but don't display it)
        self._staged_diff = self._get_staged_diff()

        # Generate commit message using the session's agent
        self._current_message = await self._generate_commit_message()

        # Check if we're in TUI mode with interactive selection
        tui_app = self._get_tui_app()
        if tui_app is not None:
            # Use TUI's interactive selection
            return await self._interactive_commit_flow(tui_app)

        # Fallback to text-based flow
        self._awaiting_choice = True
        CommitCommand._pending_commit = self
        return self._format_proposal()

    def _get_tui_app(self):
        """Get the TUI app if running in TUI mode."""
        if self.session and hasattr(self.session, "_tui_app"):
            return self.session._tui_app
        return None

    async def _interactive_commit_flow(self, tui_app) -> str:
        """Run commit flow with TUI interactive selection."""
        import asyncio

        while True:
            # Show file list in chat first
            proposal = self._format_proposal_for_tui()

            # Get user choice via TUI selector (run in thread to not block)
            loop = asyncio.get_event_loop()
            choice = await loop.run_in_executor(
                None,
                tui_app.show_commit_selection,
                self._current_message,
                self._staged_files,
                self._should_push,
            )

            if choice == "accept":
                return await self._execute_commit()
            elif choice == "cancel":
                return await self._handle_abort()
            elif choice == "edit":
                # For edit, we need to get revision instructions
                # Return a prompt and set state for next input
                self._awaiting_choice = True
                CommitCommand._pending_commit = self
                return (
                    f"{proposal}\n\n"
                    "**Enter your revision instructions:**\n\n"
                    "Examples:\n"
                    "  • `use feat type instead of chore`\n"
                    "  • `add (auth) scope`\n"
                    "  • `make it shorter`"
                )

    def _format_proposal_for_tui(self) -> str:
        """Format proposal for TUI display (without action line)."""
        file_lines = []
        total_insertions = 0
        total_deletions = 0

        for file_info in self._staged_files:
            path = file_info["path"]
            insertions = file_info.get("insertions", 0)
            deletions = file_info.get("deletions", 0)
            total_insertions += insertions
            total_deletions += deletions

            stats_parts = []
            if insertions > 0:
                stats_parts.append(f"+{insertions}")
            if deletions > 0:
                stats_parts.append(f"-{deletions}")
            stats = f" ({', '.join(stats_parts)})" if stats_parts else ""
            file_lines.append(f"  • {path}{stats}")

        files_display = "\n".join(file_lines)

        file_count = len(self._staged_files)
        summary = f"{file_count} file{'s' if file_count != 1 else ''}"
        if total_insertions > 0 or total_deletions > 0:
            summary += f" | +{total_insertions} -{total_deletions}"

        return (
            f"**Proposed commit message:**\n\n"
            f"```\n{self._current_message}\n```\n\n"
            f"**Staged files** ({summary}):\n{files_display}"
        )

    def _format_proposal(self) -> str:
        """Format the commit message proposal for display."""
        # Format file list with stats
        file_lines = []
        total_insertions = 0
        total_deletions = 0

        for file_info in self._staged_files:
            path = file_info["path"]
            insertions = file_info.get("insertions", 0)
            deletions = file_info.get("deletions", 0)
            total_insertions += insertions
            total_deletions += deletions

            # Format: filename (+insertions, -deletions)
            stats_parts = []
            if insertions > 0:
                stats_parts.append(f"+{insertions}")
            if deletions > 0:
                stats_parts.append(f"-{deletions}")
            stats = f" ({', '.join(stats_parts)})" if stats_parts else ""
            file_lines.append(f"  • {path}{stats}")

        files_display = "\n".join(file_lines)

        # Summary line
        file_count = len(self._staged_files)
        summary = f"{file_count} file{'s' if file_count != 1 else ''}"
        if total_insertions > 0 or total_deletions > 0:
            summary += f" | +{total_insertions} -{total_deletions}"

        push_note = " and push" if self._should_push else ""

        return (
            f"**Proposed commit message:**\n\n"
            f"```\n{self._current_message}\n```\n\n"
            f"**Staged files** ({summary}):\n{files_display}\n\n"
            f"---\n"
            f"**Actions:** "
            f"`[A]ccept` to commit{push_note} • "
            f"`[E]dit` to revise message • "
            f"`[C]ancel` to abort"
        )

    async def _handle_action(self, action: str) -> str:
        """Handle user action from choice selection or text input.

        Args:
            action: Action string - 'accept'/'a', 'edit'/'e', 'cancel'/'c',
                   or revision text if starts with 'edit:'
        """
        action_lower = action.lower().strip()

        # Handle accept
        if action_lower in ["accept", "a", "yes", "y", "ok"]:
            self._awaiting_choice = False
            CommitCommand._pending_commit = None
            return await self._execute_commit()

        # Handle cancel/abort
        if action_lower in ["cancel", "c", "abort", "no", "n"]:
            self._awaiting_choice = False
            CommitCommand._pending_commit = None
            return await self._handle_abort()

        # Handle edit - if just 'edit' or 'e', prompt for instructions
        if action_lower in ["edit", "e"]:
            return (
                "**Enter your revision instructions:**\n\n"
                "Examples:\n"
                "  • `use feat type instead of chore`\n"
                "  • `add (auth) scope`\n"
                "  • `make it shorter`\n"
                "  • `mention the bug fix for login`"
            )

        # Handle revision instructions (any other text)
        return await self._revise_message(action)

    async def _revise_message(self, instructions: str) -> str:
        """Revise the commit message based on user instructions."""
        logger.info(f"Revising commit message with instructions: {instructions}")

        # Generate revised message
        self._current_message = await self._generate_revised_message(instructions)

        # Keep awaiting choice
        self._awaiting_choice = True
        CommitCommand._pending_commit = self

        return self._format_proposal()

    async def _execute_commit(self) -> str:
        """Execute the git commit (and optionally push)."""
        try:
            # Execute commit
            result = subprocess.run(
                ["git", "commit", "-m", self._current_message],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return (
                    f"**Commit failed:**\n\n"
                    f"```\n{result.stderr or result.stdout}\n```"
                )

            commit_output = result.stdout.strip()

            # Optionally push
            if self._should_push:
                push_result = subprocess.run(
                    ["git", "push"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                if push_result.returncode != 0:
                    return (
                        f"**Committed but push failed:**\n\n"
                        f"Commit: `{self._current_message}`\n\n"
                        f"Push error:\n```\n{push_result.stderr}\n```"
                    )

                return (
                    f"**Successfully committed and pushed!**\n\n"
                    f"```\n{self._current_message}\n```\n\n"
                    f"{commit_output}"
                )

            return (
                f"**Successfully committed!**\n\n"
                f"```\n{self._current_message}\n```\n\n"
                f"{commit_output}\n\n"
                f"*Use `git push` to push changes to remote.*"
            )

        except subprocess.TimeoutExpired:
            return "**Error:** Git command timed out."
        except Exception as e:
            logger.error(f"Commit failed: {e}", exc_info=True)
            return f"**Error during commit:**\n\n```\n{str(e)}\n```"
        finally:
            # Reset state
            self._reset_state()

    async def _handle_abort(self) -> str:
        """Handle abort - unstage all files."""
        try:
            result = subprocess.run(
                ["git", "reset"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                return f"**Error unstaging files:**\n\n" f"```\n{result.stderr}\n```"

            return "**Commit aborted.** All files have been unstaged."

        except Exception as e:
            logger.error(f"Abort failed: {e}", exc_info=True)
            return f"**Error during abort:**\n\n```\n{str(e)}\n```"
        finally:
            self._reset_state()

    def _reset_state(self):
        """Reset command state."""
        self._current_message = ""
        self._staged_files = []
        self._staged_diff = ""
        self._should_push = False
        self._awaiting_choice = False
        CommitCommand._pending_commit = None

    def _has_staged_changes(self) -> bool:
        """Check if there are staged changes."""
        try:
            result = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                capture_output=True,
                timeout=10,
            )
            return result.returncode != 0
        except Exception:
            return False

    def _get_staged_files_with_stats(self) -> list[dict]:
        """Get list of staged files with insertion/deletion stats.

        Returns:
            List of dicts with {path, insertions, deletions}
        """
        try:
            # Get file stats using --numstat
            result = subprocess.run(
                ["git", "diff", "--cached", "--numstat"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            files = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) >= 3:
                    insertions = int(parts[0]) if parts[0] != "-" else 0
                    deletions = int(parts[1]) if parts[1] != "-" else 0
                    path = parts[2]
                    files.append(
                        {
                            "path": path,
                            "insertions": insertions,
                            "deletions": deletions,
                        }
                    )

            return files
        except Exception as e:
            logger.error(f"Failed to get staged files: {e}")
            # Fallback to just file names
            try:
                result = subprocess.run(
                    ["git", "diff", "--cached", "--name-only"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                return [
                    {"path": f, "insertions": 0, "deletions": 0}
                    for f in result.stdout.strip().split("\n")
                    if f
                ]
            except Exception:
                return []

    def _get_staged_diff(self) -> str:
        """Get the staged changes diff."""
        try:
            result = subprocess.run(
                ["git", "diff", "--cached"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout
        except Exception as e:
            logger.error(f"Failed to get staged diff: {e}")
            return ""

    async def _generate_commit_message(self) -> str:
        """Generate a commit message using the LLM."""
        if not self.session or not hasattr(self.session, "general_agent"):
            # Fallback to simple generation
            return self._simple_commit_message()

        try:
            agent = self.session.general_agent

            prompt = (
                "Generate a conventional commit message for these staged changes. "
                "Use format: type(scope): description\n"
                "Types: feat, fix, docs, style, refactor, test, chore\n"
                "Keep under 72 characters. Be concise but descriptive.\n"
                "Return ONLY the commit message, nothing else.\n\n"
                f"Changes:\n{self._staged_diff[:4000]}"
            )

            # Use the agent to generate
            messages = [{"role": "user", "content": prompt}]
            model = agent.provider_config.get_model(agent.model_tier)

            system_prompt = (
                "You are a git commit message generator. "
                "Output only the commit message."
            )
            response = agent.client.messages.create(
                model=model,
                max_tokens=200,
                messages=messages,
                system=system_prompt,
            )

            # Extract text from response
            if response.content:
                for block in response.content:
                    if hasattr(block, "text"):
                        msg: str = str(block.text).strip()
                        # Clean up - take first line only
                        msg = msg.split("\n")[0].strip()
                        # Remove quotes if present
                        msg = msg.strip('"').strip("'")
                        return msg

            return self._simple_commit_message()

        except Exception as e:
            logger.error(f"LLM commit message generation failed: {e}")
            return self._simple_commit_message()

    async def _generate_revised_message(self, instructions: str) -> str:
        """Generate a revised commit message based on instructions."""
        if not self.session or not hasattr(self.session, "general_agent"):
            return self._current_message

        try:
            agent = self.session.general_agent

            prompt = (
                f"Revise this commit message based on the instructions.\n\n"
                f"Current message: {self._current_message}\n"
                f"Instructions: {instructions}\n\n"
                f"Use conventional commit format: type(scope): description\n"
                f"Return ONLY the revised commit message, nothing else."
            )

            messages = [{"role": "user", "content": prompt}]
            model = agent.provider_config.get_model(agent.model_tier)

            system_prompt = (
                "You are a git commit message generator. "
                "Output only the commit message."
            )
            response = agent.client.messages.create(
                model=model,
                max_tokens=200,
                messages=messages,
                system=system_prompt,
            )

            if response.content:
                for block in response.content:
                    if hasattr(block, "text"):
                        msg: str = str(block.text).strip()
                        msg = msg.split("\n")[0].strip()
                        msg = msg.strip('"').strip("'")
                        return msg

            return self._current_message

        except Exception as e:
            logger.error(f"LLM revision failed: {e}")
            return self._current_message

    def _simple_commit_message(self) -> str:
        """Generate a simple commit message without LLM."""
        # Count files changed
        try:
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            files = [f for f in result.stdout.strip().split("\n") if f]
            file_count = len(files)

            if file_count == 1:
                return f"chore: update {files[0]}"
            else:
                return f"chore: update {file_count} files"
        except Exception:
            return "chore: update files"
