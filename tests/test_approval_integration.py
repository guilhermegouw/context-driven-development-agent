"""Integration tests for approval system with Agent."""

from unittest.mock import MagicMock

import pytest

from cdd_agent.agent import Agent
from cdd_agent.approval import ApprovalManager
from cdd_agent.config import ApprovalMode
from cdd_agent.config import ProviderConfig
from cdd_agent.tools import RiskLevel
from cdd_agent.tools import ToolRegistry


@pytest.fixture
def mock_provider_config():
    """Create a mock provider configuration."""
    config = ProviderConfig(
        provider_type="anthropic",
        api_key="test-key",
        base_url="https://api.anthropic.com",
        model_small="claude-3-haiku-20240307",
        model_mid="claude-3-5-sonnet-20241022",
        model_big="claude-3-opus-20240229",
    )
    return config


@pytest.fixture
def tool_registry_with_risks():
    """Create tool registry with various risk levels."""
    registry = ToolRegistry()

    @registry.register(risk_level=RiskLevel.SAFE)
    def read_file(path: str) -> str:
        """Read a file (safe operation)."""
        return f"File content from {path}"

    @registry.register(risk_level=RiskLevel.SAFE)
    def glob_files(pattern: str) -> str:
        """Find files by pattern (safe operation)."""
        return f"Files matching {pattern}: test.py, main.py"

    @registry.register(risk_level=RiskLevel.MEDIUM)
    def write_file(path: str, content: str) -> str:
        """Write a file (medium risk)."""
        return f"Written {len(content)} bytes to {path}"

    @registry.register(risk_level=RiskLevel.HIGH)
    def run_bash(command: str) -> str:
        """Run bash command (high risk)."""
        return f"Command output: {command} executed"

    return registry


