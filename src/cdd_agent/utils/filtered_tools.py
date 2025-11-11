"""Filtered tool registries for specialized agents.

This module provides tool registry wrappers that restrict which tools
agents can access, enforcing architectural boundaries.
"""

import logging
from typing import Any, Dict, Set

logger = logging.getLogger(__name__)


class ReadOnlyToolRegistry:
    """Tool registry that only allows read operations.

    Used by agents like Socrates that need to explore context
    but should never modify files.

    Example:
        base_registry = ToolRegistry()
        readonly_registry = ReadOnlyToolRegistry(base_registry)

        # This works
        readonly_registry.execute("read_file", {"path": "spec.yaml"})

        # This raises PermissionError
        readonly_registry.execute("write_file", {"path": "spec.yaml", "content": "..."})
    """

    # Tools that only read, never write
    ALLOWED_TOOLS: Set[str] = {
        "read_file",
        "list_files",
        "glob_files",
        "grep_files",
        "git_status",
        "git_diff",
        "git_log",
    }

    def __init__(self, base_registry: Any):
        """Initialize read-only registry wrapper.

        Args:
            base_registry: The underlying ToolRegistry to wrap
        """
        self.base_registry = base_registry
        logger.debug(f"Created ReadOnlyToolRegistry with {len(self.ALLOWED_TOOLS)} allowed tools")

    def get_schemas(self, include_risk_level: bool = False) -> list:
        """Return only read-only tool schemas.

        Filters the base registry's schemas to only include read operations.

        Args:
            include_risk_level: If True, include custom risk_level field.
                               Set to False when using OAuth (Anthropic rejects custom fields)

        Returns:
            List of tool schemas for read-only tools
        """
        all_schemas = self.base_registry.get_schemas(include_risk_level=include_risk_level)
        filtered_schemas = [
            schema for schema in all_schemas
            if schema.get("name") in self.ALLOWED_TOOLS
        ]

        logger.debug(
            f"Filtered schemas: {len(all_schemas)} → {len(filtered_schemas)} "
            f"(allowed: {', '.join(self.ALLOWED_TOOLS)})"
        )

        return filtered_schemas

    def execute(self, name: str, args: Dict[str, Any]) -> Any:
        """Execute tool only if it's in the allowed set.

        Args:
            name: Tool name
            args: Tool arguments

        Returns:
            Tool execution result

        Raises:
            PermissionError: If tool is not in allowed set
        """
        if name not in self.ALLOWED_TOOLS:
            error_msg = (
                f"Permission denied: '{name}' is not allowed in read-only mode. "
                f"Allowed tools: {', '.join(sorted(self.ALLOWED_TOOLS))}"
            )
            logger.error(error_msg)
            raise PermissionError(error_msg)

        logger.debug(f"Executing read-only tool: {name}")
        return self.base_registry.execute(name, args)

    def get_risk_level(self, name: str) -> str:
        """Get risk level for a tool.

        Args:
            name: Tool name

        Returns:
            Risk level ("low" for read tools, or from base registry)
        """
        if name in self.ALLOWED_TOOLS:
            return "low"  # Read tools are always low risk

        # For tools not in allowed set, delegate to base registry
        # (though execute() will block them anyway)
        return self.base_registry.get_risk_level(name)
