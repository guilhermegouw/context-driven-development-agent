"""Tool registry and basic tools for agent.

This module provides:
- ToolRegistry: Register and execute tools
- Auto-schema generation from function signatures
- Basic file and shell tools
"""

import inspect
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


def make_tool_schema(func: Callable) -> dict:
    """Auto-generate Anthropic tool schema from function signature.

    Args:
        func: Function to generate schema for

    Returns:
        Tool schema in Anthropic format
    """
    sig = inspect.signature(func)
    params = {}
    required = []

    for name, param in sig.parameters.items():
        # Determine parameter type
        param_type = "string"  # Default
        if param.annotation == int:
            param_type = "integer"
        elif param.annotation == bool:
            param_type = "boolean"
        elif param.annotation == float:
            param_type = "number"

        # Extract description from docstring if available
        description = f"Parameter: {name}"

        params[name] = {"type": param_type, "description": description}

        # Check if required (no default value)
        if param.default == inspect.Parameter.empty:
            required.append(name)

    # Get function description from docstring
    doc = inspect.getdoc(func) or f"Execute {func.__name__}"
    description = doc.split("\n")[0]  # First line of docstring

    return {
        "name": func.__name__,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": params,
            "required": required,
        },
    }


class ToolRegistry:
    """Registry for managing and executing tools."""

    def __init__(self):
        """Initialize tool registry."""
        self.tools: Dict[str, Callable] = {}
        self.schemas: Dict[str, dict] = {}

    def register(self, func: Callable) -> Callable:
        """Register a tool function.

        Can be used as a decorator:
        @registry.register
        def my_tool(arg: str) -> str:
            ...

        Args:
            func: Function to register as tool

        Returns:
            The function (for decorator use)
        """
        self.tools[func.__name__] = func
        self.schemas[func.__name__] = make_tool_schema(func)
        return func

    def get_schemas(self) -> List[dict]:
        """Get all tool schemas for LLM.

        Returns:
            List of tool schemas in Anthropic format
        """
        return list(self.schemas.values())

    def execute(self, name: str, args: dict) -> Any:
        """Execute a tool by name.

        Args:
            name: Tool name
            args: Tool arguments

        Returns:
            Tool execution result

        Raises:
            ValueError: If tool not found
        """
        if name not in self.tools:
            raise ValueError(f"Tool '{name}' not found")

        return self.tools[name](**args)

    def list_tools(self) -> List[str]:
        """Get list of registered tool names.

        Returns:
            List of tool names
        """
        return list(self.tools.keys())


# Create default registry
registry = ToolRegistry()


# ============================================================================
# Basic File Tools
# ============================================================================


@registry.register
def read_file(path: str) -> str:
    """Read contents of a file.

    Args:
        path: Path to file to read

    Returns:
        File contents as string

    Raises:
        FileNotFoundError: If file doesn't exist
        PermissionError: If file can't be read
    """
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if not file_path.is_file():
        raise ValueError(f"Not a file: {path}")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    return content


@registry.register
def write_file(path: str, content: str) -> str:
    """Write content to a file.

    Creates parent directories if they don't exist.
    Overwrites existing files.

    Args:
        path: Path to file to write
        content: Content to write

    Returns:
        Success message with file info

    Raises:
        PermissionError: If file can't be written
    """
    file_path = Path(path)

    # Create parent directories if needed
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return f"Successfully wrote {len(content)} characters to {path}"


@registry.register
def list_files(path: str = ".") -> str:
    """List files in a directory.

    Args:
        path: Directory path (defaults to current directory)

    Returns:
        List of files and directories

    Raises:
        FileNotFoundError: If directory doesn't exist
        NotADirectoryError: If path is not a directory
    """
    dir_path = Path(path)

    if not dir_path.exists():
        raise FileNotFoundError(f"Directory not found: {path}")

    if not dir_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")

    items = []
    for item in sorted(dir_path.iterdir()):
        item_type = "📁" if item.is_dir() else "📄"
        items.append(f"{item_type} {item.name}")

    return "\n".join(items) if items else "(empty directory)"


# ============================================================================
# Shell Tool
# ============================================================================


@registry.register
def run_bash(command: str) -> str:
    """Execute a bash command.

    SECURITY WARNING: Only execute trusted commands!
    This runs shell commands with full system access.

    Args:
        command: Shell command to execute

    Returns:
        Command output (stdout + stderr)

    Raises:
        subprocess.CalledProcessError: If command fails
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,  # 30 second timeout
        )

        output = result.stdout
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"

        if result.returncode != 0:
            output += f"\nExit code: {result.returncode}"

        return output

    except subprocess.TimeoutExpired:
        return "Error: Command timed out (30 second limit)"
    except Exception as e:
        return f"Error executing command: {str(e)}"


# ============================================================================
# Utility Functions
# ============================================================================


def create_default_registry() -> ToolRegistry:
    """Create a registry with all default tools.

    Returns:
        ToolRegistry with basic tools registered
    """
    # The global registry already has tools registered via decorators
    return registry


def get_tool_help(tool_name: str) -> Optional[str]:
    """Get help text for a tool.

    Args:
        tool_name: Name of tool

    Returns:
        Help text or None if tool not found
    """
    if tool_name not in registry.tools:
        return None

    func = registry.tools[tool_name]
    return inspect.getdoc(func)
