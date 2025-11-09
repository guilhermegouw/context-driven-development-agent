"""Background process execution with real-time output streaming.

This module provides:
- BackgroundProcess: Individual process management with streaming output
- BackgroundExecutor: Centralized management of multiple background processes
- Thread-safe communication via queues for real-time output streaming
- Cross-platform process interruption and cleanup
"""

import os
import queue
import signal
import subprocess
import threading
import time
import uuid
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any

from .logging import get_logger

logger = get_logger()


class ProcessStatus(str, Enum):
    """Process status enumeration."""
    STARTING = "starting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    TIMEOUT = "timeout"


class BackgroundProcess:
    """Manages a single background process with streaming output.
    
    This class handles the lifecycle of a background process including:
    - Process startup and execution
    - Real-time output streaming via queue
    - Process interruption and cleanup
    - Status tracking and metadata management
    """
    
    def __init__(
        self,
        command: str,
        process_id: str,
        output_queue: queue.Queue,
        timeout: int = 300
    ):
        """Initialize background process.
        
        Args:
            command: Command to execute
            process_id: Unique identifier for this process
            output_queue: Queue for output communication
            timeout: Timeout in seconds (default: 300)
        """
        self.command = command
        self.process_id = process_id
        self.output_queue = output_queue
        self.timeout = timeout
        
        # Process state
        self.process: Optional[subprocess.Popen] = None
        self.status = ProcessStatus.STARTING
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.exit_code: Optional[int] = None
        self.error_message: Optional[str] = None
        
        # Threading
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Output tracking
        self.output_lines: List[str] = []
        self.max_output_lines = 10000  # Prevent memory bloat
        
        logger.info(f"BackgroundProcess initialized: {process_id} for command: {command[:100]}")
    
    def start(self) -> None:
        """Start the background process in a separate thread."""
        if self._thread is not None:
            raise ValueError(f"Process {self.process_id} already started")
        
        self.start_time = time.time()
        self.status = ProcessStatus.RUNNING
        self._stop_event.clear()
        
        self._thread = threading.Thread(
            target=self._execute_process,
            daemon=True,
            name=f"BackgroundProcess-{self.process_id[:8]}"
        )
        self._thread.start()
        
        logger.info(f"BackgroundProcess started: {self.process_id}")
    
    def interrupt(self) -> bool:
        """Interrupt the running process.
        
        Returns:
            True if interrupt signal was sent, False if process not running
        """
        if self.process is None or not self.is_running():
            logger.warning(f"Attempted to interrupt non-running process: {self.process_id}")
            return False
        
        try:
            self._stop_event.set()
            
            # Try graceful termination first
            interrupted = False
            if hasattr(os, 'killpg') and self.process.pid:  # Unix-like systems
                try:
                    # Kill the process group (more reliable than individual process)
                    os.killpg(os.getpgid(self.process.pid), signal.SIGINT)
                    interrupted = True
                except (ProcessLookupError, PermissionError, OSError) as e:
                    logger.warning(f"killpg failed for {self.process_id}: {e}")
                    # Fall back to process termination
                    self.process.terminate()
                    interrupted = True
            else:  # Windows or fallback
                self.process.terminate()
                interrupted = True
            
            # Wait a bit for graceful termination
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                # Force kill if graceful termination failed
                try:
                    self.process.kill()
                except (ProcessLookupError, PermissionError) as e:
                    logger.warning(f"kill failed for {self.process_id}: {e}")
            
            self.status = ProcessStatus.INTERRUPTED
            self.end_time = time.time()
            
            # Send interruption notification
            self.output_queue.put((
                self.process_id,
                'INTERRUPTED',
                'Process interrupted by user'
            ))
            
            logger.info(f"BackgroundProcess interrupted: {self.process_id}")
            return True
            
        except (ProcessLookupError, OSError) as e:
            logger.error(f"Failed to interrupt process {self.process_id}: {e}")
            return False
    
    def is_running(self) -> bool:
        """Check if the process is currently running.
        
        Returns:
            True if process is running, False otherwise
        """
        return self.status in (ProcessStatus.STARTING, ProcessStatus.RUNNING)
    
    def get_runtime(self) -> float:
        """Get the runtime of the process in seconds.
        
        Returns:
            Runtime in seconds, 0 if not started
        """
        if self.start_time is None:
            return 0.0
        
        end = self.end_time or time.time()
        return end - self.start_time
    
    def get_exit_code(self) -> Optional[int]:
        """Get the process exit code.
        
        Returns:
            Exit code if process completed, None otherwise
        """
        return self.exit_code
    
    def get_process_id(self) -> str:
        """Get the unique process identifier.
        
        Returns:
            Process ID string
        """
        return self.process_id
    
    def _execute_process(self) -> None:
        """Execute the process and stream output to queue.
        
        This method runs in a separate thread and handles:
        - Process startup with proper error handling
        - Real-time output streaming line by line
        - Process completion detection and status updates
        - Timeout handling and cleanup
        """
        try:
            # Create process with proper setup for output streaming
            # Create new process group for interruption on Unix systems
            preexec_fn = os.setsid if hasattr(os, 'setsid') else None
            self.process = subprocess.Popen(
                self.command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,  # Line buffered
                preexec_fn=preexec_fn
            )
            
            logger.info(f"Subprocess started with PID {self.process.pid} for {self.process_id}")
            
            # Stream output line by line
            for line in iter(self.process.stdout.readline, ''):
                if self._stop_event.is_set():
                    logger.info(f"Stop event set, breaking output loop for {self.process_id}")
                    break
                
                if line:
                    line = line.rstrip('\n\r')
                    self.output_lines.append(line)
                    
                    # Prevent memory bloat
                    if len(self.output_lines) > self.max_output_lines:
                        self.output_lines = self.output_lines[-self.max_output_lines//2:]
                    
                    # Send output to queue
                    self.output_queue.put((
                        self.process_id,
                        'OUTPUT',
                        line
                    ))
            
            # Wait for process completion
            try:
                self.exit_code = self.process.wait(timeout=self.timeout)
                
                if self._stop_event.is_set():
                    self.status = ProcessStatus.INTERRUPTED
                else:
                    self.status = ProcessStatus.COMPLETED if self.exit_code == 0 else ProcessStatus.FAILED
                
                logger.info(f"Process {self.process_id} completed with exit code {self.exit_code}")
                
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.exit_code = -1
                self.status = ProcessStatus.TIMEOUT
                self.error_message = f"Process timed out after {self.timeout} seconds"
                
                logger.warning(f"Process {self.process_id} timed out")
                
                # Send timeout notification
                self.output_queue.put((
                    self.process_id,
                    'TIMEOUT',
                    self.error_message
                ))
            
        except Exception as e:
            self.exit_code = -1
            self.status = ProcessStatus.FAILED
            self.error_message = str(e)
            
            logger.error(f"Process {self.process_id} failed with error: {e}")
            
            # Send error notification
            self.output_queue.put((
                self.process_id,
                'ERROR',
                self.error_message
            ))
        
        finally:
            self.end_time = time.time()
            
            # Send completion notification
            self.output_queue.put((
                self.process_id,
                'DONE',
                {
                    'exit_code': self.exit_code,
                    'status': self.status.value,
                    'runtime': self.get_runtime(),
                    'output_lines': len(self.output_lines)
                }
            ))
            
            logger.info(f"BackgroundProcess thread ending for {self.process_id}")


class BackgroundExecutor:
    """Manages multiple background processes with centralized coordination.
    
    This class provides:
    - Process lifecycle management (start, monitor, interrupt, cleanup)
    - Thread-safe process registry and tracking
    - Output queue management for multiple processes
    - Automatic cleanup of completed processes
    - Process discovery and status reporting
    """
    
    def __init__(self, max_processes: int = 10):
        """Initialize background executor.
        
        Args:
            max_processes: Maximum number of concurrent processes
        """
        self.max_processes = max_processes
        self.processes: Dict[str, BackgroundProcess] = {}
        self.output_queue = queue.Queue()
        self._lock = threading.RLock()
        
        # Start output monitoring thread
        self._monitor_thread = threading.Thread(
            target=self._monitor_output,
            daemon=True,
            name="BackgroundExecutor-Monitor"
        )
        self._monitor_thread.start()
        
        logger.info("BackgroundExecutor initialized")
    
    def execute_command(
        self,
        command: str,
        timeout: int = 300
    ) -> BackgroundProcess:
        """Execute a command in the background.
        
        Args:
            command: Command to execute
            timeout: Timeout in seconds
            
        Returns:
            BackgroundProcess instance
            
        Raises:
            ValueError: If maximum number of processes exceeded
        """
        with self._lock:
            # Check process limit
            active_count = sum(1 for p in self.processes.values() if p.is_running())
            if active_count >= self.max_processes:
                raise ValueError(f"Maximum number of background processes ({self.max_processes}) exceeded")
            
            # Generate unique process ID
            process_id = str(uuid.uuid4())
            
            # Create and start process
            process = BackgroundProcess(
                command=command,
                process_id=process_id,
                output_queue=self.output_queue,
                timeout=timeout
            )
            
            self.processes[process_id] = process
            process.start()
            
            logger.info(f"Started background process {process_id}: {command[:100]}")
            
            return process
    
    def interrupt_process(self, process_id: str) -> bool:
        """Interrupt a running background process.
        
        Args:
            process_id: ID of process to interrupt
            
        Returns:
            True if process was interrupted, False if not found or not running
        """
        with self._lock:
            process = self.processes.get(process_id)
            if process is None:
                logger.warning(f"Process not found for interruption: {process_id}")
                return False
            
            return process.interrupt()
    
    def get_process(self, process_id: str) -> Optional[BackgroundProcess]:
        """Get a background process by ID.
        
        Args:
            process_id: ID of process to retrieve
            
        Returns:
            BackgroundProcess instance or None if not found
        """
        with self._lock:
            return self.processes.get(process_id)
    
    def list_active_processes(self) -> List[BackgroundProcess]:
        """Get list of all active (running) processes.
        
        Returns:
            List of running BackgroundProcess instances
        """
        with self._lock:
            return [p for p in self.processes.values() if p.is_running()]
    
    def list_all_processes(self) -> List[BackgroundProcess]:
        """Get list of all processes (running and completed).
        
        Returns:
            List of all BackgroundProcess instances
        """
        with self._lock:
            return list(self.processes.values())
    
    def cleanup_completed_processes(self, max_age: float = 3600) -> int:
        """Clean up completed processes older than max_age.
        
        Args:
            max_age: Maximum age in seconds to keep completed processes
            
        Returns:
            Number of processes cleaned up
        """
        with self._lock:
            current_time = time.time()
            to_remove = []
            
            for process_id, process in self.processes.items():
                if not process.is_running():
                    age = current_time - (process.end_time or current_time)
                    if age > max_age:
                        to_remove.append(process_id)
            
            for process_id in to_remove:
                del self.processes[process_id]
                logger.debug(f"Cleaned up completed process: {process_id}")
            
            return len(to_remove)
    
    def _monitor_output(self) -> None:
        """Monitor output queue and handle process notifications.
        
        This method runs in a separate thread and processes
        output notifications from all background processes.
        """
        logger.info("Background output monitor started")
        
        while True:
            try:
                # Get output notification with timeout
                process_id, msg_type, content = self.output_queue.get(timeout=1)
                
                # Log significant events
                if msg_type in ('DONE', 'ERROR', 'TIMEOUT', 'INTERRUPTED'):
                    logger.info(f"Process {process_id}: {msg_type} - {content}")
                
                self.output_queue.task_done()
                
            except queue.Empty:
                # No output, continue monitoring
                continue
            except Exception as e:
                logger.error(f"Error in output monitor: {e}")
                continue
    
    def shutdown(self) -> None:
        """Shutdown the executor and interrupt all running processes."""
        logger.info("Shutting down BackgroundExecutor")
        
        with self._lock:
            # Interrupt all running processes
            for process in self.processes.values():
                if process.is_running():
                    process.interrupt()
            
            # Wait a bit for graceful shutdown
            time.sleep(1)
            
            # Clear process registry
            self.processes.clear()
        
        logger.info("BackgroundExecutor shutdown complete")


# Global instance for application-wide use
_global_executor: Optional[BackgroundExecutor] = None


def get_background_executor() -> BackgroundExecutor:
    """Get the global background executor instance.
    
    Returns:
        BackgroundExecutor singleton instance
    """
    global _global_executor
    
    if _global_executor is None:
        _global_executor = BackgroundExecutor()
    
    return _global_executor


def shutdown_background_executor() -> None:
    """Shutdown the global background executor."""
    global _global_executor
    
    if _global_executor is not None:
        _global_executor.shutdown()
        _global_executor = None