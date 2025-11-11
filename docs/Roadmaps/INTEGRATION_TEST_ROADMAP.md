# Integration Test Roadmap - Phase 2

**Purpose:** Track integration tests to be performed after completing implementation tasks.

**Status:** 🔄 In Progress
**Last Updated:** 2025-11-09

---

## Testing Strategy

### Test Types

1. **Unit Tests** - Test individual functions in isolation (automated)
2. **Integration Tests** - Test components working together (manual/automated)
3. **End-to-End Tests** - Test complete workflows (manual)

### Testing Approach

- ✅ Unit tests written during development
- 🔄 Integration tests performed after each major task
- 🔜 E2E tests performed at end of each week

---

## Week 4: Foundation - Mechanical Layer

### Task 1: Port `initialize_project()` ✅ COMPLETE

**Unit Tests:** ✅ **PASSED**
- Fresh project initialization
- Dangerous path rejection
- Non-git repository handling
- Idempotency (run twice)
- CLAUDE.md detection

**Integration Tests:** 🔜 **PENDING**

#### IT-1.1: Manual `/init` in Fresh Project
**Status:** 🔜 Pending
**Prerequisites:** Slash command router implemented (Task 4.2)

**Test Steps:**
```bash
# 1. Create fresh test project
mkdir /tmp/test-cdd-agent && cd /tmp/test-cdd-agent
git init

# 2. Start cdd-agent chat
cdd-agent chat

# 3. Run /init
> /init

# Expected Output:
Initializing CDD project structure...
✅ CDD project initialized!

Created:
  📁 specs/tickets/
  📁 docs/features/
  📁 docs/guides/
  📄 CDD.md
  ⚙️  .cdd/templates/ (11 templates installed)

Next steps:
  1. Edit CDD.md with your project information
  2. Create your first ticket: /new feature <name>
```

**Verification Checklist:**
- [ ] Command executes without errors
- [ ] All directories created with .gitkeep files
- [ ] CDD.md created from template
- [ ] .cdd/config.yaml created with language: en
- [ ] All 11 templates copied to .cdd/templates/
- [ ] Success message displays correctly
- [ ] Console output is properly formatted (Rich)

**Expected Files:**
```
test-cdd-agent/
├── CDD.md
├── specs/tickets/.gitkeep
├── docs/features/.gitkeep
├── docs/guides/.gitkeep
└── .cdd/
    ├── config.yaml
    └── templates/ (11 files)
```

---

#### IT-1.2: `/init` with Existing CLAUDE.md (Migration)
**Status:** 🔜 Pending
**Prerequisites:** Slash command router implemented

**Test Steps:**
```bash
# 1. Create project with CLAUDE.md
mkdir /tmp/test-migration && cd /tmp/test-migration
git init
echo "# My Project Constitution" > CLAUDE.md
echo "This is from Claude Code." >> CLAUDE.md

# 2. Start cdd-agent chat
cdd-agent chat

# 3. Run /init
> /init

# Expected Output:
Initializing CDD project structure...

📄 Found existing CLAUDE.md

Migrate content from CLAUDE.md to CDD.md? [Y/n]: y

✅ Content migrated from CLAUDE.md → CDD.md
💡 You can now delete CLAUDE.md if desired

✅ CDD project initialized!
```

**Verification Checklist:**
- [ ] Detects existing CLAUDE.md
- [ ] Prompts for migration (interactive)
- [ ] Content copied correctly from CLAUDE.md to CDD.md
- [ ] Both files exist after migration (user decides to delete)
- [ ] Helpful message about deleting CLAUDE.md
- [ ] All other files/directories created correctly

---

#### IT-1.3: `/init` Idempotency (Run Twice)
**Status:** 🔜 Pending
**Prerequisites:** Slash command router implemented

**Test Steps:**
```bash
# 1. Run /init first time
> /init
# [Creates structure]

# 2. Run /init second time immediately
> /init

# Expected Output:
Initializing CDD project structure...

⚠️  CDD structure partially exists. Creating missing items only.

✅ CDD project initialized!

Created:
  (none or minimal)

Existing structure preserved:
  📁 specs/tickets/ ✅
  📁 docs/features/ ✅
  📁 docs/guides/ ✅
  📄 CDD.md ✅
```

