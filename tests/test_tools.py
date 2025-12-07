"""Unit tests for tools, specifically git_commit."""

import subprocess
from unittest.mock import Mock
from unittest.mock import patch

from cdd_agent.tools import git_commit


class TestGitCommit:
    """Test git_commit tool."""

    @patch("cdd_agent.tools.subprocess.run")
    def test_commit_with_files_parameter(self, mock_run):
        """Test successful commit with files parameter."""
        # Mock git add
        mock_run.side_effect = [
            # git add file1.txt
            Mock(returncode=0, stdout="", stderr=""),
            # git add file2.txt
            Mock(returncode=0, stdout="", stderr=""),
            # git diff --cached --name-only (check staged files)
            Mock(returncode=0, stdout="file1.txt\nfile2.txt\n", stderr=""),
            # git diff --cached --stat (diff preview)
            Mock(
                returncode=0,
                stdout=(
                    " file1.txt | 2 ++\n file2.txt | 3 +++\n"
                    " 2 files changed, 5 insertions(+)\n"
                ),
                stderr="",
            ),
            # git commit -m "message"
            Mock(returncode=0, stdout="", stderr=""),
            # git rev-parse --short HEAD (get SHA)
            Mock(returncode=0, stdout="abc1234\n", stderr=""),
        ]

        result = git_commit("Add new features", "file1.txt file2.txt")

        assert "✓ Commit created successfully!" in result
        assert "abc1234" in result
        assert "Add new features" in result
        assert "file1.txt" in result or "2 files changed" in result

        # Verify git add was called for each file
        assert mock_run.call_count == 6
        assert mock_run.call_args_list[0][0][0] == ["git", "add", "file1.txt"]
        assert mock_run.call_args_list[1][0][0] == ["git", "add", "file2.txt"]

    @patch("cdd_agent.tools.subprocess.run")
    def test_commit_with_already_staged_files(self, mock_run):
        """Test successful commit with already-staged files (no files parameter)."""
        mock_run.side_effect = [
            # git diff --cached --name-only
            Mock(returncode=0, stdout="staged.txt\n", stderr=""),
            # git diff --cached --stat
            Mock(
                returncode=0,
                stdout=" staged.txt | 1 +\n 1 file changed, 1 insertion(+)\n",
                stderr="",
            ),
            # git commit
            Mock(returncode=0, stdout="", stderr=""),
            # git rev-parse
            Mock(returncode=0, stdout="def5678\n", stderr=""),
        ]

        result = git_commit("Fix bug")

        assert "✓ Commit created successfully!" in result
        assert "def5678" in result
        assert "Fix bug" in result

    @patch("cdd_agent.tools.subprocess.run")
    def test_commit_empty_message(self, mock_run):
        """Test that empty commit message is rejected."""
        result = git_commit("")

        assert "Error: Commit message cannot be empty" in result
        mock_run.assert_not_called()

    @patch("cdd_agent.tools.subprocess.run")
    def test_commit_whitespace_only_message(self, mock_run):
        """Test that whitespace-only commit message is rejected."""
        result = git_commit("   \n\t  ")

        assert "Error: Commit message cannot be empty" in result
        mock_run.assert_not_called()

    @patch("cdd_agent.tools.subprocess.run")
    def test_commit_no_staged_changes(self, mock_run):
        """Test error when no changes are staged."""
        mock_run.side_effect = [
            # git diff --cached --name-only (empty)
            Mock(returncode=0, stdout="", stderr=""),
        ]

        result = git_commit("Some message")

        assert "Error: No changes staged for commit" in result

    @patch("cdd_agent.tools.subprocess.run")
    def test_commit_file_staging_error(self, mock_run):
        """Test error when staging a file fails."""
        mock_run.side_effect = [
            # git add nonexistent.txt (fails)
            Mock(
                returncode=1,
                stdout="",
                stderr="fatal: pathspec 'nonexistent.txt' did not match any files",
            ),
        ]

        result = git_commit("Add file", "nonexistent.txt")

        assert "Error staging file 'nonexistent.txt'" in result
        assert "pathspec" in result or "did not match" in result

    @patch("cdd_agent.tools.subprocess.run")
    def test_commit_not_a_git_repo(self, mock_run):
        """Test error when not in a git repository."""
        mock_run.side_effect = [
            # git diff --cached --name-only (fails)
            Mock(returncode=128, stdout="", stderr="fatal: not a git repository"),
        ]

        result = git_commit("Commit message")

        assert "Error: Not a git repository" in result

    @patch("cdd_agent.tools.subprocess.run")
    def test_commit_fails(self, mock_run):
        """Test error when git commit command fails."""
        mock_run.side_effect = [
            # git diff --cached --name-only
            Mock(returncode=0, stdout="file.txt\n", stderr=""),
            # git diff --cached --stat
            Mock(returncode=0, stdout=" file.txt | 1 +\n", stderr=""),
            # git commit (fails)
            Mock(returncode=1, stdout="", stderr="error: commit failed"),
        ]

        result = git_commit("Commit message")

        assert "Error creating commit" in result
        assert "commit failed" in result

    @patch("cdd_agent.tools.subprocess.run")
    def test_commit_timeout(self, mock_run):
        """Test timeout handling."""
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=["git", "commit"], timeout=10
        )

        result = git_commit("Commit message")

        assert "Error: Git command timed out" in result

    @patch("cdd_agent.tools.subprocess.run")
    def test_commit_general_exception(self, mock_run):
        """Test general exception handling."""
        mock_run.side_effect = Exception("Unexpected error")

        result = git_commit("Commit message")

        assert "Error creating commit" in result
        assert "Unexpected error" in result

    @patch("cdd_agent.tools.subprocess.run")
    def test_commit_sha_retrieval_fails(self, mock_run):
        """Test that commit still succeeds even if SHA retrieval fails."""
        mock_run.side_effect = [
            # git diff --cached --name-only
            Mock(returncode=0, stdout="file.txt\n", stderr=""),
            # git diff --cached --stat
            Mock(returncode=0, stdout=" file.txt | 1 +\n", stderr=""),
            # git commit
            Mock(returncode=0, stdout="", stderr=""),
            # git rev-parse (fails)
            Mock(returncode=1, stdout="", stderr="error"),
        ]

        result = git_commit("Commit message")

        assert "✓ Commit created successfully!" in result
        assert "unknown" in result  # SHA should be 'unknown'

    @patch("cdd_agent.tools.subprocess.run")
    def test_commit_message_trimmed(self, mock_run):
        """Test that commit message is trimmed of whitespace."""
        mock_run.side_effect = [
            # git diff --cached --name-only
            Mock(returncode=0, stdout="file.txt\n", stderr=""),
            # git diff --cached --stat
            Mock(returncode=0, stdout=" file.txt | 1 +\n", stderr=""),
            # git commit
            Mock(returncode=0, stdout="", stderr=""),
            # git rev-parse
            Mock(returncode=0, stdout="abc1234\n", stderr=""),
        ]

        result = git_commit("  Commit message with whitespace  ")

        assert "✓ Commit created successfully!" in result
        # Verify git commit was called with trimmed message
        commit_call = [
            call
            for call in mock_run.call_args_list
            if call[0][0][0:2] == ["git", "commit"]
        ][0]
        assert commit_call[0][0] == [
            "git",
            "commit",
            "-m",
            "Commit message with whitespace",
        ]

    @patch("cdd_agent.tools.subprocess.run")
    def test_commit_multiple_files(self, mock_run):
        """Test staging multiple files."""
        mock_run.side_effect = [
            # git add file1.txt
            Mock(returncode=0, stdout="", stderr=""),
            # git add file2.txt
            Mock(returncode=0, stdout="", stderr=""),
            # git add file3.txt
            Mock(returncode=0, stdout="", stderr=""),
            # git diff --cached --name-only
            Mock(
                returncode=0,
                stdout="file1.txt\nfile2.txt\nfile3.txt\n",
                stderr="",
            ),
            # git diff --cached --stat
            Mock(
                returncode=0,
                stdout=" 3 files changed, 10 insertions(+)\n",
                stderr="",
            ),
            # git commit
            Mock(returncode=0, stdout="", stderr=""),
            # git rev-parse
            Mock(returncode=0, stdout="xyz9876\n", stderr=""),
        ]

        result = git_commit("Add multiple files", "file1.txt file2.txt file3.txt")

        assert "✓ Commit created successfully!" in result
        assert "xyz9876" in result
        assert mock_run.call_count == 7  # 3 adds + 4 other commands
