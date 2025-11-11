# Testing Plan: Post-v0.0.3 Improvements

**Version:** Testing improvements from v0.0.3 → Current (pre-v0.0.4)
**Date:** 2025-11-09
**Scope:** Comprehensive testing of all new features and improvements

---

## Summary of Changes Since v0.0.3

### Phase 1: Advanced Tools & Background Execution
- ✅ Background bash execution
- ✅ Advanced tool approvals system
- ✅ Context management
- ✅ Comprehensive logging
- ✅ Lazy loading optimizations

### Phase 2: CDD Agents System (Weeks 5-7)
- ✅ **Week 5:** Socrates Agent - Requirements refinement
- ✅ **Week 6:** Planner Agent - Implementation planning
- ✅ **Week 7:** Executor Agent - Autonomous code execution

---

## Test Areas

## 1. Core Infrastructure Tests ✅

### 1.1 Background Execution System
**Files:** `src/cdd_agent/background_executor.py`, `src/cdd_agent/tools.py`

**What to test:**
```bash
# Start the agent
poetry run cdd-agent chat

# Test background bash execution
> Can you run "sleep 5 && echo 'Background test complete'" in the background?

# Expected: Command runs in background, you can continue chatting
# Expected: Notification when command completes

# Check background processes
Press Ctrl+B (or check keyboard shortcuts)

# Expected: See list of background processes
```

**Success criteria:**
- ✅ Command runs in background without blocking
- ✅ Can send new messages while command runs
- ✅ Notification appears when command completes
- ✅ Can view background process list
- ✅ Can interrupt background processes

### 1.2 Approval System
**Files:** `src/cdd_agent/approval.py`, `src/cdd_agent/tui.py`

**What to test:**
```bash
poetry run cdd-agent chat

# Test file read approval
> Can you read /etc/passwd?

# Expected: Approval prompt appears
# Options: Approve, Deny, Approve All (session), Approve All (always)

# Test dangerous command approval
> Can you delete all files in /tmp?

# Expected: Approval prompt with warning
```

**Success criteria:**
- ✅ Approval prompts appear for sensitive operations
- ✅ "Approve All" works for session
- ✅ "Always approve" persists across sessions
- ✅ Dangerous operations show warnings
- ✅ Can deny operations

### 1.3 Context Management
**Files:** `src/cdd_agent/context.py`

**What to test:**
```bash
poetry run cdd-agent chat

# Test context insertion
> Add this to context: "Project uses Python 3.10+ and Poetry"

# Later in conversation:
> What Python version should I use?

# Expected: Agent remembers the context
```

**Success criteria:**
- ✅ Can add context during conversation
- ✅ Context persists throughout session
- ✅ Agent uses context in responses

### 1.4 Logging System
**Files:** `src/cdd_agent/logging.py`

**What to test:**
```bash
# Check log file exists
ls ~/.cdd-agent/logs/

# Run with verbose logging
poetry run cdd-agent chat --verbose

# Check logs contain detailed information
tail -f ~/.cdd-agent/logs/cdd-agent-*.log
```

**Success criteria:**
- ✅ Log files created in ~/.cdd-agent/logs/
- ✅ Logs contain timestamped entries
- ✅ Different log levels work (INFO, DEBUG, ERROR)
- ✅ Tool executions are logged

---

## 2. CDD Agents Workflow (Week 5-7) 🆕

### 2.1 Socrates Agent - Requirements Refinement
**Files:** `src/cdd_agent/agents/socrates.py`, `src/cdd_agent/slash_commands/socrates_command.py`

**Full workflow test:**
```bash
poetry run cdd-agent chat

# 1. Initialize CDD project
> /init

# Expected: Creates specs/ directory structure

# 2. Create a new ticket
> /new ticket feature test-authentication

# Expected: Creates specs/tickets/feature-test-authentication/spec.yaml

# 3. Activate Socrates to refine requirements
> /socrates feature-test-authentication

# Expected: Socrates greets, analyzes spec
# Expected: Asks clarifying questions

# 4. Answer Socrates' questions
> We need JWT-based authentication with refresh tokens

# Expected: Socrates asks follow-up questions
# Expected: Gradually refines the specification

# 5. Continue until Socrates marks complete
> [Keep answering questions]

# Expected: Socrates eventually says spec is complete and exits
# Expected: spec.yaml updated with detailed requirements

# 6. Verify the refined spec
> Can you show me the contents of specs/tickets/feature-test-authentication/spec.yaml?

# Expected: Well-structured YAML with:
# - Clear description
# - Detailed acceptance criteria
# - Technical notes
```

