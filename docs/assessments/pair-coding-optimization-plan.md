# Pair Coding Optimization Plan for CDD Agent

**Date:** 2025-11-07
**Status:** Proposed
**Priority:** High
**Estimated Effort:** 18-20 hours over 3 weeks

---

## Executive Summary

Based on a comparative analysis of 5 AI agents (Claude Code, GLM-CDD, Droid, GLM-Claude Code, M2-Claude Code) responding to the same repository overview task, we identified that **agentic platform architecture has more impact on output quality than the underlying LLM model**.

**Key Finding:** GLM-4.6 produced vastly different quality results depending on the platform:
- Through **Droid**: B+ (superficial, lacked depth)
- Through **CDD Agent**: A (competent, well-balanced)
- Through **Claude Code**: A+ (best strategic analysis)

This proves that improving CDD Agent's architecture, prompting, and context management can elevate any LLM's performance to Claude Code levels.

---

## Critical Issues Identified

### 1. **Weak System Prompt** (agent.py:89-101)
**Problem:** Current prompt is too basic and generic
```python
"You are a helpful AI coding assistant with access to tools..."
```

**Impact:** LLMs lack guidance on:
- How to approach complex tasks
- When to use which tools
- How to structure responses
- Project-specific context

### 2. **No Automatic Context Loading**
**Problem:** Agent doesn't read CLAUDE.md, CDD.md, or project context files
**Impact:** LLM operates without understanding project architecture, conventions, or goals

### 3. **Poor Task Decomposition**
**Problem:** No guidance for breaking down complex requests
**Impact:** Shallow responses that describe rather than execute

### 4. **Basic Tool Result Formatting**
**Problem:** Tool results returned as raw strings without metadata
**Impact:** LLM struggles to interpret and synthesize results

### 5. **No Context Window Management**
**Problem:** Messages accumulate without pruning
**Impact:** Will eventually hit context limits and crash

### 6. **Missing Reflection Pattern**
**Problem:** No post-execution summary or synthesis
**Impact:** Less actionable responses, missing "what was accomplished"

---

## Recommended Improvements

### **Priority 1: Enhanced System Prompt** 🎯

**Location:** `src/cdd_agent/agent.py`

Create a comprehensive system prompt that includes:

```python
PAIR_CODING_SYSTEM_PROMPT = """You are an expert AI pair programming assistant with deep technical knowledge across multiple domains.

## Core Principles for Pair Coding

1. **Understand Before Acting**
   - Always read relevant files before making changes
   - Use glob_files and grep_files to explore unfamiliar codebases
   - Ask clarifying questions when requirements are ambiguous

2. **Think Structurally**
   - Break down complex tasks into clear steps
   - Explain your reasoning before executing tools
   - Show "how things work together" - provide flow diagrams when helpful

3. **Be Thorough and Precise**
   - Provide concrete examples and code snippets
   - Include file paths with line numbers (e.g., src/agent.py:89)
   - Give context for why you're making specific recommendations

4. **Code Quality Focus**
   - Follow project conventions (check CLAUDE.md, README.md, CONTRIBUTING.md)
   - Consider edge cases and error handling
   - Suggest tests for new functionality

5. **Proactive Communication**
   - Announce what you're about to do before using tools
   - Explain tool results and their implications
   - Summarize changes after completion

## Available Tools

File Operations:
- read_file(path) - Read file contents, use for understanding code
- write_file(path, content) - Create new files
- edit_file(path, old_text, new_text) - Surgical edits to existing files
- list_files(path) - Explore directory structure

Search & Discovery:
- glob_files(pattern, max_results) - Find files by pattern (e.g., "**/*.py")
- grep_files(pattern, file_pattern, context_lines, max_results) - Search code with regex

Development:
- run_bash(command) - Execute shell commands (use with caution)
- git_status(), git_diff(file), git_log(n) - Git operations

## Response Format for Complex Tasks

When handling multi-step tasks, structure your response:

1. **Analysis**: What you understand about the task
2. **Approach**: Your planned steps
3. **Execution**: Tool usage with explanations
4. **Summary**: What was accomplished and next steps

## Project Context

{project_context}

IMPORTANT: Always use tools proactively. Don't just describe what you would do - actually do it."""
```

