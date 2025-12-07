"""Unit tests for ApprovalManager."""

import os

from cdd_agent.approval import ApprovalManager
from cdd_agent.config import ApprovalMode
from cdd_agent.tools import RiskLevel


class TestApprovalManagerParanoidMode:
    """Test ApprovalManager in paranoid mode."""

    def test_paranoid_asks_for_safe_tools(
        self, approval_manager_paranoid, mock_ui_callback
    ):
        """Paranoid mode should ask for approval even for SAFE tools."""
        result = approval_manager_paranoid.should_approve(
            "read_file", {"path": "test.txt"}, RiskLevel.SAFE
        )

        assert result is True  # UI callback returned True
        mock_ui_callback.assert_called_once_with(
            "read_file", {"path": "test.txt"}, RiskLevel.SAFE
        )

    def test_paranoid_asks_for_medium_tools(
        self, approval_manager_paranoid, mock_ui_callback
    ):
        """Paranoid mode should ask for approval for MEDIUM tools."""
        result = approval_manager_paranoid.should_approve(
            "write_file",
            {"path": "test.txt", "content": "data"},
            RiskLevel.MEDIUM,
        )

        assert result is True
        mock_ui_callback.assert_called_once()

    def test_paranoid_asks_for_high_tools(
        self, approval_manager_paranoid, mock_ui_callback
    ):
        """Paranoid mode should ask for approval for HIGH risk tools."""
        result = approval_manager_paranoid.should_approve(
            "run_bash", {"command": "ls"}, RiskLevel.HIGH
        )

        assert result is True
        mock_ui_callback.assert_called_once()

    def test_paranoid_respects_denial(self, mock_ui_callback_deny):
        """Paranoid mode should respect user denial."""
        manager = ApprovalManager(
            mode=ApprovalMode.PARANOID, ui_callback=mock_ui_callback_deny
        )

        result = manager.should_approve(
            "read_file", {"path": "test.txt"}, RiskLevel.SAFE
        )

        assert result is False
        mock_ui_callback_deny.assert_called_once()


class TestApprovalManagerBalancedMode:
    """Test ApprovalManager in balanced mode."""

    def test_balanced_auto_approves_safe_tools(
        self, approval_manager_balanced, mock_ui_callback
    ):
        """Balanced mode should auto-approve SAFE tools without asking."""
        result = approval_manager_balanced.should_approve(
            "read_file", {"path": "test.txt"}, RiskLevel.SAFE
        )

        assert result is True
        # UI callback should NOT be called for SAFE tools in balanced mode
        mock_ui_callback.assert_not_called()

    def test_balanced_asks_for_medium_tools(
        self, approval_manager_balanced, mock_ui_callback
    ):
        """Balanced mode should ask for MEDIUM risk tools."""
        result = approval_manager_balanced.should_approve(
            "write_file",
            {"path": "test.txt", "content": "data"},
            RiskLevel.MEDIUM,
        )

        assert result is True
        mock_ui_callback.assert_called_once_with(
            "write_file",
            {"path": "test.txt", "content": "data"},
            RiskLevel.MEDIUM,
        )

    def test_balanced_asks_for_high_tools(
        self, approval_manager_balanced, mock_ui_callback
    ):
        """Balanced mode should ask for HIGH risk tools."""
        result = approval_manager_balanced.should_approve(
            "run_bash", {"command": "rm -rf /"}, RiskLevel.HIGH
        )

        assert result is True
        mock_ui_callback.assert_called_once()

    def test_balanced_respects_denial_for_medium(self, mock_ui_callback_deny):
        """Balanced mode should respect denial for MEDIUM tools."""
        manager = ApprovalManager(
            mode=ApprovalMode.BALANCED, ui_callback=mock_ui_callback_deny
        )

        result = manager.should_approve(
            "write_file",
            {"path": "test.txt", "content": "data"},
            RiskLevel.MEDIUM,
        )

        assert result is False


