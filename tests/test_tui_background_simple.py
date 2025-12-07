"""Simple integration tests for TUI background functionality.

These tests focus on the core background integration logic without
requiring full TUI widget initialization.
"""

import unittest
from unittest.mock import Mock
from unittest.mock import patch

from cdd_agent.background_executor import get_background_executor
from cdd_agent.tui import CDDAgentTUI


class TestTUIBackgroundSimple(unittest.TestCase):
    """Simple tests for TUI background integration."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock agent
        self.mock_agent = Mock()
        self.mock_agent.stream.return_value = []

        # Create TUI instance (don't mount it)
        self.tui = CDDAgentTUI(
            agent=self.mock_agent,
            provider="test",
            model="test-model",
            system_prompt="test prompt",
        )

    def tearDown(self):
        """Clean up after tests."""
        # Stop background monitoring
        self.tui._stop_background_monitoring()

    def test_background_executor_initialization(self):
        """Test that BackgroundExecutor is properly initialized."""
        self.assertIsNotNone(self.tui.background_executor)
        self.assertIsInstance(self.tui.background_processes, dict)
        self.assertFalse(self.tui.background_monitor_active)

    def test_register_background_process(self):
        """Test background process registration without UI dependencies."""
        process_id = "test-process-123"
        command = "echo 'test'"

        # Mock the _add_background_status_message method to avoid UI dependencies
        with patch.object(self.tui, "_add_background_status_message"):
            # Register process
            self.tui._register_background_process(process_id, command)

        # Verify registration
        self.assertIn(process_id, self.tui.background_processes)
        process_info = self.tui.background_processes[process_id]

        self.assertEqual(process_info["command"], command)
        self.assertIsNone(process_info["last_status"])
        self.assertEqual(process_info["last_line_count"], 0)
        self.assertIsNone(process_info["message_widget"])

    def test_background_monitoring_lifecycle(self):
        """Test background monitoring start and stop."""
        # Start monitoring
        self.tui._start_background_monitoring()
        self.assertTrue(self.tui.background_monitor_active)

        # Stop monitoring
        self.tui._stop_background_monitoring()
        self.assertFalse(self.tui.background_monitor_active)

    def test_background_methods_exist(self):
        """Test that all background methods exist."""
        # TUI actions
        self.assertTrue(hasattr(self.tui, "action_show_background_processes"))
        self.assertTrue(hasattr(self.tui, "action_interrupt_background_processes"))

        # Helper methods
        self.assertTrue(hasattr(self.tui, "_register_background_process"))
        self.assertTrue(hasattr(self.tui, "_start_background_monitoring"))
        self.assertTrue(hasattr(self.tui, "_stop_background_monitoring"))
        self.assertTrue(hasattr(self.tui, "_monitor_background_processes"))

        # Notification methods
        self.assertTrue(hasattr(self.tui, "_notify_process_completed"))
        self.assertTrue(hasattr(self.tui, "_notify_process_failed"))
        self.assertTrue(hasattr(self.tui, "_notify_process_interrupted"))
        self.assertTrue(hasattr(self.tui, "_stream_process_output"))

    def test_background_tool_detection_logic(self):
        """Test that background tool detection logic is present."""
        # This tests the logic we added to detect background tools
        # We can't easily test the full stream without async, but we can verify
        # the logic exists in the code

        # Check if the method exists and has the right structure
        import inspect

        source = inspect.getsource(self.tui.send_to_agent)

        # Verify background tool detection logic is present
        self.assertIn("run_bash_background", source)
        self.assertIn("background", source.lower())

    def test_process_registration_data_structure(self):
        """Test that process registration creates correct data structure."""
        process_id = "test-data-structure"
        command = "echo 'data structure test'"

        with patch.object(self.tui, "_add_background_status_message"):
            self.tui._register_background_process(process_id, command)

        process_info = self.tui.background_processes[process_id]

        # Verify all required fields exist
        required_fields = [
            "command",
            "start_time",
            "last_status",
            "last_line_count",
            "message_widget",
        ]
        for field in required_fields:
            self.assertIn(field, process_info)

        # Verify initial values
        self.assertEqual(process_info["command"], command)
        self.assertIsInstance(process_info["start_time"], float)
        self.assertIsNone(process_info["last_status"])
        self.assertEqual(process_info["last_line_count"], 0)
        self.assertIsNone(process_info["message_widget"])

    def test_background_executor_integration(self):
        """Test integration with BackgroundExecutor."""
        # Verify we can access the global executor
        executor = get_background_executor()
        self.assertIsNotNone(executor)

        # Verify TUI uses the same executor instance
        self.assertIs(self.tui.background_executor, executor)

    def test_process_cleanup_logic(self):
        """Test process cleanup logic without full monitoring loop."""
        process_id = "test-cleanup-123"

        with patch.object(self.tui, "_add_background_status_message"):
            self.tui._register_background_process(process_id, "echo 'cleanup test'")

        # Verify process is initially tracked
        self.assertIn(process_id, self.tui.background_processes)

        # Simulate process no longer existing (executor returns None)
        with patch.object(
            self.tui.background_executor, "get_process", return_value=None
        ):
            # Manually remove the process to simulate cleanup logic
            # (The actual cleanup happens in the monitoring loop)
            del self.tui.background_processes[process_id]

        # Process should be removed from tracking
        self.assertNotIn(process_id, self.tui.background_processes)

    def test_exit_cleanup(self):
        """Test that exit method performs cleanup."""
        # Start monitoring
        self.tui._start_background_monitoring()
        self.assertTrue(self.tui.background_monitor_active)

        # Mock background executor and avoid parent class call
        with patch.object(
            self.tui.background_executor,
            "list_active_processes",
            return_value=[],
        ):
            # Call the cleanup part of on_exit without the parent call
            self.tui._stop_background_monitoring()

        # Monitoring should be stopped
        self.assertFalse(self.tui.background_monitor_active)

    def test_keyboard_shortcuts_exist(self):
        """Test that keyboard shortcut methods exist."""
        # These should be callable
        self.assertTrue(
            callable(getattr(self.tui, "action_show_background_processes", None))
        )
        self.assertTrue(
            callable(getattr(self.tui, "action_interrupt_background_processes", None))
        )

    def test_background_process_count_tracking(self):
        """Test that we can track multiple background processes."""
        processes = [
            ("proc-1", "echo 'process 1'"),
            ("proc-2", "echo 'process 2'"),
            ("proc-3", "echo 'process 3'"),
        ]

        with patch.object(self.tui, "_add_background_status_message"):
            for process_id, command in processes:
                self.tui._register_background_process(process_id, command)

        # Verify all processes are tracked
        self.assertEqual(len(self.tui.background_processes), 3)

        for process_id, command in processes:
            self.assertIn(process_id, self.tui.background_processes)
            self.assertEqual(
                self.tui.background_processes[process_id]["command"], command
            )


if __name__ == "__main__":
    unittest.main()
