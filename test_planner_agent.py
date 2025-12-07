"""Test suite for Planner Agent.

This script tests:
- Plan data model (PlanStep, ImplementationPlan)
- PlannerAgent (initialization, plan generation, finalization)
- /plan command (resolution, activation, error handling)
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from src.cdd_agent.agents import PlannerAgent
from src.cdd_agent.slash_commands import PlanCommand
from src.cdd_agent.utils.plan_model import ImplementationPlan
from src.cdd_agent.utils.plan_model import PlanStep


# Mock objects for testing
class MockAgent:
    """Mock general-purpose agent."""

    def __init__(self):
        self.provider_config = {"model": "test"}
        self.tool_registry = {}

    def run(self, message: str, system_prompt=None) -> str:
        # Simulate LLM response with valid JSON
        return json.dumps(
            {
                "overview": "Test implementation plan overview",
                "steps": [
                    {
                        "number": 1,
                        "title": "Setup infrastructure",
                        "description": "Set up necessary infrastructure",
                        "complexity": "medium",
                        "estimated_time": "1 hour",
                        "dependencies": [],
                        "files_affected": ["src/setup.py"],
                    },
                    {
                        "number": 2,
                        "title": "Implement core logic",
                        "description": "Implement main functionality",
                        "complexity": "complex",
                        "estimated_time": "2 hours",
                        "dependencies": [1],
                        "files_affected": ["src/core.py"],
                    },
                ],
                "total_complexity": "medium",
                "total_estimated_time": "3 hours",
                "risks": ["API dependencies", "Performance considerations"],
            }
        )


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


# ===== Plan Model Tests =====


def test_plan_step_creation():
    """Test creating PlanStep."""
    print("\n=== Test 1: PlanStep Creation ===")

    step = PlanStep(
        number=1,
        title="Setup database",
        description="Create database schema and tables",
        complexity="medium",
        estimated_time="1 hour",
        dependencies=[],
        files_affected=["src/models/schema.py"],
    )

    assert step.number == 1
    assert step.title == "Setup database"
    assert step.complexity == "medium"
    assert len(step.files_affected) == 1

    print("✅ PlanStep created successfully")
    print(f"   - Title: {step.title}")
    print(f"   - Complexity: {step.complexity}")


def test_implementation_plan_creation():
    """Test creating ImplementationPlan."""
    print("\n=== Test 2: ImplementationPlan Creation ===")

    steps = [
        PlanStep(1, "Step 1", "Description 1", "simple", "30 min"),
        PlanStep(2, "Step 2", "Description 2", "medium", "1 hour", [1]),
    ]

    plan = ImplementationPlan(
        ticket_slug="feature-test",
        ticket_title="Test Feature",
        ticket_type="feature",
        overview="Test plan overview",
        steps=steps,
        total_complexity="medium",
        total_estimated_time="1.5 hours",
    )

    assert plan.ticket_slug == "feature-test"
    assert len(plan.steps) == 2
    assert plan.steps[1].dependencies == [1]

    print("✅ ImplementationPlan created successfully")
    print(f"   - Steps: {len(plan.steps)}")
    print(f"   - Complexity: {plan.total_complexity}")


def test_plan_to_markdown():
    """Test converting plan to markdown."""
    print("\n=== Test 3: Plan to Markdown ===")

    steps = [
        PlanStep(
            1, "Setup", "Setup infrastructure", "simple", "30 min", [], ["src/setup.py"]
        ),
        PlanStep(
            2,
            "Implement",
            "Implement core logic",
            "medium",
            "1 hour",
            [1],
            ["src/core.py"],
        ),
    ]

    plan = ImplementationPlan(
        ticket_slug="feature-test",
        ticket_title="Test Feature",
        ticket_type="feature",
        overview="Test overview",
        steps=steps,
        risks=["Risk 1", "Risk 2"],
    )

    md = plan.to_markdown()

    assert "# Implementation Plan: Test Feature" in md
    assert "Step 1: Setup" in md
    assert "Step 2: Implement" in md
    assert "Risks & Considerations" in md
    assert "/exec feature-test" in md

    print("✅ Plan converted to markdown")
    print(f"   - Markdown length: {len(md)} characters")


def test_plan_from_markdown():
    """Test parsing plan from markdown."""
    print("\n=== Test 4: Plan from Markdown ===")

    md_content = """# Implementation Plan: User Authentication