**Verification Checklist:**
- [ ] Detects existing structure
- [ ] Shows warning about partial existence
- [ ] Doesn't overwrite existing files
- [ ] Only creates missing items (if any)
- [ ] No errors or crashes

---

#### IT-1.4: `/init --force` (Overwrite)
**Status:** 🔜 Pending
**Prerequisites:** Slash command router implemented

**Test Steps:**
```bash
# 1. Create initial structure
> /init

# 2. Modify CDD.md
# [Edit CDD.md manually]

# 3. Run with --force flag
> /init --force

# Expected: CDD.md overwritten from template
```

**Verification Checklist:**
- [ ] `--force` flag parsed correctly
- [ ] CDD.md overwritten from template
- [ ] Templates reinstalled
- [ ] No user prompt (force behavior)

---

#### IT-1.5: `/init` in Dangerous Path (Error Handling)
**Status:** 🔜 Pending
**Prerequisites:** Slash command router implemented

**Test Steps:**
```bash
# 1. Try to init in home directory
cd ~
cdd-agent chat

> /init

# Expected Output:
❌ Error: Refusing to initialize in system directory: /home/guilherme
💡 Please run /init from within a project directory
```

**Verification Checklist:**
- [ ] Refuses to initialize
- [ ] Clear error message
- [ ] Helpful suggestion
- [ ] No partial initialization
- [ ] Agent remains functional after error

---

### Task 2: Port `create_new_ticket()` 🔜 PENDING

**Unit Tests:** 🔜 Pending

**Integration Tests:** 🔜 Pending

#### IT-2.1: `/new feature <name>` Creates Ticket
**Status:** 🔜 Pending
**Prerequisites:** Task 2 complete, slash command router implemented

**Test Steps:**
```bash
# Prerequisites: /init already run

> /new feature user-authentication

# Expected Output:
✅ Created: specs/tickets/feature-user-authentication/spec.yaml

Next steps:
  /socrates feature-user-authentication
```

**Verification Checklist:**
- [ ] Ticket folder created: `specs/tickets/feature-user-authentication/`
- [ ] spec.yaml created from template
- [ ] Dates auto-populated ([auto-generated] replaced)
- [ ] Success message displays
- [ ] Next step suggestion shown

---

#### IT-2.2: `/new bug <name>` Creates Bug Ticket
**Status:** 🔜 Pending

**Test Steps:**
```bash
> /new bug login-error

# Expected: specs/tickets/bug-login-error/spec.yaml created
```

**Verification Checklist:**
- [ ] Bug ticket folder created
- [ ] Uses bug-ticket-template.yaml
- [ ] Dates populated correctly

---

#### IT-2.3: `/new spike <name>` Creates Spike Ticket
**Status:** 🔜 Pending

**Test Steps:**
```bash
> /new spike oauth-research

# Expected: specs/tickets/spike-oauth-research/spec.yaml created
```

**Verification Checklist:**
- [ ] Spike ticket folder created
- [ ] Uses spike-ticket-template.yaml

---

#### IT-2.4: `/new documentation guide <name>` Creates Guide
**Status:** 🔜 Pending

**Test Steps:**
```bash
> /new documentation guide getting-started

# Expected: docs/guides/getting-started.md created
```

**Verification Checklist:**
- [ ] Guide file created in docs/guides/
- [ ] Uses guide-doc-template.md
- [ ] No date population (docs are living)

---

#### IT-2.5: `/new documentation feature <name>` Creates Feature Doc
**Status:** 🔜 Pending

**Test Steps:**
```bash
> /new documentation feature authentication

# Expected: docs/features/authentication.md created
```

**Verification Checklist:**
- [ ] Feature doc created in docs/features/
- [ ] Uses feature-doc-template.md

---

#### IT-2.6: Name Normalization
**Status:** 🔜 Pending

