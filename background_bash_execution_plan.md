# Plan: Background Bash Execution

**Time Estimate**: 3-4 hours  
**Roadmap Item**: ROADMAP.md:208-212  
**Priority**: High (Phase 1 completion)

## Overview

Implement background bash execution for long-running commands with real-time output streaming and user interruption capabilities. This will significantly improve the user experience for operations like test suites, builds, and other long-running processes.

## Current State Analysis

The current `run_bash` tool in `src/cdd_agent/tools.py` (lines 289-335) uses `subprocess.run()` with a 30-second timeout and returns the complete output at once. This approach has several limitations:

- **Blocking**: Entire agent loop waits for command completion
- **No real-time feedback**: Users see no progress during execution
- **Limited timeout**: 30-second timeout is insufficient for many operations
- **No interruption**: Users cannot cancel long-running commands

## Implementation Plan (3-4 hours)

## Phase 1: Core Background Execution Framework (1.5 hours)

### 1.1 Create Background Process Manager

**File**: `src/cdd_agent/background_executor.py` (new file)

**Features**:
- Thread-based process execution with non-blocking behavior
- Real-time output streaming via queue mechanism
- Process lifecycle management (start, monitor, interrupt)
- Thread-safe communication between worker and main thread
- Cross-platform process termination support

**Key Components**:
```python
class BackgroundProcess:
    """Manages a single background process with streaming output."""
    
    def __init__(self, command: str, process_id: str, output_queue: queue.Queue)
    def start(self) -> None
    def interrupt(self) -> bool
    def is_running(self) -> bool
    def get_exit_code(self) -> Optional[int]
    def get_process_id(self) -> str

class BackgroundExecutor:
    """Manages multiple background processes."""
    
    def __init__(self)
    def execute_command(self, command: str) -> BackgroundProcess
    def interrupt_process(self, process_id: str) -> bool
    def get_process(self, process_id: str) -> Optional[BackgroundProcess]
    def list_active_processes(self) -> List[BackgroundProcess]
    def cleanup_completed_processes(self) -> None
```

### 1.2 Streaming Output System

**Implementation Details**:
- Use `subprocess.Popen` with `stdout=subprocess.PIPE` and `stderr=subprocess.STDOUT`
- Stream output line-by-line using `iter(process.stdout.readline, '')`
- Queue-based communication with message types:
  - `('OUTPUT', line)` - Normal output line
  - `('DONE', exit_code)` - Process completed
  - `('ERROR', error_msg)` - Process error
  - `('INTERRUPTED', reason)` - Process was interrupted
- Cross-platform process termination:
  - Unix: `os.killpg(os.getpgid(pid), signal.SIGINT)`
  - Windows: `process.terminate()` fallback

### 1.3 Process ID Generation

**Unique Identifier System**:
- Generate UUID-based process IDs for uniqueness
- Track process metadata (start time, command, status)
- Process registry for active and completed processes
- Automatic cleanup of old completed processes

## Phase 2: Tool Integration (1 hour)

### 2.1 New Tool: run_bash_background

**Location**: Add to `src/cdd_agent/tools.py`

**Signature**:
```python
@registry.register(risk_level=RiskLevel.HIGH)
def run_bash_background(
    command: str, 
    timeout: int = 300,
    interruptible: bool = True
) -> str
```

**Features**:
- Start command in background thread
- Return immediately with process ID and initial status
- Apply same security checks as existing `run_bash` tool
- Support for custom timeout values
- Integration with existing approval system

**Return Format**:
```
Background process started: abc123-def456
Command: pytest tests/ -v
Status: Running
Started: 2025-01-20 14:30:15
Use get_background_status() to check progress
Use interrupt_background_process() to cancel
```

### 2.2 Companion Tools

**Status and Monitoring**:
```python
@registry.register(risk_level=RiskLevel.SAFE)
def get_background_status(process_id: str) -> str
```
- Returns current status, runtime, output line count
- Shows process information and command being executed
- Indicates if process is running, completed, or failed

**Process Interruption**:
```python
@registry.register(risk_level=RiskLevel.HIGH) 
def interrupt_background_process(process_id: str) -> str
```
- Gracefully interrupt running process
- Provide confirmation and status update
- Handle cases where process already completed

**Output Retrieval**:
```python
@registry.register(risk_level=RiskLevel.SAFE)
def get_background_output(process_id: str, lines: int = 50) -> str
```
- Retrieve recent output lines from background process
- Support for tail-like functionality
- Include both stdout and stderr output

## Phase 3: TUI Integration (1 hour)

### 3.1 Background Process UI Components

**File**: `src/cdd_agent/tui.py` (modify existing)

**New UI Elements**:
- **Background Process Panel**: Dockable panel showing active processes
- **Real-time Output Widget**: Streaming output display with scrollback
- **Process Status Bar**: Quick status indicators for running processes
- **Interrupt Button**: Dedicated UI element for process cancellation

### 3.2 Integration Points

