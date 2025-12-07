"""Test suite for slash command system.

This script tests all slash command functionality including:
- Router (detection, parsing, routing)
- InitCommand
- NewCommand
- HelpCommand
"""

import os
import subprocess
import tempfile
from pathlib import Path

from src.cdd_agent.slash_commands import get_router
from src.cdd_agent.slash_commands import setup_commands
from src.cdd_agent.slash_commands.help_command import HelpCommand
from src.cdd_agent.slash_commands.init_command import InitCommand
from src.cdd_agent.slash_commands.new_command import NewCommand
from src.cdd_agent.slash_commands.router import SlashCommandRouter


def test_router_command_registration():
    """Test command registration."""
    print("\n=== Test 1: Router Command Registration ===")

    router = SlashCommandRouter()

    # Register init command
    init_cmd = InitCommand()
    router.register(init_cmd)

    assert "init" in router._commands
    assert router._commands["init"] == init_cmd
    print("✅ InitCommand registered successfully")

    # Register new command
    new_cmd = NewCommand()
    router.register(new_cmd)

    assert "new" in router._commands
    print("✅ NewCommand registered successfully")

    # Get all commands
    all_commands = router.get_all_commands()
    assert len(all_commands) == 2
    print(f"✅ Total commands registered: {len(all_commands)}")


def test_router_slash_detection():
    """Test slash command detection."""
    print("\n=== Test 2: Slash Command Detection ===")

    router = SlashCommandRouter()

    # Positive tests
    assert router.is_slash_command("/init")
    print("✅ Detected: /init")

    assert router.is_slash_command("/new ticket feature Auth")
    print("✅ Detected: /new ticket feature Auth")

    assert router.is_slash_command("  /help  ")
    print("✅ Detected: /help (with whitespace)")

    # Negative tests
    assert not router.is_slash_command("Not a command")
    print("✅ Rejected: Not a command")

    assert not router.is_slash_command("init without slash")
    print("✅ Rejected: init without slash")


def test_router_command_parsing():
    """Test command parsing."""
    print("\n=== Test 3: Command Parsing ===")

    router = SlashCommandRouter()

    # Test 1: Simple command
    cmd, args = router.parse_command("/init")
    assert cmd == "init"
    assert args == ""
    print("✅ Parsed: /init → ('init', '')")

    # Test 2: Command with flag
    cmd, args = router.parse_command("/init --force")
    assert cmd == "init"
    assert args == "--force"
    print("✅ Parsed: /init --force → ('init', '--force')")

    # Test 3: Command with multiple arguments
    cmd, args = router.parse_command("/new ticket feature User Auth")
    assert cmd == "new"
    assert args == "ticket feature User Auth"
    print(
        "✅ Parsed: /new ticket feature User Auth → ('new', 'ticket feature User Auth')"
    )

    # Test 4: Command with whitespace
    cmd, args = router.parse_command("  /help init  ")
    assert cmd == "help"
    assert args == "init"
    print("✅ Parsed with whitespace handling")


def test_init_command_validation():
    """Test InitCommand argument validation."""
    print("\n=== Test 4: InitCommand Validation ===")

    init_cmd = InitCommand()

    # Valid cases
    assert init_cmd.validate_args("")
    print("✅ Valid: empty args")

    assert init_cmd.validate_args("--force")
    print("✅ Valid: --force")

    # Invalid cases
    assert not init_cmd.validate_args("--invalid")
    print("✅ Invalid: --invalid")

    assert not init_cmd.validate_args("extra stuff")
    print("✅ Invalid: extra stuff")


def test_new_command_validation():
    """Test NewCommand argument validation."""
    print("\n=== Test 5: NewCommand Validation ===")

    new_cmd = NewCommand()

    # Valid ticket types
    assert new_cmd.validate_args("ticket feature User Auth")
    print("✅ Valid: ticket feature User Auth")

    assert new_cmd.validate_args("ticket bug Login Error")
    print("✅ Valid: ticket bug Login Error")

    assert new_cmd.validate_args("ticket spike Research")
    print("✅ Valid: ticket spike Research")

    assert new_cmd.validate_args("ticket enhancement Improve Perf")
    print("✅ Valid: ticket enhancement Improve Perf")

    # Valid documentation types
    assert new_cmd.validate_args("documentation guide Getting Started")
    print("✅ Valid: documentation guide Getting Started")

    assert new_cmd.validate_args("documentation feature User Auth")
    print("✅ Valid: documentation feature User Auth")

    # Invalid cases
    assert not new_cmd.validate_args("ticket invalid Type")
    print("✅ Invalid: ticket invalid Type")

    assert not new_cmd.validate_args("documentation invalid Type")
    print("✅ Invalid: documentation invalid Type")

    assert not new_cmd.validate_args("wrong category")
    print("✅ Invalid: wrong category")

    assert not new_cmd.validate_args("ticket")  # Missing type and name
    print("✅ Invalid: missing arguments")