**Success criteria:**
- ✅ /socrates command activates Socrates agent
- ✅ Socrates detects vague areas in spec
- ✅ Asks relevant, specific questions
- ✅ Updates spec.yaml incrementally
- ✅ Marks self complete when spec is detailed enough
- ✅ Exits back to normal chat mode

**Test edge cases:**
```bash
# Test with already-complete spec
> /socrates feature-test-authentication

# Expected: Socrates recognizes spec is complete, auto-exits

# Test with non-existent ticket
> /socrates nonexistent-ticket

# Expected: Error message, ticket not found

# Test exiting early
> /socrates feature-test-authentication
> exit

# Expected: Exits Socrates mode, returns to chat
```

### 2.2 Planner Agent - Implementation Planning
**Files:** `src/cdd_agent/agents/planner.py`, `src/cdd_agent/slash_commands/plan_command.py`

**Full workflow test:**
```bash
poetry run cdd-agent chat

# Prerequisites: Complete Socrates flow first (spec must be refined)

# 1. Activate Planner
> /plan feature-test-authentication

# Expected: Planner greets, analyzes spec
# Expected: Generates implementation plan

# 2. Review the generated plan
# Expected: Plan shown with:
# - Overview section
# - Numbered steps (1, 2, 3...)
# - Complexity ratings (simple/medium/complex)
# - Time estimates
# - Dependencies between steps
# - Files affected per step

# 3. Plan saved automatically
> Can you show me specs/tickets/feature-test-authentication/plan.md?

# Expected: Markdown file with structured plan

# 4. Planner auto-exits
# Expected: Returns to normal chat mode
```

**Success criteria:**
- ✅ /plan command activates Planner agent
- ✅ Requires complete spec (rejects incomplete specs)
- ✅ Generates logical, step-by-step plan
- ✅ Includes complexity and time estimates
- ✅ Shows dependencies between steps
- ✅ Saves plan to plan.md
- ✅ Auto-exits when done

**Test edge cases:**
```bash
# Test with incomplete spec
> /plan feature-incomplete

# Expected: Error, spec not complete enough

# Test regenerating existing plan
> /plan feature-test-authentication

# Expected: Detects existing plan, asks to regenerate or keep

# Test with non-existent ticket
> /plan nonexistent-ticket

# Expected: Error, ticket not found
```

### 2.3 Executor Agent - Autonomous Code Execution 🚀
**Files:** `src/cdd_agent/agents/executor.py`, `src/cdd_agent/slash_commands/exec_command.py`

**Full workflow test:**
```bash
poetry run cdd-agent chat

# Prerequisites: Complete Socrates + Planner flows (need refined spec + plan)

# 1. Activate Executor
> /exec feature-test-authentication

# Expected: Executor greets, shows plan summary
# Expected: Shows available commands:
#   - continue/Enter: Execute next step
#   - status: Show progress
#   - skip: Skip current step
#   - retry: Retry failed step
#   - exit: Stop execution

# 2. Execute first step
> continue
# or just press Enter

# Expected:
# - Shows "Executing Step 1: [title]"
# - Generates code via LLM
# - Shows files created/modified
# - Shows progress (1/N steps, X%)
# - Saves execution state to execution-state.json

# 3. Check status
> status

# Expected: Shows:
# - Ticket name
# - Progress (X/N steps completed)
# - Current step number
# - Failed steps (if any)

# 4. Continue through all steps
> continue
> continue
> ...

# Expected:
# - Each step executed sequentially
# - Code generated for each step
# - Files written to filesystem
# - Progress updates after each step

# 5. Completion
# Expected: When all steps done:
# - Executor marks self complete
# - Auto-exits back to chat mode
# - Execution state saved

# 6. Test resume capability
> /exec feature-test-authentication

# Expected:
# - Detects existing execution-state.json
# - Shows "Resuming execution..."
# - Shows current progress
# - Can continue from where left off

# 7. Verify generated code
> Can you show me the files created?

# Expected: See actual code files in project
```