**TUI Class Enhancements**:
```python
class CDDAgentTUI(App):
    def __init__(self):
        self.background_executor = BackgroundExecutor()
        self.active_background_processes = {}
        self.background_output_widgets = {}
    
    def start_background_command(self, command: str, process_id: str)
    def handle_background_output(self, process_id: str, output: str)
    def show_background_processes(self)
    def interrupt_background_process(self, process_id: str)
    def cleanup_background_processes(self)
```

**Key Modifications**:
- Extend existing `@work(exclusive=True, thread=True)` pattern
- Add background process state tracking to TUI class
- Implement process output streaming to chat history
- Add keyboard shortcuts (Ctrl+C, Ctrl+B) for process management
- Auto-switch to process panel when background command starts

### 3.3 Real-time Output Display

**Output Streaming Features**:
- Line-by-line output updates in dedicated widget
- Color-coded output (stdout vs stderr)
- Scrollable output buffer with configurable size
- Process completion notification with summary

## Phase 4: Agent Loop Integration (0.5 hour)

### 4.1 Tool Execution Flow Enhancement

**File**: `src/cdd_agent/agent.py` (modify existing)

**Tool Detection Logic**:
```python
def _execute_tool(self, tool_name: str, args: dict) -> str:
    if tool_name in BACKGROUND_TOOLS:
        return self._handle_background_tool(tool_name, args)
    else:
        return self._handle_regular_tool(tool_name, args)

def _handle_background_tool(self, tool_name: str, args: dict) -> str:
    # Start background process
    # Return process ID and initial status
    # Register for completion monitoring
```

**Response Formatting**:
- Background-specific response templates
- Progress indicators and status updates
- Clear instructions for process management
- Integration with existing tool result formatting

### 4.2 Process Monitoring

**Completion Detection**:
- Background thread monitoring for process completion
- Automatic notification when processes finish
- Integration with agent response flow
- Error handling and cleanup on process failure

## Phase 5: Testing & Validation (0.5 hour)

### 5.1 Unit Tests

**File**: `tests/test_background_executor.py` (new file)

**Test Cases**:
```python
class TestBackgroundProcess:
    def test_process_lifecycle_start_run_complete(self)
    def test_process_interruption(self)
    def test_output_streaming(self)
    def test_error_handling(self)
    def test_timeout_handling(self)
    def test_concurrent_processes(self)

class TestBackgroundExecutor:
    def test_multiple_process_management(self)
    def test_process_registry(self)
    def test_cleanup_operations(self)
    def test_process_id_generation(self)
```

**Coverage Areas**:
- Process lifecycle (start, run, interrupt, complete)
- Output streaming accuracy and ordering
- Error handling (process failure, timeout, startup failure)
- Thread safety and concurrent execution
- Cross-platform compatibility (Unix/Windows)
- Resource cleanup and memory management

### 5.2 Integration Tests

**File**: `tests/test_background_integration.py` (new file)

**Test Scenarios**:
```python
class TestBackgroundIntegration:
    def test_agent_executes_long_running_command(self)
    def test_tui_displays_real_time_output(self)
    def test_user_interrupts_running_process(self)
    def test_multiple_concurrent_background_processes(self)
    def test_error_recovery_and_cleanup(self)
    def test_approval_system_integration(self)
```

**Integration Points**:
- Agent loop with background tool execution
- TUI real-time output display
- User interruption via keyboard shortcuts
- Multiple concurrent processes management
- Error recovery and cleanup procedures

### 5.3 Manual Testing Scenarios

**Test Commands**:
```bash
# Long-running test suite
cdd-agent chat "Run the full test suite with pytest"
# Expected: Background execution with live output streaming

# Build process
cdd-agent chat "Build the documentation with Sphinx"
# Expected: Background build with progress indicators

# Multiple processes
cdd-agent chat "Run tests and linting in parallel"
# Expected: Two concurrent background processes

# Process interruption
cdd-agent chat "Start a long build process"
# User presses Ctrl+C to interrupt
# Expected: Graceful process termination

# Error handling
cdd-agent chat "Run a command that will fail"
# Expected: Error displayed, process cleanup handled
```

## Implementation Details

### Technical Architecture

**Concurrency Model**:
- Background processes run in separate daemon threads
- Main thread manages UI and agent loop without blocking
- Queue-based communication ensures thread safety
- Event-driven updates to TUI components
- Non-blocking I/O for process output streaming

**Process Management**:
- UUID-based process identification
- Centralized process registry for tracking
- Automatic cleanup of completed processes
- Resource monitoring and memory management
- Graceful shutdown on application exit

**Error Handling**:
- Process startup failures with detailed error messages
- Runtime process errors captured and reported
- Thread termination and cleanup procedures
- Resource leak prevention and monitoring
- Fallback to synchronous execution on critical errors

### Security Considerations

**Risk Management**:
- Maintain existing HIGH risk classification for background execution
- Apply same dangerous command detection as `run_bash`
- Preserve approval system integration for all background tools
- Process isolation and sandboxing
- Command validation and sanitization

**Access Control**:
- Background processes inherit same security context as main application
- File system access controls remain consistent
- Network access restrictions maintained
- Resource limits and quotas enforced

### Performance Considerations

**Resource Usage**:
- Memory usage target: <50MB per background process
- CPU usage optimization for streaming output
- I/O buffering to reduce system call overhead
- Thread pool management for scalability

