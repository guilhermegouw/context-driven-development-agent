"""Test suite for Executor Agent.

This script tests:
- Execution state model (StepExecution, ExecutionState)
- ExecutorAgent (initialization, code generation, step execution)
- /exec command (resolution, activation, error handling)
"""

import asyncio
import os
import tempfile
from datetime import datetime
from pathlib import Path

from src.cdd_agent.agents import ExecutorAgent
from src.cdd_agent.slash_commands import ExecCommand
from src.cdd_agent.utils.execution_state import ExecutionState, StepExecution


# Mock objects for testing
class MockAgent:
    """Mock general-purpose agent."""

    def __init__(self):
        self.provider_config = {"model": "test"}
        self.tool_registry = {}

    def run(self, message: str, system_prompt=None) -> str:
        # Simulate LLM response with code generation
        return """I'll implement this step by creating the necessary files.

```python:src/example.py
def hello_world():
    \"\"\"Simple hello world function.\"\"\"
    return "Hello, World!"


def main():
    print(hello_world())


if __name__ == "__main__":
    main()
```

```python:tests/test_example.py
import pytest
from src.example import hello_world


def test_hello_world():
    assert hello_world() == "Hello, World!"
```

This implementation creates a simple hello world module with tests.
"""


class MockSession:
    """Mock ChatSession."""

    def __init__(self):
        self.general_agent = MockAgent()
        self.provider_config = {"model": "test"}
        self.tool_registry = {}
        self.current_agent = None

    def is_in_agent_mode(self):
        return self.current_agent is not None

    def get_current_agent_name(self):
        return self.current_agent.name if self.current_agent else None

    def switch_to_agent(self, agent_class, target_path):
        self.current_agent = agent_class(
            target_path=target_path,
            session=self,
            provider_config=self.provider_config,
            tool_registry=self.tool_registry,
        )
        return self.current_agent.initialize()


# ===== Execution State Model Tests =====


def test_step_execution_creation():
    """Test creating StepExecution."""
    print("\n=== Test 1: StepExecution Creation ===")

    step_exec = StepExecution(
        step_number=1,
        status="pending",
        started_at=None,
        completed_at=None,
        files_created=[],
        error=None,
    )

    assert step_exec.step_number == 1
    assert step_exec.status == "pending"
    assert step_exec.started_at is None
    assert step_exec.files_created == []

    print("✓ StepExecution created successfully")


def test_step_execution_to_dict():
    """Test StepExecution serialization."""
    print("\n=== Test 2: StepExecution Serialization ===")

    step_exec = StepExecution(
        step_number=1,
        status="completed",
        started_at="2025-01-15T10:00:00",
        completed_at="2025-01-15T10:30:00",
        files_created=["src/example.py", "tests/test_example.py"],
        error=None,
    )

    # StepExecution uses asdict from dataclasses
    from dataclasses import asdict

    data = asdict(step_exec)

    assert data["step_number"] == 1
    assert data["status"] == "completed"
    assert data["started_at"] == "2025-01-15T10:00:00"
    assert len(data["files_created"]) == 2
    assert "src/example.py" in data["files_created"]

    print("✓ StepExecution serialized to dict successfully")


def test_execution_state_creation():
    """Test creating ExecutionState."""
    print("\n=== Test 3: ExecutionState Creation ===")

    state = ExecutionState(
        ticket_slug="feature-user-auth",
        current_step=0,
        step_executions={},
        started_at=datetime.now().isoformat(),
        status="in_progress",
    )

    assert state.ticket_slug == "feature-user-auth"
    assert state.current_step == 0
    assert state.status == "in_progress"
    assert state.completed_at is None

    print("✓ ExecutionState created successfully")


def test_execution_state_progress():
    """Test ExecutionState progress calculation."""
    print("\n=== Test 4: ExecutionState Progress ===")

    state = ExecutionState(
        ticket_slug="feature-user-auth",
        current_step=2,
        step_executions={
            1: StepExecution(
                step_number=1,
                status="completed",
                started_at="2025-01-15T10:00:00",
                completed_at="2025-01-15T10:30:00",
                files_created=["src/auth.py"],
            ),
            2: StepExecution(
                step_number=2,
                status="completed",
                started_at="2025-01-15T10:30:00",
                completed_at="2025-01-15T11:00:00",
                files_created=["src/models.py"],
            ),
            3: StepExecution(
                step_number=3,
                status="pending",
                started_at=None,
                completed_at=None,
                files_created=[],
            ),
        },
        started_at="2025-01-15T10:00:00",
    )

    # Use actual methods from ExecutionState
    completed_steps = state.get_completed_steps()
    total_steps = 3
    percentage = int(state.get_progress_percentage(total_steps))

    assert len(completed_steps) == 2
    assert state.current_step == 2
    assert state.status == "in_progress"
    assert percentage == 66  # 2/3 = 66%

    print(f"✓ Progress calculated: {percentage}% complete")


