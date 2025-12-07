"""Tests for background bash execution tools.

This module tests:
- run_bash_background tool functionality
- get_background_status tool functionality
- interrupt_background_process tool functionality
- get_background_output tool functionality
- list_background_processes tool functionality
- Integration between tools and background executor
"""

import re
import time
import unittest
from unittest.mock import patch

from cdd_agent.tools import get_background_output
from cdd_agent.tools import get_background_status
from cdd_agent.tools import interrupt_background_process
from cdd_agent.tools import list_background_processes
from cdd_agent.tools import run_bash_background


class TestBackgroundTools(unittest.TestCase):
    """Test background execution tools."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear any existing background processes
        from cdd_agent.background_executor import get_background_executor

        executor = get_background_executor()
        executor.cleanup_completed_processes(max_age=-1)

    def test_run_bash_background_success(self):
        """Test successful background command execution."""
        result = run_bash_background("echo 'Hello from background'")

        # Should contain process ID
        self.assertIn("Background process started:", result)
        self.assertIn("Hello from background", result)
        self.assertIn("Status: running", result)

        # Should contain management commands
        self.assertIn("get_background_status(", result)
        self.assertIn("get_background_output(", result)
        self.assertIn("interrupt_background_process(", result)

        # Extract process ID for further testing
        match = re.search(r"Background process started: (\w+-\w+-\w+-\w+-\w+)", result)
        self.assertIsNotNone(match)

    def test_run_bash_background_with_timeout(self):
        """Test background execution with custom timeout."""
        result = run_bash_background("echo 'test'", timeout=60)

        self.assertIn("Background process started:", result)
        # Should work regardless of timeout value

    def test_run_bash_background_error_handling(self):
        """Test error handling in background execution."""
        result = run_bash_background("exit 42")  # Command that fails

        # Should still start the process successfully
        self.assertIn("Background process started:", result)

    def test_get_background_status_success(self):
        """Test getting status of a valid process."""
        # Start a background process
        start_result = run_bash_background("echo 'test'")
        match = re.search(
            r"Background process started: (\w+-\w+-\w+-\w+-\w+)", start_result
        )

        if match:
            process_id = match.group(1)

            # Wait a moment for process to potentially complete
            time.sleep(0.1)

            # Get status
            status = get_background_status(process_id)

            self.assertIn("Background Process Status:", status)
            self.assertIn(process_id, status)
            self.assertIn("Command: echo 'test'", status)
            self.assertIn("Status:", status)
            self.assertIn("Runtime:", status)

            # Status should be one of the valid statuses
            valid_statuses = [
                "running",
                "completed",
                "failed",
                "interrupted",
                "timeout",
            ]
            status_match = any(status_val in status for status_val in valid_statuses)
            self.assertTrue(
                status_match, f"Status should contain one of {valid_statuses}"
            )

    def test_get_background_status_not_found(self):
        """Test getting status of non-existent process."""
        result = get_background_status("non-existent-process-id")

        self.assertIn("Error: Process not found:", result)

    def test_get_background_output_success(self):
        """Test getting output from a running process."""
        # Start a process that generates output
        start_result = run_bash_background(
            "bash -c 'for i in {1..3}; do echo \"Line $i\"; done'"
        )
        match = re.search(
            r"Background process started: (\w+-\w+-\w+-\w+-\w+)", start_result
        )

        if match:
            process_id = match.group(1)

            # Wait for process to complete
            time.sleep(0.2)

            # Get output
            output = get_background_output(process_id)

            self.assertIn("Background Process Output:", output)
            self.assertIn(process_id, output)
            self.assertIn("Command:", output)
            self.assertIn("Status:", output)
            self.assertIn("Line 1", output)
            self.assertIn("Line 2", output)
            self.assertIn("Line 3", output)
            self.assertIn("Total output lines:", output)

    def test_get_background_output_not_found(self):
        """Test getting output from non-existent process."""
        result = get_background_output("non-existent-process-id")

        self.assertIn("Error: Process not found:", result)

    def test_get_background_output_with_lines_limit(self):
        """Test getting output with line limit."""
        # Start a process that generates many lines
        start_result = run_bash_background(
            "bash -c 'for i in {1..10}; do echo \"Line $i\"; done'"
        )
        match = re.search(
            r"Background process started: (\w+-\w+-\w+-\w+-\w+)", start_result
        )

        if match:
            process_id = match.group(1)

            # Wait for process to complete
            time.sleep(0.2)

            # Get limited output
            output = get_background_output(process_id, lines=3)

            self.assertIn("Showing last 3 of", output)
            self.assertIn("Total output lines: 10", output)
            # Should contain the last lines
            self.assertIn("Line 8", output)
            self.assertIn("Line 9", output)
            self.assertIn("Line 10", output)

            # Test with different line count
            output2 = get_background_output(process_id, lines=5)
            self.assertIn("Showing last 5 of", output2)

    def test_list_background_processes_empty(self):
        """Test listing processes when none exist."""
        # Clear all processes
        from cdd_agent.background_executor import get_background_executor

        executor = get_background_executor()
        executor.cleanup_completed_processes(max_age=-1)

        result = list_background_processes()

        self.assertEqual(result, "No background processes found")

    def test_list_background_processes_with_active(self):
        """Test listing processes with active ones."""
        # Start a couple of processes
        run_bash_background("echo 'Process 1'")
        run_bash_background("echo 'Process 2'")

        # List processes
        result = list_background_processes()

        self.assertIn("Background Processes", result)
        self.assertIn("total", result)
        self.assertIn("Summary:", result)
        self.assertIn("running", result)
        self.assertIn("completed", result)
        self.assertIn("process_id", result.lower())

    def test_interrupt_background_process_success(self):
        """Test interrupting a running process."""
        # Start a long-running process
        start_result = run_bash_background(
            "bash -c \"for i in {1..10}; do echo 'Step $i'; sleep 0.1; done\""
        )
        match = re.search(
            r"Background process started: (\w+-\w+-\w+-\w+-\w+)", start_result
        )

        if match:
            process_id = match.group(1)

            # Let it run for a bit
            time.sleep(0.2)

            # Interrupt the process
            result = interrupt_background_process(process_id)

            self.assertIn("Interrupt signal sent to process:", result)
            self.assertIn(process_id, result)

            # Wait a moment for interruption to take effect
            time.sleep(0.2)

            # Check status to confirm interruption
            status = get_background_status(process_id)
            self.assertIn("interrupted", status.lower())

    def test_interrupt_background_process_not_found(self):
        """Test interrupting non-existent process."""
        result = interrupt_background_process("non-existent-process-id")

        self.assertIn("Error: Process not found:", result)

    def test_interrupt_background_process_not_running(self):
        """Test interrupting process that's not running."""
        # Start and wait for a quick process to complete
        start_result = run_bash_background("echo 'Quick task'")
        match = re.search(
            r"Background process started: (\w+-\w+-\w+-\w+-\w+)", start_result
        )

        if match:
            process_id = match.group(1)

            # Wait for process to complete
            time.sleep(0.2)

            # Try to interrupt completed process
            result = interrupt_background_process(process_id)

            self.assertIn("is not running", result)
            self.assertIn("status:", result)

    def test_integration_complete_workflow(self):
        """Test complete workflow: start, monitor, get output, interrupt."""
        # 1. Start a long-running process (simple sleep command)
        start_result = run_bash_background(
            "bash -c 'for i in {1..3}; do echo \"Step $i\"; sleep 0.2; done'"
        )
        match = re.search(
            r"Background process started: (\w+-\w+-\w+-\w+-\w+)", start_result
        )
        self.assertIsNotNone(match)
        process_id = match.group(1)

        # 2. Check initial status
        status = get_background_status(process_id)
        self.assertIn("running", status.lower())

        # 3. Wait for some output to accumulate
        time.sleep(0.3)

        # 4. Get output (may have some content by now)
        output = get_background_output(process_id, lines=5)
        # Output might be available or not, both are valid
        self.assertTrue("Step 1" in output or "No output available" in output)

        # 4. List all processes (should include our process)
        processes = list_background_processes()
        # Should contain the truncated process ID
        self.assertIn(process_id[:12], processes)
        # Should contain our command
        self.assertIn("Step $i", processes)

        # 5. Let it run a bit more then interrupt
        time.sleep(0.1)
        interrupt_result = interrupt_background_process(process_id)
        self.assertIn("Interrupt signal sent", interrupt_result)

        # 6. Check final status
        time.sleep(0.2)
        final_status = get_background_status(process_id)
        self.assertIn("interrupted", final_status.lower())


class TestBackgroundToolsErrorHandling(unittest.TestCase):
    """Test error handling in background tools."""

    @patch("cdd_agent.tools.get_background_executor")
    def test_run_bash_background_executor_error(self, mock_get_executor):
        """Test run_bash_background when executor fails."""
        mock_get_executor.side_effect = Exception("Executor error")

        result = run_bash_background("echo 'test'")

        self.assertIn("Error starting background process:", result)
        self.assertIn("Executor error", result)

    @patch("cdd_agent.tools.get_background_executor")
    def test_get_background_status_executor_error(self, mock_get_executor):
        """Test get_background_status when executor fails."""
        mock_get_executor.side_effect = Exception("Executor error")

        result = get_background_status("test-id")

        self.assertIn("Error getting process status:", result)
        self.assertIn("Executor error", result)

    @patch("cdd_agent.tools.get_background_executor")
    def test_interrupt_background_process_executor_error(self, mock_get_executor):
        """Test interrupt_background_process when executor fails."""
        mock_get_executor.side_effect = Exception("Executor error")

        result = interrupt_background_process("test-id")

        self.assertIn("Error interrupting process:", result)
        self.assertIn("Executor error", result)


if __name__ == "__main__":
    unittest.main()
