"""Execution state tracking for the Executor Agent.

This module provides data structures for tracking the progress of
autonomous code execution, and execution mode definitions that control
which tools are available to the agent.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from enum import Enum
from pathlib import Path


class ExecutionMode(Enum):
    """Execution modes for the agent.

    Modes:
        NORMAL: Full tool access with approval prompts (default behavior)
        PLAN: Read-only mode for exploration and planning without modifications
        YOLO: Full tool access with auto-approval and no confirmation prompts
    """

    NORMAL = "normal"
    PLAN = "plan"
    YOLO = "yolo"

    def is_read_only(self) -> bool:
        """Check if this mode restricts to read-only operations.

        Returns:
            True if mode is read-only (PLAN), False otherwise
        """
        return self == ExecutionMode.PLAN

    def get_display_name(self) -> str:
        """Get human-readable display name for the mode.

        Returns:
            Display name string
        """
        if self == ExecutionMode.NORMAL:
            return "Normal"
        elif self == ExecutionMode.PLAN:
            return "Plan"
        elif self == ExecutionMode.YOLO:
            return "YOLO MODE"
        return self.value.capitalize()

    def get_icon(self) -> str:
        """Get emoji icon for the mode.

        Returns:
            Emoji string representing the mode
        """
        if self == ExecutionMode.NORMAL:
            return "▶"  # Play icon for normal execution
        elif self == ExecutionMode.PLAN:
            return "⏸"  # Pause icon for plan mode
        elif self == ExecutionMode.YOLO:
            return "🚀"  # Rocket icon for YOLO mode
        return "•"

    def get_description(self) -> str:
        """Get detailed description of the mode.

        Returns:
            Description string
        """
        if self == ExecutionMode.NORMAL:
            return "Full tool access"
        elif self == ExecutionMode.PLAN:
            return "Read-only (exploration and planning)"
        elif self == ExecutionMode.YOLO:
            return "Auto-approve all actions"
        return ""

    def is_yolo(self) -> bool:
        """Check if this mode is YOLO (auto-approve all).

        Returns:
            True if mode is YOLO, False otherwise
        """
        return self == ExecutionMode.YOLO

    def get_next_mode(self) -> "ExecutionMode":
        """Get the next mode in the cycle.

        Cycles: NORMAL → PLAN → YOLO → NORMAL

        Returns:
            Next ExecutionMode in the cycle
        """
        if self == ExecutionMode.NORMAL:
            return ExecutionMode.PLAN
        elif self == ExecutionMode.PLAN:
            return ExecutionMode.YOLO
        elif self == ExecutionMode.YOLO:
            return ExecutionMode.NORMAL
        return ExecutionMode.NORMAL


@dataclass
class StepExecution:
    """Execution state for a single implementation step.

    Attributes:
        step_number: Step number in the plan
        status: Current status (pending/in_progress/completed/failed)
        started_at: When execution started (ISO format)
        completed_at: When execution completed (ISO format)
        error: Error message if failed
        files_created: List of files created by this step
        files_modified: List of files modified by this step
    """

    step_number: int
    status: str = "pending"  # pending, in_progress, completed, failed
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)

    def __post_init__(self):
        """Validate step execution data."""
        valid_statuses = ["pending", "in_progress", "completed", "failed"]
        if self.status not in valid_statuses:
            raise ValueError(
                f"Invalid status '{self.status}'. "
                f"Must be one of: {', '.join(valid_statuses)}"
            )


@dataclass
class ExecutionState:
    """Overall execution state for a ticket implementation.

    Attributes:
        ticket_slug: Ticket identifier
        current_step: Current step number being executed
        step_executions: Dict mapping step number to execution state
        started_at: When execution started (ISO format)
        completed_at: When execution completed (ISO format)
        status: Overall status (in_progress/completed/failed/paused)
    """

    ticket_slug: str
    current_step: int
    step_executions: dict[int, StepExecution]
    started_at: str
    completed_at: str | None = None
    status: str = "in_progress"

    def __post_init__(self):
        """Ensure started_at is set."""
        if not self.started_at:
            self.started_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation
        """
        data = asdict(self)
        # Convert StepExecution objects to dicts
        data["step_executions"] = {
            str(k): v for k, v in data["step_executions"].items()
        }
        return data

    def to_json(self) -> str:
        """Serialize to JSON string.

        Returns:
            JSON string

        Example:
            >>> state.to_json()
            '{"ticket_slug": "feature-test", ...}'
        """
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "ExecutionState":
        """Create from dictionary.

        Args:
            data: Dictionary data

        Returns:
            ExecutionState instance
        """
        # Convert step_executions back to StepExecution objects
        step_execs = {}
        for k, v in data.get("step_executions", {}).items():
            step_execs[int(k)] = StepExecution(**v)

        return cls(
            ticket_slug=data["ticket_slug"],
            current_step=data["current_step"],
            step_executions=step_execs,
            started_at=data["started_at"],
            completed_at=data.get("completed_at"),
            status=data.get("status", "in_progress"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "ExecutionState":
        """Parse from JSON string.

        Args:
            json_str: JSON string

        Returns:
            ExecutionState instance

        Raises:
            ValueError: If JSON is invalid
        """
        try:
            data = json.loads(json_str)
            return cls.from_dict(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

    def save(self, path: Path) -> None:
        """Save state to file.

        Args:
            path: Path to save to (typically execution-state.json)

        Example:
            >>> state.save(Path("specs/tickets/feature-auth/execution-state.json"))
        """
        path.write_text(self.to_json())

    @classmethod
    def load(cls, path: Path) -> "ExecutionState" | None:
        """Load state from file.

        Args:
            path: Path to load from

        Returns:
            ExecutionState if file exists, None otherwise

        Example:
            >>> state = ExecutionState.load(Path("execution-state.json"))
        """
        if not path.exists():
            return None

        try:
            return cls.from_json(path.read_text())
        except Exception:
            return None

    def get_completed_steps(self) -> list[int]:
        """Get list of completed step numbers.

        Returns:
            List of step numbers with status "completed"
        """
        return [
            num
            for num, exec_state in self.step_executions.items()
            if exec_state.status == "completed"
        ]

    def get_failed_steps(self) -> list[int]:
        """Get list of failed step numbers.

        Returns:
            List of step numbers with status "failed"
        """
        return [
            num
            for num, exec_state in self.step_executions.items()
            if exec_state.status == "failed"
        ]

    def get_progress_percentage(self, total_steps: int) -> float:
        """Calculate completion percentage.

        Args:
            total_steps: Total number of steps in plan

        Returns:
            Percentage complete (0-100)
        """
        completed = len(self.get_completed_steps())
        return (completed / total_steps * 100) if total_steps > 0 else 0

    def mark_step_started(self, step_number: int) -> None:
        """Mark a step as started.

        Args:
            step_number: Step number to mark
        """
        if step_number not in self.step_executions:
            self.step_executions[step_number] = StepExecution(step_number)

        self.step_executions[step_number].status = "in_progress"
        self.step_executions[step_number].started_at = datetime.now().isoformat()

    def mark_step_completed(
        self,
        step_number: int,
        files_created: list[str],
        files_modified: list[str],
    ) -> None:
        """Mark a step as completed.

        Args:
            step_number: Step number to mark
            files_created: List of files created
            files_modified: List of files modified
        """
        if step_number not in self.step_executions:
            self.step_executions[step_number] = StepExecution(step_number)

        self.step_executions[step_number].status = "completed"
        self.step_executions[step_number].completed_at = datetime.now().isoformat()
        self.step_executions[step_number].files_created = files_created
        self.step_executions[step_number].files_modified = files_modified

    def mark_step_failed(self, step_number: int, error: str) -> None:
        """Mark a step as failed.

        Args:
            step_number: Step number to mark
            error: Error message
        """
        if step_number not in self.step_executions:
            self.step_executions[step_number] = StepExecution(step_number)

        self.step_executions[step_number].status = "failed"
        self.step_executions[step_number].error = error
        self.step_executions[step_number].completed_at = datetime.now().isoformat()
