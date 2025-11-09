# Phase 5: Manual Testing Checklist for Background Bash Execution

**Test Date**: 2025-11-08
**Tester**: [Your Name]
**Version**: v0.0.3+
**Status**: ⏳ Pending

---

## Prerequisites

- [ ] CDD Agent installed (`pip install cdd-agent` or `poetry install`)
- [ ] Valid API key configured (`cdd-agent auth setup`)
- [ ] Test environment ready (Python 3.10+)

---

## Test Scenario 1: Long-Running Test Suite ⏱️

**Objective**: Verify background execution with live output streaming

### Steps:
1. Start CDD Agent chat mode:
   ```bash
   cdd-agent chat
   ```

2. Send message:
   ```
   Run the full test suite with pytest in the background
   ```

### Expected Behavior:
- [ ] Agent uses `run_bash_background` tool
- [ ] Process starts immediately with process ID displayed
- [ ] UI shows "🚀 Starting background process: pytest..." announcement
- [ ] Agent remains responsive while process runs
- [ ] Real-time output streams to chat (if implemented)
- [ ] Process completion notification appears when done

### Actual Results:
```
[Record observations here]
```

**Status**: ⏹ Not Run | ✅ Pass | ❌ Fail

---

## Test Scenario 2: Check Process Status 📊

**Objective**: Verify status checking of running processes

### Steps:
1. Start a long-running background process:
   ```
   Run "sleep 30" in the background
   ```

2. Check its status:
   ```
   Check the status of the background process
   ```

### Expected Behavior:
- [ ] Agent uses `get_background_status` tool
- [ ] Shows process ID, command, runtime, status (running)
- [ ] Output line count displayed
- [ ] UI shows "📊 Checking background process: {id}..." announcement

### Actual Results:
```
[Record observations here]
```

**Status**: ⏹ Not Run | ✅ Pass | ❌ Fail

---

## Test Scenario 3: Process Interruption ⏹

**Objective**: Verify graceful process termination

### Steps:
1. Start a long-running process:
   ```
   Run "sleep 60" in the background
   ```

2. Interrupt it:
   ```
   Interrupt the running background process
   ```

   **OR** use keyboard shortcut: `Ctrl+I`

### Expected Behavior:
- [ ] Agent uses `interrupt_background_process` tool
- [ ] Process terminates gracefully
- [ ] Interruption notification appears
- [ ] UI shows "⏹ Interrupting background process: {id}..." announcement
- [ ] Process status changes to "interrupted"

### Actual Results:
```
[Record observations here]
```

**Status**: ⏹ Not Run | ✅ Pass | ❌ Fail

---

## Test Scenario 4: Multiple Concurrent Processes 🔄

**Objective**: Verify multiple background processes run concurrently

### Steps:
1. Start first process:
   ```
   Run "echo 'Process 1' && sleep 10" in the background
   ```

2. Start second process:
   ```
   Run "echo 'Process 2' && sleep 10" in the background
   ```

3. List all processes:
   ```
   Show all background processes
   ```

   **OR** use keyboard shortcut: `Ctrl+B`

### Expected Behavior:
- [ ] Both processes start independently
- [ ] Each gets unique process ID
- [ ] List shows both processes with their status
- [ ] UI shows "📋 Listing all background processes"
- [ ] No blocking or interference between processes

### Actual Results:
```
[Record observations here]
```

**Status**: ⏹ Not Run | ✅ Pass | ❌ Fail

---

## Test Scenario 5: Retrieve Process Output 📄

**Objective**: Verify output retrieval from background process

### Steps:
1. Start process with output:
   ```
   Run "for i in {1..10}; do echo Line $i; sleep 1; done" in the background
   ```

2. Wait 5 seconds, then retrieve output:
   ```
   Get the output from the background process
   ```

### Expected Behavior:
- [ ] Agent uses `get_background_output` tool
- [ ] Shows recent output lines (last 50 by default)
- [ ] Output formatted clearly
- [ ] UI shows "📄 Retrieving output from {id}... (last 50 lines)"

### Actual Results:
```
[Record observations here]
```

**Status**: ⏹ Not Run | ✅ Pass | ❌ Fail

---

## Test Scenario 6: Error Handling ❌

**Objective**: Verify proper error handling and cleanup

### Steps:
1. Run a command that will fail:
   ```
   Run "python nonexistent_script.py" in the background
   ```

2. Check status after completion:
   ```
   Check the status of the background process
   ```

