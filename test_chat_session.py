"""Test suite for chat session management.

This script tests the session management system including:
- ChatSession (agent switching, state management)
- BaseAgent (lifecycle, abstract methods)
- TestAgent (integration testing)
"""

import os
import subprocess
import tempfile
from pathlib import Path

from src.cdd_agent.agents import TestAgent
from src.cdd_agent.session import ChatSession


# Mock objects for testing
class MockAgent:
    """Mock general-purpose agent for testing."""

    def __init__(self):
        self.provider_config = {"model": "test"}
        self.tool_registry = {}

    def run(self, message: str, system_prompt=None) -> str:
        return f"General agent response to: {message}"

    def stream(self, message: str, system_prompt=None):
        return iter([{"type": "text", "text": f"Streaming: {message}"}])


class MockProviderConfig:
    """Mock provider config."""

    pass


class MockToolRegistry:
    """Mock tool registry."""

    pass


def test_chat_session_initialization():
    """Test ChatSession initialization."""
    print("\n=== Test 1: ChatSession Initialization ===")

    agent = MockAgent()
    session = ChatSession(agent, MockProviderConfig(), MockToolRegistry())

    assert session.general_agent == agent
    assert session.current_agent is None
    assert not session.is_in_agent_mode()
    assert session.get_current_agent_name() is None

    print("✅ ChatSession initialized correctly")
    print(f"   - General agent: {type(session.general_agent).__name__}")
    print(f"   - In agent mode: {session.is_in_agent_mode()}")
    print(f"   - Current agent: {session.get_current_agent_name()}")


