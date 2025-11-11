"""YAML parser for ticket specifications.

This module provides utilities for parsing, validating, and saving
ticket spec.yaml files used in the CDD workflow.
"""

from pathlib import Path
from typing import Optional

import yaml


class TicketParseError(Exception):
    """Raised when ticket spec parsing fails."""

    pass


class TicketSpec:
    """Represents a parsed ticket specification.

    Attributes:
        title: Ticket title
        type: Ticket type (feature, bug, refactor, chore, doc)
        description: Detailed description of the ticket
        acceptance_criteria: List of acceptance criteria
        technical_notes: Optional technical implementation notes
        dependencies: Optional list of dependent tickets
        raw_data: Full YAML content as dict
        file_path: Path to the spec.yaml file
    """

    def __init__(self, data: dict, file_path: Optional[Path] = None):
        """Initialize ticket spec from parsed YAML data.

        Args:
            data: Parsed YAML data as dictionary
            file_path: Optional path to source file
        """
        self.raw_data = data
        self.file_path = file_path

        # Required fields
        self.title = data.get("title", "")
        self.type = data.get("type", "")
        self.description = data.get("description", "")

        # Optional fields
        self.acceptance_criteria = data.get("acceptance_criteria", [])
        self.technical_notes = data.get("technical_notes", "")
        self.dependencies = data.get("dependencies", [])

    def validate(self) -> list[str]:
        """Validate ticket spec completeness.

        Returns:
            List of validation errors (empty if valid)

        Example:
            >>> spec = TicketSpec({"title": "Test"})
            >>> errors = spec.validate()
            >>> print(errors)
            ['Missing required field: type', 'Missing required field: description']
        """
        errors = []

        # Check required fields
        if not self.title:
            errors.append("Missing required field: title")
        if not self.type:
            errors.append("Missing required field: type")
        if not self.description:
            errors.append("Missing required field: description")

        # Validate type
        valid_types = ["feature", "bug", "refactor", "chore", "doc"]
        if self.type and self.type not in valid_types:
            errors.append(
                f"Invalid ticket type '{self.type}'. "
                f"Must be one of: {', '.join(valid_types)}"
            )

        return errors

    def is_complete(self) -> bool:
        """Check if specification is sufficiently detailed.

        A spec is considered complete if:
        - All required fields are present
        - Description is substantial (>100 chars)
        - Has at least one acceptance criterion

        Returns:
            True if spec is complete enough for implementation
        """
        # Must pass validation
        if self.validate():
            return False

        # Description should be substantial
        if len(self.description.strip()) < 100:
            return False

        # Should have acceptance criteria
        if not self.acceptance_criteria:
            return False

        return True

    def get_vague_areas(self) -> list[str]:
        """Identify areas that need more detail.

        Returns:
            List of areas that are incomplete or vague

        Example:
            >>> spec = TicketSpec({"title": "Add auth", "type": "feature",
            ...                    "description": "Add authentication"})
            >>> areas = spec.get_vague_areas()
            >>> print(areas)
            ['Description is too brief (need 100+ chars)',
             'No acceptance criteria defined']
        """
        vague_areas = []

        # Check description length
        desc_len = len(self.description.strip())
        if desc_len == 0:
            vague_areas.append("Description is empty")
        elif desc_len < 50:
            vague_areas.append(
                "Description is very brief (need 100+ chars for clarity)"
            )
        elif desc_len < 100:
            vague_areas.append("Description could use more detail (aim for 100+ chars)")

        # Check acceptance criteria
        if not self.acceptance_criteria:
            vague_areas.append("No acceptance criteria defined")
        elif len(self.acceptance_criteria) < 2:
            vague_areas.append(
                "Only one acceptance criterion - consider adding more scenarios"
            )

        # Check for common vague words
        vague_words = ["somehow", "maybe", "probably", "tbd", "todo", "fix", "improve"]
        desc_lower = self.description.lower()
        found_vague = [word for word in vague_words if word in desc_lower]
        if found_vague:
            vague_areas.append(
                f"Contains vague terms: {', '.join(found_vague)} - need specifics"
            )

        # Check technical notes for complex features
        if self.type == "feature" and not self.technical_notes:
            vague_areas.append(
                "No technical notes provided (helpful for implementation planning)"
            )

        return vague_areas

    def update(self, updates: dict) -> None:
        """Update spec fields with new values.

        Args:
            updates: Dictionary of field updates

        Example:
            >>> spec.update({"description": "New description",
            ...              "acceptance_criteria": ["Criterion 1", "Criterion 2"]})
        """
        # Update attributes
        if "title" in updates:
            self.title = updates["title"]
        if "type" in updates:
            self.type = updates["type"]
        if "description" in updates:
            self.description = updates["description"]
        if "acceptance_criteria" in updates:
            self.acceptance_criteria = updates["acceptance_criteria"]
        if "technical_notes" in updates:
            self.technical_notes = updates["technical_notes"]
        if "dependencies" in updates:
            self.dependencies = updates["dependencies"]

        # Update raw data
        self.raw_data.update(updates)

    def to_dict(self) -> dict:
        """Convert spec to dictionary for YAML serialization.

        Returns:
            Dictionary representation of the spec
        """
        return {
            "title": self.title,
            "type": self.type,
            "description": self.description,
            "acceptance_criteria": self.acceptance_criteria,
            "technical_notes": self.technical_notes,
            "dependencies": self.dependencies,
        }


def parse_ticket_spec(file_path: Path) -> TicketSpec:
    """Parse a ticket spec.yaml file.

    Args:
        file_path: Path to spec.yaml file

    Returns:
        Parsed TicketSpec object

    Raises:
        TicketParseError: If file doesn't exist or YAML is invalid

    Example:
        >>> spec = parse_ticket_spec(Path("specs/tickets/feature-auth/spec.yaml"))
        >>> print(spec.title)
        'User Authentication'
    """
    if not file_path.exists():
        raise TicketParseError(f"Ticket spec not found: {file_path}")

    try:
        with open(file_path, "r") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise TicketParseError(f"Invalid YAML structure in {file_path}")

        return TicketSpec(data, file_path=file_path)

    except yaml.YAMLError as e:
        raise TicketParseError(f"YAML parsing error in {file_path}: {e}")
    except Exception as e:
        raise TicketParseError(f"Error reading {file_path}: {e}")


def save_ticket_spec(spec: TicketSpec, file_path: Optional[Path] = None) -> None:
    """Save a ticket spec back to YAML file.

    Args:
        spec: TicketSpec object to save
        file_path: Optional path (defaults to spec.file_path)

    Raises:
        TicketParseError: If no file path provided

    Example:
        >>> spec.update({"description": "Updated description"})
        >>> save_ticket_spec(spec)
    """
    target_path = file_path or spec.file_path

    if not target_path:
        raise TicketParseError("No file path provided for saving")

    try:
        with open(target_path, "w") as f:
            yaml.dump(
                spec.to_dict(),
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )

        # Update spec's file path if it was None
        if not spec.file_path:
            spec.file_path = target_path

    except Exception as e:
        raise TicketParseError(f"Error saving to {target_path}: {e}")
