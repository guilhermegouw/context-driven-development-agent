# Quick Test Guide - Post v0.0.3

## 🚀 Fast Start (5 minutes)

```bash
# 1. Start the agent
poetry run cdd-agent chat

# 2. Test basic chat
> Hello! Can you explain what you can do?

# 3. Test background execution
> Can you run "sleep 3 && echo 'Background works!'" in the background?
# ✓ You should be able to type while it runs
# ✓ You'll see a notification when it completes

# 4. Test approvals
> Can you read /etc/hosts?
# ✓ Approval prompt should appear

# 5. Quick exit
> exit
```

---

## 🎯 Main Feature Test (15 minutes)

### Test the Complete CDD Workflow

```bash
poetry run cdd-agent chat

# STEP 1: Initialize
> /init

# STEP 2: Create ticket
> /new ticket feature hello-world

# STEP 3: Refine with Socrates
> /socrates feature-hello-world
> Create a simple Python hello world program that can be run from command line
> It should print "Hello, World!" when run
> No special libraries needed
> That's all!
> exit

# STEP 4: Generate plan
> /plan feature-hello-world

# STEP 5: Execute plan
> /exec feature-hello-world
> continue
> continue  # Repeat for each step
# (or just press Enter)

# STEP 6: Verify
> Can you show me what files were created?
> Can you run the hello world program?
```

**Expected result:**
- Socrates refines the spec
- Planner creates implementation steps
- Executor generates working Python code
- You can run the generated program

---

## 📋 Command Reference

### Slash Commands
```bash
/init                    # Initialize CDD project
/help                    # Show help
/new ticket <type> <name>  # Create ticket
/socrates <ticket>       # Refine requirements
/plan <ticket>           # Generate plan
/exec <ticket>           # Execute plan
exit                     # Exit current mode
```

### Executor Commands (when in /exec mode)
```bash
continue  # or just Enter - Execute next step
status    # Show progress
skip      # Skip current step
retry     # Retry failed step
exit      # Stop execution
```

### Keyboard Shortcuts (in TUI)
```bash
Ctrl+B    # Show background processes
Ctrl+C    # Interrupt/cancel
?         # Show help
F1        # Show keyboard shortcuts
```

---

## ✅ Quick Checklist

**Infrastructure:**
- [ ] Chat works
- [ ] Background commands run without blocking
- [ ] Approval prompts appear
- [ ] Markdown renders correctly

**CDD Workflow:**
- [ ] `/init` creates project structure
- [ ] `/new ticket` creates ticket
- [ ] `/socrates` asks clarifying questions
- [ ] `/plan` generates implementation steps
- [ ] `/exec` generates working code

**Quality:**
- [ ] No crashes
- [ ] Error messages are clear
- [ ] Can exit/resume execution
- [ ] Files are created correctly

---

## 🐛 Common Issues & Solutions

**Problem:** Socrates won't exit
**Solution:** Type `exit` explicitly

**Problem:** Executor seems stuck
**Solution:** Press Enter or type `continue`

**Problem:** Can't find ticket
**Solution:** Use exact ticket name, e.g., `feature-hello-world` not `hello-world`

**Problem:** Plan says "spec not complete"
**Solution:** Run `/socrates` first to refine requirements

**Problem:** Execution interrupted
**Solution:** Just run `/exec <ticket>` again - it will resume from where it left off

---

## 📊 What to Look For

**Good Signs:**
- ✅ Smooth streaming responses (like ChatGPT)
- ✅ Background processes show progress indicators
- ✅ Approval prompts are clear and actionable
- ✅ Agents ask relevant questions
- ✅ Generated code is syntactically correct
- ✅ Progress percentages make sense

**Red Flags:**
- ❌ Crashes or stack traces
- ❌ Frozen/hanging UI
- ❌ Generated code has syntax errors
- ❌ Files created in wrong locations
- ❌ Agents repeating same questions
- ❌ Progress not saving between sessions

---

## 🎨 Test Scenarios

### Scenario 1: Simple Python Script
```
Ticket: feature-calculator
Requirements: Basic calculator (add, subtract, multiply, divide)
Expected: Working Python script with functions
```

### Scenario 2: FastAPI Endpoint
```
Ticket: feature-hello-api
Requirements: FastAPI endpoint that returns "Hello, World!" at GET /
Expected: FastAPI app file, requirements.txt
```

### Scenario 3: Data Processing
```
Ticket: feature-csv-reader
Requirements: Read CSV file and print summary statistics
Expected: Python script with pandas/csv reading logic
```

---

## 🔥 Stress Test

If you want to push the limits:

```bash
# Create a more complex ticket
> /new ticket feature real-time-chat

# Give Socrates challenging requirements
> /socrates feature-real-time-chat
> Build a real-time chat system with WebSockets
> It should support multiple rooms
> Users can join/leave rooms
> Messages are persisted to SQLite
> Include authentication
# [Continue answering questions...]

# See how well Planner handles complexity
> /plan feature-real-time-chat

# Let Executor try to implement it
> /exec feature-real-time-chat
```

Expected: System should handle complexity gracefully, even if implementation isn't perfect.

---

## 📞 Quick Help

**Get help in chat:**
```bash
> /help
```

**Show keyboard shortcuts:**
```bash
Press ? or F1 in TUI
```

**Check version:**
```bash
poetry run cdd-agent --version
```

**View logs:**
```bash
tail -f ~/.cdd-agent/logs/cdd-agent-*.log
```

**Run tests:**
```bash
# All tests
poetry run pytest

# Just agent tests
python test_socrates_agent.py
python test_planner_agent.py
python test_executor_agent.py
```

---

## 💡 Pro Tips

1. **Start simple:** Test with a "hello world" before trying complex features
2. **Check files:** After Executor runs, verify files exist and have content
3. **Use status:** In Executor mode, `status` command shows useful progress info
4. **Resume works:** You can Ctrl+C during execution and resume later
5. **Logs help:** Check logs if something seems wrong
6. **Test edge cases:** Try missing tickets, incomplete specs, etc.

---

**Happy testing! 🚀**

Report any issues you find - even small UX annoyances are valuable feedback!