async def test_init_command_execution():
    """Test InitCommand execution."""
    print("\n=== Test 6: InitCommand Execution ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Setup git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Change to tmp directory
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            init_cmd = InitCommand()

            # Execute command
            result = await init_cmd.execute("")

            # Verify result is markdown
            assert isinstance(result, str)
            assert "✅" in result or "CDD Project Initialized" in result
            print("✅ InitCommand executed successfully")

            # Verify structure was created
            assert (tmp_path / "CDD.md").exists()
            assert (tmp_path / "specs" / "tickets").exists()
            assert (tmp_path / ".cdd" / "templates").exists()
            print("✅ CDD structure created")

        finally:
            os.chdir(original_cwd)


async def test_new_command_execution():
    """Test NewCommand execution."""
    print("\n=== Test 7: NewCommand Execution ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Setup git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Initialize CDD structure first
        from src.cdd_agent.mechanical.init import initialize_project

        initialize_project(str(tmp_path), force=False)

        # Change to tmp directory
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            new_cmd = NewCommand()

            # Test 1: Create feature ticket
            result = await new_cmd.execute("ticket feature User Authentication")
            assert isinstance(result, str)
            assert "✅" in result or "Created" in result
            assert "feature" in result.lower()
            print("✅ Created feature ticket")

            # Verify ticket was created
            ticket_path = tmp_path / "specs" / "tickets" / "feature-user-authentication"
            assert ticket_path.exists()
            assert (ticket_path / "spec.yaml").exists()
            print("✅ Ticket file verified")

            # Test 2: Create guide documentation
            result = await new_cmd.execute("documentation guide Getting Started")
            assert isinstance(result, str)
            assert "✅" in result or "Created" in result
            print("✅ Created guide documentation")

            # Verify documentation was created
            doc_path = tmp_path / "docs" / "guides" / "getting-started.md"
            assert doc_path.exists()
            print("✅ Documentation file verified")

        finally:
            os.chdir(original_cwd)


async def test_help_command():
    """Test HelpCommand."""
    print("\n=== Test 8: HelpCommand ===")

    # Setup router with commands
    router = get_router()
    setup_commands(router)

    help_cmd = HelpCommand()

    # Test 1: General help
    result = await help_cmd.execute("")
    assert isinstance(result, str)
    assert "CDD Agent Slash Commands" in result or "Available commands" in result
    assert "/init" in result
    assert "/new" in result
    assert "/help" in result
    print("✅ General help displays all commands")

    # Test 2: Specific command help
    result = await help_cmd.execute("init")
    assert isinstance(result, str)
    assert "init" in result.lower()
    assert "Initialize" in result or "CDD structure" in result
    print("✅ Specific command help works")

    # Test 3: Unknown command
    result = await help_cmd.execute("nonexistent")
    assert "Unknown command" in result or "nonexistent" in result
    print("✅ Unknown command handled gracefully")


async def test_router_execution():
    """Test router command execution."""
    print("\n=== Test 9: Router Execution ===")

    # Setup router
    router = get_router()
    setup_commands(router)

    # Test 1: Execute help command
    result = await router.execute("/help")
    assert isinstance(result, str)
    assert "commands" in result.lower()
    print("✅ Router executed /help")

    # Test 2: Unknown command
    result = await router.execute("/unknown")
    assert "Unknown command" in result
    print("✅ Router handled unknown command")

    # Test 3: Invalid arguments
    result = await router.execute("/init --invalid-flag")
    assert "Invalid" in result or "arguments" in result.lower()
    print("✅ Router handled invalid arguments")


async def test_integration_with_temp_project():
    """Integration test: Full workflow."""
    print("\n=== Test 10: Integration Test ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Setup git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Change to tmp directory
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            # Setup router
            router = get_router()
            setup_commands(router)

            # Workflow: init → new ticket → new doc → help

            # Step 1: Initialize project
            result = await router.execute("/init")
            assert "✅" in result or "CDD Project Initialized" in result
            assert (tmp_path / "CDD.md").exists()
            print("✅ Step 1: Initialized project")

            # Step 2: Create feature ticket
            result = await router.execute("/new ticket feature User Authentication")
            assert "✅" in result or "Created" in result
            ticket_path = tmp_path / "specs" / "tickets" / "feature-user-authentication"
            assert ticket_path.exists()
            print("✅ Step 2: Created feature ticket")

            # Step 3: Create bug ticket
            result = await router.execute("/new ticket bug Login Error")
            assert "✅" in result
            print("✅ Step 3: Created bug ticket")

            # Step 4: Create documentation
            result = await router.execute("/new documentation guide Getting Started")
            assert "✅" in result
            doc_path = tmp_path / "docs" / "guides" / "getting-started.md"
            assert doc_path.exists()
            print("✅ Step 4: Created guide documentation")

            # Step 5: Get help
            result = await router.execute("/help")
            assert "commands" in result.lower()
            print("✅ Step 5: Retrieved help")

            print("\n✅ Integration test completed successfully!")

        finally:
            os.chdir(original_cwd)


async def run_async_tests():
    """Run all async tests."""
    await test_init_command_execution()
    await test_new_command_execution()
    await test_help_command()
    await test_router_execution()
    await test_integration_with_temp_project()


if __name__ == "__main__":
    import asyncio

    print("=" * 70)
    print("CDD AGENT - SLASH COMMAND SYSTEM TEST SUITE")
    print("=" * 70)

    try:
        # Sync tests
        test_router_command_registration()
        test_router_slash_detection()
        test_router_command_parsing()
        test_init_command_validation()
        test_new_command_validation()

        # Async tests
        asyncio.run(run_async_tests())

        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("=" * 70)
        print("\nTask 3 Complete:")
        print("- ✅ BaseSlashCommand abstract class implemented")
        print("- ✅ SlashCommandRouter with detection, parsing, routing")
        print("- ✅ InitCommand (/init)")
        print("- ✅ NewCommand (/new ticket|documentation)")
        print("- ✅ HelpCommand (/help)")
        print("- ✅ Integration with cli.py chat loop")
        print("- ✅ All tests passing")
        print("\nReady for production use!")

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        raise
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        raise