**Test Steps:**
```bash
> /new feature "User Authentication System"

# Expected: specs/tickets/feature-user-authentication-system/
#           (spaces converted to dashes, lowercase)
```

**Verification Checklist:**
- [ ] Spaces converted to dashes
- [ ] All lowercase
- [ ] Special characters removed
- [ ] Duplicate dashes removed

---

#### IT-2.7: Overwrite Handling (Ticket Exists)
**Status:** 🔜 Pending

**Test Steps:**
```bash
# 1. Create ticket
> /new feature user-auth

# 2. Try to create same ticket again
> /new feature user-auth

# Expected Output:
⚠️  Ticket already exists: specs/tickets/feature-user-auth

Ticket already exists. Overwrite? [y/N]: n

💡 Tip: Type 'cancel' or press Ctrl+C to abort
Enter a different name for the feature ticket: user-auth-v2

✅ Created: specs/tickets/feature-user-auth-v2/spec.yaml
```

**Verification Checklist:**
- [ ] Detects existing ticket
- [ ] Prompts for overwrite
- [ ] Prompts for alternative name
- [ ] Allows cancellation
- [ ] Creates with new name correctly

---

### Task 3: Implement Slash Command Router 🔜 PENDING

**Unit Tests:** 🔜 Pending

**Integration Tests:** 🔜 Pending

#### IT-3.1: `/help` Shows All Commands
**Status:** 🔜 Pending

**Test Steps:**
```bash
> /help

# Expected Output:
📋 CDD Agent Slash Commands

**Project Setup:**
  /init [--force]              Initialize CDD project structure

**Ticket Creation:**
  /new feature <name>          Create feature ticket
  /new bug <name>              Create bug ticket
  ...

**Tips:**
- All work happens in this chat - no terminal switching!
- Type /init to get started
```

**Verification Checklist:**
- [ ] All commands listed
- [ ] Formatted nicely with Rich
- [ ] Usage examples clear
- [ ] Tips section helpful

---

#### IT-3.2: Unknown Slash Command Error
**Status:** 🔜 Pending

**Test Steps:**
```bash
> /unknown-command

# Expected Output:
❌ Unknown command: /unknown-command
💡 Type /help for available commands
```

**Verification Checklist:**
- [ ] Detects unknown command
- [ ] Helpful error message
- [ ] Suggests /help
- [ ] Doesn't crash

---

#### IT-3.3: Slash Command vs Regular Message
**Status:** 🔜 Pending

**Test Steps:**
```bash
# 1. Regular message (no slash)
> help me with this code

# Expected: Sent to LLM as regular message

# 2. Slash command
> /help

# Expected: Handled by slash command router
```

**Verification Checklist:**
- [ ] Regular messages go to LLM
- [ ] Slash commands intercepted
- [ ] No confusion between modes

---

### Task 4: Chat Session Integration 🔜 PENDING

**Integration Tests:** 🔜 Pending

#### IT-4.1: Chat Session Startup
**Status:** 🔜 Pending

**Test Steps:**
```bash
cdd-agent chat

# Expected Output:
Welcome to CDD Agent! Type /help for available commands.

>
```

**Verification Checklist:**
- [ ] Chat starts successfully
- [ ] Welcome message shown
- [ ] Prompt ready for input
- [ ] No errors in startup

---

#### IT-4.2: Mix Slash Commands and Regular Chat
**Status:** 🔜 Pending

**Test Steps:**
```bash
> /init
[Initializes project]

> What is CDD?
[LLM responds about CDD]

> /new feature auth
[Creates ticket]

> Help me understand this error
[LLM responds]
```

**Verification Checklist:**
- [ ] Slash commands work
- [ ] Regular chat works
- [ ] Smooth transitions
- [ ] Context preserved

---

### Task 5: BaseAgent Architecture 🔜 PENDING

**Integration Tests:** 🔜 Pending

#### IT-5.1: Agent Initialization
**Status:** 🔜 Pending

**Test Steps:**
```python
# In test script
from cdd_agent.agents.base import BaseAgent

# Test that BaseAgent can be instantiated
# Test system prompt loading
# Test context loading
```