def test_execution_state_save_load():
    """Test ExecutionState save/load."""
    print("\n=== Test 5: ExecutionState Save/Load ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "execution_state.json"

        # Create and save state
        original_state = ExecutionState(
            ticket_slug="feature-user-auth",
            current_step=1,
            step_executions={
                1: StepExecution(
                    step_number=1,
                    status="completed",
                    started_at="2025-01-15T10:00:00",
                    completed_at="2025-01-15T10:30:00",
                    files_created=["src/auth.py"],
                )
            },
            started_at="2025-01-15T10:00:00",
        )

        original_state.save(state_path)

        assert state_path.exists()

        # Load state
        loaded_state = ExecutionState.load(state_path)

        assert loaded_state.ticket_slug == "feature-user-auth"
        assert loaded_state.current_step == 1
        assert 1 in loaded_state.step_executions
        assert loaded_state.step_executions[1].status == "completed"
        assert len(loaded_state.step_executions[1].files_created) == 1

        print("✓ ExecutionState saved and loaded successfully")


# ===== ExecutorAgent Tests =====


def test_executor_agent_initialization():
    """Test ExecutorAgent initialization."""
    print("\n=== Test 6: ExecutorAgent Initialization ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        ticket_dir = Path(tmpdir) / "specs" / "tickets" / "feature-user-auth"
        ticket_dir.mkdir(parents=True)

        # Create spec.yaml
        spec_path = ticket_dir / "spec.yaml"
        spec_path.write_text(
            """title: User Authentication
type: feature
description: Implement user authentication system
acceptance_criteria:
  - Users can register
  - Users can login
"""
        )

        # Create plan.md
        plan_path = ticket_dir / "plan.md"
        plan_path.write_text(
            """# Implementation Plan: User Authentication

## Overview
Implement basic authentication system

## Steps

### Step 1: Setup infrastructure
**Complexity:** medium
**Estimated Time:** 1 hour
**Dependencies:** None
**Files Affected:**
- src/auth.py

Set up auth module structure
"""
        )

        # Initialize agent
        session = MockSession()
        agent = ExecutorAgent(
            target_path=spec_path,
            session=session,
            provider_config={"model": "test"},
            tool_registry={},
        )

        greeting = agent.initialize()

        assert agent.spec is not None
        assert agent.plan is not None
        assert agent.execution_state is not None
        assert agent.execution_state.current_step == 1  # Starts at step 1, not 0
        assert "executor" in greeting.lower()
        assert (
            "1" in greeting and "step" in greeting.lower()
        )  # "1 implementation steps"

        print("✓ ExecutorAgent initialized successfully")


def test_executor_agent_existing_state():
    """Test ExecutorAgent resuming from existing state."""
    print("\n=== Test 7: ExecutorAgent Resume from State ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        ticket_dir = Path(tmpdir) / "specs" / "tickets" / "feature-user-auth"
        ticket_dir.mkdir(parents=True)

        # Create spec.yaml
        spec_path = ticket_dir / "spec.yaml"
        spec_path.write_text(
            """title: User Authentication
type: feature
description: Implement user authentication
"""
        )

        # Create plan.md
        plan_path = ticket_dir / "plan.md"
        plan_path.write_text(
            """# Implementation Plan

## Steps

### Step 1: Setup
**Complexity:** simple
**Estimated Time:** 30 min

### Step 2: Implementation
**Complexity:** medium
**Estimated Time:** 1 hour
"""
        )

        # Create existing execution state
        state_path = ticket_dir / "execution-state.json"  # Note the hyphen!
        existing_state = ExecutionState(
            ticket_slug="feature-user-auth",
            current_step=2,  # Already completed step 1, now on step 2
            step_executions={
                1: StepExecution(
                    step_number=1,
                    status="completed",
                    started_at="2025-01-15T10:00:00",
                    completed_at="2025-01-15T10:30:00",
                    files_created=["src/setup.py"],
                )
            },
            started_at="2025-01-15T10:00:00",
        )
        existing_state.save(state_path)

        # Initialize agent
        session = MockSession()
        agent = ExecutorAgent(
            target_path=spec_path,
            session=session,
            provider_config={"model": "test"},
            tool_registry={},
        )

        greeting = agent.initialize()

        assert agent.execution_state.current_step == 2  # Loaded from state
        assert 1 in agent.execution_state.step_executions
        assert agent.execution_state.step_executions[1].status == "completed"
        assert "resuming" in greeting.lower()
        # Should show "Current Step: 2" and "1/2 steps completed"
        assert "1/2" in greeting or ("1" in greeting and "2" in greeting)

        print("✓ ExecutorAgent resumed from existing state")


def test_code_block_parsing():
    """Test parsing code blocks from LLM response."""
    print("\n=== Test 8: Code Block Parsing ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        ticket_dir = Path(tmpdir) / "specs" / "tickets" / "feature-test"
        ticket_dir.mkdir(parents=True)

        spec_path = ticket_dir / "spec.yaml"
        spec_path.write_text(
            """title: Test Feature
type: feature
"""
        )

        plan_path = ticket_dir / "plan.md"
        plan_path.write_text(
            """# Plan

## Steps

### Step 1: Create module
**Complexity:** simple
**Estimated Time:** 30 min
"""
        )

        session = MockSession()
        agent = ExecutorAgent(
            target_path=spec_path,
            session=session,
            provider_config={"model": "test"},
            tool_registry={},
        )
        agent.initialize()

        # Mock LLM response with code blocks
        llm_response = """I'll create the module.

```python:src/module.py
def hello():
    return "Hello"
```

```python:tests/test_module.py
from src.module import hello

def test_hello():
    assert hello() == "Hello"
```

This implements the basic module.
"""

        result = agent._parse_code_response(llm_response)

        assert "files" in result
        assert len(result["files"]) == 2
        assert "src/module.py" in result["files"]
        assert "tests/test_module.py" in result["files"]
        assert "def hello():" in result["files"]["src/module.py"]
        assert "explanation" in result

        print(f"✓ Parsed {len(result['files'])} code blocks successfully")


async def test_executor_process_next_step():
    """Test executing next step."""
    print("\n=== Test 9: Execute Next Step ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        ticket_dir = Path(tmpdir) / "specs" / "tickets" / "feature-test"
        ticket_dir.mkdir(parents=True)

        spec_path = ticket_dir / "spec.yaml"
        spec_path.write_text(
            """title: Test Feature
type: feature
"""
        )

        plan_path = ticket_dir / "plan.md"
        plan_path.write_text(
            """# Plan

## Steps

### Step 1: Create module
**Complexity:** simple
**Estimated Time:** 30 min
**Files Affected:**
- src/example.py
"""
        )

        session = MockSession()
        agent = ExecutorAgent(
            target_path=spec_path,
            session=session,
            provider_config={"model": "test"},
            tool_registry={},
        )
        agent.initialize()

        # Process next step (should execute step 1)
        await agent.process("continue")

        # Check that step was executed
        assert 1 in agent.execution_state.step_executions
        step_exec = agent.execution_state.step_executions[1]
        assert step_exec.status == "completed"

        # Check that files were created or modified
        total_files = len(step_exec.files_created) + len(step_exec.files_modified)
        assert total_files > 0

        print("✓ Step execution initiated successfully")


async def test_executor_skip_command():
    """Test skip command."""
    print("\n=== Test 10: Skip Command ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        ticket_dir = Path(tmpdir) / "specs" / "tickets" / "feature-test"
        ticket_dir.mkdir(parents=True)

        spec_path = ticket_dir / "spec.yaml"
        spec_path.write_text(
            """title: Test Feature
type: feature
"""
        )

        plan_path = ticket_dir / "plan.md"
        plan_path.write_text(
            """# Plan

## Steps

### Step 1: First step
**Complexity:** simple

### Step 2: Second step
**Complexity:** simple
"""
        )

        session = MockSession()
        agent = ExecutorAgent(
            target_path=spec_path,
            session=session,
            provider_config={"model": "test"},
            tool_registry={},
        )
        agent.initialize()

        # Skip step 1
        response = await agent.process("skip")

        assert agent.execution_state.current_step == 2  # Moved to next step
        assert 1 in agent.execution_state.step_executions
        # Skip marks as "completed" (even though skipped)
        assert agent.execution_state.step_executions[1].status == "completed"
        assert "skipped" in response.lower()

        print("✓ Step skipped successfully")


async def test_executor_status_command():
    """Test status command."""
    print("\n=== Test 11: Status Command ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        ticket_dir = Path(tmpdir) / "specs" / "tickets" / "feature-test"
        ticket_dir.mkdir(parents=True)

        spec_path = ticket_dir / "spec.yaml"
        spec_path.write_text(
            """title: Test Feature
type: feature
"""
        )

        plan_path = ticket_dir / "plan.md"
        plan_path.write_text(
            """# Plan

## Steps

### Step 1: First step
**Complexity:** simple
"""
        )

        session = MockSession()
        agent = ExecutorAgent(
            target_path=spec_path,
            session=session,
            provider_config={"model": "test"},
            tool_registry={},
        )
        agent.initialize()

        # Get status
        response = await agent.process("status")

        assert "execution status" in response.lower() or "status" in response.lower()
        assert "test feature" in response.lower()  # Ticket title
        assert "0/1" in response or "current step" in response.lower()

        print("✓ Status displayed successfully")


# ===== /exec Command Tests =====


async def test_exec_command_no_args():
    """Test /exec without arguments."""
    print("\n=== Test 12: /exec Without Arguments ===")

    cmd = ExecCommand()
    response = await cmd.execute("")

    assert "usage" in response.lower()
    assert "/exec <ticket-slug>" in response.lower()

    print("✓ /exec shows usage when no args provided")


async def test_exec_command_ticket_not_found():
    """Test /exec with non-existent ticket."""
    print("\n=== Test 13: /exec Ticket Not Found ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        os.chdir(tmpdir)

        # Create specs/tickets directory
        tickets_dir = Path(tmpdir) / "specs" / "tickets"
        tickets_dir.mkdir(parents=True)

        cmd = ExecCommand()
        response = await cmd.execute("nonexistent-ticket")

        assert "error" in response.lower()
        assert "not found" in response.lower()

        print("✓ /exec handles missing ticket correctly")


async def test_exec_command_no_plan():
    """Test /exec when plan doesn't exist."""
    print("\n=== Test 14: /exec No Plan Found ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        os.chdir(tmpdir)

        # Create ticket without plan
        ticket_dir = Path(tmpdir) / "specs" / "tickets" / "feature-test"
        ticket_dir.mkdir(parents=True)

        spec_path = ticket_dir / "spec.yaml"
        spec_path.write_text(
            """title: Test Feature
type: feature
"""
        )

        cmd = ExecCommand()
        response = await cmd.execute("feature-test")

        assert "error" in response.lower()
        assert "no implementation plan" in response.lower()
        assert "/plan" in response.lower()

        print("✓ /exec requires plan to exist")


async def test_exec_command_success():
    """Test successful /exec activation."""
    print("\n=== Test 15: /exec Successful Activation ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        os.chdir(tmpdir)

        # Create ticket with plan
        ticket_dir = Path(tmpdir) / "specs" / "tickets" / "feature-test"
        ticket_dir.mkdir(parents=True)

        spec_path = ticket_dir / "spec.yaml"
        spec_path.write_text(
            """title: Test Feature
type: feature
"""
        )

        plan_path = ticket_dir / "plan.md"
        plan_path.write_text(
            """# Plan

## Steps

### Step 1: Create module
**Complexity:** simple
"""
        )

        # Set up command with session
        session = MockSession()
        cmd = ExecCommand()
        cmd.session = session

        response = await cmd.execute("feature-test")

        # Should activate Executor agent
        assert session.is_in_agent_mode()
        assert isinstance(session.current_agent, ExecutorAgent)
        assert "executor" in response.lower() or "feature-test" in response.lower()

        print("✓ /exec activated ExecutorAgent successfully")


# ===== Run All Tests =====


async def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("EXECUTOR AGENT TEST SUITE")
    print("=" * 60)

    tests = [
        # Execution State Model (sync)
        test_step_execution_creation,
        test_step_execution_to_dict,
        test_execution_state_creation,
        test_execution_state_progress,
        test_execution_state_save_load,
        # ExecutorAgent (sync)
        test_executor_agent_initialization,
        test_executor_agent_existing_state,
        test_code_block_parsing,
    ]

    async_tests = [
        # ExecutorAgent (async)
        test_executor_process_next_step,
        test_executor_skip_command,
        test_executor_status_command,
        # /exec Command (async)
        test_exec_command_no_args,
        test_exec_command_ticket_not_found,
        test_exec_command_no_plan,
        test_exec_command_success,
    ]

    passed = 0
    failed = 0

    # Run sync tests
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            failed += 1
            print(f"✗ FAILED: {test.__name__}")
            print(f"  Error: {e}")
        except Exception as e:
            failed += 1
            print(f"✗ ERROR: {test.__name__}")
            print(f"  Exception: {e}")

    # Run async tests
    for test in async_tests:
        try:
            await test()
            passed += 1
        except AssertionError as e:
            failed += 1
            print(f"✗ FAILED: {test.__name__}")
            print(f"  Error: {e}")
        except Exception as e:
            failed += 1
            print(f"✗ ERROR: {test.__name__}")
            print(f"  Exception: {e}")

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    exit(0 if success else 1)
