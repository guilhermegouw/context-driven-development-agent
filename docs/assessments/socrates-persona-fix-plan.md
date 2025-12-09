# Socrates Persona Fix - Implementation Plan

## Problem Statement

The Socrates agent loses its persona after several interactions when using weaker LLMs (GLM 4.6, Minimax M2) because:

1. **780-line system prompt** is too complex for weaker models
2. **Unbounded conversation history** floods the context window
3. **`gathered_info` dict is declared but never used** - no state tracking
4. **No conversation compaction** unlike the main Agent class
5. **Dynamic prompt variables** change every message, confusing models

## Expected Socrates Behavior (from original Claude Code version)

### Core Identity
- **Requirements gatherer**, NOT solution provider
- Uses **Socratic method** - questions to help developers think
- **Progressive clarification** with ✅/❓ markers
- Stays strictly in scope - requirements only

### Conversation Flow
1. **Initialize**: Load context (CDD.md, template, target file)
2. **Discover**: Ask questions through phases:
   - Phase 1: Problem understanding
   - Phase 2: User and context analysis
   - Phase 3: Requirements definition
   - Phase 4: Edge cases and constraints
3. **Synthesize**: Show complete summary
4. **Approve**: Get user approval before saving

### Key Behaviors
- **Never suggest solutions** - redirect to questions
- **Challenge vague answers** - "Can you give an example?"
- **Acknowledge clarity, target gaps** - use ✅/❓ pattern
- **One question at a time** - natural conversation flow
- **Track information gathered** - know what's missing

---

## Implementation Strategy

### Approach: Hybrid (Information Tracking + Condensed Prompt + Compaction)