**Verification Checklist:**
- [ ] BaseAgent instantiates
- [ ] Loads system prompts from markdown
- [ ] Context loading works
- [ ] Tool schemas returned

---

## Week 5: Socrates Agent

### Task 6: Socrates Agent Implementation 🔜 PENDING

**Integration Tests:** 🔜 Pending

#### IT-6.1: `/socrates <ticket>` Launches Agent
**Status:** 🔜 Pending

**Test Steps:**
```bash
# Prerequisites: /init and /new feature user-auth completed

> /socrates feature-user-auth

# Expected Output:
👋 Hey! I'm Socrates. Let me load context before we start...

📚 Context loaded:
- Project: [From CDD.md]
- Working on: feature-user-auth
- Template structure: [Summarized]

What problem are you solving?

>
```

**Verification Checklist:**
- [ ] Agent mode activates
- [ ] Context loads correctly
- [ ] Initial message displayed
- [ ] Agent waits for input
- [ ] Status indicator shows agent mode

---

#### IT-6.2: Socratic Dialogue Flow
**Status:** 🔜 Pending

**Test Steps:**
```bash
[After /socrates launches]

> Users need to authenticate to access private data

# Expected: Socrates asks clarifying question
✅ Got it - authentication is missing.
❓ What kind of users are these?

> Business users, project managers

# Expected: Socrates acknowledges and asks next question
✅ Clear: Business users, project managers.
❓ Desktop, mobile, or both?

> Desktop mostly

[Continue dialogue...]
```

**Verification Checklist:**
- [ ] Socrates asks relevant questions
- [ ] Progressive clarification pattern works
- [ ] Acknowledges answers (✅)
- [ ] Asks new questions (❓)
- [ ] Stays in requirements scope
- [ ] No implementation suggestions

---

#### IT-6.3: Socrates Summary and Approval
**Status:** 🔜 Pending

**Test Steps:**
```bash
[After several dialogue turns]

# Expected: Socrates shows summary
Here's the complete specification:

**Ticket:** feature-user-auth
**Type:** Feature

**User Story:**
As a business user
I want to authenticate with username/password
So that I can access my private project data

**Acceptance Criteria:**
- User can log in with credentials
- Session persists for 24 hours
- User can log out
...

Does this look good? Type 'yes' to save or 'no' to continue editing.

> yes

# Expected:
✅ Saved to specs/tickets/feature-user-auth/spec.yaml!

Type 'exit' to return to chat.

> exit

# Expected: Back in general chat mode
```

**Verification Checklist:**
- [ ] Summary shows complete spec
- [ ] Approval prompt works
- [ ] spec.yaml written correctly
- [ ] YAML is valid
- [ ] All required fields populated
- [ ] Exit returns to chat

---

#### IT-6.4: Socrates Tool Restrictions (Read-Only)
**Status:** 🔜 Pending

**Test Steps:**
```bash
[While in Socrates mode]

# Socrates should ONLY be able to:
# - read_file
# - list_files
# - glob_files
# - grep_files

# Should NOT be able to:
# - write_file (except final spec.yaml)
# - edit_file
# - bash commands
```

**Verification Checklist:**
- [ ] Socrates can read files
- [ ] Socrates cannot write files (except spec.yaml at end)
- [ ] Socrates cannot execute bash
- [ ] Tool restrictions enforced by code

---

#### IT-6.5: Exit Socrates Before Completion
**Status:** 🔜 Pending

**Test Steps:**
```bash
[While in Socrates dialogue]

> exit

# Expected Output:
⚠️ Specification incomplete. Progress not saved.

Type any message to return to general chat.

>
```

**Verification Checklist:**
- [ ] Exit command works
- [ ] Warning about incomplete work
- [ ] Returns to chat
- [ ] No spec.yaml written
- [ ] Agent state cleaned up

---

## Week 6: Planner Agent

### Task 7: Planner Agent Implementation 🔜 PENDING

**Integration Tests:** 🔜 Pending