**Ticket:** `feature-user-auth`
**Type:** feature
**Complexity:** medium
**Estimated Time:** 4 hours
**Created:** 2025-11-09

---

## Overview

Implement user authentication system.

---

## Implementation Steps

### Step 1: Create User Model

**Description:** Create database model for users
**Complexity:** simple
**Estimated Time:** 30 min
**Dependencies:** None

**Files Affected:**
- `src/models/user.py`

---

### Step 2: Add Authentication

**Description:** Implement auth logic
**Complexity:** medium
**Estimated Time:** 1 hour
**Dependencies:** Step 1

**Files Affected:**
- `src/auth.py`

---

## Risks & Considerations

- Security considerations
- Performance impact

---
"""

    plan = ImplementationPlan.from_markdown(md_content, "feature-user-auth")

    assert plan.ticket_slug == "feature-user-auth"
    assert plan.ticket_title == "User Authentication"
    assert len(plan.steps) == 2
    assert plan.steps[0].title == "Create User Model"
    assert plan.steps[1].dependencies == [1]
    assert len(plan.risks) == 2

    print("✅ Plan parsed from markdown")
    print(f"   - Title: {plan.ticket_title}")
    print(f"   - Steps: {len(plan.steps)}")


def test_markdown_roundtrip():
    """Test markdown save/load roundtrip."""
    print("\n=== Test 5: Markdown Roundtrip ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        plan_path = Path(tmp_dir) / "plan.md"

        # Create plan
        original_plan = ImplementationPlan(
            ticket_slug="test-ticket",
            ticket_title="Test Ticket",
            ticket_type="feature",
            overview="Original overview",
            steps=[
                PlanStep(1, "Step One", "Description", "simple", "30 min"),
                PlanStep(2, "Step Two", "Description", "medium", "1 hour", [1]),
            ],
        )

        # Save to markdown
        plan_path.write_text(original_plan.to_markdown())

        # Load back
        loaded_plan = ImplementationPlan.from_markdown(
            plan_path.read_text(), "test-ticket"
        )

        assert loaded_plan.ticket_title == original_plan.ticket_title
        assert len(loaded_plan.steps) == len(original_plan.steps)
        assert loaded_plan.steps[0].title == original_plan.steps[0].title

        print("✅ Markdown roundtrip successful")


def test_plan_from_json():
    """Test parsing plan from JSON (LLM response)."""
    print("\n=== Test 6: Plan from JSON ===")

    json_str = json.dumps(
        {
            "overview": "JSON test plan",
            "steps": [
                {
                    "number": 1,
                    "title": "First step",
                    "description": "Do this first",
                    "complexity": "simple",
                    "estimated_time": "30 min",
                    "dependencies": [],
                    "files_affected": ["file1.py"],
                }
            ],
            "total_complexity": "simple",
            "total_estimated_time": "30 min",
            "risks": [],
        }
    )

    plan = ImplementationPlan.from_json(json_str, "test-slug", "Test Title", "feature")

    assert plan.ticket_slug == "test-slug"
    assert plan.ticket_title == "Test Title"
    assert len(plan.steps) == 1
    assert plan.steps[0].title == "First step"

    print("✅ Plan parsed from JSON")


# ===== Planner Agent Tests =====


async def test_planner_initialization_complete_spec():
    """Test Planner initialization with complete spec."""
    print("\n=== Test 7: Planner Initialization (Complete Spec) ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        spec_path = Path(tmp_dir) / "spec.yaml"
        spec_path.write_text(
            """title: User Authentication
type: feature
description: |
  Implement comprehensive user authentication with email/password and OAuth.
  Support Google and GitHub providers. Include password reset flow.
acceptance_criteria:
  - Users can register with email
  - Users can log in
  - OAuth works