**Success criteria:**
- ✅ /exec command activates Executor agent
- ✅ Requires existing plan (rejects if no plan.md)
- ✅ Executes steps in order
- ✅ Generates code via LLM
- ✅ Parses code blocks correctly (```lang:path/to/file format)
- ✅ Writes files to filesystem
- ✅ Shows progress percentage
- ✅ Saves execution state after each step
- ✅ Can resume interrupted execution
- ✅ Auto-exits when complete

**Test commands:**
```bash
# Test skip command
> skip

# Expected: Skips current step, moves to next

# Test status command
> status

# Expected: Shows execution status

# Test interrupting and resuming
# 1. Start execution
> /exec feature-test-authentication
> continue

# 2. Exit mid-execution
> exit

# 3. Resume later
> /exec feature-test-authentication

# Expected: Resumes from saved state

# Test with failed step
# (Simulate by having LLM generate invalid code)
> continue

# If step fails:
# Expected: Shows error message
# Expected: Offers retry option

> retry

# Expected: Retries the failed step
```

**Test edge cases:**
```bash
# Test without plan
> /exec feature-no-plan

# Expected: Error, no plan found, suggests running /plan first

# Test with non-existent ticket
> /exec nonexistent-ticket

# Expected: Error, ticket not found
```

---

## 3. End-to-End CDD Workflow Test 🎯

**Complete workflow from scratch:**

```bash
poetry run cdd-agent chat

# Step 1: Initialize project
> /init

# Step 2: Create ticket
> /new ticket feature user-authentication

# Step 3: Refine requirements with Socrates
> /socrates feature-user-authentication
> We need JWT authentication for a FastAPI backend
> [Answer all questions until Socrates completes]

# Step 4: Generate plan with Planner
> /plan feature-user-authentication
# [Review generated plan]

# Step 5: Execute with Executor
> /exec feature-user-authentication
> continue
> continue
> ...
# [Continue until all steps complete]

# Step 6: Verify results
> Can you list all files that were created?
> Can you show me the test file?
> Can you run the tests?
```

**Success criteria:**
- ✅ Complete workflow runs without errors
- ✅ Each agent transitions smoothly
- ✅ Final code is functional
- ✅ All files created as planned
- ✅ Tests pass (if test step included in plan)

---

## 4. Regression Tests ✅

### 4.1 Existing Features Still Work
```bash
# Test basic chat
> What is Python?

# Test file operations
> Can you create a file called test.txt with "hello" in it?

# Test code execution
> Can you run "python --version"?

# Test help command
> /help

# Test version command
poetry run cdd-agent --version
```

**Success criteria:**
- ✅ All v0.0.3 features still work
- ✅ No regressions in core functionality

---

## 5. Performance & Quality Tests 🚦

### 5.1 Startup Performance
```bash
# Test startup time
time poetry run cdd-agent --help

# Expected: Should complete in <2 seconds
# Target: <200ms (aspirational)
```

### 5.2 Memory Usage
```bash
# Monitor memory during long conversation
poetry run cdd-agent chat
# Have a long conversation (20+ messages)
# Monitor memory with: ps aux | grep cdd-agent
```

### 5.3 Test Suite
```bash
# Run all tests
poetry run pytest

# Expected: Most tests passing
# Known issues:
# - 2 lazy loading tests (pre-existing)
# - 2-3 performance tests (pre-existing)
# - All other tests should pass

# Run specific test suites
poetry run pytest tests/test_approval.py -v
poetry run pytest tests/test_background_executor.py -v
poetry run pytest tests/test_tui_background_integration.py -v

# Run Week 5-7 agent tests
poetry run python test_socrates_agent.py
poetry run python test_planner_agent.py
poetry run python test_executor_agent.py
```

**Success criteria:**
- ✅ test_socrates_agent.py: 15/15 passing
- ✅ test_planner_agent.py: 14/14 passing
- ✅ test_executor_agent.py: 15/15 passing
- ✅ TUI background tests: 16/16 passing
- ✅ Approval tests: All passing
- ✅ Background executor tests: All passing

---

## 6. User Experience Tests 🎨

### 6.1 TUI Improvements
```bash
poetry run cdd-agent chat

# Test markdown rendering
> **Bold text** and *italic text* and `code`

# Test code blocks
> ```python
> def hello():
>     return "world"
> ```

# Test streaming
# Expected: Responses stream token-by-token (smooth, ChatGPT-like)

# Test keyboard shortcuts
# Press ? or F1 for help
# Expected: Shows keyboard shortcuts overlay

# Test background process indicator
> Run "sleep 10 && echo done" in background
# Expected: See background process indicator in UI
```

**Success criteria:**
- ✅ Markdown renders correctly
- ✅ Code blocks have syntax highlighting
- ✅ Streaming is smooth (no lag/stuttering)
- ✅ Keyboard shortcuts work
- ✅ Background indicators visible

---

## 7. Error Handling Tests 🛡️

### 7.1 Graceful Failures
```bash
# Test with invalid API key
export ANTHROPIC_API_KEY=invalid
poetry run cdd-agent chat
# Expected: Clear error message

# Test network failure
# (Disconnect network, then try to send message)
> Hello
# Expected: Clear error message, doesn't crash

# Test with corrupted spec file
# Manually edit specs/tickets/.../spec.yaml to be invalid YAML
> /socrates feature-broken
# Expected: Clear error message, doesn't crash

# Test interrupt during execution
> /exec feature-test-authentication
> continue
# Press Ctrl+C during step execution
# Expected: Graceful shutdown, state saved
```

**Success criteria:**
- ✅ All errors show clear messages
- ✅ No crashes or stack traces shown to user
- ✅ State saved even on interruption
- ✅ Can recover from errors

---

## Quick Test Checklist

For rapid testing, run through this checklist:

**5-Minute Smoke Test:**
- [ ] `poetry run cdd-agent --version` works
- [ ] `poetry run cdd-agent chat` starts
- [ ] Basic chat works (send a message)
- [ ] `/help` shows help
- [ ] Background command works (`Run "echo test" in background`)
- [ ] Approval prompt appears (read /etc/passwd)

**15-Minute Core Test:**
- [ ] Initialize project (`/init`)
- [ ] Create ticket (`/new ticket feature test`)
- [ ] Activate Socrates (`/socrates feature-test`)
- [ ] Answer 2-3 questions
- [ ] Exit Socrates (`exit`)
- [ ] Run `/plan feature-test`
- [ ] Review generated plan

**30-Minute Full Workflow:**
- [ ] Complete 5 & 15 minute tests
- [ ] Run `/exec feature-test`
- [ ] Execute 2-3 steps with Executor
- [ ] Check `status`
- [ ] Exit and resume execution
- [ ] Verify files created
- [ ] Run automated tests (`poetry run pytest`)

---

## Test Result Template

```markdown
## Test Results: [Date]

**Tester:** [Your Name]
**Version:** [Current version]
**Environment:** [OS, Python version]

### Infrastructure Tests
- [ ] Background execution: PASS/FAIL
- [ ] Approval system: PASS/FAIL
- [ ] Context management: PASS/FAIL
- [ ] Logging: PASS/FAIL

### CDD Agents
- [ ] Socrates Agent: PASS/FAIL
- [ ] Planner Agent: PASS/FAIL
- [ ] Executor Agent: PASS/FAIL
- [ ] Full workflow: PASS/FAIL

### Regression Tests
- [ ] Basic chat: PASS/FAIL
- [ ] File operations: PASS/FAIL
- [ ] Code execution: PASS/FAIL

### Performance
- [ ] Startup time: [X]ms
- [ ] Memory usage: [X]MB

### Issues Found
1. [Description]
2. [Description]

### Notes
[Any additional observations]
```

---

## Priority Testing Order

1. **Critical Path (Test First):**
   - Week 5-7 agents workflow (Socrates → Planner → Executor)
   - Background execution system
   - Approval system

2. **High Priority:**
   - TUI improvements
   - Error handling
   - State persistence (resume capability)

3. **Medium Priority:**
   - Performance metrics
   - Logging system
   - Context management

4. **Low Priority:**
   - Edge cases
   - Stress testing
   - Memory profiling

---

## Automated Test Commands

```bash
# Run all unit tests
poetry run pytest -v

# Run specific test files
poetry run pytest tests/test_approval.py -v
poetry run pytest tests/test_background_executor.py -v
poetry run pytest tests/test_tui_background_integration.py -v

# Run agent tests
python test_socrates_agent.py
python test_planner_agent.py
python test_executor_agent.py

# Run with coverage
poetry run pytest --cov=src/cdd_agent --cov-report=html

# Check code quality
poetry run black --check src/
poetry run ruff check src/

# Performance profiling
python scripts/profile_startup.py
```

---

## Notes & Tips

**For testing agents:**
- Use simple, clear requirements (avoid complex nested logic on first test)
- Start with a "hello world" level feature
- Verify each agent's output before moving to next
- Check generated files match expectations

**For testing background execution:**
- Use `sleep` commands for predictable timing
- Test both short (1-2s) and longer (10-30s) commands
- Verify you can interact with chat while command runs

**For testing approvals:**
- Try both safe and dangerous operations
- Test "approve all" at different scopes (session vs always)
- Verify approvals persist across sessions when configured

**Common Issues:**
- If agent doesn't exit: Type `exit` explicitly
- If execution state corrupted: Delete `execution-state.json` and restart
- If background processes stuck: Use Ctrl+B to view and interrupt

---

## Success Metrics

**For Release Readiness:**
- ✅ All critical path tests passing
- ✅ No crashes during normal usage
- ✅ Automated test suite: 161+ tests passing
- ✅ Agent tests: 44/44 passing
- ✅ Can complete full Socrates → Planner → Executor workflow
- ✅ Generated code is functional
- ✅ State persists correctly (can resume)

**Quality Bar:**
- Code quality checks passing (Black, Ruff)
- No known critical bugs
- Documentation updated
- User-facing error messages are clear

---

**Ready to test? Start with the 5-minute smoke test, then dive into the Week 5-7 agents workflow! 🚀**