class TestAgentWithApproval:
    """Test Agent integration with ApprovalManager."""

    def test_agent_with_paranoid_mode_asks_for_safe_tools(
        self, mock_provider_config, tool_registry_with_risks
    ):
        """Agent with paranoid mode should ask for approval on safe tools."""
        mock_ui_callback = MagicMock(return_value=True)
        approval_manager = ApprovalManager(
            mode=ApprovalMode.PARANOID, ui_callback=mock_ui_callback
        )

        agent = Agent(
            provider_config=mock_provider_config,
            tool_registry=tool_registry_with_risks,
            approval_manager=approval_manager,
        )

        # Execute a SAFE tool
        result = agent._execute_tool("read_file", {"path": "test.txt"}, "tool_1")

        # Should have asked for approval
        mock_ui_callback.assert_called_once()
        assert result["type"] == "tool_result"
        assert "File content" in result["content"]

    def test_agent_with_paranoid_mode_respects_denial(
        self, mock_provider_config, tool_registry_with_risks
    ):
        """Agent should respect approval denial."""
        mock_ui_callback = MagicMock(return_value=False)  # Deny
        approval_manager = ApprovalManager(
            mode=ApprovalMode.PARANOID, ui_callback=mock_ui_callback
        )

        agent = Agent(
            provider_config=mock_provider_config,
            tool_registry=tool_registry_with_risks,
            approval_manager=approval_manager,
        )

        # Try to execute tool - should be denied
        result = agent._execute_tool("run_bash", {"command": "ls"}, "tool_1")

        mock_ui_callback.assert_called_once()
        assert result["type"] == "tool_result"
        assert result["is_error"] is True
        assert "denied" in result["content"].lower()

    def test_agent_with_balanced_mode_auto_approves_safe(
        self, mock_provider_config, tool_registry_with_risks
    ):
        """Agent with balanced mode should auto-approve SAFE tools."""
        mock_ui_callback = MagicMock(return_value=True)
        approval_manager = ApprovalManager(
            mode=ApprovalMode.BALANCED, ui_callback=mock_ui_callback
        )

        agent = Agent(
            provider_config=mock_provider_config,
            tool_registry=tool_registry_with_risks,
            approval_manager=approval_manager,
        )

        # Execute SAFE tool
        result = agent._execute_tool("read_file", {"path": "test.txt"}, "tool_1")

        # Should NOT have asked (auto-approved)
        mock_ui_callback.assert_not_called()
        assert result["type"] == "tool_result"
        assert "File content" in result["content"]

    def test_agent_with_balanced_mode_asks_for_medium(
        self, mock_provider_config, tool_registry_with_risks
    ):
        """Agent with balanced mode should ask for MEDIUM risk tools."""
        mock_ui_callback = MagicMock(return_value=True)
        approval_manager = ApprovalManager(
            mode=ApprovalMode.BALANCED, ui_callback=mock_ui_callback
        )

        agent = Agent(
            provider_config=mock_provider_config,
            tool_registry=tool_registry_with_risks,
            approval_manager=approval_manager,
        )

        # Execute MEDIUM risk tool
        result = agent._execute_tool(
            "write_file", {"path": "test.txt", "content": "data"}, "tool_1"
        )

        # Should have asked for approval
        mock_ui_callback.assert_called_once()
        assert result["type"] == "tool_result"
        assert "Written" in result["content"]

    def test_agent_with_trusting_mode_remembers_approval(
        self, mock_provider_config, tool_registry_with_risks
    ):
        """Agent with trusting mode should remember approvals."""
        mock_ui_callback = MagicMock(return_value=True)
        approval_manager = ApprovalManager(
            mode=ApprovalMode.TRUSTING, ui_callback=mock_ui_callback
        )

        agent = Agent(
            provider_config=mock_provider_config,
            tool_registry=tool_registry_with_risks,
            approval_manager=approval_manager,
        )

        # First execution - should ask
        result1 = agent._execute_tool(
            "write_file", {"path": "test1.txt", "content": "data"}, "tool_1"
        )
        assert mock_ui_callback.call_count == 1

        # Second execution of same tool - should NOT ask (remembered)
        result2 = agent._execute_tool(
            "write_file", {"path": "test2.txt", "content": "other"}, "tool_2"
        )
        assert mock_ui_callback.call_count == 1  # Still only called once

        assert result1["type"] == "tool_result"
        assert result2["type"] == "tool_result"

    def test_agent_without_approval_manager_executes_normally(
        self, mock_provider_config, tool_registry_with_risks
    ):
        """Agent without approval manager should execute tools normally."""
        agent = Agent(
            provider_config=mock_provider_config,
            tool_registry=tool_registry_with_risks,
            approval_manager=None,  # No approval manager
        )

        # Should execute without asking
        result = agent._execute_tool("run_bash", {"command": "ls"}, "tool_1")

        assert result["type"] == "tool_result"
        assert "Command output" in result["content"]

    def test_agent_handles_approval_manager_exception(
        self, mock_provider_config, tool_registry_with_risks
    ):
        """Agent should handle approval manager exceptions gracefully."""
        mock_ui_callback = MagicMock(side_effect=Exception("UI error"))
        approval_manager = ApprovalManager(
            mode=ApprovalMode.PARANOID, ui_callback=mock_ui_callback
        )

        agent = Agent(
            provider_config=mock_provider_config,
            tool_registry=tool_registry_with_risks,
            approval_manager=approval_manager,
        )

        # Should handle exception and still execute (or deny gracefully)
        result = agent._execute_tool("read_file", {"path": "test.txt"}, "tool_1")

        # Should either execute or return an error, but not crash
        assert result["type"] == "tool_result"


