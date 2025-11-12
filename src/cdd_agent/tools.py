"""Tool registry and basic tools for agent.

This module provides:
- ToolRegistry: Register and execute tools
- Auto-schema generation from function signatures
- Basic file and shell tools
- Risk-based tool classification for approval system
"""

import fnmatch
import inspect
import re
import subprocess
import time
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# Import background execution components
from .background_executor import get_background_executor, ProcessStatus


class RiskLevel(str, Enum):
    """Risk level classification for tools.

    Used by the approval system to determine which tools need user approval.
    """

    SAFE = "safe"  # Read-only operations, no side effects
    MEDIUM = "medium"  # File modifications, reversible changes
    HIGH = "high"  # Dangerous operations, permanent changes


def make_tool_schema(func: Callable, risk_level: RiskLevel = RiskLevel.SAFE) -> dict:
    """Auto-generate Anthropic tool schema from function signature.

    Args:
        func: Function to generate schema for
        risk_level: Risk classification for approval system

    Returns:
        Tool schema in Anthropic format with risk metadata
    """
    sig = inspect.signature(func)
    params = {}
    required = []

    for name, param in sig.parameters.items():
        # Determine parameter type
        param_type = "string"  # Default
        if param.annotation is int:
            param_type = "integer"
        elif param.annotation is bool:
            param_type = "boolean"
        elif param.annotation is float:
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
        "risk_level": risk_level.value,  # Add risk metadata
    }


class ToolRegistry:
    """Registry for managing and executing tools."""

    def __init__(self):
        """Initialize tool registry."""
        self.tools: Dict[str, Callable] = {}
        self.schemas: Dict[str, dict] = {}
        self.risk_levels: Dict[str, RiskLevel] = {}

    def register(
        self, func: Callable = None, risk_level: RiskLevel = RiskLevel.SAFE
    ) -> Callable:
        """Register a tool function with risk classification.

        Can be used as a decorator:
        @registry.register
        def my_tool(arg: str) -> str:
            ...

        Or with risk level:
        @registry.register(risk_level=RiskLevel.HIGH)
        def dangerous_tool(arg: str) -> str:
            ...

        Args:
            func: Function to register as tool
            risk_level: Risk classification for approval system

        Returns:
            The function (for decorator use) or decorator function
        """

        def decorator(f: Callable) -> Callable:
            self.tools[f.__name__] = f
            self.schemas[f.__name__] = make_tool_schema(f, risk_level)
            self.risk_levels[f.__name__] = risk_level
            return f

        # Support both @register and @register(risk_level=...)
        if func is None:
            # Called with arguments: @register(risk_level=...)
            return decorator
        else:
            # Called without arguments: @register
            return decorator(func)

    def get_schemas(
        self, include_risk_level: bool = False, read_only: bool = False
    ) -> List[dict]:
        """Get all tool schemas for LLM.

        Args:
            include_risk_level: If True, include custom risk_level field.
                               Set to False when using OAuth (Anthropic rejects custom fields)
            read_only: If True, only return SAFE (read-only) tools for Plan Mode

        Returns:
            List of tool schemas in Anthropic format

        Read-only tools (RiskLevel.SAFE):
            - read_file: Read file contents
            - list_files: List directory contents
            - glob_files: Find files by pattern
            - grep_files: Search file contents
            - git_status: Check git status
            - git_diff: View git diff
            - git_log: View git log
            - get_background_status: Check background process status
            - get_background_output: Get background process output
            - list_background_processes: List all background processes
        """
        schemas = list(self.schemas.values())

        # Filter to read-only tools if requested (for Plan Mode)
        if read_only:
            schemas = [
                schema
                for schema in schemas
                if schema.get("risk_level") == RiskLevel.SAFE.value
            ]

        if not include_risk_level:
            # Remove risk_level field for API compatibility
            # OAuth API rejects custom fields: "Extra inputs are not permitted"
            schemas = [
                {k: v for k, v in schema.items() if k != "risk_level"}
                for schema in schemas
            ]

        return schemas

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

    def get_risk_level(self, name: str) -> RiskLevel:
        """Get risk level for a tool.

        Args:
            name: Tool name

        Returns:
            Risk level of the tool

        Raises:
            ValueError: If tool not found
        """
        if name not in self.risk_levels:
            raise ValueError(f"Tool '{name}' not found")
        return self.risk_levels[name]


