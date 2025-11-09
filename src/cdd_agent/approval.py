"""Tool approval management for CDD Agent.

This module provides:
- ApprovalManager: Manages tool execution approval logic
- Dangerous pattern detection for bash commands and file paths
- Session-based approval memory for trusting mode
"""

import os
import re
from pathlib import Path
from typing import Callable, Optional, Set

from .config import ApprovalMode
from .tools import RiskLevel


class ApprovalManager:
    """Manages tool execution approvals based on configured mode.

    Supports three approval modes:
    - PARANOID: Ask for approval on every tool execution
    - BALANCED: Auto-approve safe read-only tools, ask for writes
    - TRUSTING: Remember approvals within session, minimal interruptions
    """

    def __init__(
        self,
        mode: ApprovalMode,
        ui_callback: Optional[Callable[[str, dict, RiskLevel], bool]] = None,
    ):
        """Initialize approval manager.

        Args:
            mode: Approval mode (paranoid/balanced/trusting)
            ui_callback: Function to call for user approval
                         (tool_name, args, risk_level) -> bool
        """
        self.mode = mode
        self.ui_callback = ui_callback
        self._session_approvals: Set[str] = set()  # Approved tools in this session
        self._project_root = self._detect_project_root()

    def should_approve(self, tool_name: str, args: dict, risk_level: RiskLevel) -> bool:
        """Determine if tool execution should be approved.

        Args:
            tool_name: Name of the tool to execute
            args: Tool arguments
            risk_level: Risk classification of the tool

        Returns:
            True if tool should be executed, False otherwise
        """
        # Check if already approved in this session (for trusting mode)
        if self.mode == ApprovalMode.TRUSTING:
            if tool_name in self._session_approvals:
                return True

        # Auto-approve based on mode and risk level
        if self.mode == ApprovalMode.BALANCED:
            if risk_level == RiskLevel.SAFE:
                return True  # Auto-approve safe read-only tools

        # For paranoid mode, always ask
        # For balanced mode, ask for MEDIUM/HIGH risk
        # For trusting mode, ask if not in session approvals
        if self.ui_callback:
            approved = self.ui_callback(tool_name, args, risk_level)

            # Remember approval in trusting mode
            if approved and self.mode == ApprovalMode.TRUSTING:
                self._session_approvals.add(tool_name)

            return approved

        # Default: deny if no UI callback
        return False

    def is_dangerous_command(self, command: str) -> tuple[bool, Optional[str]]:
        """Check if a bash command contains dangerous patterns.

        Args:
            command: Bash command string

        Returns:
            Tuple of (is_dangerous, warning_message)
        """
        dangerous_patterns = [
            (r"\brm\s+-rf?\s+", "Recursive file deletion (rm -rf)"),
            (r"\brm\s+-r\s+", "Recursive file deletion (rm -r)"),
            (r"\bsudo\s+rm", "Sudo file deletion"),
            (r"\bdd\s+if=/dev/zero", "Disk overwrite with dd"),
            (r"\bdd\s+of=/dev/", "Writing to device with dd"),
            (r"\bgit\s+reset\s+--hard", "Hard git reset (loses changes)"),
            (r"\bgit\s+push\s+.*--force", "Force git push"),
            (r"\bgit\s+push\s+.*-f\b", "Force git push"),
            (r"\bsudo\s+", "Sudo command (elevated privileges)"),
            (r">\s*/dev/sd[a-z]", "Writing to disk device"),
            (r"\bmkfs\.", "Filesystem formatting"),
            (r"\bchmod\s+000", "Removing all permissions"),
            (r"\bchmod\s+-R\s+777", "Dangerous recursive permissions"),
        ]

        for pattern, warning in dangerous_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return (True, warning)

        return (False, None)

    def is_outside_project(self, path: str) -> bool:
        """Check if a file path is outside the project directory.

        Args:
            path: File path to check

        Returns:
            True if path is outside project root
        """
        try:
            abs_path = Path(path).resolve()
            return not abs_path.is_relative_to(self._project_root)
        except (ValueError, OSError):
            # If path resolution fails, consider it dangerous
            return True

    def is_system_path(self, path: str) -> bool:
        """Check if a file path is a system/sensitive path.

        Args:
            path: File path to check

        Returns:
            True if path is a system path
        """
        sensitive_paths = [
            "/etc/",
            "/sys/",
            "/proc/",
            "/dev/",
            "/boot/",
            "~/.ssh/",
            "~/.gnupg/",
            "/usr/bin/",
            "/usr/sbin/",
            "/sbin/",
            "/bin/",
        ]

        abs_path = os.path.expanduser(path)

        for sensitive in sensitive_paths:
            sensitive_abs = os.path.expanduser(sensitive)
            if abs_path.startswith(sensitive_abs):
                return True

        return False

    def _detect_project_root(self) -> Path:
        """Detect the project root directory.

        Looks for common project indicators like .git, pyproject.toml, etc.

        Returns:
            Path to project root (or current directory if not detected)
        """
        current = Path.cwd()

        # Walk up the directory tree looking for project indicators
        for parent in [current] + list(current.parents):
            if any(
                (parent / indicator).exists()
                for indicator in [".git", "pyproject.toml", "package.json", "go.mod"]
            ):
                return parent

        # Default to current directory
        return current

    def reset_session_approvals(self) -> None:
        """Reset session approvals (useful for starting new conversation)."""
        self._session_approvals.clear()

    def get_session_approvals(self) -> Set[str]:
        """Get the set of approved tools in this session.

        Returns:
            Set of tool names that have been approved
        """
        return self._session_approvals.copy()
