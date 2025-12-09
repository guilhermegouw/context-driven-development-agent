"""Commit slash command - Automated git commit with AI-generated messages.

This command analyzes staged changes and generates conventional commit messages,
with options to accept, revise, or abort.
"""

import logging
import subprocess

from .base import BaseSlashCommand

logger = logging.getLogger(__name__)


class CommitCommand(BaseSlashCommand):
    """Automated git commit with conventional commit message generation.

    This command:
    1. Analyzes staged changes via git diff --cached
    2. Generates a conventional commit message using the LLM
    3. Allows user to accept, revise, or abort
    4. Executes git commit when approved

    Usage:
        /commit           - Generate commit message for staged changes
        /commit --push    - Commit and push after approval
        /commit --abort   - Unstage all files

    The revision loop allows iterating on the commit message until satisfied.
    """

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
        # State for revision loop
        self._current_message = ""
        self._staged_changes = ""
        self._should_push = False
        self._awaiting_response = False
        self._response_type = None  # "action" or "revision"

    async def execute(self, args: str) -> str:
        """Execute the /commit command.

        Args:
            args: Command arguments (--push, --abort, or revision instructions)

        Returns:
            Result message with commit status or prompt for action
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

        # If we're awaiting a response from user
        if self._awaiting_response:
            return await self._handle_user_response(args)

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

        # Get staged changes
        self._staged_changes = self._get_staged_diff()
        if not self._staged_changes:
            return "**Error:** Failed to get staged changes."

        # Generate commit message using the session's agent
        self._current_message = await self._generate_commit_message()

        # Set up for user response
        self._awaiting_response = True
        self._response_type = "action"

        # Format the proposal
        return self._format_proposal()

    def _format_proposal(self) -> str:
        """Format the commit message proposal for display."""
        # Truncate diff for display
        diff_preview = self._staged_changes[:1500]
        if len(self._staged_changes) > 1500:
            diff_preview += "\n... (truncated)"

        push_note = " **and push**" if self._should_push else ""

        return (
            f"**Proposed commit message:**\n\n"
            f"```\n{self._current_message}\n```\n\n"
            f"**Staged changes preview:**\n"
            f"```diff\n{diff_preview}\n```\n\n"
            f"---\n"
            f"**Choose an action:**\n"
            f"- Type `accept` to commit{push_note} with this message\n"
            f"- Type `abort` to unstage all files and cancel\n"
            f"- Type your revision instructions to modify the message\n\n"
            f"*Example revisions: 'use feat type', 'add auth scope', "
            f"'make it shorter'*"
        )

    async def _handle_user_response(self, response: str) -> str:
        """Handle user's response to the commit proposal."""
        response_lower = response.strip().lower()

        # Handle accept
        if response_lower in ["accept", "yes", "y", "ok", "confirm"]:
            self._awaiting_response = False
            return await self._execute_commit()

        # Handle abort
        if response_lower in ["abort", "cancel", "no", "n"]:
            self._awaiting_response = False
            return await self._handle_abort()

        # Handle revision instructions
        if response.strip():
            return await self._revise_message(response)

        # Empty response
        return (
            "**Please provide a valid response:**\n"
            "- `accept` - Commit with the proposed message\n"
            "- `abort` - Cancel and unstage files\n"
            "- Or type revision instructions"
        )

    async def _revise_message(self, instructions: str) -> str:
        """Revise the commit message based on user instructions."""
        logger.info(f"Revising commit message with instructions: {instructions}")

        # Generate revised message
        self._current_message = await self._generate_revised_message(instructions)

        # Keep awaiting response
        self._awaiting_response = True
        self._response_type = "action"

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
                return (
                    f"**Error unstaging files:**\n\n"
                    f"```\n{result.stderr}\n```"
                )

            return "**Commit aborted.** All files have been unstaged."

        except Exception as e:
            logger.error(f"Abort failed: {e}", exc_info=True)
            return f"**Error during abort:**\n\n```\n{str(e)}\n```"
        finally:
            self._reset_state()

    def _reset_state(self):
        """Reset command state."""
        self._current_message = ""
        self._staged_changes = ""
        self._should_push = False
        self._awaiting_response = False
        self._response_type = None

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
                f"Changes:\n{self._staged_changes[:4000]}"
            )

            # Use the agent to generate
            messages = [{"role": "user", "content": prompt}]
            model = agent.provider_config.get_model(agent.model_tier)

            response = agent.client.messages.create(
                model=model,
                max_tokens=200,
                messages=messages,
                system="You are a git commit message generator. Output only the commit message.",
            )

            # Extract text from response
            if response.content:
                for block in response.content:
                    if hasattr(block, "text"):
                        msg = block.text.strip()
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

            response = agent.client.messages.create(
                model=model,
                max_tokens=200,
                messages=messages,
                system="You are a git commit message generator. Output only the commit message.",
            )

            if response.content:
                for block in response.content:
                    if hasattr(block, "text"):
                        msg = block.text.strip()
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