class TestApprovalManagerTrustingMode:
    """Test ApprovalManager in trusting mode."""

    def test_trusting_asks_first_time(
        self, approval_manager_trusting, mock_ui_callback
    ):
        """Trusting mode should ask on first use of a tool."""
        result = approval_manager_trusting.should_approve(
            "write_file",
            {"path": "test.txt", "content": "data"},
            RiskLevel.MEDIUM,
        )

        assert result is True
        mock_ui_callback.assert_called_once()

    def test_trusting_remembers_approval(
        self, approval_manager_trusting, mock_ui_callback
    ):
        """Trusting mode should remember approval and not ask again."""
        # First call - should ask
        approval_manager_trusting.should_approve(
            "write_file",
            {"path": "test1.txt", "content": "data"},
            RiskLevel.MEDIUM,
        )

        mock_ui_callback.reset_mock()

        # Second call for same tool - should NOT ask (remembered)
        result = approval_manager_trusting.should_approve(
            "write_file",
            {"path": "test2.txt", "content": "other"},
            RiskLevel.MEDIUM,
        )

        assert result is True
        # UI callback should NOT be called second time
        mock_ui_callback.assert_not_called()

    def test_trusting_different_tools_separate(
        self, approval_manager_trusting, mock_ui_callback
    ):
        """Trusting mode should track different tools separately."""
        # Approve write_file
        approval_manager_trusting.should_approve(
            "write_file",
            {"path": "test.txt", "content": "data"},
            RiskLevel.MEDIUM,
        )

        mock_ui_callback.reset_mock()

        # Using different tool (run_bash) should still ask
        result = approval_manager_trusting.should_approve(
            "run_bash", {"command": "ls"}, RiskLevel.HIGH
        )

        assert result is True
        mock_ui_callback.assert_called_once()

    def test_trusting_reset_session_approvals(
        self, approval_manager_trusting, mock_ui_callback
    ):
        """Trusting mode should forget approvals when session is reset."""
        # First approval
        approval_manager_trusting.should_approve(
            "write_file",
            {"path": "test.txt", "content": "data"},
            RiskLevel.MEDIUM,
        )

        # Reset session
        approval_manager_trusting.reset_session_approvals()

        mock_ui_callback.reset_mock()

        # Should ask again after reset
        result = approval_manager_trusting.should_approve(
            "write_file",
            {"path": "test2.txt", "content": "data"},
            RiskLevel.MEDIUM,
        )

        assert result is True
        mock_ui_callback.assert_called_once()

    def test_trusting_get_session_approvals(self, approval_manager_trusting):
        """Test getting session approvals."""
        # Initially empty
        assert len(approval_manager_trusting.get_session_approvals()) == 0

        # Approve some tools
        approval_manager_trusting.should_approve(
            "write_file",
            {"path": "test.txt", "content": "data"},
            RiskLevel.MEDIUM,
        )
        approval_manager_trusting.should_approve(
            "run_bash", {"command": "ls"}, RiskLevel.HIGH
        )

        # Check session approvals
        approvals = approval_manager_trusting.get_session_approvals()
        assert "write_file" in approvals
        assert "run_bash" in approvals
        assert len(approvals) == 2

    def test_trusting_denial_not_remembered(self, mock_ui_callback_deny):
        """Trusting mode should not remember denials, only approvals."""
        manager = ApprovalManager(
            mode=ApprovalMode.TRUSTING, ui_callback=mock_ui_callback_deny
        )

        # First call - denied
        result1 = manager.should_approve(
            "write_file",
            {"path": "test.txt", "content": "data"},
            RiskLevel.MEDIUM,
        )
        assert result1 is False

        mock_ui_callback_deny.reset_mock()

        # Second call - should ask again (denial not remembered)
        result2 = manager.should_approve(
            "write_file",
            {"path": "test2.txt", "content": "data"},
            RiskLevel.MEDIUM,
        )

        assert result2 is False
        # Should have been called again
        mock_ui_callback_deny.assert_called_once()


class TestDangerousCommandDetection:
    """Test dangerous command pattern detection."""

    def test_detect_rm_rf(self):
        """Should detect rm -rf as dangerous."""
        manager = ApprovalManager(mode=ApprovalMode.PARANOID, ui_callback=None)

        is_dangerous, warning = manager.is_dangerous_command("rm -rf /tmp/test")

        assert is_dangerous is True
        assert "Recursive file deletion" in warning

    def test_detect_sudo_rm(self):
        """Should detect sudo rm as dangerous."""
        manager = ApprovalManager(mode=ApprovalMode.PARANOID, ui_callback=None)

        is_dangerous, warning = manager.is_dangerous_command("sudo rm test.txt")

        assert is_dangerous is True
        assert "Sudo file deletion" in warning

    def test_detect_dd_overwrite(self):
        """Should detect dd disk overwrite."""
        manager = ApprovalManager(mode=ApprovalMode.PARANOID, ui_callback=None)

        is_dangerous, warning = manager.is_dangerous_command(
            "dd if=/dev/zero of=/dev/sda"
        )

        assert is_dangerous is True
        assert "dd" in warning.lower()

    def test_detect_git_reset_hard(self):
        """Should detect git reset --hard."""
        manager = ApprovalManager(mode=ApprovalMode.PARANOID, ui_callback=None)

        is_dangerous, warning = manager.is_dangerous_command("git reset --hard HEAD~1")

        assert is_dangerous is True
        assert "git reset" in warning.lower()

    def test_detect_force_push(self):
        """Should detect git push --force."""
        manager = ApprovalManager(mode=ApprovalMode.PARANOID, ui_callback=None)

        is_dangerous, warning = manager.is_dangerous_command(
            "git push origin main --force"
        )

        assert is_dangerous is True
        assert "force" in warning.lower()

    def test_detect_sudo_command(self):
        """Should detect sudo commands."""
        manager = ApprovalManager(mode=ApprovalMode.PARANOID, ui_callback=None)

        is_dangerous, warning = manager.is_dangerous_command("sudo apt-get install foo")

        assert is_dangerous is True
        assert "sudo" in warning.lower()

    def test_detect_chmod_777(self):
        """Should detect dangerous chmod 777."""
        manager = ApprovalManager(mode=ApprovalMode.PARANOID, ui_callback=None)

        is_dangerous, warning = manager.is_dangerous_command("chmod -R 777 /var/www")

        assert is_dangerous is True
        assert "permissions" in warning.lower()

    def test_safe_command_not_flagged(self):
        """Safe commands should not be flagged as dangerous."""
        manager = ApprovalManager(mode=ApprovalMode.PARANOID, ui_callback=None)

        is_dangerous, warning = manager.is_dangerous_command("ls -la")

        assert is_dangerous is False
        assert warning is None

    def test_safe_git_commands_not_flagged(self):
        """Safe git commands should not be flagged."""
        manager = ApprovalManager(mode=ApprovalMode.PARANOID, ui_callback=None)

        commands = [
            "git status",
            "git diff",
            "git log",
            "git add .",
            "git commit -m 'test'",
            "git push origin main",
        ]

        for cmd in commands:
            is_dangerous, warning = manager.is_dangerous_command(cmd)
            assert (
                is_dangerous is False
            ), f"Command '{cmd}' incorrectly flagged as dangerous"


