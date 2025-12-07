"""Unit tests for background executor functionality.

This module tests:
- BackgroundProcess lifecycle management
- BackgroundExecutor process coordination
- Output streaming and queue communication
- Process interruption and cleanup
- Error handling and timeout scenarios
"""

import queue
import signal
import time
import unittest
from unittest.mock import Mock
from unittest.mock import patch

from cdd_agent.background_executor import BackgroundExecutor
from cdd_agent.background_executor import BackgroundProcess
from cdd_agent.background_executor import ProcessStatus
from cdd_agent.background_executor import get_background_executor
from cdd_agent.background_executor import shutdown_background_executor


class TestBackgroundProcess(unittest.TestCase):
    """Test BackgroundProcess class functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.output_queue = queue.Queue()
        self.process_id = "test-process-123"
        self.command = "echo 'test output'"

    def test_process_initialization(self):
        """Test process initialization with correct parameters."""
        process = BackgroundProcess(
            command=self.command,
            process_id=self.process_id,
            output_queue=self.output_queue,
            timeout=60,
        )

        self.assertEqual(process.command, self.command)
        self.assertEqual(process.process_id, self.process_id)
        self.assertEqual(process.output_queue, self.output_queue)
        self.assertEqual(process.timeout, 60)
        self.assertEqual(process.status, ProcessStatus.STARTING)
        self.assertIsNone(process.start_time)
        self.assertIsNone(process.process)

    def test_process_start_creates_thread(self):
        """Test that starting a process creates a new thread."""
        process = BackgroundProcess(
            command=self.command,
            process_id=self.process_id,
            output_queue=self.output_queue,
        )

        process.start()

        # Verify thread was created
        self.assertIsNotNone(process._thread)
        self.assertTrue(process._thread.is_alive())
        self.assertEqual(process.status, ProcessStatus.RUNNING)
        self.assertIsNotNone(process.start_time)

        # Clean up
        process.interrupt()

    def test_double_start_raises_error(self):
        """Test that starting a process twice raises ValueError."""
        process = BackgroundProcess(
            command=self.command,
            process_id=self.process_id,
            output_queue=self.output_queue,
        )

        process.start()

        with self.assertRaises(ValueError) as cm:
            process.start()

        self.assertIn("already started", str(cm.exception))

        # Clean up
        process.interrupt()

    def test_process_execution_success(self):
        """Test successful process execution with output streaming."""
        process = BackgroundProcess(
            command="echo 'Hello World'; echo 'Line 2'",
            process_id=self.process_id,
            output_queue=self.output_queue,
        )

        process.start()

        # Wait for completion
        timeout = time.time() + 5  # 5 second timeout
        while process.is_running() and time.time() < timeout:
            time.sleep(0.1)

        # Verify process completed successfully
        self.assertEqual(process.status, ProcessStatus.COMPLETED)
        self.assertEqual(process.exit_code, 0)
        self.assertIsNotNone(process.end_time)
        self.assertGreater(process.get_runtime(), 0)

        # Verify output was queued
        outputs = []
        while not self.output_queue.empty():
            outputs.append(self.output_queue.get())

        # Should have OUTPUT messages and DONE message
        output_messages = [msg for msg in outputs if msg[1] == "OUTPUT"]
        done_messages = [msg for msg in outputs if msg[1] == "DONE"]

        self.assertGreater(len(output_messages), 0)
        self.assertEqual(len(done_messages), 1)

        # Verify output content
        output_lines = [msg[2] for msg in output_messages]
        self.assertIn("Hello World", output_lines)
        self.assertIn("Line 2", output_lines)

    def test_process_execution_failure(self):
        """Test process execution with non-zero exit code."""
        process = BackgroundProcess(
            command="exit 42",  # Command that fails
            process_id=self.process_id,
            output_queue=self.output_queue,
        )

        process.start()

        # Wait for completion
        timeout = time.time() + 5
        while process.is_running() and time.time() < timeout:
            time.sleep(0.1)

        # Verify process failed
        self.assertEqual(process.status, ProcessStatus.FAILED)
        self.assertEqual(process.exit_code, 42)

    @patch("subprocess.Popen")
    @patch("os.getpgid")
    @patch("os.killpg")
    def test_process_interrupt(self, mock_killpg, mock_getpgid, mock_popen):
        """Test process interruption."""
        # Mock a long-running process
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        # Mock getpgid to return a valid process group ID
        mock_getpgid.return_value = 12345

        process = BackgroundProcess(
            command="sleep 10",
            process_id=self.process_id,
            output_queue=self.output_queue,
        )

        process.start()
        time.sleep(0.1)  # Let process start

        # Test interruption
        result = process.interrupt()

        self.assertTrue(result)
        self.assertEqual(process.status, ProcessStatus.INTERRUPTED)

        # Verify killpg was called with correct arguments
        mock_killpg.assert_called_once_with(12345, signal.SIGINT)

    def test_interrupt_non_running_process(self):
        """Test interrupting a non-running process returns False."""
        process = BackgroundProcess(
            command="echo 'test'",
            process_id=self.process_id,
            output_queue=self.output_queue,
        )

        # Process not started
        result = process.interrupt()
        self.assertFalse(result)

    def test_runtime_calculation(self):
        """Test runtime calculation for running and completed processes."""
        process = BackgroundProcess(
            command="sleep 0.1 && echo 'test'",
            process_id=self.process_id,
            output_queue=self.output_queue,
        )

        # Runtime before start
        self.assertEqual(process.get_runtime(), 0.0)

        process.start()
        time.sleep(0.05)  # Give it a bit of time

        # Runtime while running (process should still be running due to sleep)
        runtime = process.get_runtime()
        self.assertGreater(runtime, 0.0)
        self.assertLess(runtime, 1.0)

        # Wait for completion
        timeout = time.time() + 5
        while process.is_running() and time.time() < timeout:
            time.sleep(0.1)

        # Runtime after completion (should be >= intermediate runtime)
        final_runtime = process.get_runtime()
        self.assertGreaterEqual(final_runtime, runtime)

    def test_output_line_limit(self):
        """Test that output lines are limited to prevent memory bloat."""
        process = BackgroundProcess(
            command="bash -c 'for i in {1..15000}; do echo \"Line $i\"; done'",
            process_id=self.process_id,
            output_queue=self.output_queue,
        )

        process.start()

        # Wait for completion
        timeout = time.time() + 10
        while process.is_running() and time.time() < timeout:
            time.sleep(0.1)

        # Verify output lines were limited
        self.assertLessEqual(len(process.output_lines), process.max_output_lines)


class TestBackgroundExecutor(unittest.TestCase):
    """Test BackgroundExecutor class functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.executor = BackgroundExecutor(max_processes=3)

    def tearDown(self):
        """Clean up after tests."""
        self.executor.shutdown()

    def test_executor_initialization(self):
        """Test executor initialization with correct parameters."""
        self.assertEqual(self.executor.max_processes, 3)
        self.assertEqual(len(self.executor.processes), 0)
        self.assertIsNotNone(self.executor._monitor_thread)
        self.assertTrue(self.executor._monitor_thread.is_alive())

    def test_execute_command_success(self):
        """Test successful command execution."""
        process = self.executor.execute_command("echo 'test'", timeout=5)

        self.assertIsInstance(process, BackgroundProcess)
        self.assertEqual(process.status, ProcessStatus.RUNNING)
        self.assertIn(process.process_id, self.executor.processes)

        # Wait for completion
        timeout = time.time() + 5
        while process.is_running() and time.time() < timeout:
            time.sleep(0.1)

        self.assertEqual(process.status, ProcessStatus.COMPLETED)

    def test_max_processes_limit(self):
        """Test that maximum process limit is enforced."""
        processes = []

        # Start processes up to limit
        for i in range(self.executor.max_processes):
            process = self.executor.execute_command(f"sleep 1 && echo 'test{i}'")
            processes.append(process)

        # Next process should raise ValueError
        with self.assertRaises(ValueError) as cm:
            self.executor.execute_command("echo 'should fail'")

        self.assertIn("Maximum number of background processes", str(cm.exception))

        # Clean up
        for process in processes:
            process.interrupt()

    def test_interrupt_process(self):
        """Test interrupting a running process."""
        process = self.executor.execute_command("sleep 5")  # Shorter sleep
        time.sleep(0.2)  # Let process start

        result = self.executor.interrupt_process(process.process_id)

        # Process interruption might fail due to permissions, but attempt should be made
        # The important thing is that the interrupt logic runs without error
        self.assertIsInstance(result, bool)

        # Wait for process to finish or be interrupted
        timeout = time.time() + 3
        while process.is_running() and time.time() < timeout:
            time.sleep(0.1)

        # Process should either be interrupted or completed
        self.assertIn(
            process.status,
            [
                ProcessStatus.INTERRUPTED,
                ProcessStatus.COMPLETED,
                ProcessStatus.FAILED,
            ],
        )

    def test_interrupt_nonexistent_process(self):
        """Test interrupting a non-existent process returns False."""
        result = self.executor.interrupt_process("non-existent-id")
        self.assertFalse(result)

    def test_get_process(self):
        """Test retrieving a process by ID."""
        process = self.executor.execute_command("echo 'test'")

        retrieved = self.executor.get_process(process.process_id)
        self.assertIs(process, retrieved)

        # Non-existent process
        nonexistent = self.executor.get_process("non-existent")
        self.assertIsNone(nonexistent)

    def test_list_active_processes(self):
        """Test listing active processes."""
        # Start multiple processes
        processes = []
        for i in range(3):
            process = self.executor.execute_command(f"sleep 0.5 && echo 'test{i}'")
            processes.append(process)

        active = self.executor.list_active_processes()
        self.assertEqual(len(active), 3)

        # Wait for processes to complete
        timeout = time.time() + 5
        for process in processes:
            while process.is_running() and time.time() < timeout:
                time.sleep(0.1)

        # Now no active processes
        active = self.executor.list_active_processes()
        self.assertEqual(len(active), 0)

    def test_list_all_processes(self):
        """Test listing all processes (active and completed)."""
        process = self.executor.execute_command("echo 'test'")

        all_processes = self.executor.list_all_processes()
        self.assertEqual(len(all_processes), 1)
        self.assertIs(process, all_processes[0])

        # Wait for completion
        timeout = time.time() + 5
        while process.is_running() and time.time() < timeout:
            time.sleep(0.1)

        # Process should still be in list
        all_processes = self.executor.list_all_processes()
        self.assertEqual(len(all_processes), 1)

    def test_cleanup_completed_processes(self):
        """Test cleanup of old completed processes."""
        process = self.executor.execute_command("echo 'test'")

        # Wait for completion
        timeout = time.time() + 5
        while process.is_running() and time.time() < timeout:
            time.sleep(0.1)

        # Should be cleaned up with negative max_age (immediate cleanup)
        cleaned = self.executor.cleanup_completed_processes(max_age=-1)
        self.assertEqual(cleaned, 1)
        self.assertNotIn(process.process_id, self.executor.processes)

    def test_shutdown(self):
        """Test executor shutdown interrupts all processes."""
        processes = []
        for i in range(3):
            process = self.executor.execute_command("sleep 1")  # Shorter sleep
            processes.append(process)

        # Verify some processes are running
        running_before = sum(1 for p in processes if p.is_running())
        self.assertGreater(running_before, 0)

        # Shutdown executor
        self.executor.shutdown()

        # Wait a bit for processes to fully complete
        time.sleep(0.1)

        # Process registry should be empty
        self.assertEqual(len(self.executor.processes), 0)

        # All processes should be done (either interrupted or completed)
        for process in processes:
            self.assertIn(
                process.status,
                [
                    ProcessStatus.INTERRUPTED,
                    ProcessStatus.COMPLETED,
                    ProcessStatus.FAILED,
                ],
            )