def test_agent_mode_detection():
    """Test agent mode detection."""
    print("\n=== Test 2: Agent Mode Detection ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        target_path = Path(tmp_dir) / "test.txt"
        target_path.write_text("test content")

        agent = MockAgent()
        session = ChatSession(agent, MockProviderConfig(), MockToolRegistry())

        # Initially not in agent mode
        assert not session.is_in_agent_mode()
        print("✅ Initially not in agent mode")

        # Switch to agent mode
        greeting = session.switch_to_agent(TestAgent, target_path)
        assert session.is_in_agent_mode()
        assert session.get_current_agent_name() == "TestAgent"
        assert "Entering TestAgent Mode" in greeting
        print("✅ Successfully switched to agent mode")
        print(f"   - Agent name: {session.get_current_agent_name()}")

        # Exit agent mode
        completion = session.exit_agent()
        assert not session.is_in_agent_mode()
        assert session.get_current_agent_name() is None
        assert "Exiting TestAgent Mode" in completion
        print("✅ Successfully exited agent mode")


def test_switch_to_agent():
    """Test switching to agent."""
    print("\n=== Test 3: Switch to Agent ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        target_path = Path(tmp_dir) / "test-ticket.yaml"
        target_path.write_text("ticket: test")

        agent = MockAgent()
        session = ChatSession(agent, MockProviderConfig(), MockToolRegistry())

        # Switch to TestAgent
        greeting = session.switch_to_agent(TestAgent, target_path)

        assert session.current_agent is not None
        assert isinstance(session.current_agent, TestAgent)
        assert session.current_ticket == target_path
        assert "Hello! I'm **TestAgent**" in greeting

        print("✅ Agent activated successfully")
        print(f"   - Agent instance: {type(session.current_agent).__name__}")
        print(f"   - Target path: {session.current_ticket}")


def test_exit_agent():
    """Test exiting agent mode."""
    print("\n=== Test 4: Exit Agent ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        target_path = Path(tmp_dir) / "test.txt"
        target_path.write_text("content")

        agent = MockAgent()
        session = ChatSession(agent, MockProviderConfig(), MockToolRegistry())

        # Enter agent mode
        session.switch_to_agent(TestAgent, target_path)
        assert session.is_in_agent_mode()

        # Exit agent mode
        completion = session.exit_agent()

        assert not session.is_in_agent_mode()
        assert session.current_agent is None
        assert session.current_ticket is None
        assert "TestAgent completed" in completion

        print("✅ Agent deactivated successfully")
        print(f"   - Completion message: {completion[:50]}...")


def test_cannot_switch_while_in_agent_mode():
    """Test error when trying to switch while already in agent mode."""
    print("\n=== Test 5: Cannot Switch While in Agent Mode ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        target1 = Path(tmp_dir) / "test1.txt"
        target2 = Path(tmp_dir) / "test2.txt"
        target1.write_text("content1")
        target2.write_text("content2")

        agent = MockAgent()
        session = ChatSession(agent, MockProviderConfig(), MockToolRegistry())

        # Enter agent mode
        session.switch_to_agent(TestAgent, target1)

        # Try to switch again (should fail)
        try:
            session.switch_to_agent(TestAgent, target2)
            assert False, "Should raise RuntimeError"
        except RuntimeError as e:
            assert "Already in TestAgent mode" in str(e)
            print(f"✅ Correctly raised error: {e}")


async def test_process_input_general_chat():
    """Test processing input in general chat mode."""
    print("\n=== Test 6: Process Input - General Chat ===")

    agent = MockAgent()
    session = ChatSession(agent, MockProviderConfig(), MockToolRegistry())

    # Process regular message (not slash command)
    response, should_exit = await session.process_input("Hello, how are you?")

    # Should return None (caller handles with general agent)
    assert response is None
    assert not should_exit

    print("✅ General chat input processed correctly")
    print(f"   - Response: {response} (None = use general agent)")
    print(f"   - Should exit: {should_exit}")


async def test_process_input_agent_mode():
    """Test processing input in agent mode."""
    print("\n=== Test 7: Process Input - Agent Mode ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        target_path = Path(tmp_dir) / "test.txt"
        target_path.write_text("content")

        agent = MockAgent()
        session = ChatSession(agent, MockProviderConfig(), MockToolRegistry())

        # Switch to agent mode
        session.switch_to_agent(TestAgent, target_path)

        # Process message in agent mode
        response, should_exit = await session.process_input("Test message 1")

        assert response is not None
        assert "Test message 1" in response
        assert "Message 1/3" in response
        assert not should_exit

        print("✅ Agent mode input processed correctly")
        print(f"   - Response: {response[:50]}...")


async def test_process_input_exit_command():
    """Test exit command in agent mode."""
    print("\n=== Test 8: Process Input - Exit Command ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        target_path = Path(tmp_dir) / "test.txt"
        target_path.write_text("content")

        agent = MockAgent()
        session = ChatSession(agent, MockProviderConfig(), MockToolRegistry())

        # Switch to agent mode
        session.switch_to_agent(TestAgent, target_path)

        # Process exit command
        response, should_exit = await session.process_input("exit")

        assert response is not None
        assert "Exiting TestAgent Mode" in response
        assert not session.is_in_agent_mode()

        print("✅ Exit command processed correctly")
        print(f"   - Back in general chat: {not session.is_in_agent_mode()}")


async def test_process_input_slash_command():
    """Test slash command processing."""
    print("\n=== Test 9: Process Input - Slash Command ===")

    agent = MockAgent()
    session = ChatSession(agent, MockProviderConfig(), MockToolRegistry())

    # Process slash command
    response, should_exit = await session.process_input("/help")

    assert response is not None
    assert "commands" in response.lower() or "help" in response.lower()

    print("✅ Slash command processed correctly")
    print(f"   - Response length: {len(response)} characters")


async def test_auto_exit_after_completion():
    """Test automatic exit when agent marks itself complete."""
    print("\n=== Test 10: Auto-Exit After Completion ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        target_path = Path(tmp_dir) / "test.txt"
        target_path.write_text("content")

        agent = MockAgent()
        session = ChatSession(agent, MockProviderConfig(), MockToolRegistry())

        # Switch to agent mode
        session.switch_to_agent(TestAgent, target_path)

        # Send 3 messages (TestAgent auto-exits after 3)
        response1, _ = await session.process_input("Message 1")
        assert session.is_in_agent_mode()
        print("   After message 1: Still in agent mode")

        response2, _ = await session.process_input("Message 2")
        assert session.is_in_agent_mode()
        print("   After message 2: Still in agent mode")

        response3, _ = await session.process_input("Message 3")
        # Should auto-exit after 3rd message
        assert not session.is_in_agent_mode()
        assert "Exiting TestAgent Mode" in response3

        print("✅ Agent auto-exited after completion")


def test_get_status():
    """Test session status reporting."""
    print("\n=== Test 11: Session Status ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        target_path = Path(tmp_dir) / "test.txt"
        target_path.write_text("content")

        agent = MockAgent()
        session = ChatSession(agent, MockProviderConfig(), MockToolRegistry())

        # Status in general mode
        status1 = session.get_status()
        assert status1["mode"] == "general"
        assert status1["agent_name"] is None
        assert status1["current_ticket"] is None
        print(f"✅ General mode status: {status1}")

        # Switch to agent mode
        session.switch_to_agent(TestAgent, target_path)

        # Status in agent mode
        status2 = session.get_status()
        assert status2["mode"] == "agent"
        assert status2["agent_name"] == "TestAgent"
        assert status2["current_ticket"] == str(target_path)
        print(f"✅ Agent mode status: {status2}")


def test_base_agent_lifecycle():
    """Test BaseAgent lifecycle methods."""
    print("\n=== Test 12: BaseAgent Lifecycle ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        target_path = Path(tmp_dir) / "test.txt"
        target_path.write_text("test content")

        agent = TestAgent(
            target_path=target_path,
            session=None,
            provider_config=None,
            tool_registry=None,
        )

        # Test initialization
        greeting = agent.initialize()
        assert "Hello! I'm **TestAgent**" in greeting
        print(f"✅ Initialize: {greeting[:40]}...")

        # Test is_done (initially False)
        assert not agent.is_done()
        print("✅ is_done() initially: False")

        # Test mark_complete
        agent.mark_complete()
        assert agent.is_done()
        print("✅ mark_complete() → is_done(): True")

        # Test finalize
        completion = agent.finalize()
        assert "TestAgent completed" in completion
        print(f"✅ Finalize: {completion[:40]}...")


async def test_integration_full_workflow():
    """Integration test: Full workflow with agent switching."""
    print("\n=== Test 13: Integration - Full Workflow ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Setup git repo
        subprocess.run(["git", "init"], cwd=tmp_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_dir,
            check=True,
            capture_output=True,
        )

        # Initialize CDD structure
        from src.cdd_agent.mechanical.init import initialize_project

        initialize_project(str(tmp_dir), force=False)

        original_cwd = os.getcwd()
        os.chdir(tmp_dir)

        try:
            # Create ticket
            from src.cdd_agent.mechanical.new_ticket import create_new_ticket

            ticket_result = create_new_ticket("feature", "Test Feature")
            ticket_path = ticket_result["ticket_path"] / "spec.yaml"

            # Create session
            agent = MockAgent()
            session = ChatSession(agent, MockProviderConfig(), MockToolRegistry())

            print("   Step 1: Created CDD structure and ticket")

            # Workflow: init → switch to agent → interact → exit
            # Step 1: Process /init (already done above)

            # Step 2: Switch to agent
            greeting = session.switch_to_agent(TestAgent, ticket_path)
            assert "Entering TestAgent Mode" in greeting
            print("   Step 2: Switched to TestAgent")

            # Step 3: Interact with agent
            r1, _ = await session.process_input("First message")
            assert "Message 1/3" in r1
            print("   Step 3: Sent first message to agent")

            # Step 4: Continue interaction
            r2, _ = await session.process_input("Second message")
            assert "Message 2/3" in r2
            print("   Step 4: Sent second message to agent")

            # Step 5: Auto-exit after 3 messages
            r3, _ = await session.process_input("Third message")
            assert not session.is_in_agent_mode()
            print("   Step 5: Agent auto-exited after 3 messages")

            # Step 6: Back in general chat
            r4, _ = await session.process_input("General chat message")
            assert r4 is None  # Should use general agent
            print("   Step 6: Back in general chat")

            print("\n✅ Integration test completed successfully!")

        finally:
            os.chdir(original_cwd)


async def run_async_tests():
    """Run all async tests."""
    await test_process_input_general_chat()
    await test_process_input_agent_mode()
    await test_process_input_exit_command()
    await test_process_input_slash_command()
    await test_auto_exit_after_completion()
    await test_integration_full_workflow()


if __name__ == "__main__":
    import asyncio

    print("=" * 70)
    print("CDD AGENT - CHAT SESSION TEST SUITE")
    print("=" * 70)

    try:
        # Sync tests
        test_chat_session_initialization()
        test_agent_mode_detection()
        test_switch_to_agent()
        test_exit_agent()
        test_cannot_switch_while_in_agent_mode()
        test_get_status()
        test_base_agent_lifecycle()

        # Async tests
        asyncio.run(run_async_tests())

        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("=" * 70)
        print("\nTask 4 Complete:")
        print("- ✅ BaseAgent abstract class implemented")
        print("- ✅ ChatSession with agent switching")
        print("- ✅ TestAgent for integration testing")
        print("- ✅ CLI integration complete")
        print("- ✅ All 13 tests passing")
        print("\nReady for specialized agents (Week 5-7)!")

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        raise
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        raise
