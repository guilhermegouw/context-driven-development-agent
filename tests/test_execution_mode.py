"""Tests for execution mode functionality.

This module tests:
- ExecutionMode enum and helper methods
- Tool registry read-only filtering
- Agent execution mode integration
- Config manager execution mode handling
"""

import os
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.cdd_agent.agent import Agent
from src.cdd_agent.config import ConfigManager, ProviderConfig, Settings
from src.cdd_agent.tools import RiskLevel, ToolRegistry
from src.cdd_agent.utils.execution_state import ExecutionMode


class TestExecutionModeEnum:
    """Test ExecutionMode enum and its helper methods."""

    def test_execution_mode_values(self):
        """Test ExecutionMode enum values."""
        assert ExecutionMode.NORMAL.value == "normal"
        assert ExecutionMode.PLAN.value == "plan"

    def test_is_read_only(self):
        """Test is_read_only method."""
        assert ExecutionMode.NORMAL.is_read_only() is False
        assert ExecutionMode.PLAN.is_read_only() is True

    def test_get_display_name(self):
        """Test get_display_name method."""
        assert ExecutionMode.NORMAL.get_display_name() == "Normal"
        assert ExecutionMode.PLAN.get_display_name() == "Plan"

    def test_get_icon(self):
        """Test get_icon method."""
        assert ExecutionMode.NORMAL.get_icon() == "▶"
        assert ExecutionMode.PLAN.get_icon() == "⏸"

    def test_get_description(self):
        """Test get_description method."""
        assert "full" in ExecutionMode.NORMAL.get_description().lower()
        assert "read-only" in ExecutionMode.PLAN.get_description().lower()


class TestToolRegistryFiltering:
    """Test tool registry read-only filtering."""

    def test_get_schemas_all_tools(self):
        """Test getting all tools without filtering."""
        registry = ToolRegistry()

        # Register test tools with different risk levels
        @registry.register(risk_level=RiskLevel.SAFE)
        def read_tool():
            """Read-only tool."""
            pass

        @registry.register(risk_level=RiskLevel.MEDIUM)
        def write_tool():
            """Write tool."""
            pass

        @registry.register(risk_level=RiskLevel.HIGH)
        def dangerous_tool():
            """Dangerous tool."""
            pass

        # Get all tools
        all_tools = registry.get_schemas(read_only=False)
        assert len(all_tools) == 3

        # Check tool names
        tool_names = {tool["name"] for tool in all_tools}
        assert "read_tool" in tool_names
        assert "write_tool" in tool_names
        assert "dangerous_tool" in tool_names

    def test_get_schemas_read_only_filter(self):
        """Test getting only read-only (SAFE) tools."""
        registry = ToolRegistry()

        # Register test tools with different risk levels
        @registry.register(risk_level=RiskLevel.SAFE)
        def read_tool():
            """Read-only tool."""
            pass

        @registry.register(risk_level=RiskLevel.MEDIUM)
        def write_tool():
            """Write tool."""
            pass

        @registry.register(risk_level=RiskLevel.HIGH)
        def dangerous_tool():
            """Dangerous tool."""
            pass

        # Get only read-only tools
        read_only_tools = registry.get_schemas(read_only=True, include_risk_level=True)
        assert len(read_only_tools) == 1

        # Check only SAFE tool is included
        assert read_only_tools[0]["name"] == "read_tool"
        assert read_only_tools[0]["risk_level"] == RiskLevel.SAFE.value

    def test_get_schemas_include_risk_level(self):
        """Test risk_level field inclusion/exclusion."""
        registry = ToolRegistry()

        @registry.register(risk_level=RiskLevel.SAFE)
        def test_tool():
            """Test tool."""
            pass

        # With risk_level
        with_risk = registry.get_schemas(include_risk_level=True)
        assert "risk_level" in with_risk[0]

        # Without risk_level (for OAuth compatibility)
        without_risk = registry.get_schemas(include_risk_level=False)
        assert "risk_level" not in without_risk[0]


