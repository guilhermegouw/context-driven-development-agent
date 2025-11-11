"""Specialized CDD agents.

Agents:
- SocratesAgent (Week 5): Refine ticket requirements through dialogue
- PlannerAgent (Week 6): Generate implementation plans
- ExecutorAgent (Week 7): Execute autonomous coding

For Week 4 (Task 4), we provide a TestAgent for integration testing.
"""

from .executor import ExecutorAgent
from .planner import PlannerAgent
from .socrates import SocratesAgent
from .test_agent import TestAgent

__all__ = [
    "TestAgent",
    "SocratesAgent",
    "PlannerAgent",
    "ExecutorAgent",
]