#### IT-7.1: `/plan <ticket>` Launches Planner
**Status:** 🔜 Pending

**Test Steps:**
```bash
# Prerequisites: Spec completed with /socrates

> /plan feature-user-auth

# Expected Output:
📋 Got it! I'll create the implementation plan.

**Loading context...**

📚 Context loaded:
- Spec: specs/tickets/feature-user-auth/spec.yaml
- Project: [From CDD.md]
- Template: feature-plan-template.md

**Starting codebase analysis** (limited to 10 files)...
```

**Verification Checklist:**
- [ ] Planner mode activates
- [ ] Loads spec.yaml
- [ ] Loads project context
- [ ] Shows analysis limits
- [ ] Begins autonomous analysis

---

#### IT-7.2: Planner Autonomous Analysis
**Status:** 🔜 Pending

**Test Steps:**
```bash
[After /plan launches]

# Expected: Planner analyzes codebase
Analyzing patterns...
- Found authentication pattern in auth.py
- Detected FastAPI framework
- Found existing user model
...

**Analysis complete.**

❓ Should authentication use JWT tokens or sessions?

> JWT tokens

# Expected: Makes remaining decisions autonomously
```

**Verification Checklist:**
- [ ] Analyzes codebase (respects 10 file limit)
- [ ] Detects patterns correctly
- [ ] Makes autonomous decisions (90%+)
- [ ] Asks 1-3 questions max
- [ ] Questions are relevant and specific

---

#### IT-7.3: Planner Generates Plan
**Status:** 🔜 Pending

**Test Steps:**
```bash
[After answering planner questions]

# Expected: Plan generation
Generating implementation plan...

📋 Plan generated!

**Overview:**
- 8 implementation steps
- Estimated effort: 4-6 hours
- Technologies: FastAPI, JWT, bcrypt
- Key decisions: 3 documented

Would you like to see the full plan?

> yes

[Shows plan preview]

Save plan to plan.md?

> yes

✅ Plan saved to specs/tickets/feature-user-auth/plan.md!

Type 'exit' to return to chat.
```

**Verification Checklist:**
- [ ] Plan generated with steps
- [ ] Effort estimates included
- [ ] Technologies listed
- [ ] Decisions documented
- [ ] plan.md written
- [ ] Valid markdown format
- [ ] Follows template structure

---

## Week 7: Executor Agent

### Task 8: Executor Agent Implementation 🔜 PENDING

**Integration Tests:** 🔜 Pending

#### IT-8.1: `/exec <ticket>` Launches Executor
**Status:** 🔜 Pending

**Test Steps:**
```bash
# Prerequisites: Spec and plan completed

> /exec feature-user-auth

# Expected Output:
🚀 Starting implementation from plan.md...

**Total steps:** 8
**Estimated time:** 4-6 hours

Let's begin with step 1...
```

**Verification Checklist:**
- [ ] Executor mode activates
- [ ] Loads spec and plan
- [ ] Shows step count
- [ ] Shows time estimate
- [ ] Begins execution

---

#### IT-8.2: Executor Step-by-Step Execution
**Status:** 🔜 Pending

**Test Steps:**
```bash
[After /exec launches]

# Expected: Executes steps sequentially
📝 Step 1: Create authentication routes
   - Creating src/api/auth.py
   - Adding login endpoint
   - Adding logout endpoint
✅ Step 1 complete

Running quality checks...
✅ Black formatting passed
✅ Ruff linting passed

📝 Step 2: Implement JWT token generation
...
```

**Verification Checklist:**
- [ ] Executes steps in order
- [ ] Shows progress indicators
- [ ] Runs quality checks after each step
- [ ] Updates progress.yaml
- [ ] Tracks files touched

---

#### IT-8.3: Executor Quality Gate Failures
**Status:** 🔜 Pending

**Test Steps:**
```bash
[During execution]

📝 Step 3: Add password hashing
✅ Step 3 complete

Running quality checks...
✅ Black formatting passed
❌ Ruff linting failed

**Issues found:**
- Line 42: Unused import 'datetime'
- Line 55: Variable 'token' not defined

**Options:**
1. Debug and fix now
2. Mark as known issue and continue
3. Stop implementation

Your choice?

> 1

[Executor fixes issues]
✅ Issues resolved
✅ All checks passing
```

