"""Tests for the commit slash command.

This module tests:
- Commit command metadata and initialization
- Staged changes detection
- Staged files with stats retrieval
- Commit message generation (with and without LLM)
- Accept/edit/cancel action flow
- Git operation execution
"""

import subprocess
import unittest
from unittest.mock import AsyncMock, Mock, patch

import pytest

from cdd_agent.slash_commands.commit_command import CommitCommand


class TestCommitCommandMetadata(unittest.TestCase):
    """Test commit command metadata."""

    def setUp(self):
        """Set up test fixtures."""
        self.command = CommitCommand()

    def test_command_name(self):
        """Test command name is set correctly."""
        self.assertEqual(self.command.name, "commit")

    def test_command_description(self):
        """Test command description is set."""
        self.assertIn("commit", self.command.description.lower())

    def test_command_usage(self):
        """Test command usage includes options."""
        self.assertIn("--push", self.command.usage)
        self.assertIn("--abort", self.command.usage)

    def test_command_examples(self):
        """Test command examples are provided."""
        self.assertIsInstance(self.command.examples, list)
        self.assertGreater(len(self.command.examples), 0)
        self.assertIn("/commit", self.command.examples)


class TestCommitCommandStagedChanges(unittest.TestCase):
    """Test staged changes detection."""

    def setUp(self):
        """Set up test fixtures."""
        self.command = CommitCommand()

    @patch("subprocess.run")
    def test_has_staged_changes_true(self, mock_run):
        """Test detection when there are staged changes."""
        mock_run.return_value = Mock(returncode=1)  # Non-zero = has changes
        self.assertTrue(self.command._has_staged_changes())

    @patch("subprocess.run")
    def test_has_staged_changes_false(self, mock_run):
        """Test detection when there are no staged changes."""
        mock_run.return_value = Mock(returncode=0)  # Zero = no changes
        self.assertFalse(self.command._has_staged_changes())

    @patch("subprocess.run")
    def test_has_staged_changes_error(self, mock_run):
        """Test detection handles errors gracefully."""
        mock_run.side_effect = Exception("Git error")
        self.assertFalse(self.command._has_staged_changes())


class TestCommitCommandStagedFilesWithStats(unittest.TestCase):
    """Test staged files with stats retrieval."""

    def setUp(self):
        """Set up test fixtures."""
        self.command = CommitCommand()

    @patch("subprocess.run")
    def test_get_staged_files_with_stats(self, mock_run):
        """Test getting staged files with insertion/deletion stats."""
        mock_run.return_value = Mock(
            stdout="10\t5\tsrc/main.py\n20\t0\tsrc/utils.py\n",
            returncode=0
        )
        result = self.command._get_staged_files_with_stats()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["path"], "src/main.py")
        self.assertEqual(result[0]["insertions"], 10)
        self.assertEqual(result[0]["deletions"], 5)
        self.assertEqual(result[1]["path"], "src/utils.py")
        self.assertEqual(result[1]["insertions"], 20)
        self.assertEqual(result[1]["deletions"], 0)

    @patch("subprocess.run")
    def test_get_staged_files_binary_file(self, mock_run):
        """Test handling binary files (shown as - in git numstat)."""
        mock_run.return_value = Mock(
            stdout="-\t-\timage.png\n5\t2\tREADME.md\n",
            returncode=0
        )
        result = self.command._get_staged_files_with_stats()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["path"], "image.png")
        self.assertEqual(result[0]["insertions"], 0)
        self.assertEqual(result[0]["deletions"], 0)

    @patch("subprocess.run")
    def test_get_staged_files_fallback(self, mock_run):
        """Test fallback to name-only when numstat fails."""
        # First call (numstat) fails, second call (name-only) succeeds
        mock_run.side_effect = [
            Exception("Git error"),
            Mock(stdout="file1.py\nfile2.py\n", returncode=0),
        ]
        result = self.command._get_staged_files_with_stats()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["path"], "file1.py")
        self.assertEqual(result[0]["insertions"], 0)

    @patch("subprocess.run")
    def test_get_staged_diff(self, mock_run):
        """Test getting staged diff content."""
        mock_run.return_value = Mock(stdout="diff content", returncode=0)
        result = self.command._get_staged_diff()
        self.assertEqual(result, "diff content")


