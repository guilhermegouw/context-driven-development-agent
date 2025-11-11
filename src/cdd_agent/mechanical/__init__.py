"""Mechanical layer for CDD Agent.

This module provides file generation utilities that don't require AI:
- Project initialization (init.py)
- Ticket/documentation creation (new_ticket.py)
"""

from .init import initialize_project, InitializationError
from .new_ticket import (
    create_new_ticket,
    create_new_documentation,
    TicketCreationError,
    normalize_ticket_name,
)

__all__ = [
    # Initialization
    "initialize_project",
    "InitializationError",
    # Ticket/documentation creation
    "create_new_ticket",
    "create_new_documentation",
    "TicketCreationError",
    "normalize_ticket_name",
]