# Create default registry
registry = ToolRegistry()


# ============================================================================
# Basic File Tools
# ============================================================================


@registry.register(risk_level=RiskLevel.SAFE)
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
    from .logging import get_logger
    logger = get_logger()

    logger.info(f"📖 READ_FILE called: {path}")

    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if not file_path.is_file():
        raise ValueError(f"Not a file: {path}")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    logger.info(f"📖 READ_FILE completed: {path} ({len(content)} chars)")

    return content


@registry.register(risk_level=RiskLevel.MEDIUM)
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


@registry.register(risk_level=RiskLevel.SAFE)
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
    from .logging import get_logger
    logger = get_logger()

    logger.info(f"📂 LIST_FILES called: {path}")

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


@registry.register(risk_level=RiskLevel.HIGH)
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
    from .logging import get_logger
    logger = get_logger()

    # Truncate long commands for logging
    cmd_preview = command[:100] + "..." if len(command) > 100 else command
    logger.info(f"🔧 RUN_BASH called: {cmd_preview}")

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
# Advanced Search Tools
# ============================================================================


def _load_gitignore_patterns(cwd: Path) -> List[str]:
    """Load patterns from .gitignore file.

    Args:
        cwd: Current working directory

    Returns:
        List of gitignore patterns
    """
    gitignore = cwd / ".gitignore"
    patterns = []

    if gitignore.exists():
        try:
            with open(gitignore, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if line and not line.startswith("#"):
                        patterns.append(line)
        except Exception:
            pass  # Ignore errors reading .gitignore

    # Always ignore common directories
    patterns.extend(
        [
            ".git",
            "__pycache__",
            "node_modules",
            ".venv",
            "venv",
            "*.pyc",
            ".DS_Store",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            "dist",
            "build",
            "*.egg-info",
        ]
    )

    return patterns


def _should_include_path(path: Path, gitignore_patterns: List[str]) -> bool:
    """Check if path should be included (not in gitignore).

    Args:
        path: File path to check
        gitignore_patterns: List of gitignore patterns

    Returns:
        True if file should be included
    """
    if not path.is_file():
        return False

    path_str = str(path)
    path_parts = path.parts

    for pattern in gitignore_patterns:
        # Handle directory patterns
        if pattern.endswith("/"):
            if pattern.rstrip("/") in path_parts:
                return False
        # Handle glob patterns
        elif fnmatch.fnmatch(path.name, pattern):
            return False
        # Handle path patterns
        elif fnmatch.fnmatch(path_str, f"*{pattern}*"):
            return False

    return True


def _format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string
    """
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f}MB"


def _format_relative_time(timestamp: float) -> str:
    """Format timestamp as relative time.

    Args:
        timestamp: Unix timestamp

    Returns:
        Relative time string (e.g., "2 hours ago")
    """
    now = time.time()
    diff = now - timestamp

    if diff < 60:
        return "just now"
    elif diff < 3600:
        minutes = int(diff / 60)
        return f"{minutes} min ago"
    elif diff < 86400:
        hours = int(diff / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    else:
        days = int(diff / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"


@registry.register(risk_level=RiskLevel.SAFE)
def glob_files(pattern: str, max_results: int = 100) -> str:
    """Find files matching a glob pattern.

    Supports advanced patterns like **/*.py (all Python files recursively).
    Respects .gitignore patterns by default.

    Args:
        pattern: Glob pattern (e.g., "**/*.py", "src/**/*.test.js")
        max_results: Maximum number of results to return

    Returns:
        Formatted string with matched file paths and metadata

    Examples:
        glob_files("**/*.py")  # All Python files
        glob_files("tests/**/*.test.js")  # All test files in tests/
        glob_files("*.md", max_results=10)  # Max 10 markdown files
    """
    cwd = Path.cwd()
    matches = []

    # Load .gitignore patterns
    gitignore_patterns = _load_gitignore_patterns(cwd)

    try:
        # Handle ** recursive patterns
        if "**" in pattern:
            # Extract the part after **/
            parts = pattern.split("**/")
            if len(parts) > 1 and parts[0]:
                # Pattern like "src/**/*.py"
                base_dir = cwd / parts[0]
                search_pattern = parts[-1]
            else:
                # Pattern like "**/*.py"
                base_dir = cwd
                search_pattern = parts[-1]

            if base_dir.exists():
                for path in base_dir.rglob(search_pattern):
                    if _should_include_path(path, gitignore_patterns):
                        matches.append(path)
        else:
            # Non-recursive glob
            for path in cwd.glob(pattern):
                if _should_include_path(path, gitignore_patterns):
                    matches.append(path)

        # Sort by modification time (most recent first)
        matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        # Limit results
        matches = matches[:max_results]

        # Format output
        if not matches:
            return f"No files found matching pattern: {pattern}"

        result = [f"Found {len(matches)} file(s) matching '{pattern}':\n"]

        for path in matches:
            try:
                # Get relative path from cwd
                rel_path = path.relative_to(cwd)

                # Get file metadata
                stat = path.stat()
                size = _format_file_size(stat.st_size)
                mtime = _format_relative_time(stat.st_mtime)

                result.append(f"  {rel_path} ({size}, {mtime})")
            except Exception:
                # Skip files we can't stat
                continue

        return "\n".join(result)

    except Exception as e:
        return f"Error searching for pattern '{pattern}': {str(e)}"


@registry.register(risk_level=RiskLevel.SAFE)
def grep_files(
    pattern: str,
    file_pattern: str = "**/*",
    context_lines: int = 0,
    max_results: int = 100,
) -> str:
    """Search for a regex pattern in files.

    Args:
        pattern: Regex pattern to search for
        file_pattern: Glob pattern for files to search (default: all files)
        context_lines: Number of context lines before/after match
        max_results: Maximum number of matches to return

    Returns:
        Formatted string with matches, file paths, and line numbers

    Examples:
        grep_files("TODO")  # Find all TODO comments
        grep_files("class\\s+\\w+", "**/*.py")  # Find class definitions
        grep_files("import React", "**/*.tsx", context_lines=2)  # With context
    """
    cwd = Path.cwd()
    gitignore_patterns = _load_gitignore_patterns(cwd)
    from .logging import get_logger
    logger = get_logger()

    pattern_preview = pattern[:50] + "..." if len(pattern) > 50 else pattern
    logger.info(f"🔍 GREP_FILES called: pattern='{pattern_preview}', file_pattern='{file_pattern}'")

    matches_found = []

    try:
        # Compile regex pattern
        regex = re.compile(pattern)

        # Find files to search
        files_to_search = []
        if "**" in file_pattern:
            parts = file_pattern.split("**/")
            base_dir = cwd / parts[0] if parts[0] else cwd
            search_pattern = parts[-1] if len(parts) > 1 else "*"

            if base_dir.exists():
                for path in base_dir.rglob(search_pattern):
                    if _should_include_path(path, gitignore_patterns):
                        files_to_search.append(path)
        else:
            for path in cwd.glob(file_pattern):
                if _should_include_path(path, gitignore_patterns):
                    files_to_search.append(path)

        # Search files
        for file_path in files_to_search:
            try:
                # Skip binary files
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                for line_num, line in enumerate(lines, 1):
                    if regex.search(line):
                        # Get context lines
                        context_before = []
                        context_after = []

                        if context_lines > 0:
                            start = max(0, line_num - context_lines - 1)
                            end = min(len(lines), line_num + context_lines)

                            context_before = lines[start : line_num - 1]
                            context_after = lines[line_num:end]

                        matches_found.append(
                            {
                                "file": file_path.relative_to(cwd),
                                "line_num": line_num,
                                "line": line.rstrip(),
                                "context_before": [
                                    ctx.rstrip() for ctx in context_before
                                ],
                                "context_after": [
                                    ctx.rstrip() for ctx in context_after
                                ],
                            }
                        )

                        if len(matches_found) >= max_results:
                            break

            except (UnicodeDecodeError, PermissionError):
                # Skip binary files or files we can't read
                continue

            if len(matches_found) >= max_results:
                break

        # Format output
        if not matches_found:
            return f"No matches found for pattern: {pattern}"

        result = [f"Found {len(matches_found)} match(es) for '{pattern}':\n"]

        for match in matches_found:
            result.append(f"{match['file']}:{match['line_num']}")

            # Add context before
            for line in match["context_before"]:
                result.append(f"  {line}")

            # Add matching line (highlighted)
            result.append(f"> {match['line']}")

            # Add context after
            for line in match["context_after"]:
                result.append(f"  {line}")

            result.append("")  # Blank line between matches

        return "\n".join(result)

    except re.error as e:
        return f"Invalid regex pattern: {str(e)}"
    except Exception as e:
        return f"Error searching for pattern '{pattern}': {str(e)}"


@registry.register(risk_level=RiskLevel.MEDIUM)
def edit_file(path: str, old_text: str, new_text: str) -> str:
    """Edit a file by replacing old_text with new_text.

    Performs exact string replacement. For safety, the replacement must be unique
    in the file (or it will fail). Use read_file first to see the exact content.

    Args:
        path: Path to file to edit
        old_text: Exact text to find and replace (must be unique)
        new_text: Text to replace with

    Returns:
        Success message with changes made

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If old_text not found or not unique

    Examples:
        edit_file("config.py", "DEBUG = False", "DEBUG = True")
        edit_file(
            "app.py",
            "def old_func():\\n    pass",
            "def new_func():\\n    return 42",
        )
    """
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if not file_path.is_file():
        raise ValueError(f"Not a file: {path}")

    # Read current content
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Check if old_text exists
    if old_text not in content:
        raise ValueError(f"Text not found in file: {old_text[:100]}...")

    # Check if old_text is unique
    count = content.count(old_text)
    if count > 1:
        raise ValueError(
            f"Text appears {count} times in file. "
            "Please provide more context to make it unique."
        )

    # Perform replacement
    new_content = content.replace(old_text, new_text)

    # Write back
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    # Calculate changes
    old_lines = old_text.count("\n") + 1
    new_lines = new_text.count("\n") + 1
    diff_lines = new_lines - old_lines

    return (
        f"Successfully edited {path}: "
        f"replaced {old_lines} line(s) with {new_lines} line(s) "
        f"({diff_lines:+d} lines)"
    )


# ============================================================================
# Git Tools
# ============================================================================


@registry.register(risk_level=RiskLevel.SAFE)
def git_status() -> str:
    """Show git status of the repository.

    Returns:
        Git status output or error message
    """
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return "Not a git repository or git not available"

        output = result.stdout.strip()
        if not output:
            return "Working tree clean (no changes)"

        return f"Git status:\n{output}"

    except subprocess.TimeoutExpired:
        return "Error: Git command timed out"
    except Exception as e:
        return f"Error running git status: {str(e)}"


@registry.register(risk_level=RiskLevel.SAFE)
def git_diff(file_path: str = "") -> str:
    """Show git diff for a file or entire repository.

    Args:
        file_path: Specific file to diff (optional, defaults to all changes)

    Returns:
        Git diff output
    """
    try:
        cmd = ["git", "diff"]
        if file_path:
            cmd.append(file_path)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return f"Error running git diff: {result.stderr}"

        output = result.stdout.strip()
        if not output:
            return "No changes to show"

        return output

    except subprocess.TimeoutExpired:
        return "Error: Git command timed out"
    except Exception as e:
        return f"Error running git diff: {str(e)}"


@registry.register(risk_level=RiskLevel.SAFE)
def git_log(max_commits: int = 10) -> str:
    """Show recent git commit history.

    Args:
        max_commits: Maximum number of commits to show

    Returns:
        Git log output
    """
    try:
        result = subprocess.run(
            ["git", "log", f"-{max_commits}", "--oneline", "--decorate"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return "Not a git repository or git not available"

        output = result.stdout.strip()
        if not output:
            return "No commits found"

        return f"Recent commits:\n{output}"

    except subprocess.TimeoutExpired:
        return "Error: Git command timed out"
    except Exception as e:
        return f"Error running git log: {str(e)}"


@registry.register(risk_level=RiskLevel.HIGH)
def git_commit(message: str, files: str = "") -> str:
    """Create a git commit with the specified message.

    This tool will:
    1. Stage files if specified (or use already-staged files)
    2. Show a diff preview of what will be committed
    3. Validate the commit message
    4. Execute the commit
    5. Return commit information

    Args:
        message: Commit message (required, must not be empty)
        files: Space-separated list of files to stage
            (optional, uses staged files if empty)

    Returns:
        Success message with commit SHA and stats, or error message
    """
    try:
        # Validate commit message
        if not message or not message.strip():
            return "Error: Commit message cannot be empty"

        message = message.strip()

        # Stage files if specified
        if files:
            file_list = files.split()
            for file_path in file_list:
                result = subprocess.run(
                    ["git", "add", file_path],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    return f"Error staging file '{file_path}': {result.stderr}"

        # Check if there are staged changes
        status_result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if status_result.returncode != 0:
            return "Error: Not a git repository or git not available"

        staged_files = status_result.stdout.strip()
        if not staged_files:
            return (
                "Error: No changes staged for commit. "
                "Use 'files' parameter to stage files or run 'git add' first."
            )

        # Get diff preview of staged changes
        diff_result = subprocess.run(
            ["git", "diff", "--cached", "--stat"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        diff_preview = diff_result.stdout.strip()

        # Execute the commit
        commit_result = subprocess.run(
            ["git", "commit", "-m", message],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if commit_result.returncode != 0:
            return f"Error creating commit: {commit_result.stderr}"

        # Get the commit SHA
        sha_result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        commit_sha = (
            sha_result.stdout.strip() if sha_result.returncode == 0 else "unknown"
        )

        # Format success message
        success_msg = "✓ Commit created successfully!\n\n"
        success_msg += f"Commit: {commit_sha}\n"
        success_msg += f"Message: {message}\n\n"
        success_msg += f"Changes:\n{diff_preview}"

        return success_msg

    except subprocess.TimeoutExpired:
        return "Error: Git command timed out"
    except Exception as e:
        return f"Error creating commit: {str(e)}"


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


# ============================================================================
# Background Bash Tools
# ============================================================================


@registry.register(risk_level=RiskLevel.HIGH)
def run_bash_background(
    command: str, 
    timeout: int = 300
) -> str:
    """Execute a bash command in the background with real-time output streaming.

    SECURITY WARNING: Only execute trusted commands!
    This runs shell commands with full system access.

    Args:
        command: Shell command to execute
        timeout: Timeout in seconds (default: 300)

    Returns:
        Success message with process ID and management instructions,
        or error message if command couldn't be started
    """
    from .logging import get_logger
    logger = get_logger()

    # Truncate long commands for logging
    cmd_preview = command[:100] + "..." if len(command) > 100 else command
    logger.info(f"🔧 RUN_BASH_BACKGROUND called: {cmd_preview}")

    try:
        # Get global background executor
        executor = get_background_executor()
        
        # Start background process
        process = executor.execute_command(command, timeout)
        
        # Format success response
        response = f"✓ Background process started: {process.process_id}\n\n"
        response += f"Command: {command}\n"
        response += f"Status: {process.status.value}\n"
        response += f"Started: {_format_timestamp(process.start_time) if process.start_time else 'Unknown'}\n\n"
        response += "Management commands:\n"
        response += f"- get_background_status('{process.process_id}') to check progress\n"
        response += f"- get_background_output('{process.process_id}') to view output\n"
        response += f"- interrupt_background_process('{process.process_id}') to cancel\n\n"
        response += "Note: Process will continue running in the background even after this response."
        
        return response

    except Exception as e:
        error_msg = f"Error starting background process: {str(e)}"
        logger.error(error_msg)
        return error_msg


@registry.register(risk_level=RiskLevel.SAFE)
def get_background_status(process_id: str) -> str:
    """Get status of a background process.

    Args:
        process_id: ID of the background process

    Returns:
        Status information or error message
    """
    from .logging import get_logger
    logger = get_logger()

    try:
        executor = get_background_executor()
        process = executor.get_process(process_id)
        
        if process is None:
            return f"Error: Process not found: {process_id}"
        
        # Calculate runtime
        runtime = process.get_runtime()
        
        # Format status response
        response = f"Background Process Status: {process_id}\n\n"
        response += f"Command: {process.command}\n"
        response += f"Status: {process.status.value}\n"
        response += f"Runtime: {runtime:.2f} seconds\n"
        response += f"Exit Code: {process.exit_code if process.exit_code is not None else 'Still running'}\n"
        response += f"Output Lines: {len(process.output_lines)}\n"
        
        if process.start_time:
            response += f"Started: {_format_timestamp(process.start_time)}\n"
        
        if process.end_time:
            response += f"Ended: {_format_timestamp(process.end_time)}\n"
        
        if process.error_message:
            response += f"Error: {process.error_message}\n"
        
        # Add recommendations based on status
        if process.is_running():
            response += f"\n💡 Use get_background_output('{process_id}') to see real-time output"
            response += f"\n💡 Use interrupt_background_process('{process_id}') to cancel"
        elif process.status == ProcessStatus.COMPLETED:
            response += f"\n✅ Process completed successfully"
        elif process.status == ProcessStatus.FAILED:
            response += f"\n❌ Process failed - check output for details"
        elif process.status == ProcessStatus.INTERRUPTED:
            response += f"\n⚠️ Process was interrupted by user"
        
        return response

    except Exception as e:
        error_msg = f"Error getting process status: {str(e)}"
        logger.error(error_msg)
        return error_msg


@registry.register(risk_level=RiskLevel.HIGH)
def interrupt_background_process(process_id: str) -> str:
    """Interrupt a running background process.

    Args:
        process_id: ID of the background process to interrupt

    Returns:
        Success message or error message
    """
    from .logging import get_logger
    logger = get_logger()

    try:
        executor = get_background_executor()
        
        # Check if process exists
        process = executor.get_process(process_id)
        if process is None:
            return f"Error: Process not found: {process_id}"
        
        # Check if process is still running
        if not process.is_running():
            return f"Process {process_id} is not running (status: {process.status.value})"
        
        # Attempt to interrupt
        success = executor.interrupt_process(process_id)
        
        if success:
            return f"✓ Interrupt signal sent to process: {process_id}\n\n" \
                   f"The process should stop shortly. Use get_background_status('{process_id}') " \
                   f"to confirm it has been interrupted."
        else:
            return f"Failed to interrupt process: {process_id}"

    except Exception as e:
        error_msg = f"Error interrupting process: {str(e)}"
        logger.error(error_msg)
        return error_msg


@registry.register(risk_level=RiskLevel.SAFE)
def get_background_output(process_id: str, lines: int = 50) -> str:
    """Get recent output from a background process.

    Args:
        process_id: ID of the background process
        lines: Number of recent lines to retrieve (default: 50)

    Returns:
        Process output or error message
    """
    from .logging import get_logger
    logger = get_logger()

    try:
        executor = get_background_executor()
        process = executor.get_process(process_id)
        
        if process is None:
            return f"Error: Process not found: {process_id}"
        
        # Get recent output lines
        output_lines = process.output_lines
        if not output_lines:
            return f"No output available for process {process_id} (status: {process.status.value})"
        
        # Get the requested number of lines (most recent)
        if lines > 0:
            recent_lines = output_lines[-lines:]
        else:
            recent_lines = output_lines  # All lines if lines <= 0
        
        # Format output response
        response = f"Background Process Output: {process_id}\n"
        response += f"Command: {process.command}\n"
        response += f"Status: {process.status.value}\n"
        response += f"Showing last {len(recent_lines)} of {len(output_lines)} lines:\n"
        response += "─" * 60 + "\n"
        
        for line in recent_lines:
            response += line + "\n"
        
        # Add status information
        response += "─" * 60 + "\n"
        response += f"Total output lines: {len(output_lines)}\n"
        
        if process.is_running():
            response += f"💡 Process still running - output may continue"
        else:
            response += f"✅ Process finished (exit code: {process.exit_code})"
        
        return response

    except Exception as e:
        error_msg = f"Error getting process output: {str(e)}"
        logger.error(error_msg)
        return error_msg


@registry.register(risk_level=RiskLevel.SAFE)
def list_background_processes() -> str:
    """List all background processes.

    Returns:
        List of all processes with their status
    """
    from .logging import get_logger
    logger = get_logger()

    try:
        executor = get_background_executor()
        all_processes = executor.list_all_processes()
        
        if not all_processes:
            return "No background processes found"
        
        # Sort by start time (newest first)
        all_processes.sort(key=lambda p: p.start_time or 0, reverse=True)
        
        # Format response
        response = f"Background Processes ({len(all_processes)} total):\n\n"
        
        active_count = 0
        for process in all_processes:
            runtime = process.get_runtime()
            
            # Status emoji
            if process.is_running():
                status_emoji = "🟢"
                active_count += 1
            elif process.status == ProcessStatus.COMPLETED:
                status_emoji = "✅"
            elif process.status == ProcessStatus.FAILED:
                status_emoji = "❌"
            elif process.status == ProcessStatus.INTERRUPTED:
                status_emoji = "⚠️"
            else:
                status_emoji = "❓"
            
            response += f"{status_emoji} {process.process_id[:12]}... "
            response += f"({process.status.value})\n"
            response += f"   Command: {process.command[:60]}{'...' if len(process.command) > 60 else ''}\n"
            response += f"   Runtime: {runtime:.1f}s | "
            response += f"Lines: {len(process.output_lines)}"
            
            if process.exit_code is not None:
                response += f" | Exit: {process.exit_code}"
            
            response += f"\n"
            
            if process.start_time:
                response += f"   Started: {_format_timestamp(process.start_time)}\n"
            
            response += "\n"
        
        # Summary
        response += f"Summary: {active_count} running, {len(all_processes) - active_count} completed\n"
        response += f"💡 Use get_background_status('process_id') for details\n"
        response += f"💡 Use interrupt_background_process('process_id') to cancel running processes"
        
        return response

    except Exception as e:
        error_msg = f"Error listing processes: {str(e)}"
        logger.error(error_msg)
        return error_msg


def _format_timestamp(timestamp: float) -> str:
    """Format a timestamp for display.
    
    Args:
        timestamp: Unix timestamp
        
    Returns:
        Formatted timestamp string
    """
    import datetime
    
    dt = datetime.datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M:%S")