technical_notes: Use bcrypt for hashing
dependencies: []
"""
        )

        session = MockSession()
        agent = PlannerAgent(
            target_path=spec_path,
            session=session,
            provider_config={},
            tool_registry={},
        )

        greeting = agent.initialize()

        assert "Planner" in greeting
        assert "User Authentication" in greeting or "Generating" in greeting

        print("✅ Planner initialized with complete spec")


async def test_planner_initialization_incomplete_spec():
    """Test Planner with incomplete spec."""
    print("\n=== Test 8: Planner Initialization (Incomplete Spec) ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        spec_path = Path(tmp_dir) / "spec.yaml"
        spec_path.write_text(
            """title: Incomplete
type: feature
description: Too brief
acceptance_criteria: []
technical_notes: ""
dependencies: []
"""
        )

        session = MockSession()
        agent = PlannerAgent(
            target_path=spec_path,
            session=session,
            provider_config={},
            tool_registry={},
        )

        greeting = agent.initialize()

        assert "incomplete" in greeting.lower()
        assert "socrates" in greeting.lower()

        print("✅ Planner detected incomplete spec")


async def test_plan_generation():
    """Test plan generation via LLM."""
    print("\n=== Test 9: Plan Generation ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        spec_path = Path(tmp_dir) / "spec.yaml"
        spec_path.write_text(
            """title: Test Feature
type: feature
description: |
  A comprehensive test feature with detailed requirements
  that meets all completeness criteria for planning.
acceptance_criteria:
  - Criterion 1
  - Criterion 2
technical_notes: Technical details
dependencies: []
"""
        )

        session = MockSession()
        agent = PlannerAgent(
            target_path=spec_path,
            session=session,
            provider_config={},
            tool_registry={},
        )

        # Initialize (shows greeting)
        agent.initialize()

        # Generate plan
        await agent.process("generate")

        assert agent.plan is not None
        assert len(agent.plan.steps) > 0
        assert agent.is_done()

        print("✅ Plan generated successfully")
        print(f"   - Steps: {len(agent.plan.steps)}")


async def test_planner_finalization():
    """Test planner finalization."""
    print("\n=== Test 10: Planner Finalization ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        spec_path = Path(tmp_dir) / "spec.yaml"
        spec_path.write_text(
            """title: Test
type: feature
description: |
  Detailed description with more than 100 characters to meet
  the completeness requirements for the planner agent.
acceptance_criteria:
  - Criterion 1
technical_notes: Notes
dependencies: []
"""
        )

        session = MockSession()
        agent = PlannerAgent(
            target_path=spec_path,
            session=session,
            provider_config={},
            tool_registry={},
        )

        agent.initialize()
        await agent.process("generate")

        summary = agent.finalize()

        assert "Planner completed" in summary
        assert "plan.md" in summary.lower()

        print("✅ Planner finalized successfully")


# ===== Slash Command Tests =====


async def test_plan_command_usage():
    """Test /plan command usage help."""
    print("\n=== Test 11: /plan Command Usage ===")

    cmd = PlanCommand()

    # No args
    result = await cmd.execute("")
    assert "Usage:" in result
    assert "/plan <ticket-slug>" in result

    print("✅ /plan shows usage when no args")


async def test_plan_command_activation():
    """Test /plan command activates agent."""
    print("\n=== Test 12: /plan Command Activation ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        original_cwd = os.getcwd()
        os.chdir(tmp_dir)

        try:
            # Setup
            subprocess.run(
                ["git", "init"], cwd=tmp_dir, check=True, capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=tmp_dir,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=tmp_dir,
                check=True,
                capture_output=True,
            )

            from src.cdd_agent.mechanical.init import initialize_project
            from src.cdd_agent.mechanical.new_ticket import create_new_ticket

            initialize_project(tmp_dir, force=False)
            create_new_ticket("feature", "Test Feature")

            # Update spec to be complete
            spec_path = (
                Path(tmp_dir)
                / "specs"
                / "tickets"
                / "feature-test-feature"
                / "spec.yaml"
            )
            spec_path.write_text(
                """title: Test Feature
type: feature
description: |
  A comprehensive test feature description with enough detail
  to pass all completeness checks for the planner agent.
acceptance_criteria:
  - Users can do X
  - System handles Y