**Verification Checklist:**
- [ ] Detects quality gate failures
- [ ] Shows specific issues
- [ ] Offers resolution options
- [ ] Can fix automatically
- [ ] Can continue with issues
- [ ] Can stop execution

---

#### IT-8.4: Executor Resumability
**Status:** 🔜 Pending

**Test Steps:**
```bash
# Session 1: Start execution
> /exec feature-user-auth
[Completes steps 1-3]
[Crash or manual exit]

# Session 2: Resume
> /exec feature-user-auth

# Expected Output:
🚀 Resuming implementation from progress.yaml...

**Completed steps:** 3
**Remaining steps:** 5

Starting from step 4...
```

**Verification Checklist:**
- [ ] Detects progress.yaml
- [ ] Shows completed steps
- [ ] Skips completed work
- [ ] Continues from next step
- [ ] All state preserved

---

## Week 8: Polish & Utilities

### Task 9: Utility Commands 🔜 PENDING

**Integration Tests:** 🔜 Pending

#### IT-9.1: `/status` Shows Ticket Progress
**Status:** 🔜 Pending

**Test Steps:**
```bash
> /status feature-user-auth

# Expected Output:
📊 Status: feature-user-auth

**Specification:** ✅ Complete
**Plan:** ✅ Complete
**Implementation:** 🔄 In Progress (3/8 steps)

**Progress:**
✅ Step 1: Create authentication routes
✅ Step 2: Implement JWT generation
✅ Step 3: Add password hashing
⏳ Step 4: Create user model (in progress)
⏸️  Step 5: Add login logic
⏸️  Step 6: Add logout logic
...

**Estimated remaining:** 2-3 hours
```

**Verification Checklist:**
- [ ] Shows spec status
- [ ] Shows plan status
- [ ] Shows implementation progress
- [ ] Lists all steps with status
- [ ] Estimates remaining time

---

#### IT-9.2: `/list` Shows All Tickets
**Status:** 🔜 Pending

**Test Steps:**
```bash
> /list

# Expected Output:
📋 All Tickets

**Features:**
- feature-user-auth (🔄 In Progress - 3/8 steps)
- feature-api-rate-limiting (📄 Spec Only)

**Bugs:**
- bug-login-error (✅ Complete)

**Spikes:**
- spike-oauth-providers (📝 Planning)

Total: 4 tickets
```

**Verification Checklist:**
- [ ] Lists all tickets by type
- [ ] Shows status indicators
- [ ] Shows progress for in-progress tickets
- [ ] Groups by type
- [ ] Shows total count

---

## End-to-End Workflow Tests

### E2E-1: Complete Feature Development (Fresh Project)
**Status:** 🔜 Pending
**Prerequisites:** All Week 4-7 tasks complete

**Test Steps:**
```bash
# 1. Initialize project
> /init
✅ Project initialized

# 2. Create ticket
> /new feature user-authentication
✅ Ticket created

# 3. Write specification
> /socrates feature-user-authentication
[Complete dialogue]
✅ Spec saved

# 4. Generate plan
> /plan feature-user-authentication
[Answer 1-3 questions]
✅ Plan generated

# 5. Implement
> /exec feature-user-authentication
[Implementation with quality gates]
✅ Implementation complete

# 6. Verify
- All files created
- Tests passing
- Code formatted
- Linting clean
```

**Verification Checklist:**
- [ ] Complete workflow works end-to-end
- [ ] No errors or crashes
- [ ] All files created correctly
- [ ] Quality gates pass
- [ ] Acceptance criteria met

---

### E2E-2: Resume After Crash
**Status:** 🔜 Pending

**Test Steps:**
```bash
# 1. Start execution
> /exec feature-auth
[Completes 2 steps, then crash/exit]

# 2. Restart cdd-agent
cdd-agent chat

# 3. Resume
> /exec feature-auth
# Expected: Continues from step 3
```