class TestCommitCommandSimpleMessage(unittest.TestCase):
    """Test simple commit message generation (without LLM)."""

    def setUp(self):
        """Set up test fixtures."""
        self.command = CommitCommand()

    @patch("subprocess.run")
    def test_simple_message_single_file(self, mock_run):
        """Test simple message for single file."""
        mock_run.return_value = Mock(stdout="src/main.py\n", returncode=0)
        result = self.command._simple_commit_message()
        self.assertIn("src/main.py", result)
        self.assertTrue(result.startswith("chore:"))

    @patch("subprocess.run")
    def test_simple_message_multiple_files(self, mock_run):
        """Test simple message for multiple files."""
        mock_run.return_value = Mock(stdout="file1.py\nfile2.py\nfile3.py\n", returncode=0)
        result = self.command._simple_commit_message()
        self.assertIn("3 files", result)
        self.assertTrue(result.startswith("chore:"))

    @patch("subprocess.run")
    def test_simple_message_error(self, mock_run):
        """Test simple message handles errors."""
        mock_run.side_effect = Exception("Error")
        result = self.command._simple_commit_message()
        self.assertEqual(result, "chore: update files")


class TestCommitCommandFormatProposal(unittest.TestCase):
    """Test proposal formatting."""

    def setUp(self):
        """Set up test fixtures."""
        self.command = CommitCommand()
        self.command._current_message = "feat: add new feature"
        self.command._staged_files = [
            {"path": "src/main.py", "insertions": 10, "deletions": 5},
            {"path": "src/utils.py", "insertions": 20, "deletions": 0},
        ]

    def test_format_proposal_shows_files(self):
        """Test proposal shows file list instead of diff."""
        result = self.command._format_proposal()

        # Should contain file names
        self.assertIn("src/main.py", result)
        self.assertIn("src/utils.py", result)

        # Should contain stats
        self.assertIn("+10", result)
        self.assertIn("-5", result)

        # Should contain commit message
        self.assertIn("feat: add new feature", result)

        # Should contain action options
        self.assertIn("[A]ccept", result)
        self.assertIn("[E]dit", result)
        self.assertIn("[C]ancel", result)

    def test_format_proposal_shows_summary(self):
        """Test proposal shows file count and total stats."""
        result = self.command._format_proposal()

        # Should show file count
        self.assertIn("2 files", result)

        # Should show total stats
        self.assertIn("+30", result)  # 10 + 20
        self.assertIn("-5", result)

    def test_format_proposal_with_push(self):
        """Test proposal mentions push when flag is set."""
        self.command._should_push = True
        result = self.command._format_proposal()

        self.assertIn("and push", result)


@pytest.mark.asyncio
class TestCommitCommandExecute:
    """Test commit command execute method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.command = CommitCommand()

    @patch.object(CommitCommand, "_has_staged_changes")
    async def test_no_staged_changes(self, mock_has_staged):
        """Test execute when no staged changes."""
        mock_has_staged.return_value = False

        result = await self.command.execute("")

        assert "No staged changes" in result
        assert "git add" in result

    @patch.object(CommitCommand, "_has_staged_changes")
    @patch.object(CommitCommand, "_get_staged_files_with_stats")
    @patch.object(CommitCommand, "_get_staged_diff")
    @patch.object(CommitCommand, "_generate_commit_message")
    async def test_starts_commit_flow(self, mock_generate, mock_diff, mock_files, mock_has_staged):
        """Test execute starts commit flow with staged changes."""
        mock_has_staged.return_value = True
        mock_files.return_value = [{"path": "test.py", "insertions": 5, "deletions": 2}]
        mock_diff.return_value = "diff content"
        mock_generate.return_value = "feat: test commit"

        result = await self.command.execute("")

        assert "Proposed commit message" in result
        assert "feat: test commit" in result
        assert "[A]ccept" in result
        assert "[E]dit" in result
        assert "[C]ancel" in result

    async def test_abort_flag(self):
        """Test execute with --abort flag."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stderr="")

            result = await self.command.execute("--abort")

            assert "aborted" in result.lower()

    @patch.object(CommitCommand, "_has_staged_changes")
    @patch.object(CommitCommand, "_get_staged_files_with_stats")
    @patch.object(CommitCommand, "_get_staged_diff")
    @patch.object(CommitCommand, "_generate_commit_message")
    async def test_push_flag_sets_state(self, mock_generate, mock_diff, mock_files, mock_has_staged):
        """Test --push flag sets should_push state."""
        mock_has_staged.return_value = True
        mock_files.return_value = [{"path": "test.py", "insertions": 1, "deletions": 0}]
        mock_diff.return_value = "diff"
        mock_generate.return_value = "feat: test"

        await self.command.execute("--push")

        assert self.command._should_push is True