### Expected Behavior:
- [ ] Process starts successfully
- [ ] Process fails with clear error message
- [ ] Exit code displayed (non-zero)
- [ ] Error output captured
- [ ] UI shows failure notification
- [ ] No memory leaks or stuck processes

### Actual Results:
```
[Record observations here]
```

**Status**: ⏹ Not Run | ✅ Pass | ❌ Fail

---

## Test Scenario 7: Keyboard Shortcuts ⌨️

**Objective**: Verify TUI keyboard shortcuts work correctly

### Steps:
1. Start CDD Agent in chat mode
2. Start a background process
3. Test shortcuts:
   - Press `Ctrl+B` → Should show all background processes
   - Press `Ctrl+I` → Should interrupt running processes
   - Press `Ctrl+O` → Should show output of last process

### Expected Behavior:
- [ ] `Ctrl+B` displays process list in chat
- [ ] `Ctrl+I` interrupts all running processes with confirmation
- [ ] `Ctrl+O` shows output of most recent background process
- [ ] All shortcuts work without hanging UI
- [ ] Help text (`/help`) documents these shortcuts

### Actual Results:
```
[Record observations here]
```

**Status**: ⏹ Not Run | ✅ Pass | ❌ Fail

---

## Test Scenario 8: Process Context Across Turns 🔄

**Objective**: Verify agent maintains process context in conversation

### Steps:
1. Start a background process:
   ```
   Run "sleep 20" in the background
   ```

2. Have a normal conversation (unrelated to background process):
   ```
   What is the capital of France?
   ```

3. Ask about the background process:
   ```
   Is my background process still running?
   ```

### Expected Behavior:
- [ ] Agent remembers the background process
- [ ] Can check its status without needing process ID
- [ ] Provides accurate status information
- [ ] Context maintained across conversation turns

### Actual Results:
```
[Record observations here]
```

**Status**: ⏹ Not Run | ✅ Pass | ❌ Fail

---

## Test Scenario 9: Approval System Integration 🔒

**Objective**: Verify background tools respect approval settings

### Steps:
1. Configure approval (if applicable)
2. Request background execution:
   ```
   Run pytest in the background
   ```

3. When prompted, approve/deny

### Expected Behavior:
- [ ] Background tool triggers approval prompt (if enabled)
- [ ] Shows tool name and risk level
- [ ] Approval/denial works correctly
- [ ] Denied execution doesn't leave zombie processes

### Actual Results:
```
[Record observations here]
```

**Status**: ⏹ Not Run | ✅ Pass | ❌ Fail

---

## Test Scenario 10: Stress Test - Many Processes 💪

**Objective**: Verify system handles multiple concurrent processes

### Steps:
1. Start 5 concurrent background processes:
   ```
   Run these commands in the background:
   - sleep 30
   - echo "test1" && sleep 30
   - echo "test2" && sleep 30
   - echo "test3" && sleep 30
   - echo "test4" && sleep 30
   ```

2. List all processes:
   ```
   Show all background processes
   ```

3. Interrupt all:
   ```
   Interrupt all running background processes
   ```

### Expected Behavior:
- [ ] All 5 processes start successfully
- [ ] Each gets unique ID
- [ ] List shows all processes correctly
- [ ] Interrupt successfully terminates all
- [ ] No memory leaks
- [ ] UI remains responsive

### Actual Results:
```
[Record observations here]
```

**Status**: ⏹ Not Run | ✅ Pass | ❌ Fail

---

## Summary

### Test Results

| Test Scenario | Status | Notes |
|---------------|--------|-------|
| 1. Long-Running Test Suite | ⏹ | |
| 2. Check Process Status | ⏹ | |
| 3. Process Interruption | ⏹ | |
| 4. Multiple Concurrent Processes | ⏹ | |
| 5. Retrieve Process Output | ⏹ | |
| 6. Error Handling | ⏹ | |
| 7. Keyboard Shortcuts | ⏹ | |
| 8. Process Context Across Turns | ⏹ | |
| 9. Approval System Integration | ⏹ | |
| 10. Stress Test - Many Processes | ⏹ | |

**Overall Pass Rate**: 0/10 (0%)

### Issues Found

1. [Issue description]
2. [Issue description]
3. ...

### Recommendations

1. [Recommendation]
2. [Recommendation]
3. ...

---

## Sign-Off

- [ ] All critical tests pass
- [ ] No blockers identified
- [ ] Ready for production

**Tested By**: ________________
**Date**: ________________
**Signature**: ________________