**Verification Checklist:**
- [ ] State persisted in progress.yaml
- [ ] Resumes from correct step
- [ ] No duplicate work
- [ ] Completes successfully

---

### E2E-3: Multiple Tickets (Parallel Work)
**Status:** 🔜 Pending

**Test Steps:**
```bash
# 1. Create multiple tickets
> /new feature auth
> /new bug login-error
> /new spike oauth

# 2. Work on ticket 1
> /socrates feature-auth
[Complete]

# 3. Switch to ticket 2
> /socrates bug-login-error
[Complete]

# 4. Check status of all
> /list
```

**Verification Checklist:**
- [ ] Multiple tickets coexist
- [ ] Can switch between tickets
- [ ] No state interference
- [ ] Each ticket independent

---

## Performance Tests

### P-1: Large Project Initialization
**Status:** 🔜 Pending

**Test Steps:**
```bash
# In a project with 1000+ files
> /init
# Expected: Completes in <2 seconds
```

**Verification Checklist:**
- [ ] Fast execution (<2s)
- [ ] No performance issues
- [ ] No memory leaks

---

### P-2: Long-Running Executor Session
**Status:** 🔜 Pending

**Test Steps:**
```bash
# Execute plan with 20+ steps
> /exec large-feature
# Run for 30+ minutes
```

**Verification Checklist:**
- [ ] No memory leaks
- [ ] Progress tracked correctly
- [ ] Can resume after interrupt
- [ ] No performance degradation

---

## Error Handling Tests

### E-1: Network Failures
**Status:** 🔜 Pending

**Test Steps:**
```bash
# Simulate network failure during LLM call
# [Disconnect network]
> /socrates feature-auth
# [Network error occurs]
```

**Verification Checklist:**
- [ ] Graceful error message
- [ ] Retry option offered
- [ ] State preserved
- [ ] Agent recovers after reconnect

---

### E-2: Invalid Spec/Plan Files
**Status:** 🔜 Pending

**Test Steps:**
```bash
# Manually corrupt spec.yaml
# Try to run /plan
> /plan feature-auth

# Expected: Clear error about invalid YAML
```

**Verification Checklist:**
- [ ] Detects invalid files
- [ ] Clear error messages
- [ ] Suggests fix
- [ ] Doesn't crash

---

### E-3: Permission Errors
**Status:** 🔜 Pending

**Test Steps:**
```bash
# Make specs/ directory read-only
# Try to create ticket
> /new feature auth

# Expected: Permission error with helpful message
```

**Verification Checklist:**
- [ ] Detects permission issues
- [ ] Clear error message
- [ ] Suggests resolution
- [ ] Doesn't corrupt files

---

## Test Status Summary

### Week 4 Progress
- **Task 1:** Unit tests ✅ | Integration tests 🔜
- **Task 2:** Not started 🔜
- **Task 3:** Not started 🔜
- **Task 4:** Not started 🔜
- **Task 5:** Not started 🔜

### Week 5 Progress
- **Task 6:** Not started 🔜

### Week 6 Progress
- **Task 7:** Not started 🔜

### Week 7 Progress
- **Task 8:** Not started 🔜

### Week 8 Progress
- **Task 9:** Not started 🔜

---

## Testing Notes

### General Guidelines

1. **Test in order** - Complete integration tests for Task N before starting Task N+1
2. **Document failures** - Add notes below each failing test
3. **Update status** - Mark tests as ✅ PASSED or ❌ FAILED with details
4. **Report blockers** - Flag any tests that block subsequent work

### Test Environment

- **OS:** Linux (Fedora 42)
- **Python:** 3.10+
- **Terminal:** WezTerm with Rich support
- **Git:** Required for all tests

### How to Update This Document

After completing each task:

1. Run unit tests (automated)
2. Run integration tests (manual)
3. Update test status (🔜 → ✅ or ❌)
4. Add notes about failures or issues
5. Check off verification items

---

**Last Updated:** 2025-11-09
**Next Review:** After completing Task 2