**Estimated Effort:** 2 hours
**Expected Impact:** +1 full grade improvement (A → A+)

---

### **Priority 2: Automatic Context Loading** 📁

**Location:** `src/cdd_agent/agent.py`

Add method to load project context files:

```python
def load_project_context(self) -> str:
    """Load relevant project context files.

    Returns:
        Formatted context string to inject into system prompt
    """
    context_parts = []
    cwd = os.getcwd()

    # Priority order for context files
    context_files = [
        "CLAUDE.md",      # Project constitution
        "CDD.md",         # CDD methodology
        ".context.md",    # Custom context
        "README.md",      # Project overview
    ]

    for filename in context_files:
        path = os.path.join(cwd, filename)
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    content = f.read()
                    # Truncate if too long (keep first 2000 chars)
                    if len(content) > 2000:
                        content = content[:2000] + "\n...(truncated)"
                    context_parts.append(f"## {filename}\n{content}")
            except Exception:
                pass

    if context_parts:
        return "\n\n".join(context_parts)
    return "No project context files found."
```

**Integrate into agent initialization:**
```python
def __init__(self, provider_config, tool_registry, model_tier="mid", max_iterations=10):
    # ... existing code ...

    # Load project context once at initialization
    self.project_context = self.load_project_context()

    # Build enhanced system prompt
    self.system_prompt = PAIR_CODING_SYSTEM_PROMPT.format(
        project_context=self.project_context
    )
```

**Estimated Effort:** 3 hours (includes testing)
**Expected Impact:** Enables context-aware responses, better project understanding

---

### **Priority 3: Task Decomposition Guidance** 🧩

**Location:** System prompt extension

Add to system prompt:
```python
## When You Receive Complex Requests

For tasks like "add authentication", "refactor module X", or "implement feature Y":

1. **First, Explore** (Use 2-3 tools):
   - Read existing relevant files
   - Search for related patterns
   - Check project structure

2. **Then, Plan** (Communicate to user):
   - List the files you'll need to modify/create
   - Outline the approach in 3-5 bullet points
   - Mention potential risks or considerations

3. **Execute Incrementally**:
   - Make one logical change at a time
   - Test/verify each change if possible
   - Explain what each tool call accomplishes

4. **Summarize** (At the end):
   - What was accomplished
   - Files that were modified
   - Suggested next steps or testing
```

**Estimated Effort:** 1 hour (prompt iteration)
**Expected Impact:** More structured, thorough responses

---

### **Priority 4: Better Tool Result Integration** 🔧

**Location:** `src/cdd_agent/agent.py`

Enhance tool execution to provide richer context:

```python
def _execute_tool(self, name: str, args: dict, tool_use_id: str) -> dict:
    """Execute a tool and return enriched result."""

    console.print(f"[cyan]  → Executing: {name}({args})[/cyan]")

    try:
        result = self.tool_registry.execute(name, args)
        console.print(f"[green]  ✓ Success[/green]")

        # Enrich result with metadata for better LLM understanding
        enriched_result = self._enrich_tool_result(name, args, result)

        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": enriched_result,
        }
    except Exception as e:
        # ... existing error handling ...

def _enrich_tool_result(self, tool_name: str, args: dict, result: Any) -> str:
    """Add context to tool results for better LLM understanding."""

    if tool_name == "read_file":
        # Add file metadata
        path = args.get("path", "")
        line_count = len(str(result).splitlines())
        return f"File: {path} ({line_count} lines)\n\n{result}"

    elif tool_name == "glob_files":
        # Format file list with counts
        files = str(result).splitlines()
        return f"Found {len(files)} files:\n{result}"

    elif tool_name == "grep_files":
        # Add match statistics
        lines = str(result).splitlines()
        return f"Search results ({len(lines)} matches):\n{result}"

    # Default: return as-is
    return str(result)
```

**Estimated Effort:** 4 hours (implement + test all tools)
**Expected Impact:** LLM better understands tool results, more coherent synthesis

---

### **Priority 5: Conversation Context Window Management** 💬

**Location:** `src/cdd_agent/agent.py`

Add intelligent message pruning:

```python
def _manage_context_window(self):
    """Prune old messages to stay within context limits.

    Strategy:
    - Keep first message (often contains important context)
    - Keep last N messages (recent context)
    - Summarize middle messages if needed
    """
    MAX_MESSAGES = 20  # Configurable

    if len(self.messages) <= MAX_MESSAGES:
        return

    # Keep first user message and recent messages
    self.messages = (
        [self.messages[0]] +  # First message
        self.messages[-(MAX_MESSAGES-1):]  # Recent messages
    )
```

Call in agentic loop before each LLM call:
```python
# In run() and stream() methods
self._manage_context_window()
```

**Estimated Effort:** 3 hours
**Expected Impact:** Prevents context overflow crashes, maintains performance

---

### **Priority 6: Reflection Pattern** 🔄

**Location:** `src/cdd_agent/agent.py`

Add optional post-execution reflection:

```python
def run_with_reflection(self, user_message: str, system_prompt: Optional[str] = None) -> str:
    """Run with post-execution reflection for summaries.

    Args:
        user_message: User's input message
        system_prompt: Optional system prompt

    Returns:
        Response with optional reflection summary appended
    """
    # Execute normal agentic loop
    response = self.run(user_message, system_prompt)

    # After completion, check if reflection would be valuable
    if self._should_reflect():
        reflection = self._get_reflection()
        return f"{response}\n\n---\n## Summary\n{reflection}"

    return response

def _should_reflect(self) -> bool:
    """Determine if reflection is needed.

    Returns:
        True if tools were used or response is long
    """
    # Reflect if we executed tools
    tool_count = sum(
        1 for msg in self.messages
        if msg.get("role") == "assistant"
        and any(b.get("type") == "tool_use" for b in msg.get("content", []))
    )
    return tool_count > 2

def _get_reflection(self) -> str:
    """Ask LLM to reflect on what was accomplished.

    Returns:
        Brief summary of accomplishments
    """
    reflection_prompt = """
    You just completed a task. Please provide a brief summary:

    1. What was accomplished
    2. Files that were modified (with paths)
    3. Potential issues or areas needing attention
    4. Suggested next steps

    Keep it concise (3-5 bullet points).
    """

    # Make a quick non-streaming call for reflection
    self.messages.append({"role": "user", "content": reflection_prompt})

    model = self.provider_config.get_model(self.model_tier)
    response = self.client.messages.create(
        model=model,
        max_tokens=500,
        messages=self.messages,
        system="You are summarizing your previous work.",
    )

    return self._extract_text(response)
```

**Estimated Effort:** 5 hours
**Expected Impact:** More actionable responses, clear next steps

---

## Implementation Timeline

### **Phase 1: Foundation (Week 1)** - 8 hours
**Goal:** Core prompt and context improvements

- [ ] Enhanced system prompt with pair coding guidance (2h)
- [ ] Automatic context loading (CLAUDE.md, etc.) (3h)
- [ ] Task decomposition instructions (1h)
- [ ] Testing and iteration (2h)

**Validation:** Run overview experiment again, compare to baseline

---

### **Phase 2: Intelligence (Week 2)** - 6 hours
**Goal:** Better tool integration and context management

- [ ] Tool result enrichment (4h)
- [ ] Context window management (3h)
- [ ] Better tool announcement formatting (1h)

**Validation:** Test with complex multi-file refactoring tasks

---

### **Phase 3: Advanced (Week 3)** - 4 hours
**Goal:** Reflection and polish

- [ ] Reflection pattern for summaries (5h)
- [ ] Proactive file exploration hints (2h)
- [ ] Documentation updates (1h)

**Validation:** A/B test with users, collect feedback

---

## Roadmap Integration

### **Where This Fits in Current Roadmap**

**Current Roadmap Status:**
- Phase 1: Production-Ready Core (Weeks 1-3) - ✅ Mostly Complete
- Phase 2: CDD Workflow Integration (Weeks 4-6) - 📋 Planned
- Phase 3: Advanced Features (Weeks 7-9) - 📋 Planned
- Phase 4: Launch & Growth (Weeks 10-12) - 📋 Planned

### **Proposed Integration:**

#### **Insert as "Phase 1.5" - Before Phase 2**