class TestAgentExecutionMode:
    """Test Agent execution mode integration."""

    @pytest.fixture
    def mock_provider_config(self):
        """Create mock provider config."""
        return ProviderConfig(
            auth_token="test-token",
            base_url="https://api.test.com",
            models={"small": "test-small", "mid": "test-mid", "big": "test-big"},
        )

    @pytest.fixture
    def tool_registry(self):
        """Create tool registry with test tools."""
        registry = ToolRegistry()

        @registry.register(risk_level=RiskLevel.SAFE)
        def read_file(path: str):
            """Read file."""
            return f"Content of {path}"

        @registry.register(risk_level=RiskLevel.MEDIUM)
        def write_file(path: str, content: str):
            """Write file."""
            return f"Wrote to {path}"

        return registry

    def test_agent_defaults_to_normal_mode(self, mock_provider_config, tool_registry):
        """Test agent defaults to NORMAL execution mode."""
        agent = Agent(
            provider_config=mock_provider_config,
            tool_registry=tool_registry,
        )
        assert agent.execution_mode == ExecutionMode.NORMAL

    def test_agent_can_start_in_plan_mode(self, mock_provider_config, tool_registry):
        """Test agent can start in PLAN mode."""
        agent = Agent(
            provider_config=mock_provider_config,
            tool_registry=tool_registry,
            execution_mode=ExecutionMode.PLAN,
        )
        assert agent.execution_mode == ExecutionMode.PLAN

    def test_agent_can_switch_execution_mode(self, mock_provider_config, tool_registry):
        """Test agent can switch execution mode at runtime."""
        agent = Agent(
            provider_config=mock_provider_config,
            tool_registry=tool_registry,
        )

        # Start in NORMAL mode
        assert agent.execution_mode == ExecutionMode.NORMAL

        # Switch to PLAN mode
        agent.set_execution_mode(ExecutionMode.PLAN)
        assert agent.execution_mode == ExecutionMode.PLAN

        # Switch back to NORMAL mode
        agent.set_execution_mode(ExecutionMode.NORMAL)
        assert agent.execution_mode == ExecutionMode.NORMAL


class TestConfigManagerExecutionMode:
    """Test ConfigManager execution mode handling."""

    def test_settings_default_execution_mode(self):
        """Test Settings has default_execution_mode field."""
        settings = Settings(
            default_provider="anthropic",
            providers={
                "anthropic": ProviderConfig(
                    auth_token="test",
                    base_url="https://api.test.com",
                    models={"small": "test-s", "mid": "test-m", "big": "test-b"},
                )
            },
        )
        assert settings.default_execution_mode == "normal"

    def test_settings_validates_execution_mode(self):
        """Test Settings validates execution mode."""
        with pytest.raises(ValueError, match="must be 'normal' or 'plan'"):
            Settings(
                default_provider="anthropic",
                providers={
                    "anthropic": ProviderConfig(
                        auth_token="test",
                        base_url="https://api.test.com",
                        models={"small": "test-s", "mid": "test-m", "big": "test-b"},
                    )
                },
                default_execution_mode="invalid",
            )

    def test_get_effective_execution_mode_defaults_to_normal(self, tmp_path):
        """Test get_effective_execution_mode defaults to normal."""
        config_manager = ConfigManager(config_dir=tmp_path)

        # Create minimal config
        settings = Settings(
            default_provider="anthropic",
            providers={
                "anthropic": ProviderConfig(
                    auth_token="test",
                    base_url="https://api.test.com",
                    models={"small": "test-s", "mid": "test-m", "big": "test-b"},
                )
            },
        )
        config_manager.save(settings)

        # Should default to "normal"
        mode = config_manager.get_effective_execution_mode()
        assert mode == "normal"

    def test_get_effective_execution_mode_cli_flag_priority(self, tmp_path):
        """Test CLI flag has highest priority."""
        config_manager = ConfigManager(config_dir=tmp_path)

        # Create config with plan mode
        settings = Settings(
            default_provider="anthropic",
            providers={
                "anthropic": ProviderConfig(
                    auth_token="test",
                    base_url="https://api.test.com",
                    models={"small": "test-s", "mid": "test-m", "big": "test-b"},
                )
            },
            default_execution_mode="normal",
        )
        config_manager.save(settings)

        # CLI flag should override config
        mode = config_manager.get_effective_execution_mode(plan_flag=True)
        assert mode == "plan"

    def test_get_effective_execution_mode_env_var_priority(self, tmp_path):
        """Test environment variable has second priority."""
        config_manager = ConfigManager(config_dir=tmp_path)

        # Create config with normal mode
        settings = Settings(
            default_provider="anthropic",
            providers={
                "anthropic": ProviderConfig(
                    auth_token="test",
                    base_url="https://api.test.com",
                    models={"small": "test-s", "mid": "test-m", "big": "test-b"},
                )
            },
            default_execution_mode="normal",
        )
        config_manager.save(settings)

        # Environment variable should override config
        with patch.dict(os.environ, {"CDD_EXECUTION_MODE": "plan"}):
            mode = config_manager.get_effective_execution_mode()
            assert mode == "plan"

    def test_get_effective_execution_mode_config_file(self, tmp_path):
        """Test config file value is used when no overrides."""
        config_manager = ConfigManager(config_dir=tmp_path)

        # Create config with plan mode
        settings = Settings(
            default_provider="anthropic",
            providers={
                "anthropic": ProviderConfig(
                    auth_token="test",
                    base_url="https://api.test.com",
                    models={"small": "test-s", "mid": "test-m", "big": "test-b"},
                )
            },
            default_execution_mode="plan",
        )
        config_manager.save(settings)

        # Should use config file value
        mode = config_manager.get_effective_execution_mode()
        assert mode == "plan"

    def test_get_effective_execution_mode_invalid_env_var(self, tmp_path):
        """Test invalid environment variable raises error."""
        config_manager = ConfigManager(config_dir=tmp_path)

        # Create minimal config
        settings = Settings(
            default_provider="anthropic",
            providers={
                "anthropic": ProviderConfig(
                    auth_token="test",
                    base_url="https://api.test.com",
                    models={"small": "test-s", "mid": "test-m", "big": "test-b"},
                )
            },
        )
        config_manager.save(settings)

        # Invalid env var should raise error
        with patch.dict(os.environ, {"CDD_EXECUTION_MODE": "invalid"}):
            with pytest.raises(ValueError, match="Invalid CDD_EXECUTION_MODE"):
                config_manager.get_effective_execution_mode()