@pytest.mark.asyncio
class TestCommitCommandActions:
    """Test handling user actions in commit flow."""

    def setup_method(self):
        """Set up test fixtures."""
        self.command = CommitCommand()
        self.command._awaiting_choice = True
        self.command._current_message = "feat: test commit"
        self.command._staged_files = [{"path": "test.py", "insertions": 5, "deletions": 2}]
        self.command._staged_diff = "diff content"
        CommitCommand._pending_commit = self.command

    async def test_accept_action(self):
        """Test accepting commit message."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="committed", stderr="")

            result = await self.command._handle_action("accept")

            assert "Successfully committed" in result
            assert self.command._awaiting_choice is False

    async def test_accept_shortcut(self):
        """Test 'a' as accept shortcut."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="committed", stderr="")

            result = await self.command._handle_action("a")

            assert "Successfully committed" in result

    async def test_cancel_action(self):
        """Test canceling commit."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stderr="")

            result = await self.command._handle_action("cancel")

            assert "aborted" in result.lower()
            assert self.command._awaiting_choice is False

    async def test_cancel_shortcut(self):
        """Test 'c' as cancel shortcut."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stderr="")

            result = await self.command._handle_action("c")

            assert "aborted" in result.lower()

    async def test_edit_action_prompts_for_instructions(self):
        """Test 'edit' prompts for revision instructions."""
        result = await self.command._handle_action("edit")

        assert "revision instructions" in result.lower()
        assert self.command._awaiting_choice is True  # Still waiting

    async def test_edit_shortcut(self):
        """Test 'e' as edit shortcut."""
        result = await self.command._handle_action("e")

        assert "revision instructions" in result.lower()

    async def test_revision_instructions(self):
        """Test providing revision instructions."""
        with patch.object(
            self.command, "_generate_revised_message", new_callable=AsyncMock
        ) as mock_revise:
            mock_revise.return_value = "feat(api): revised message"

            result = await self.command._handle_action("use feat(api) type")

            assert "Proposed commit message" in result
            assert "feat(api): revised message" in result
            assert self.command._awaiting_choice is True


@pytest.mark.asyncio
class TestCommitCommandGitOperations:
    """Test git operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.command = CommitCommand()
        self.command._current_message = "feat: test commit"

    async def test_execute_commit_success(self):
        """Test successful commit execution."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0, stdout="[main abc123] feat: test commit", stderr=""
            )

            result = await self.command._execute_commit()

            assert "Successfully committed" in result
            assert "feat: test commit" in result

    async def test_execute_commit_failure(self):
        """Test commit failure handling."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=1, stdout="", stderr="nothing to commit"
            )

            result = await self.command._execute_commit()

            assert "failed" in result.lower()

    async def test_execute_commit_with_push(self):
        """Test commit with push."""
        self.command._should_push = True

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="pushed", stderr="")

            result = await self.command._execute_commit()

            assert "pushed" in result.lower()
            # Should have called run twice (commit and push)
            assert mock_run.call_count == 2

    async def test_execute_commit_push_failure(self):
        """Test commit succeeds but push fails."""
        self.command._should_push = True

        with patch("subprocess.run") as mock_run:
            # First call (commit) succeeds, second (push) fails
            mock_run.side_effect = [
                Mock(returncode=0, stdout="committed", stderr=""),
                Mock(returncode=1, stdout="", stderr="push rejected"),
            ]

            result = await self.command._execute_commit()

            assert "Committed but push failed" in result
            assert "push rejected" in result

    async def test_handle_abort_success(self):
        """Test successful abort."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stderr="")

            result = await self.command._handle_abort()

            assert "aborted" in result.lower()
            mock_run.assert_called_once()

    async def test_handle_abort_failure(self):
        """Test abort failure."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1, stderr="error")

            result = await self.command._handle_abort()

            assert "Error" in result


class TestCommitCommandState(unittest.TestCase):
    """Test command state management."""

    def setUp(self):
        """Set up test fixtures."""
        self.command = CommitCommand()

    def test_initial_state(self):
        """Test initial state is clean."""
        self.assertEqual(self.command._current_message, "")
        self.assertEqual(self.command._staged_files, [])
        self.assertEqual(self.command._staged_diff, "")
        self.assertFalse(self.command._should_push)
        self.assertFalse(self.command._awaiting_choice)

    def test_reset_state(self):
        """Test state reset."""
        # Set some state
        self.command._current_message = "test"
        self.command._staged_files = [{"path": "test.py", "insertions": 1, "deletions": 0}]
        self.command._staged_diff = "diff"
        self.command._should_push = True
        self.command._awaiting_choice = True
        CommitCommand._pending_commit = self.command

        # Reset
        self.command._reset_state()

        # Verify reset
        self.assertEqual(self.command._current_message, "")
        self.assertEqual(self.command._staged_files, [])
        self.assertEqual(self.command._staged_diff, "")
        self.assertFalse(self.command._should_push)
        self.assertFalse(self.command._awaiting_choice)
        self.assertIsNone(CommitCommand._pending_commit)


if __name__ == "__main__":
    unittest.main()
