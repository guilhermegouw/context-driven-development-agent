"""Writer Agent - Handles file persistence for other agents.

This agent is a simple, deterministic file writer with no LLM interaction.
It validates, formats, and atomically writes content to disk.
"""

import logging
import tempfile
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


class WriterAgent:
    """Simple file persistence agent (no LLM, pure I/O).

    This agent receives content from other agents (like Socrates)
    and handles the actual file write with validation and safety checks.

    Why separate from Socrates?
    - Clear separation: gathering vs persisting
    - Works with any LLM (no model-dependent behavior)
    - Centralized validation and error handling
    - Atomic writes for safety

    Example:
        # Socrates generates content
        content = socrates.generate_spec()

        # Writer saves it
        writer = WriterAgent(target_path="specs/feature-auth/spec.yaml")
        result = writer.save(content)
    """

    def __init__(self, target_path: Path):
        """Initialize writer agent.

        Args:
            target_path: Path where content should be saved
        """
        self.target_path = Path(target_path)
        self.name = "Writer"
        self.description = "File persistence with validation"

        logger.info(f"Writer agent initialized for: {self.target_path}")

    def save(self, content: str) -> str:
        """Save content to target file with validation.

        Process:
        1. Validate format (YAML/Markdown)
        2. Create parent directories if needed
        3. Write atomically (temp file → rename)
        4. Verify write succeeded
        5. Return user-friendly message

        Args:
            content: Content to write (YAML or Markdown string)

        Returns:
            Success message with file path

        Raises:
            ValueError: If content format is invalid
            OSError: If file write fails
        """
        logger.info(f"Starting save operation for: {self.target_path}")

        try:
            # Step 1: Validate content format
            self._validate_content(content)
            logger.debug("Content validation passed")

            # Step 2: Ensure parent directory exists
            self._ensure_parent_dir()
            logger.debug(f"Parent directory ready: {self.target_path.parent}")

            # Step 3: Write atomically
            self._write_atomic(content)
            logger.info(f"Successfully wrote file: {self.target_path}")

            # Step 4: Verify write
            if not self.target_path.exists():
                raise OSError(f"File write verification failed: {self.target_path}")

            # Step 5: Return success message
            file_size = self.target_path.stat().st_size
            return (
                f"✅ **File saved successfully**\n\n"
                f"**Path:** `{self.target_path}`\n"
                f"**Size:** {file_size} bytes\n"
                f"**Format:** {self._detect_format()}\n\n"
                f"The file is ready to use."
            )

        except Exception as e:
            logger.error(f"Failed to save file: {e}", exc_info=True)
            return (
                f"❌ **Failed to save file**\n\n"
                f"**Path:** `{self.target_path}`\n"
                f"**Error:** {str(e)}\n\n"
                f"Please check the error message and try again."
            )

    def _validate_content(self, content: str) -> None:
        """Validate content format.

        Args:
            content: Content to validate

        Raises:
            ValueError: If content is invalid
        """
        if not content or not content.strip():
            raise ValueError("Content is empty")

        file_format = self._detect_format()

        if file_format == "yaml":
            self._validate_yaml(content)
        elif file_format == "markdown":
            self._validate_markdown(content)
        else:
            # Unknown format, allow it (assume text)
            logger.warning(f"Unknown file format for {self.target_path.suffix}, skipping validation")

    def _validate_yaml(self, content: str) -> None:
        """Validate YAML syntax.

        Args:
            content: YAML content to validate

        Raises:
            ValueError: If YAML is invalid
        """
        try:
            yaml.safe_load(content)
            logger.debug("YAML validation passed")
        except yaml.YAMLError as e:
            logger.error(f"YAML validation failed: {e}")
            raise ValueError(f"Invalid YAML syntax: {str(e)}")

    def _validate_markdown(self, content: str) -> None:
        """Validate markdown content.

        Basic checks for markdown format.

        Args:
            content: Markdown content to validate

        Raises:
            ValueError: If markdown looks invalid
        """
        # Basic markdown validation
        if len(content.strip()) < 10:
            raise ValueError("Markdown content is too short (minimum 10 characters)")

        # Check for at least one heading (# Header)
        if not any(line.strip().startswith("#") for line in content.splitlines()):
            logger.warning("Markdown file has no headings (no # found)")

        logger.debug("Markdown validation passed")

    def _detect_format(self) -> str:
        """Detect file format from extension.

        Returns:
            Format string: "yaml", "markdown", or "unknown"
        """
        suffix = self.target_path.suffix.lower()

        if suffix in [".yaml", ".yml"]:
            return "yaml"
        elif suffix in [".md", ".markdown"]:
            return "markdown"
        else:
            return "unknown"

    def _ensure_parent_dir(self) -> None:
        """Create parent directories if they don't exist.

        Raises:
            OSError: If directory creation fails
        """
        parent = self.target_path.parent

        if not parent.exists():
            logger.info(f"Creating parent directory: {parent}")
            parent.mkdir(parents=True, exist_ok=True)

    def _write_atomic(self, content: str) -> None:
        """Write file atomically using temp file + rename.

        This prevents partial writes if the process is interrupted.

        Process:
        1. Write to temp file in same directory
        2. Rename temp file to target (atomic operation)

        Args:
            content: Content to write

        Raises:
            OSError: If write fails
        """
        # Write to temp file in same directory (ensures same filesystem)
        temp_fd, temp_path = tempfile.mkstemp(
            dir=self.target_path.parent,
            prefix=f".{self.target_path.name}.",
            suffix=".tmp"
        )

        try:
            # Write content to temp file
            with open(temp_fd, "w", encoding="utf-8") as f:
                f.write(content)

            logger.debug(f"Wrote to temp file: {temp_path}")

            # Atomic rename
            Path(temp_path).rename(self.target_path)
            logger.debug(f"Renamed {temp_path} → {self.target_path}")

        except Exception as e:
            # Clean up temp file on error
            try:
                Path(temp_path).unlink()
            except Exception:
                pass
            raise OSError(f"Atomic write failed: {str(e)}")

    def verify(self) -> bool:
        """Verify that target file exists and is readable.

        Returns:
            True if file exists and can be read
        """
        if not self.target_path.exists():
            return False

        try:
            self.target_path.read_text(encoding="utf-8")
            return True
        except Exception as e:
            logger.error(f"File verification failed: {e}")
            return False