class TestExecutionModeIntegration:
    """Integration tests for execution mode."""

    def test_plan_mode_limits_available_tools(self):
        """Test that plan mode actually limits tools available to LLM."""
        from src.cdd_agent.tools import create_default_registry

        registry = create_default_registry()

        # Get tools in normal mode
        normal_tools = registry.get_schemas(read_only=False)

        # Get tools in plan mode
        plan_tools = registry.get_schemas(read_only=True)

        # Plan mode should have fewer tools
        assert len(plan_tools) < len(normal_tools)

        # Plan mode should only have SAFE tools
        for tool in plan_tools:
            # Need to check the original schema with risk_level
            tool_with_risk = [
                t for t in registry.get_schemas(read_only=True, include_risk_level=True)
                if t["name"] == tool["name"]
            ][0]
            assert tool_with_risk["risk_level"] == RiskLevel.SAFE.value

    def test_plan_mode_includes_expected_read_only_tools(self):
        """Test plan mode includes expected read-only tools."""
        from src.cdd_agent.tools import create_default_registry

        registry = create_default_registry()
        plan_tools = registry.get_schemas(read_only=True)
        tool_names = {tool["name"] for tool in plan_tools}

        # Check for expected read-only tools
        expected_tools = {
            "read_file",
            "list_files",
            "glob_files",
            "grep_files",
            "git_status",
            "git_diff",
            "git_log",
        }

        assert expected_tools.issubset(tool_names)

    def test_plan_mode_excludes_write_tools(self):
        """Test plan mode excludes write/dangerous tools."""
        from src.cdd_agent.tools import create_default_registry

        registry = create_default_registry()
        plan_tools = registry.get_schemas(read_only=True)
        tool_names = {tool["name"] for tool in plan_tools}

        # Check that write/dangerous tools are NOT included
        excluded_tools = {
            "write_file",
            "edit_file",
            "run_bash",
            "git_commit",
        }

        assert excluded_tools.isdisjoint(tool_names)
