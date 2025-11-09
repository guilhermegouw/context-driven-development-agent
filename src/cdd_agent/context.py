"""Hierarchical context loading for CDD Agent.

This module handles loading and merging context files from multiple locations:
- Global context: ~/.cdd/CDD.md or ~/.claude/CLAUDE.md
- Project context: CDD.md or CLAUDE.md at project root

Context priority (recency bias): Global → Project (Project overrides Global)
"""

from pathlib import Path
from typing import Optional


class ContextLoader:
    """Manages hierarchical context loading and merging."""

    # Project root markers (searched in order)
    PROJECT_MARKERS = [
        ".git",
        "pyproject.toml",
        "package.json",
        "go.mod",
        "Cargo.toml",
        "pom.xml",
        "build.gradle",
    ]

    # Global context locations (searched in order)
    GLOBAL_CONTEXT_PATHS = [
        "~/.cdd/CDD.md",
        "~/.claude/CLAUDE.md",
    ]

    # Project context filenames (searched in order)
    PROJECT_CONTEXT_NAMES = [
        "CDD.md",
        "CLAUDE.md",
    ]

    def __init__(self, cwd: Optional[Path] = None, enable_cache: bool = True):
        """Initialize context loader.

        Args:
            cwd: Current working directory (defaults to os.getcwd())
            enable_cache: Whether to cache loaded contexts
        """
        self.cwd = cwd or Path.cwd()
        self.enable_cache = enable_cache
        self._cache: Optional[str] = None
        self._project_root: Optional[Path] = None

    def detect_project_root(self) -> Optional[Path]:
        """Detect project root by searching upward for markers.

        Searches from current directory upward until finding a project marker
        (.git, pyproject.toml, etc.) or reaching the filesystem root.

        Returns:
            Path to project root, or None if not found
        """
        if self._project_root is not None:
            return self._project_root

        current = self.cwd.resolve()

        # Walk up the directory tree
        for parent in [current] + list(current.parents):
            # Check for any project marker
            for marker in self.PROJECT_MARKERS:
                if (parent / marker).exists():
                    self._project_root = parent
                    return parent

        # No project root found
        return None

    def load_global_context(self) -> Optional[str]:
        """Load global context from home directory.

        Tries locations in order:
        1. ~/.cdd/CDD.md
        2. ~/.claude/CLAUDE.md

        Returns:
            Global context content, or None if not found
        """
        for path_str in self.GLOBAL_CONTEXT_PATHS:
            path = Path(path_str).expanduser()
            if path.exists() and path.is_file():
                try:
                    return path.read_text(encoding="utf-8")
                except Exception:
                    # Skip if we can't read the file
                    continue

        return None

    def load_project_context(self) -> Optional[str]:
        """Load project context from project root.

        Tries filenames in order at project root:
        1. CDD.md
        2. CLAUDE.md

        Returns:
            Project context content, or None if not found
        """
        project_root = self.detect_project_root()
        if project_root is None:
            return None

        for filename in self.PROJECT_CONTEXT_NAMES:
            path = project_root / filename
            if path.exists() and path.is_file():
                try:
                    return path.read_text(encoding="utf-8")
                except Exception:
                    # Skip if we can't read the file
                    continue

        return None

    def merge_contexts(
        self, global_context: Optional[str], project_context: Optional[str]
    ) -> Optional[str]:
        """Merge global and project contexts.

        Concatenation order: Global → Project
        This gives project context higher priority due to LLM recency bias.

        Args:
            global_context: Global context content
            project_context: Project context content

        Returns:
            Merged context, or None if both are empty
        """
        parts = []

        if global_context:
            parts.append("# Global Context\n\n" + global_context.strip())

        if project_context:
            parts.append("# Project Context\n\n" + project_context.strip())

        if not parts:
            return None

        # Join with separator (global first, project second for recency bias)
        return "\n\n" + "─" * 80 + "\n\n".join(parts)

    def load_context(self, use_cache: bool = True) -> Optional[str]:
        """Load and merge all contexts.

        Args:
            use_cache: Whether to use cached context if available

        Returns:
            Merged context content, or None if no context found
        """
        # Return cached context if available
        if use_cache and self.enable_cache and self._cache is not None:
            return self._cache

        # Load contexts
        global_context = self.load_global_context()
        project_context = self.load_project_context()

        # Merge contexts
        merged = self.merge_contexts(global_context, project_context)

        # Cache result
        if self.enable_cache:
            self._cache = merged

        return merged

    def get_context_info(self) -> dict:
        """Get information about loaded contexts.

        Returns:
            Dictionary with context loading details
        """
        project_root = self.detect_project_root()

        # Check which global context exists
        global_path = None
        for path_str in self.GLOBAL_CONTEXT_PATHS:
            path = Path(path_str).expanduser()
            if path.exists() and path.is_file():
                global_path = str(path)
                break

        # Check which project context exists
        project_path = None
        if project_root:
            for filename in self.PROJECT_CONTEXT_NAMES:
                path = project_root / filename
                if path.exists() and path.is_file():
                    project_path = str(path)
                    break

        return {
            "project_root": str(project_root) if project_root else None,
            "global_context": global_path,
            "project_context": project_path,
            "has_context": bool(global_path or project_path),
        }

    def clear_cache(self) -> None:
        """Clear cached context."""
        self._cache = None