technical_notes: Use framework Z
dependencies: []
"""
            )

            # Create session and command
            session = MockSession()
            cmd = PlanCommand()
            cmd.session = session

            # Execute command
            result = await cmd.execute("feature-test-feature")

            assert "Planner" in result or "Generating" in result
            assert session.is_in_agent_mode()
            assert session.get_current_agent_name() == "Planner"

            print("✅ /plan activated Planner agent")

        finally:
            os.chdir(original_cwd)


async def test_plan_command_errors():
    """Test /plan error handling."""
    print("\n=== Test 13: /plan Error Handling ===")

    # Test: ticket not found
    cmd = PlanCommand()
    cmd.session = MockSession()

    result = await cmd.execute("nonexistent-ticket")
    assert "Error" in result or "not found" in result.lower()
    print("✅ /plan handles missing ticket")

    # Test: already in agent mode
    class FakeAgent:
        name = "TestAgent"

    cmd.session.current_agent = FakeAgent()
    result = await cmd.execute("any-ticket")
    assert "Already in" in result or "Error" in result
    print("✅ /plan prevents double activation")


# ===== Integration Tests =====


async def test_full_workflow():
    """Integration test: Full Planner workflow."""
    print("\n=== Test 14: Full Planner Workflow ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        original_cwd = os.getcwd()
        os.chdir(tmp_dir)

        try:
            # Setup
            subprocess.run(
                ["git", "init"], cwd=tmp_dir, check=True, capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=tmp_dir,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=tmp_dir,
                check=True,
                capture_output=True,
            )

            from src.cdd_agent.mechanical.init import initialize_project
            from src.cdd_agent.mechanical.new_ticket import create_new_ticket

            initialize_project(tmp_dir, force=False)
            create_new_ticket("feature", "User Auth")

            # Make spec complete
            spec_path = (
                Path(tmp_dir) / "specs" / "tickets" / "feature-user-auth" / "spec.yaml"
            )
            spec_path.write_text(
                """title: User Authentication
type: feature
description: |
  Implement comprehensive authentication system with email/password
  and OAuth support. Users should be able to register, login, and
  reset passwords securely.
acceptance_criteria:
  - Users can register
  - Users can log in
  - OAuth works
technical_notes: Use bcrypt
dependencies: []
"""
            )

            print("   Step 1: Created ticket with complete spec")

            # Create session
            session = MockSession()

            # Activate Planner via command
            cmd = PlanCommand()
            cmd.session = session
            await cmd.execute("feature-user-auth")

            assert session.is_in_agent_mode()
            print("   Step 2: Activated Planner")

            # Generate plan
            agent = session.current_agent
            await agent.process("generate")

            print("   Step 3: Generated plan")

            # Verify plan saved
            plan_path = spec_path.parent / "plan.md"
            assert plan_path.exists()
            print("   Step 4: Plan saved to plan.md")

            # Finalize
            summary = agent.finalize()
            assert "Planner completed" in summary
            print("   Step 5: Finalized")

            print("\n✅ Full workflow completed successfully!")

        finally:
            os.chdir(original_cwd)


async def run_async_tests():
    """Run all async tests."""
    await test_planner_initialization_complete_spec()
    await test_planner_initialization_incomplete_spec()
    await test_plan_generation()
    await test_planner_finalization()
    await test_plan_command_usage()
    await test_plan_command_activation()
    await test_plan_command_errors()
    await test_full_workflow()


if __name__ == "__main__":
    import asyncio

    print("=" * 70)
    print("CDD AGENT - PLANNER AGENT TEST SUITE")
    print("=" * 70)

    try:
        # Sync tests
        test_plan_step_creation()
        test_implementation_plan_creation()
        test_plan_to_markdown()
        test_plan_from_markdown()
        test_markdown_roundtrip()
        test_plan_from_json()

        # Async tests
        asyncio.run(run_async_tests())

        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("=" * 70)
        print("\nWeek 6 Complete:")
        print("- ✅ Plan data model with markdown roundtrip")
        print("- ✅ PlannerAgent with LLM integration")
        print("- ✅ /plan command with ticket resolution")
        print("- ✅ Full workflow integration")
        print("- ✅ All 14 tests passing")
        print("\nReady for Week 7: Executor Agent!")

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        raise
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        raise