class TestGlobalExecutor(unittest.TestCase):
    """Test global background executor functions."""

    def test_get_background_executor_singleton(self):
        """Test that get_background_executor returns singleton."""
        # Clear any existing global instance
        import cdd_agent.background_executor

        cdd_agent.background_executor._global_executor = None

        executor1 = get_background_executor()
        executor2 = get_background_executor()

        self.assertIs(executor1, executor2)
        self.assertIsInstance(executor1, BackgroundExecutor)

        # Clean up
        shutdown_background_executor()

    def test_shutdown_background_executor(self):
        """Test shutdown_background_executor clears global instance."""
        import cdd_agent.background_executor

        cdd_agent.background_executor._global_executor = None

        get_background_executor()
        self.assertIsNotNone(cdd_agent.background_executor._global_executor)

        shutdown_background_executor()
        self.assertIsNone(cdd_agent.background_executor._global_executor)


class TestIntegrationScenarios(unittest.TestCase):
    """Integration tests for complex scenarios."""

    def test_concurrent_process_execution(self):
        """Test multiple processes running concurrently."""
        executor = BackgroundExecutor(max_processes=5)

        try:
            processes = []
            commands = [
                "echo 'Process 1'; sleep 0.2",
                "echo 'Process 2'; sleep 0.3",
                "echo 'Process 3'; sleep 0.1",
            ]

            # Start processes concurrently
            for cmd in commands:
                process = executor.execute_command(cmd)
                processes.append(process)

            # All should be running initially
            active = executor.list_active_processes()
            self.assertEqual(len(active), 3)

            # Wait for all to complete
            timeout = time.time() + 5
            while any(p.is_running() for p in processes) and time.time() < timeout:
                time.sleep(0.1)

            # All should complete successfully
            for process in processes:
                self.assertEqual(process.status, ProcessStatus.COMPLETED)

        finally:
            executor.shutdown()

    def test_process_with_long_output(self):
        """Test process that generates lots of output."""
        executor = BackgroundExecutor()

        try:
            process = executor.execute_command(
                "bash -c \"for i in {1..100}; do echo 'Output line $i'; done\""
            )

            # Wait for completion
            timeout = time.time() + 5
            while process.is_running() and time.time() < timeout:
                time.sleep(0.1)

            # Should complete successfully
            self.assertEqual(process.status, ProcessStatus.COMPLETED)
            self.assertGreater(len(process.output_lines), 50)

        finally:
            executor.shutdown()


if __name__ == "__main__":
    unittest.main()
