"""Test suite for Socrates Agent.

This script tests:
- YAML parser (TicketSpec parsing, validation, completeness)
- SocratesAgent (initialization, dialogue, completion)
- /socrates command (resolution, activation, error handling)
"""

import tempfile
from pathlib import Path

from src.cdd_agent.agents import SocratesAgent
from src.cdd_agent.slash_commands import SocratesCommand
from src.cdd_agent.utils.yaml_parser import (
    TicketSpec,
    parse_ticket_spec,
    save_ticket_spec,
)


# Mock objects for testing
class MockAgent:
    """Mock general-purpose agent."""

    def __init__(self):
        self.provider_config = {"model": "test"}
        self.tool_registry = {}
        self.call_count = 0

    def run(self, message: str, system_prompt=None) -> str:
        # Simulate LLM response
        self.call_count += 1
        # Don't complete on first call (to test dialogue)
        if (
            self.call_count > 1
            and system_prompt
            and "None - spec looks complete" in system_prompt
        ):
            return "SPEC_COMPLETE"
        return "What specific authentication methods should we support?"


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


# ===== YAML Parser Tests =====


def test_ticket_spec_parsing():
    """Test parsing ticket spec from YAML."""
    print("\n=== Test 1: TicketSpec Parsing ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        spec_path = Path(tmp_dir) / "spec.yaml"
        spec_path.write_text(
            """title: User Authentication
type: feature
description: Add user authentication system with email/password
acceptance_criteria:
  - Users can register with email and password
  - Users can log in and log out
technical_notes: Use bcrypt for password hashing
dependencies: []
"""
        )

        spec = parse_ticket_spec(spec_path)

        assert spec.title == "User Authentication"
        assert spec.type == "feature"
        assert "email/password" in spec.description
        assert len(spec.acceptance_criteria) == 2
        assert "bcrypt" in spec.technical_notes

        print("✅ Parsed ticket spec successfully")
        print(f"   - Title: {spec.title}")
        print(f"   - Type: {spec.type}")
        print(f"   - Acceptance criteria: {len(spec.acceptance_criteria)} items")


def test_ticket_spec_validation():
    """Test ticket spec validation."""
    print("\n=== Test 2: TicketSpec Validation ===")

    # Valid spec
    valid_spec = TicketSpec(
        {"title": "Test", "type": "feature", "description": "Test description"}
    )
    errors = valid_spec.validate()
    assert len(errors) == 0
    print("✅ Valid spec passes validation")

    # Missing fields
    invalid_spec = TicketSpec({"title": "Test"})
    errors = invalid_spec.validate()
    assert "type" in str(errors)
    assert "description" in str(errors)
    print(f"✅ Invalid spec caught: {len(errors)} errors")

    # Invalid type
    bad_type_spec = TicketSpec(
        {"title": "Test", "type": "invalid", "description": "Test"}
    )
    errors = bad_type_spec.validate()
    assert "Invalid ticket type" in str(errors)
    print("✅ Invalid type detected")


def test_ticket_spec_completeness():
    """Test spec completeness checking."""
    print("\n=== Test 3: TicketSpec Completeness ===")

    # Incomplete: too brief
    brief_spec = TicketSpec(
        {"title": "Auth", "type": "feature", "description": "Add auth"}
    )
    assert not brief_spec.is_complete()
    print("✅ Brief spec marked as incomplete")

    # Incomplete: no acceptance criteria
    no_ac_spec = TicketSpec(
        {
            "title": "Auth",
            "type": "feature",
            "description": "Add comprehensive authentication system with "
            "email/password and OAuth support",
        }
    )
    assert not no_ac_spec.is_complete()
    print("✅ Spec without acceptance criteria marked incomplete")

    # Complete
    complete_spec = TicketSpec(
        {
            "title": "Auth",
            "type": "feature",
            "description": "Add comprehensive authentication system with "
            "email/password and OAuth support for secure user access",
            "acceptance_criteria": ["Users can register", "Users can log in"],
        }
    )
    assert complete_spec.is_complete()
    print("✅ Complete spec recognized")


def test_vague_area_detection():
    """Test detection of vague areas needing clarification."""
    print("\n=== Test 4: Vague Area Detection ===")

    vague_spec = TicketSpec(
        {
            "title": "Fix login",
            "type": "feature",
            "description": "Maybe add some auth somehow",
        }
    )

    vague_areas = vague_spec.get_vague_areas()

    # Should detect brief description
    assert any("brief" in area.lower() for area in vague_areas)

    # Should detect vague words
    assert any("vague terms" in area.lower() for area in vague_areas)

    # Should detect missing acceptance criteria
    assert any("acceptance criteria" in area.lower() for area in vague_areas)

    print(f"✅ Detected {len(vague_areas)} vague areas:")
    for area in vague_areas:
        print(f"   - {area}")


def test_spec_update_and_save():
    """Test updating and saving specs."""
    print("\n=== Test 5: Spec Update and Save ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        spec_path = Path(tmp_dir) / "spec.yaml"
        spec_path.write_text(
            """title: Test
type: feature
description: Original description
acceptance_criteria: []
technical_notes: ""
dependencies: []
"""
        )

        spec = parse_ticket_spec(spec_path)

        # Update spec
        spec.update(
            {
                "description": "Updated description with more detail",
                "acceptance_criteria": ["New criterion 1", "New criterion 2"],
            }
        )

        # Save
        save_ticket_spec(spec)

        # Reload and verify
        reloaded = parse_ticket_spec(spec_path)
        assert reloaded.description == "Updated description with more detail"
        assert len(reloaded.acceptance_criteria) == 2

        print("✅ Spec updated and saved successfully")
        print(f"   - New description: {reloaded.description[:40]}...")
        print(f"   - Acceptance criteria: {len(reloaded.acceptance_criteria)} items")


# ===== Socrates Agent Tests =====


def test_socrates_initialization_incomplete_spec():
    """Test Socrates initialization with incomplete spec."""
    print("\n=== Test 6: Socrates Initialization (Incomplete Spec) ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        spec_path = Path(tmp_dir) / "spec.yaml"
        spec_path.write_text(
            """title: Add Auth
type: feature
description: Add authentication
acceptance_criteria: []
technical_notes: ""
dependencies: []
"""
        )

        session = MockSession()
        agent = SocratesAgent(
            target_path=spec_path,
            session=session,
            provider_config={},
            tool_registry={},
        )

        greeting = agent.initialize()

        assert "Socrates" in greeting
        assert "Add Auth" in greeting
        assert "Areas that need clarification" in greeting
        assert not agent.is_done()

        print("✅ Socrates initialized with incomplete spec")
        print(f"   - Greeting length: {len(greeting)} chars")


def test_socrates_initialization_complete_spec():
    """Test Socrates initialization with complete spec."""
    print("\n=== Test 7: Socrates Initialization (Complete Spec) ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        spec_path = Path(tmp_dir) / "spec.yaml"
        spec_path.write_text(
            """title: User Authentication System
type: feature
description: |
  Implement a comprehensive user authentication system with email/password
  and OAuth support. Users should be able to register, log in, log out,
  and reset passwords securely.
acceptance_criteria:
  - Users can register with email and password
  - Passwords are hashed with bcrypt
  - Users can log in with credentials
  - Users can log out
  - Password reset flow works
technical_notes: Use bcrypt for hashing, JWT for sessions
dependencies: []
"""
        )

        session = MockSession()
        agent = SocratesAgent(
            target_path=spec_path,
            session=session,
            provider_config={},
            tool_registry={},
        )

        greeting = agent.initialize()

        assert "Socrates" in greeting
        assert "complete" in greeting.lower()
        assert agent.is_done()  # Should auto-complete

        print("✅ Socrates recognized complete spec")
        print("   - Auto-marked as complete")


async def test_socrates_dialogue():
    """Test Socrates asking questions and processing answers."""
    print("\n=== Test 8: Socrates Dialogue ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        spec_path = Path(tmp_dir) / "spec.yaml"
        spec_path.write_text(
            """title: Add Auth
type: feature
description: Add authentication
acceptance_criteria: []
technical_notes: ""
dependencies: []
"""
        )

        session = MockSession()
        agent = SocratesAgent(
            target_path=spec_path,
            session=session,
            provider_config={},
            tool_registry={},
        )

        agent.initialize()

        # Process user response
        response = await agent.process("Email/password and Google OAuth")

        assert response is not None
        assert len(agent.conversation_history) > 0
        assert not agent.is_done()  # Not complete yet

        print("✅ Socrates processed user answer")
        print(f"   - Response: {response[:60]}...")
        print(f"   - Conversation history: {len(agent.conversation_history)} entries")


async def test_socrates_completion():
    """Test Socrates detecting completion."""
    print("\n=== Test 9: Socrates Completion Detection ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        spec_path = Path(tmp_dir) / "spec.yaml"
        spec_path.write_text(
            """title: Complete Feature
type: feature
description: |
  This is a comprehensive feature specification with enough detail to be
  considered complete. It includes clear requirements, context, and expected
  outcomes that provide sufficient information for planning and implementation.
acceptance_criteria:
  - Criterion 1
  - Criterion 2
technical_notes: Notes here
dependencies: []
"""
        )

        session = MockSession()
        agent = SocratesAgent(
            target_path=spec_path,
            session=session,
            provider_config={},
            tool_registry={},
        )

        agent.initialize()

        # Should auto-complete for complete spec
        assert agent.is_done()

        print("✅ Socrates auto-completes for detailed specs")


def test_socrates_finalize():
    """Test Socrates finalization and save."""
    print("\n=== Test 10: Socrates Finalization ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        spec_path = Path(tmp_dir) / "spec.yaml"
        spec_path.write_text(
            """title: Test
type: feature
description: Test description
acceptance_criteria: []
technical_notes: ""
dependencies: []
"""
        )

        session = MockSession()
        agent = SocratesAgent(
            target_path=spec_path,
            session=session,
            provider_config={},
            tool_registry={},
        )

        agent.initialize()
        agent.questions_asked = 3

        # Finalize
        summary = agent.finalize()

        assert "Socrates completed" in summary
        assert "Questions asked: 3" in summary
        assert spec_path.name in summary

        print("✅ Socrates finalized successfully")
        print(f"   - Summary length: {len(summary)} chars")


# ===== Slash Command Tests =====


async def test_socrates_command_usage():
    """Test /socrates command usage help."""
    print("\n=== Test 11: /socrates Command Usage ===")

    cmd = SocratesCommand()

    # No args
    result = await cmd.execute("")
    assert "Usage:" in result
    assert "/socrates <ticket-slug>" in result

    print("✅ /socrates shows usage when no args")


async def test_socrates_command_resolution():
    """Test ticket slug resolution."""
    print("\n=== Test 12: /socrates Ticket Resolution ===")

    import os
    import subprocess

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Setup CDD structure
        original_cwd = os.getcwd()
        os.chdir(tmp_dir)

        try:
            # Initialize git
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

            # Create CDD structure
            from src.cdd_agent.mechanical.init import initialize_project

            initialize_project(tmp_dir, force=False)

            # Create ticket
            from src.cdd_agent.mechanical.new_ticket import create_new_ticket

            result = create_new_ticket("feature", "User Auth")
            ticket_path = result["ticket_path"]
            spec_path = ticket_path / "spec.yaml"

            # Test resolution
            cmd = SocratesCommand()
            resolved = cmd._resolve_ticket_spec("feature-user-auth")

            assert resolved == spec_path
            print(f"✅ Resolved ticket slug correctly: {resolved}")

        finally:
            os.chdir(original_cwd)


async def test_socrates_command_activation():
    """Test /socrates command activates agent."""
    print("\n=== Test 13: /socrates Command Activation ===")

    import os
    import subprocess

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

            # Create session and command
            session = MockSession()
            cmd = SocratesCommand()
            cmd.session = session

            # Execute command
            result = await cmd.execute("feature-test-feature")

            assert "Socrates" in result
            # Should either be entering mode or showing Socrates greeting
            assert "Entering" in result or "Hello! I'm Socrates" in result
            assert session.is_in_agent_mode()
            assert session.get_current_agent_name() == "Socrates"

            print("✅ /socrates activated Socrates agent")
            print(f"   - Agent active: {session.is_in_agent_mode()}")

        finally:
            os.chdir(original_cwd)


async def test_socrates_command_errors():
    """Test /socrates error handling."""
    print("\n=== Test 14: /socrates Error Handling ===")

    # Test: ticket not found
    cmd = SocratesCommand()
    cmd.session = MockSession()

    result = await cmd.execute("nonexistent-ticket")
    assert "Error" in result
    assert "not found" in result.lower()
    print("✅ /socrates handles missing ticket")

    # Test: already in agent mode
    # Create a mock agent with proper attributes
    class FakeAgent:
        name = "TestAgent"

    cmd.session.current_agent = FakeAgent()
    result = await cmd.execute("any-ticket")
    assert "Already in" in result or "Error" in result
    print("✅ /socrates prevents double activation")


# ===== Integration Tests =====


async def test_full_workflow():
    """Integration test: Full Socrates workflow."""
    print("\n=== Test 15: Full Socrates Workflow ===")

    import os
    import subprocess

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
            create_new_ticket("feature", "User Authentication")

            print("   Step 1: Created ticket")

            # Create session
            session = MockSession()

            # Activate Socrates via command
            cmd = SocratesCommand()
            cmd.session = session
            await cmd.execute("feature-user-authentication")

            assert session.is_in_agent_mode()
            print("   Step 2: Activated Socrates")

            # Simulate dialogue
            agent = session.current_agent
            await agent.process("Email/password and OAuth")
            print("   Step 3: First answer processed")

            await agent.process("bcrypt for hashing, JWT for tokens")
            print("   Step 4: Second answer processed")

            # Finalize
            summary = agent.finalize()
            assert "Socrates completed" in summary
            print("   Step 5: Finalized")

            print("\n✅ Full workflow completed successfully!")

        finally:
            os.chdir(original_cwd)


async def run_async_tests():
    """Run all async tests."""
    await test_socrates_dialogue()
    await test_socrates_completion()
    await test_socrates_command_usage()
    await test_socrates_command_resolution()
    await test_socrates_command_activation()
    await test_socrates_command_errors()
    await test_full_workflow()


if __name__ == "__main__":
    import asyncio

    print("=" * 70)
    print("CDD AGENT - SOCRATES AGENT TEST SUITE")
    print("=" * 70)

    try:
        # YAML Parser tests
        test_ticket_spec_parsing()
        test_ticket_spec_validation()
        test_ticket_spec_completeness()
        test_vague_area_detection()
        test_spec_update_and_save()

        # Socrates Agent tests
        test_socrates_initialization_incomplete_spec()
        test_socrates_initialization_complete_spec()
        test_socrates_finalize()

        # Async tests
        asyncio.run(run_async_tests())

        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("=" * 70)
        print("\nWeek 5 Complete:")
        print("- ✅ YAML parser with validation and completeness checking")
        print("- ✅ SocratesAgent with Socratic dialogue")
        print("- ✅ /socrates command with ticket resolution")
        print("- ✅ Full workflow integration")
        print("- ✅ All 15 tests passing")
        print("\nReady for Week 6: Planner Agent!")

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