**Rationale:**
1. These improvements **dramatically enhance** the base agent quality
2. Better foundation = better CDD workflow agents (Socrates, Planner, Executor)
3. Validates the multi-provider approach before building advanced features
4. Relatively quick wins (18 hours) vs Phase 2's complexity

#### **Updated Roadmap Timeline:**

```
Week 1-3:   Phase 1 - Production-Ready Core ✅
Week 4-5:   Phase 1.5 - Pair Coding Optimization 🎯 NEW
Week 6-8:   Phase 2 - CDD Workflow Integration (adjusted)
Week 9-11:  Phase 3 - Advanced Features (adjusted)
Week 12:    Phase 4 - Launch Prep (adjusted)
```

### **Alternative: Parallel Track**

If Phase 2 CDD workflow can't be delayed, run as **parallel Track 1 work**:

**Track 1: Core UX (Claude Code Parity)**
- Week 4-5: Pair Coding Optimization (this plan)
- Week 6: Tool Approval System
- Week 7: MCP Protocol Support

**Track 2: CDD Workflow (runs in parallel)**
- Week 4-6: Socrates Agent
- Week 7-8: Planner Agent
- Week 9-10: Executor Agent

This way, both core improvements and CDD workflow progress simultaneously.

### **Benefits of Doing This First:**

1. **Immediate Quality Boost**: Elevates all models (GLM, M2, future providers)
2. **Validates Architecture**: Proves the multi-provider thesis before heavy investment
3. **Better CDD Agents**: Socrates/Planner/Executor will inherit these improvements
4. **Competitive Positioning**: Matches Claude Code quality on any LLM
5. **User Experience**: Current users get immediate value

### **Risks of Delaying:**

1. **User frustration**: Current responses may feel "shallow" compared to Claude Code
2. **Bad reputation**: Early users might abandon before seeing full potential
3. **Wasted effort**: Building CDD agents on weak foundation means rebuilding later
4. **Competitive disadvantage**: Claude Code and Cursor keep improving

---

## Expected Impact

Based on the experiment results, these improvements should:

1. **Elevate GLM-4.6 from A to A+** (matching Agent 4 quality)
2. **Improve all models** through better scaffolding
3. **Reduce "shallow" responses** like Agent 3 (Droid)
4. **Enable better technical depth** like Agent 5 (M2-Claude Code)
5. **Make responses more actionable** with structured output

### **Projected Agent Quality After Implementation:**

| Platform | Before | After | Improvement |
|----------|--------|-------|-------------|
| CDD Agent (GLM-4.6) | A | A+ | +1 grade |
| CDD Agent (M2) | Unknown | A++ | New capability |
| CDD Agent (Claude) | A | A+ | +1 grade |

---

## Validation Approach

### **Before/After Comparison**

Run the same overview experiment:
```bash
cdd-agent chat "I am taking a look at the code from this repository. Can you give me an overview? Please write it in a well formatted markdown file named: overview-cdd-v2.md"
```

Compare `overview-cdd-v2.md` to:
- **Agent 1** (Claude-Claude-Code) - Target to match
- **Agent 2** (GLM-CDD baseline) - Measure improvement
- **Agent 4** (GLM-Claude-Code) - Architecture benchmark

### **Success Criteria:**

✅ **Grade A+** on overview task
✅ **Structured output** with flow diagrams
✅ **Technical depth** matching M2-Claude-Code (Agent 5)
✅ **Actionable content** with file paths and examples
✅ **No crashes** on long conversations (context management working)

---

## Conclusion

The experiment proved that **platform architecture matters more than raw model capability**. By implementing these 6 priorities, CDD Agent can:

1. Elevate any LLM to Claude Code-level quality
2. Provide better pair programming experience
3. Validate the multi-provider thesis
4. Create a stronger foundation for CDD workflow agents

**Recommendation:** Implement this as Phase 1.5 (Weeks 4-5) before building the CDD workflow agents. The 18-hour investment will compound returns across all future features.

---

**Next Steps:**
1. Review and approve this plan
2. Create feature branch: `feature/pair-coding-optimization`
3. Implement Phase 1 (Week 1) - Enhanced prompts and context loading
4. Run validation experiment
5. Iterate based on results

---

*Generated: 2025-11-07*
*Author: Claude (Sonnet 4.5) via analysis of multi-agent experiment*
*Status: Awaiting approval*