We will:
1. **Reduce system prompt** from 780 → ~200 lines (structured rules)
2. **Implement `gathered_info` tracking** with phase detection
3. **Add conversation compaction** when history exceeds threshold
4. **Inject periodic persona reminders** every 5 turns
5. **Make state explicit** in every prompt (don't rely on model memory)

---

## Detailed Implementation

### 1. New `gathered_info` Structure

```python
# In SocratesAgent.__init__()
self.gathered_info = {
    "phase": "problem_discovery",  # Current conversation phase
    "problem": {
        "description": "",
        "examples": [],
        "impact": ""
    },
    "users": {
        "who": [],
        "context": "",
        "workflow": ""
    },
    "requirements": {
        "must_have": [],
        "success_criteria": [],
        "constraints": []
    },
    "edge_cases": [],
    "gaps": []  # What we still need to ask about
}
```

### 2. Phase Detection Logic

```python
PHASES = [
    "problem_discovery",    # What's the problem?
    "user_analysis",        # Who has this problem?
    "requirements",         # What should the solution do?
    "edge_cases",          # What happens when things go wrong?
    "wrap_up"              # Ready to show summary
]

def _detect_current_phase(self) -> str:
    """Determine which phase we're in based on gathered info."""
    info = self.gathered_info

    # Phase 1: Problem - need description and at least one example
    if not info["problem"]["description"] or not info["problem"]["examples"]:
        return "problem_discovery"

    # Phase 2: Users - need to know who and their context
    if not info["users"]["who"]:
        return "user_analysis"

    # Phase 3: Requirements - need must_haves and success criteria
    if not info["requirements"]["must_have"] or not info["requirements"]["success_criteria"]:
        return "requirements"

    # Phase 4: Edge cases - need at least 2
    if len(info["edge_cases"]) < 2:
        return "edge_cases"

    # Ready for wrap-up
    return "wrap_up"
```

### 3. Information Extraction (After Each Response)

```python
def _extract_info_from_exchange(self, user_input: str, assistant_response: str):
    """Extract key information from the latest exchange.

    Uses simple pattern matching - doesn't need LLM.
    """
    user_lower = user_input.lower()

    # Problem indicators
    if any(word in user_lower for word in ["problem", "issue", "bug", "broken", "doesn't work"]):
        if not self.gathered_info["problem"]["description"]:
            self.gathered_info["problem"]["description"] = user_input[:200]

    # Example indicators
    if any(word in user_lower for word in ["example", "for instance", "like when", "specifically"]):
        self.gathered_info["problem"]["examples"].append(user_input[:150])

    # User indicators
    if any(word in user_lower for word in ["users", "customers", "developers", "admins", "team"]):
        # Extract mentioned user types
        for user_type in ["users", "customers", "developers", "admins", "managers"]:
            if user_type in user_lower and user_type not in self.gathered_info["users"]["who"]:
                self.gathered_info["users"]["who"].append(user_type)

    # Requirement indicators
    if any(word in user_lower for word in ["should", "must", "need to", "has to", "require"]):
        self.gathered_info["requirements"]["must_have"].append(user_input[:150])

    # Success criteria indicators
    if any(word in user_lower for word in ["success", "done when", "complete when", "works if"]):
        self.gathered_info["requirements"]["success_criteria"].append(user_input[:150])

    # Edge case indicators
    if any(word in user_lower for word in ["what if", "edge case", "error", "fail", "wrong"]):
        self.gathered_info["edge_cases"].append(user_input[:150])

    # Update phase
    self.gathered_info["phase"] = self._detect_current_phase()

    # Identify gaps
    self._update_gaps()
```

### 4. Gap Identification

```python
def _update_gaps(self):
    """Identify what information is still missing."""
    gaps = []
    info = self.gathered_info

    if not info["problem"]["description"]:
        gaps.append("Problem description not clear")
    if not info["problem"]["examples"]:
        gaps.append("No concrete examples of the problem")
    if not info["users"]["who"]:
        gaps.append("Users not identified")
    if not info["requirements"]["must_have"]:
        gaps.append("Core requirements not defined")
    if not info["requirements"]["success_criteria"]:
        gaps.append("Success criteria not established")
    if len(info["edge_cases"]) < 2:
        gaps.append("Edge cases need more exploration")

    self.gathered_info["gaps"] = gaps
```

### 5. Condensed System Prompt (~200 lines)

```python
def _build_socrates_prompt(self) -> str:
    """Build a condensed, structured system prompt."""

    # Get current state
    phase = self.gathered_info["phase"]
    gaps = self.gathered_info["gaps"]

    return f'''You are Socrates, a requirements gathering specialist.

## STRICT RULES (NEVER VIOLATE)

❌ FORBIDDEN - Never say these:
- "You should..." / "I suggest..." / "Try using..."
- "The best approach is..." / "Let me help you implement..."
- Any implementation details (code, libraries, APIs, databases)

✅ REQUIRED - Always do these:
- Ask questions about WHAT and WHY, never HOW
- Use ✅ to acknowledge clear information
- Use ❓ to highlight what's still unclear
- Challenge vague answers: "Can you give a specific example?"
- One question at a time

## CURRENT STATE

**Phase:** {phase}
**Turn:** {len(self.conversation_history) // 2}

### Information Gathered:
{self._format_gathered_info()}

### Gaps to Fill (ask about these):
{self._format_gaps()}

## PHASE-SPECIFIC GUIDANCE

{self._get_phase_guidance(phase)}

## RESPONSE FORMAT

Always structure responses as:

✅ Clear: [What you understood from their answer]

❓ [Your follow-up question targeting a gap]

## EXAMPLES

Good response:
"✅ Clear: The API is slow, affecting user exports.

❓ When users experience this slowness, what specifically are they trying to export?
Is it small files that are slow, or does it only happen with large datasets?"

Bad response (NEVER DO THIS):
"You should add caching to the API. I suggest using Redis for this."

## TARGET FILE

Working on: {self.target_path}
Document type: {self.document_type}

Continue the requirements discovery dialogue. Ask ONE question targeting the gaps listed above.
'''
```

### 6. Conversation Compaction

```python
MAX_HISTORY_MESSAGES = 14  # 7 exchanges

def _compact_conversation_history(self):
    """Compact conversation history when it gets too long.

    Strategy:
    - Keep first 2 messages (context loading)
    - Keep last 8 messages (recent context)
    - Middle messages are "absorbed" into gathered_info
    """
    if len(self.conversation_history) <= MAX_HISTORY_MESSAGES:
        return  # No compaction needed

    logger.info(f"Compacting conversation from {len(self.conversation_history)} messages")

    # Extract info from middle messages before removing them
    middle_start = 2
    middle_end = len(self.conversation_history) - 8

    for i in range(middle_start, middle_end, 2):
        if i + 1 < len(self.conversation_history):
            user_msg = self.conversation_history[i].get("content", "")
            asst_msg = self.conversation_history[i + 1].get("content", "")
            self._extract_info_from_exchange(user_msg, asst_msg)

    # Keep first 2 + last 8
    first_messages = self.conversation_history[:2]
    recent_messages = self.conversation_history[-8:]

    # Add a summary message in between
    summary_msg = {
        "role": "assistant",
        "content": f"[Previous discussion summarized - gathered: {self._format_gathered_info_brief()}]"
    }

    self.conversation_history = first_messages + [summary_msg] + recent_messages
    logger.info(f"Compacted to {len(self.conversation_history)} messages")
```

### 7. Persona Reinforcement

```python
REMINDER_INTERVAL = 5  # Every 5 turns

def _maybe_inject_persona_reminder(self):
    """Inject persona reminder every N turns."""
    turn_count = len(self.conversation_history) // 2

    if turn_count > 0 and turn_count % REMINDER_INTERVAL == 0:
        reminder = '''[SOCRATES REMINDER]
You are Socrates - requirements gatherer only.
❌ Do NOT suggest solutions or implementations
✅ Ask about: problems, users, requirements, edge cases
Current phase: {phase}
Gaps to fill: {gaps}
Continue with ONE question.'''.format(
            phase=self.gathered_info["phase"],
            gaps=", ".join(self.gathered_info["gaps"][:3])
        )

        # Insert as system-style message
        self.conversation_history.append({
            "role": "user",  # Some models handle "system" mid-conversation poorly
            "content": reminder
        })
```

### 8. Updated `process()` Method

```python
async def process(self, user_input: str) -> str:
    """Process user response with state tracking and compaction."""
    logger.debug(f"Processing user input (length: {len(user_input)})")

    # Step 1: Add user message
    self.conversation_history.append({"role": "user", "content": user_input})

    # Step 2: Compact history if needed
    self._compact_conversation_history()

    # Step 3: Maybe inject persona reminder
    self._maybe_inject_persona_reminder()

    try:
        # Step 4: Get LLM response
        response = await self._conduct_dialogue(user_input)

        # Step 5: Extract info from this exchange
        self._extract_info_from_exchange(user_input, response)

        # Step 6: Add response to history
        self.conversation_history.append({"role": "assistant", "content": response})

        # Step 7: Check for summary/approval
        if self._is_showing_summary(response):
            self.shown_summary = True

        if self.shown_summary and self._user_approved(user_input):
            await self._generate_document_content()
            self.mark_complete()
            return self._get_completion_message()

        return response

    except Exception as e:
        logger.error(f"Error in Socrates dialogue: {e}", exc_info=True)
        return f"**Error:** {str(e)}\n\nPlease try again."
```

---

## File Changes Summary

### Modified Files

1. **`src/cdd_agent/agents/socrates.py`**
   - Replace `_build_socrates_prompt()` (780 lines → ~200 lines)
   - Implement `gathered_info` structure and methods
   - Add `_extract_info_from_exchange()`
   - Add `_detect_current_phase()`
   - Add `_update_gaps()`
   - Add `_compact_conversation_history()`
   - Add `_maybe_inject_persona_reminder()`
   - Update `process()` to use new flow
   - Add helper methods for formatting state

2. **`src/cdd_agent/session/base_agent.py`**
   - (Optional) Add `compact_history()` as base method

### New Constants

```python
# At top of socrates.py
MAX_HISTORY_MESSAGES = 14  # Compact when exceeds this
REMINDER_INTERVAL = 5      # Inject reminder every N turns
PHASES = ["problem_discovery", "user_analysis", "requirements", "edge_cases", "wrap_up"]
```

---

## Testing Strategy

### Unit Tests
1. Test `_extract_info_from_exchange()` with various inputs
2. Test `_detect_current_phase()` with different gathered_info states
3. Test `_compact_conversation_history()` preserves first/last messages
4. Test `_update_gaps()` correctly identifies missing info

### Integration Tests
1. Full conversation flow with mocked LLM
2. Verify persona maintained after 10+ exchanges
3. Verify compaction triggers at correct threshold
4. Verify phase transitions are correct

### Manual Testing
1. Test with GLM 4.6 - verify persona maintained
2. Test with Minimax M2 - verify persona maintained
3. Compare behavior with Claude (should be equivalent or better)

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Info extraction too simplistic | Start simple, iterate based on real usage |
| Compaction loses important context | Keep first 2 + last 8, summarize middle |
| Reminder injection feels unnatural | Use subtle format, only every 5 turns |
| Phase detection too rigid | Allow manual override, fuzzy matching |
| New prompt still too long | Further condense if needed, test iteratively |

---

## Success Criteria

1. ✅ Socrates maintains persona for 20+ exchanges with GLM 4.6
2. ✅ Socrates maintains persona for 20+ exchanges with Minimax M2
3. ✅ `gathered_info` correctly tracks conversation state
4. ✅ Phase transitions happen at appropriate times
5. ✅ Summary generation includes all gathered information
6. ✅ No regression with Claude/GPT models
7. ✅ All existing tests pass

---

## Implementation Order

1. **Phase 1**: Add `gathered_info` structure and extraction (low risk)
2. **Phase 2**: Implement conversation compaction (medium risk)
3. **Phase 3**: Replace system prompt with condensed version (higher risk)
4. **Phase 4**: Add persona reinforcement (low risk)
5. **Phase 5**: Test with weak models, iterate

Each phase can be tested independently before moving to the next.