class TestPathSafetyChecks:
    """Test path safety checks."""

    def test_is_outside_project(self, temp_project_dir):
        """Should detect paths outside project directory."""
        manager = ApprovalManager(mode=ApprovalMode.PARANOID, ui_callback=None)
        manager._project_root = temp_project_dir

        # Path outside project
        outside_path = "/tmp/other_project/file.txt"
        assert manager.is_outside_project(outside_path) is True

        # Path inside project
        inside_path = str(temp_project_dir / "file.txt")
        assert manager.is_outside_project(inside_path) is False

    def test_is_system_path(self):
        """Should detect system/sensitive paths."""
        manager = ApprovalManager(mode=ApprovalMode.PARANOID, ui_callback=None)

        system_paths = [
            "/etc/passwd",
            "/sys/kernel",
            "/proc/cpuinfo",
            "/dev/sda",
            "/boot/grub",
            "~/.ssh/id_rsa",
            "~/.gnupg/private-keys",
            "/usr/bin/python",
            "/sbin/init",
        ]

        for path in system_paths:
            assert (
                manager.is_system_path(path) is True
            ), f"Path '{path}' not detected as system path"

    def test_non_system_path(self):
        """Normal paths should not be flagged as system paths."""
        manager = ApprovalManager(mode=ApprovalMode.PARANOID, ui_callback=None)

        normal_paths = [
            "/home/user/project/file.txt",
            "~/Documents/notes.md",
            "./src/main.py",
            "test.txt",
        ]

        for path in normal_paths:
            assert (
                manager.is_system_path(path) is False
            ), f"Path '{path}' incorrectly flagged as system"

    def test_project_root_detection(self, temp_project_dir):
        """Should detect project root from .git directory."""
        # Change to temp project directory
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)

            manager = ApprovalManager(mode=ApprovalMode.PARANOID, ui_callback=None)

            # Should detect temp_project_dir as root (has .git)
            assert manager._project_root == temp_project_dir
        finally:
            os.chdir(original_cwd)

    def test_project_root_detection_with_pyproject(self, tmp_path):
        """Should detect project root from pyproject.toml."""
        project_dir = tmp_path / "python_project"
        project_dir.mkdir()
        (project_dir / "pyproject.toml").touch()

        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)

            manager = ApprovalManager(mode=ApprovalMode.PARANOID, ui_callback=None)

            assert manager._project_root == project_dir
        finally:
            os.chdir(original_cwd)


class TestApprovalManagerNoCallback:
    """Test ApprovalManager behavior without UI callback."""

    def test_no_callback_denies_by_default(self):
        """Without UI callback, should deny by default."""
        manager = ApprovalManager(mode=ApprovalMode.PARANOID, ui_callback=None)

        result = manager.should_approve("run_bash", {"command": "ls"}, RiskLevel.HIGH)

        assert result is False

    def test_balanced_no_callback_approves_safe(self):
        """Balanced mode without callback should still auto-approve SAFE."""
        manager = ApprovalManager(mode=ApprovalMode.BALANCED, ui_callback=None)

        result = manager.should_approve(
            "read_file", {"path": "test.txt"}, RiskLevel.SAFE
        )

        assert result is True

    def test_balanced_no_callback_denies_medium(self):
        """Balanced mode without callback should deny MEDIUM/HIGH."""
        manager = ApprovalManager(mode=ApprovalMode.BALANCED, ui_callback=None)

        result = manager.should_approve(
            "write_file",
            {"path": "test.txt", "content": "data"},
            RiskLevel.MEDIUM,
        )

        assert result is False