**Scalability**:
- Support for 10+ concurrent background processes
- Efficient queue management for high-volume output
- Memory-efficient output buffering with configurable limits
- Graceful degradation under resource pressure

## Success Criteria

### Functional Requirements

**Core Functionality**:
```bash
# Long-running command execution
cdd-agent chat "Run the test suite"
# Expected: Starts pytest in background, streams output live to UI

# Process interruption
cdd-agent chat "Build the project" 
# User can press Ctrl+C to interrupt build process
# Expected: Graceful termination with confirmation

# Multiple concurrent processes
cdd-agent chat "Run tests and build documentation in parallel"
# Expected: Both commands run simultaneously with independent output streams

# Process monitoring
cdd-agent chat "Check status of running processes"
# Expected: List of active processes with status indicators
```

**User Experience**:
- Non-blocking agent loop during background execution
- Real-time output streaming with <100ms latency
- Clear process status indicators and progress feedback
- Intuitive interruption controls with confirmation
- Comprehensive error reporting and recovery options

### Performance Requirements

**Response Times**:
- Background process start: <200ms
- Output streaming latency: <100ms per line
- Process interruption response: <500ms
- UI update frequency: 30-60 FPS during active streaming

**Resource Limits**:
- Memory usage: <50MB per background process
- Thread usage: 1 thread per background process
- File descriptor usage: <5 per background process
- CPU overhead: <5% of total system resources

## Risk Assessment

### Low Risk Items
- **Well-defined scope**: Clear requirements with existing patterns
- **Proven technologies**: Uses established threading and subprocess patterns
- **Non-breaking changes**: Maintains backward compatibility
- **Incremental implementation**: Can be delivered in phases

### Medium Risk Items
- **Cross-platform complexity**: Process management differences between Unix/Windows
- **Thread synchronization**: Potential race conditions in concurrent execution
- **TUI state management**: Complex UI updates during concurrent operations
- **Resource management**: Memory and file descriptor leak potential

### Mitigation Strategies

**Technical Risks**:
- Extensive unit testing with mocked processes
- Platform-specific testing on Unix and Windows
- Thread safety analysis and validation
- Resource monitoring and cleanup procedures

**Integration Risks**:
- Gradual rollout with feature flags
- Comprehensive integration testing
- Fallback mechanisms for error conditions
- Detailed logging and debugging support

**Performance Risks**:
- Performance testing with multiple concurrent processes
- Memory profiling and optimization
- Load testing under various conditions
- Resource usage monitoring and alerting

## Deliverables

### Code Deliverables
1. **BackgroundExecutor module** (`src/cdd_agent/background_executor.py`)
2. **Enhanced tools module** with background tools (`src/cdd_agent/tools.py`)
3. **Updated TUI** with background process UI (`src/cdd_agent/tui.py`)
4. **Enhanced agent loop** with background tool support (`src/cdd_agent/agent.py`)

### Test Deliverables
1. **Unit test suite** (`tests/test_background_executor.py`)
2. **Integration test suite** (`tests/test_background_integration.py`)
3. **Manual test procedures** and validation scripts
4. **Performance benchmarks** and resource usage profiles

### Documentation Deliverables
1. **API documentation** for new tools and classes
2. **User guide** for background process features
3. **Developer documentation** for architecture and design
4. **Troubleshooting guide** for common issues

## Next Steps

### Immediate Actions (Week 1)
1. **Implement BackgroundExecutor class** - Core process management functionality
2. **Create streaming output system** - Queue-based communication mechanism
3. **Add basic background tools** - Initial tool registry integration
4. **Write unit tests** - Test-driven development approach

### Intermediate Actions (Week 1-2)
1. **Integrate with TUI** - Real-time UI updates and process management
2. **Enhance agent loop** - Background tool detection and handling
3. **Add companion tools** - Status, output, and interruption tools
4. **Integration testing** - End-to-end workflow validation

### Final Actions (Week 2)
1. **Performance optimization** - Resource usage and response time tuning
2. **Error handling完善** - Comprehensive error scenarios and recovery
3. **Documentation** - User and developer documentation
4. **User acceptance testing** - Real-world usage validation

## Success Metrics

### Development Metrics
- **Code coverage**: >90% for background execution components
- **Test pass rate**: 100% for all automated tests
- **Performance benchmarks**: All response time targets met
- **Resource usage**: Within specified memory and CPU limits

### User Experience Metrics
- **Non-blocking execution**: Agent remains responsive during background operations
- **Real-time feedback**: Users see progress within 100ms of process output
- **Interruption responsiveness**: Process cancellation within 500ms
- **Error recovery**: Graceful handling and clear error messages

### Integration Metrics
- **Backward compatibility**: Existing functionality unchanged
- **Approval system integration**: All background tools respect approval settings
- **Cross-platform compatibility**: Works consistently on Unix and Windows
- **Concurrent execution**: Support for 10+ simultaneous background processes

---

**Status**: Planning Complete  
**Next Action**: Begin Phase 1 implementation with BackgroundExecutor class  
**Target Completion**: End of Week 1 (3-4 hours total development time)