class TestRiskLevelClassification:
    """Test that tools are properly classified with risk levels."""

    def test_tool_registry_stores_risk_levels(self, tool_registry_with_risks):
        """Tool registry should store risk levels for each tool."""
        assert tool_registry_with_risks.get_risk_level("read_file") == RiskLevel.SAFE
        assert tool_registry_with_risks.get_risk_level("glob_files") == RiskLevel.SAFE
        assert tool_registry_with_risks.get_risk_level("write_file") == RiskLevel.MEDIUM
        assert tool_registry_with_risks.get_risk_level("run_bash") == RiskLevel.HIGH

    def test_tool_schema_includes_risk_level(self, tool_registry_with_risks):
        """Tool schema should include risk_level metadata."""
        schemas = tool_registry_with_risks.get_schemas(include_risk_level=True)

        read_file_schema = next(s for s in schemas if s["name"] == "read_file")
        assert read_file_schema["risk_level"] == "safe"

        write_file_schema = next(s for s in schemas if s["name"] == "write_file")
        assert write_file_schema["risk_level"] == "medium"

        run_bash_schema = next(s for s in schemas if s["name"] == "run_bash")
        assert run_bash_schema["risk_level"] == "high"


class TestApprovalUICallback:
    """Test approval UI callback integration."""

    def test_ui_callback_receives_correct_parameters(
        self, mock_provider_config, tool_registry_with_risks
    ):
        """UI callback should receive tool name, args, and risk level."""
        mock_ui_callback = MagicMock(return_value=True)
        approval_manager = ApprovalManager(
            mode=ApprovalMode.PARANOID, ui_callback=mock_ui_callback
        )

        agent = Agent(
            provider_config=mock_provider_config,
            tool_registry=tool_registry_with_risks,
            approval_manager=approval_manager,
        )

        # Execute a tool
        agent._execute_tool(
            "write_file", {"path": "test.txt", "content": "data"}, "tool_1"
        )

        # Verify UI callback was called with correct parameters
        mock_ui_callback.assert_called_once_with(
            "write_file",
            {"path": "test.txt", "content": "data"},
            RiskLevel.MEDIUM,
        )

    def test_ui_callback_return_value_controls_execution(
        self, mock_provider_config, tool_registry_with_risks
    ):
        """UI callback return value should control whether tool executes."""
        # Test with approval
        mock_ui_approve = MagicMock(return_value=True)
        approval_manager_approve = ApprovalManager(
            mode=ApprovalMode.PARANOID, ui_callback=mock_ui_approve
        )

        agent_approve = Agent(
            provider_config=mock_provider_config,
            tool_registry=tool_registry_with_risks,
            approval_manager=approval_manager_approve,
        )

        result_approved = agent_approve._execute_tool(
            "read_file", {"path": "test.txt"}, "tool_1"
        )
        # Successful execution - no is_error key or is_error is False
        assert result_approved.get("is_error", False) is False
        assert "File content" in result_approved["content"]

        # Test with denial
        mock_ui_deny = MagicMock(return_value=False)
        approval_manager_deny = ApprovalManager(
            mode=ApprovalMode.PARANOID, ui_callback=mock_ui_deny
        )

        agent_deny = Agent(
            provider_config=mock_provider_config,
            tool_registry=tool_registry_with_risks,
            approval_manager=approval_manager_deny,
        )

        result_denied = agent_deny._execute_tool(
            "read_file", {"path": "test.txt"}, "tool_2"
        )
        assert result_denied.get("is_error", False) is True
        assert "denied" in result_denied["content"].lower()


class TestDangerousCommandIntegration:
    """Test dangerous command detection integration with approval."""

    def test_dangerous_command_warning_in_ui_callback(
        self, mock_provider_config, tool_registry_with_risks
    ):
        """Dangerous commands should trigger warnings visible to UI."""
        mock_ui_callback = MagicMock(return_value=True)
        approval_manager = ApprovalManager(
            mode=ApprovalMode.BALANCED, ui_callback=mock_ui_callback
        )

        agent = Agent(
            provider_config=mock_provider_config,
            tool_registry=tool_registry_with_risks,
            approval_manager=approval_manager,
        )

        # Execute dangerous bash command
        agent._execute_tool("run_bash", {"command": "rm -rf /tmp/test"}, "tool_1")

        # UI callback should be called (HIGH risk)
        mock_ui_callback.assert_called_once()

        # The ApprovalManager should detect it as dangerous
        is_dangerous, warning = approval_manager.is_dangerous_command(
            "rm -rf /tmp/test"
        )
        assert is_dangerous is True
        assert warning is not None
