"""Shared test fixtures for CDD Agent tests."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from cdd_agent.approval import ApprovalManager
from cdd_agent.config import ApprovalMode
from cdd_agent.tools import RiskLevel, ToolRegistry


@pytest.fixture
def mock_ui_callback():
    """Create a mock UI callback for approval tests."""
    return MagicMock(return_value=True)


@pytest.fixture
def mock_ui_callback_deny():
    """Create a mock UI callback that always denies."""
    return MagicMock(return_value=False)


@pytest.fixture
def approval_manager_paranoid(mock_ui_callback):
    """Create ApprovalManager in paranoid mode."""
    return ApprovalManager(mode=ApprovalMode.PARANOID, ui_callback=mock_ui_callback)


@pytest.fixture
def approval_manager_balanced(mock_ui_callback):
    """Create ApprovalManager in balanced mode."""
    return ApprovalManager(mode=ApprovalMode.BALANCED, ui_callback=mock_ui_callback)


@pytest.fixture
def approval_manager_trusting(mock_ui_callback):
    """Create ApprovalManager in trusting mode."""
    return ApprovalManager(mode=ApprovalMode.TRUSTING, ui_callback=mock_ui_callback)


@pytest.fixture
def tool_registry():
    """Create a basic tool registry for testing."""
    registry = ToolRegistry()

    @registry.register(risk_level=RiskLevel.SAFE)
    def read_file(path: str) -> str:
        """Read a file (safe operation)."""
        return f"Reading {path}"

    @registry.register(risk_level=RiskLevel.MEDIUM)
    def write_file(path: str, content: str) -> str:
        """Write a file (medium risk)."""
        return f"Writing to {path}"

    @registry.register(risk_level=RiskLevel.HIGH)
    def run_bash(command: str) -> str:
        """Run bash command (high risk)."""
        return f"Running: {command}"

    return registry


@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary project directory with .git marker."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    (project_dir / ".git").mkdir()
    return project_dir
