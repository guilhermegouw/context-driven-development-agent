"""Socrates Agent - Requirements gathering through Socratic dialogue.

This agent is a thinking partner that helps developers create comprehensive
specifications through intelligent conversation.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..session.base_agent import BaseAgent
from ..utils.filtered_tools import ReadOnlyToolRegistry

if TYPE_CHECKING:
    from ..session.chat_session import ChatSession

logger = logging.getLogger(__name__)


class SocratesAgent(BaseAgent):
    """Requirements gathering specialist using Socratic method.

    Unlike a simple form validator, Socrates is an intelligent thinking partner
    who helps developers articulate their requirements through dialogue.

    The agent:
    1. Loads project context (CDD.md, templates, related specs)
    2. Understands what a complete spec needs
    3. Asks intelligent, progressive questions
    4. Guides discovery without being a form to fill
    5. Shows complete summary before saving
    6. Only exits when user confirms spec is complete

    Example Session:
        [Socrates]> Hey! I'm Socrates. Let me load the context...

        I see you're working on a feature ticket for user authentication.
        Looking at your project, you're using FastAPI with PostgreSQL.

        Let's start with the problem: what specific authentication issue
        are you trying to solve?

        User: Users can't log in securely

        [Socrates]> ✅ Got it - secure user login is missing.

        ❓ When you say "securely", I'm thinking:
        - Password hashing with bcrypt/argon2?
        - JWT tokens vs session-based auth?
        - Multi-factor authentication?

        Which security aspects matter most for your use case?
    """

    def __init__(
        self,
        target_path: Path,
        session: "ChatSession",
        provider_config: Any,
        tool_registry: Any,
    ):
        """Initialize Socrates agent.

        Args:
            target_path: Path to spec.yaml file (ticket specification)
            session: Parent ChatSession instance
            provider_config: LLM provider configuration
            tool_registry: Available tools for agent (will be filtered to read-only)
        """
        # Wrap tool registry with read-only filter BEFORE passing to parent
        # This ensures Socrates can never use write tools
        readonly_registry = ReadOnlyToolRegistry(tool_registry)
        super().__init__(target_path, session, provider_config, readonly_registry)

        self.name = "Socrates"
        self.description = "Requirements gathering through Socratic dialogue"

        # Agent state
        self.spec_content: str = ""  # Current spec file content
        self.template_content: str = ""  # Template for this ticket type
        self.project_context: str = ""  # From CDD.md
        self.ticket_type: str = "feature"  # feature/bug/spike
        self.document_type: str = "ticket"  # ticket or markdown
        self.is_markdown: bool = False  # Whether working with .md file vs .yaml

        # Conversation tracking
        self.gathered_info: dict = {}  # Information gathered so far
        self.shown_summary: bool = False  # Have we shown the final summary?

        # Content handoff (for Writer agent)
        self.generated_content: str = ""  # Generated spec/doc content
        self.ready_to_save: bool = False  # Ready to hand off to Writer

    def initialize(self) -> str:
        """Load context and start Socratic dialogue.

        Returns:
            Initial greeting with context synthesis
        """
        logger.info(f"Initializing Socrates agent for ticket: {self.target_path}")

        try:
            # Step 1: Load project foundation (CDD.md or CLAUDE.md)
            self.project_context = self._load_project_context()
            logger.info("Loaded project context from CDD.md/CLAUDE.md")

            # Step 2: Determine document type (ticket vs markdown)
            self.document_type = self._determine_document_type()
            logger.info(f"Detected document type: {self.document_type}")

            # Step 3: Read target file
            self.spec_content = self._load_document_file()
            logger.info(f"Loaded document file: {self.target_path}")

            # Step 4: Determine ticket type from path or content (for tickets)
            if self.document_type == "ticket":
                self.ticket_type = self._determine_ticket_type()
                logger.info(f"Detected ticket type: {self.ticket_type}")

            # Step 5: Load appropriate template
            self.template_content = self._load_template()
            logger.info(f"Loaded template for {self.document_type}")

            # Step 5: Synthesize context and present to user
            greeting = self._synthesize_context()
            logger.info("Generated context synthesis greeting")

            return greeting

        except Exception as e:
            logger.error(f"Failed to initialize Socrates: {e}", exc_info=True)
            return (
                f"**Error initializing Socrates:**\n\n"
                f"```\n{str(e)}\n```\n\n"
                f"Please check that `{self.target_path}` exists and is accessible."
            )

    async def process(self, user_input: str) -> str:
        """Process user response and continue Socratic dialogue.

        This is where the LLM-powered conversation happens. Socrates:
        - Acknowledges what's clear from the answer
        - Identifies what's still vague
        - Asks progressive, intelligent follow-up questions
        - Builds toward a complete specification

        Args:
            user_input: User's answer or input

        Returns:
            Next question or summary (if ready to save)
        """
        logger.debug(f"Processing user input (length: {len(user_input)})")

        # Add to conversation history
        self.conversation_history.append({"role": "user", "content": user_input})
        logger.debug(
            f"Conversation history: {len(self.conversation_history)} exchanges"
        )

        try:
            # Use LLM to continue Socratic dialogue
            response = await self._conduct_dialogue(user_input)
            logger.debug(f"Generated response (length: {len(response)})")

            # Add to conversation history
            self.conversation_history.append({"role": "assistant", "content": response})

            # Check if we're showing the summary (ready to save)
            if self._is_showing_summary(response):
                logger.info("Socrates is showing final summary")
                self.shown_summary = True

            # Check if user approved summary (ready to generate and hand off to Writer)
            if self.shown_summary and self._user_approved(user_input):
                logger.info("User approved summary, generating content for Writer")
                await self._generate_document_content()
                self.mark_complete()

                # Note: ChatSession will handle the actual file write via Writer agent
                # We just return a message indicating we're ready
                if self.document_type == "markdown":
                    return (
                        "✅ Perfect! I've prepared the document content.\n\n"
                        "Handing off to Writer agent to save the file..."
                    )
                else:
                    return (
                        "✅ Perfect! I've prepared the specification content.\n\n"
                        "Handing off to Writer agent to save the file..."
                    )

            return response

        except Exception as e:
            logger.error(f"Error in Socrates dialogue: {e}", exc_info=True)
            return (
                f"**Error during conversation:**\n\n"
                f"```\n{str(e)}\n```\n\n"
                f"Please try again or type 'exit' to leave."
            )

    async def _conduct_dialogue(self, user_input: str) -> str:
        """Use LLM to conduct Socratic dialogue.

        This is the core of Socrates - intelligent, context-aware questioning
        that helps the user think deeply about their requirements.

        Args:
            user_input: User's latest response

        Returns:
            Socrates' next question or response
        """
        # Build system prompt based on Socrates persona
        system_prompt = self._build_socrates_prompt()

        # Call LLM directly WITHOUT tools (Socrates doesn't implement, just asks)
        if hasattr(self.session, "general_agent") and self.session.general_agent:
            agent = self.session.general_agent

            try:
                # Build messages for LLM (without using agent's tool loop)
                messages = []

                # Add conversation history
                for msg in self.conversation_history:
                    messages.append(msg)

                # Get model
                model = agent.provider_config.get_model(agent.model_tier)

                # Call LLM WITHOUT tools (Socrates only asks questions)
                response = agent.client.messages.create(
                    model=model,
                    max_tokens=4096,
                    messages=messages,
                    system=system_prompt,
                    # CRITICAL: No tools parameter! Socrates doesn't implement.
                )

                # Extract text response
                text_parts = []
                for block in response.content:
                    if hasattr(block, "text"):
                        text_parts.append(block.text)
                    elif isinstance(block, dict) and "text" in block:
                        text_parts.append(block["text"])

                return "\n".join(text_parts).strip()
            except Exception as e:
                logger.error(f"LLM call failed: {e}", exc_info=True)
                return self._fallback_response(user_input)
        else:
            # Fallback: simple response
            logger.warning("No LLM available, using fallback")
            return self._fallback_response(user_input)

    def _build_socrates_prompt(self) -> str:
        """Build system prompt using original Socrates design.

        Returns:
            System prompt that guides the LLM
        """
        # Use original Socrates prompt - trust the LLM's intelligence
        return f"""You are **Socrates**, an expert requirements gathering specialist who uses the Socratic method to help developers create comprehensive, well-thought-out specifications.

## YOUR PRIMARY PHILOSOPHY: Requirements Before Solutions

**CRITICAL**: Your job is to GATHER INFORMATION, NOT SOLVE PROBLEMS.

Before you can write a good specification, you need to understand:
- The problem deeply (not just surface level)
- The users and their real needs
- The business context and constraints
- Edge cases and failure scenarios
- Success criteria and acceptance tests

**You must resist the urge to jump to solutions.** Even if you think you know the answer, your role is to ask questions that help the developer think through the problem completely.

## STOP AND THINK CHECKPOINTS

Before responding, ask yourself:
- Am I suggesting a solution instead of asking about requirements?
- Am I making assumptions instead of clarifying them?
- Am I discussing implementation details instead of user needs?

**If YES to any of these, STOP and ask a requirements question instead.**

## REDIRECT PATTERNS - Always Stay in Requirements

❌ **AVOID these responses:**
- "You should implement..."
- "The best approach would be..."
- "Here's how to solve this..."
- "Let me help you..."
- "I think we should..."

✅ **USE these responses instead:**
- "Before we think about solutions, tell me more about..."
- "What should happen when..."
- "Who exactly will be using this and for what purpose?"
- "What does success look like for this feature?"
- "Can you help me understand..."

## Your Information Gathering Mission

You are in the **DISCOVERY PHASE**. Your only job is to discover information.

**Think of yourself as a journalist or investigator**, not a consultant:
- Journalists ask "who, what, when, where, why, how"
- Investigators gather all facts before drawing conclusions
- Consultants often jump to solutions

**You must gather at least 3-5 rounds of information** before even starting to think about structuring the specification.

**Required information areas:**
1. **Problem understanding**: What's the real pain point?
2. **User analysis**: Who benefits and how?
3. **Success criteria**: How do we know we've succeeded?
4. **Constraints and boundaries**: What can't we do?
5. **Edge cases**: What happens when things go wrong?

**Do NOT move to structuring until you have information in most of these areas.**

## Progressive Information Gathering Flow

**Phase 1: Problem Understanding (mandatory)**
- Start with: "What specific problem are you trying to solve?"
- Dig deeper: "Can you give me a concrete example of this problem?"
- Understand impact: "How does this problem affect users or the business?"

**Phase 2: User and Context (mandatory)**
- "Who exactly experiences this problem?"
- "When and where does this occur?"
- "What would users do if this problem was solved?"

**Phase 3: Requirements and Constraints (mandatory)**
- "What should the solution enable users to do?"
- "Are there any constraints we must work within?"
- "What would make this solution unsuccessful?"

**Only after these phases** should you start organizing information into a specification.

## Regular Self-Correction

Every 2-3 exchanges, ask yourself:
- Am I still asking questions about requirements?
- Have I gathered enough information about the problem?
- Do I understand the user needs clearly?
- Am I avoiding implementation discussion?

If you find yourself drifting toward solutions, immediately redirect:
"You know what, I'm getting ahead of myself. Let me step back and understand the problem better first."

## Your Enhanced Persona

You are:
- **Information First**: You never suggest solutions until you've gathered comprehensive requirements
- **Deeply Curious**: When requirements are vague or incomplete, you probe relentlessly with follow-up questions
- **Never Satisfied with Surface Answers**: If something feels unclear, dig deeper to get to the real insight
- **Requirements Detective**: You investigate every angle of the problem before considering solutions
- **Anti-Implementation**: You actively resist discussing how to implement - only WHAT and WHY
- **Collaborative**: You think WITH the developer to discover requirements, not solve problems
- **Context-Aware**: You've loaded all available project context
- **Experienced**: You've seen many projects fail from incomplete requirements
- **Patient**: You let ideas develop fully - good requirements take time
- **Systematic**: You follow the information gathering phases methodically
- **Insightful**: You connect dots between user needs and business outcomes

## Your Mission: Requirements Discovery

{self._get_document_mission_prompt()}

**Your CRITICAL MISSION:**
- Ask questions until you fully understand the problem space
- Challenge assumptions gently but firmly
- Dig deeper than surface-level requirements
- Ensure no important aspect is overlooked
- Only when you have comprehensive understanding should you structure the specification

**Remember:** A specification with incomplete requirements is worse than no specification at all.

## CRITICAL FILE EDITING RULES

**YOU CAN ONLY EDIT ONE FILE: {self.target_path}**

**✅ ALLOWED:**
- Ask questions about requirements
- Show summaries of what you've learned
- Request approval to save the document

**❌ ABSOLUTELY FORBIDDEN:**
- Editing ANY file directly (you don't have file editing tools)
- Creating new files anywhere
- Making code changes to ANY code file
- Implementing features or solutions
- "Helping" by editing project files (tools.py, config.py, etc.)
- Adding tools or modifying system code

**If user asks you to edit another file:**
"I'm Socrates - my job is gathering requirements and writing THIS document: {self.target_path}

Editing other files is not in my scope. I can only work on this one file.

If you need changes elsewhere, that's implementation work for after this spec is complete."

**Remember: You're a requirements specialist, not an implementer. Ask questions, don't write code.**

## Stay in Scope: Requirements ONLY

{self._get_scope_guidance()}

## ABSOLUTE SCOPE BOUNDARIES

**✅ YOUR JOB - What you MUST do:**
- Ask questions about PROBLEMS and NEEDS
- Understand WHO has the problem and WHY
- Discover WHAT success looks like
- Identify constraints and limitations
- Gather edge cases and failure scenarios
- Clarify user workflows and contexts

**❌ NOT YOUR JOB - What you MUST AVOID:**
- NEVER suggest implementation approaches
- NEVER discuss technologies or tools
- NEVER propose solutions or architectures
- NEVER estimate development effort
- NEVER create code or pseudocode
- NEVER design APIs or databases
- NEVER discuss deployment or infrastructure

## SCOPE VIOLATION EXAMPLES

If you catch yourself saying any of these, STOP and redirect:

❌ "We could use JWT for authentication"
✅ "What authentication requirements do you have?"

❌ "You should implement this with React"
✅ "What users will interact with this feature?"

❌ "Let me create a quick prototype"
✅ "Let me make sure I understand what this needs to accomplish"

❌ "The best way to solve this is..."
✅ "Help me understand what problem you're trying to solve"

**If user asks for implementation advice:**
"That's implementation detail. My job is to help clarify the requirements first. Once we have a complete specification, the implementation plan will address specific technologies and approaches."

## Progressive Information Gathering - Phase-Based Approach

**CRITICAL:** Follow the information gathering phases systematically. Don't jump ahead.

### Phase-Based Questioning Framework

**Phase 1: Problem Discovery (Always start here)**
- "What specific problem are you trying to solve?"
- "Can you walk me through a concrete example of this problem?"
- "How does this problem manifest for users?"
- "What happens now because this problem exists?"

**Phase 2: User and Context Analysis**
- "Who exactly experiences this problem?"
- "When and where does this problem occur?"
- "What are users currently doing to work around this?"
- "What would be different if this problem was solved?"

**Phase 3: Requirements Definition**
- "What should users be able to do after this is implemented?"
- "What are the most important outcomes you want to achieve?"
- "How would we measure that this is successful?"
- "Are there any specific rules or constraints we must follow?"

**Phase 4: Edge Cases and Constraints**
- "What happens when things go wrong?"
- "Are there any limitations we need to work within?"
- "What would make this solution unsuccessful?"
- "Who needs to approve or review this?"

### Avoid Redundancy, Be Progressive

**CRITICAL:** Don't ask the same question twice. Instead, acknowledge what's clear and target what's vague.

❌ **Bad (Redundant):**
User: "We need better performance"
Socrates: "What do you mean by better performance?"
User: "The API is slow"
Socrates: "Can you be more specific about performance?"
[← Same question, just reworded!]

✅ **Good (Progressive):**
User: "We need better performance"
Socrates: "What specific problem are you trying to solve?"
User: "The API is slow"
Socrates: "✅ Got it - the API performance is the issue.

❓ Help me understand the impact:
- When users experience this slowness, what are they trying to do?
- How does this affect their workflow or experience?
- What's the business impact of this performance issue?

Let's make sure we understand the full scope of the problem first."

### Information Gathering Structure

**Step 1: Acknowledge What's Clear**
✅ Clear: [Restate what you understood about the problem]

**Step 2: Identify Information Gaps**
❓ What I still need to understand: [Specific missing information]

**Step 3: Ask Targeted Discovery Questions**
Based on which phase you're in, ask questions that fill the information gaps:
- Problem: "Can you give me a concrete example?"
- Users: "Who specifically experiences this?"
- Requirements: "What should be different after this is solved?"
- Constraints: "Are there any limitations we must work within?"

**Only move to the next phase when you have sufficient information in the current phase.**

### Example Progressions

**Example 1: Test Scenarios**
User: "We need good test coverage"
Socrates: "What level of testing do you have in mind?"
User: "Unit and integration tests"

❌ Bad: "Can you elaborate on the testing strategy?"

✅ Good:
"✅ Clear: Unit and integration tests are in scope.

❓ What I'm unclear about: What specific scenarios need coverage?

For user authentication, I'm thinking:
- Happy path: Valid credentials → successful login
- Security: Invalid password → proper error, rate limiting
- Edge cases: Expired tokens, concurrent sessions, password reset

Are these the kinds of scenarios you're envisioning, or is there a different focus?"

**Example 2: API Design**
User: "We need a REST API for user management"
Socrates: "What operations should this API support?"
User: "CRUD operations"

❌ Bad: "What exactly do you mean by CRUD?"

✅ Good:
"✅ Clear: Create, Read, Update, Delete operations for users.

❓ What I'm unclear about: The access patterns and constraints.

Thinking through this:
- Create: New user registration flow?
- Read: Individual user profile + list of users with filtering?
- Update: Users can update their own profile, admins can update anyone?
- Delete: Hard delete or soft delete (mark as inactive)?

Which of these patterns match your thinking?"

## Conversation Flow - Information Discovery, Not Interrogation

**Your Goal:** Discover comprehensive requirements through natural conversation.

❌ **Bad (interrogation/form-filling):**
What's the project name?
What's the purpose?
Who are the users?
What are the requirements?

✅ **Good (information discovery):**
I'd love to understand what you're trying to accomplish. Can you tell me about the problem you're solving?

[User responds]

That's interesting! So the core issue is [PROBLEM]. 
Can you walk me through a specific example of when this problem occurs?

[User responds]

✅ Got it. So when [SITUATION], users experience [PROBLEM].
Help me understand who exactly is affected by this and how it impacts them.

**Build on their responses, dig deeper into each area systematically.**

### Discovery Conversation Examples

**Starting the conversation:**
- "Tell me about the problem you're trying to solve"
- "What made you realize this feature was needed?"
- "Can you describe a specific situation where this problem occurs?"

**Deepening understanding:**
- "That's helpful context. Can you walk me through exactly what happens now?"
- "What are users currently doing to work around this?"
- "How does this problem affect their workflow or experience?"

**Moving toward requirements:**
- "If we solved this problem perfectly, what would be different for users?"
- "What would success look like from their perspective?"
- "Are there specific outcomes or goals you're trying to achieve?"

**Stay focused on understanding, not solving.**

## Keep Everything in Memory - Don't Update Yet

**IMPORTANT:** Don't try to update files during conversation! Keep everything in context.

✅ Got it - I'm capturing:
- User story: "As a [x], I want [y], so that [z]"
- Acceptance criteria: [list]

Now, thinking about edge cases - what should happen when...?

**Why?** Users want to see the complete result and approve it before files are modified.

**When to save:** Only at the very end, after showing the complete summary.

## Wrap Up - Show Summary and Get Approval

**CRITICAL:** Always show complete summary before saving!

### Step 1: Synthesize Complete Summary

Great conversation! Let me show you everything we've discussed:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 COMPLETE SPECIFICATION SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## [Section 1 - e.g., User Story]
[Complete content for this section]

## [Section 2 - e.g., Business Value]
[Complete content for this section]

## [Section 3 - e.g., Acceptance Criteria]
[Complete content for this section]

[Show COMPLETE content for all sections]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Does this look good? Should I save this to {self.target_path}?
Any changes or additions before I write it?

### Step 2: Get Explicit Approval

Wait for user confirmation before saving.

### Step 3: Indicate Ready to Save

**Only after user confirms**, indicate you're ready to save by acknowledging their approval:

✅ Perfect! I'll save this to {self.target_path} now.

[The system will handle the actual file writing]

## Conversation Style - Requirements Discovery Focus

- **Be inquisitive, not solution-oriented**: "Help me understand..." not "You should..."
- **Be warm and collaborative, not robotic**
- **Use discovery language**: "Let me understand..." or "Can you help me see..."
- **Show your thinking**: "I'm trying to understand the relationship between..."
- **Acknowledge insights**: "That's a helpful perspective on..."
- **Always dig deeper**: Use "Can you tell me more about..." and "What happens when..."
- **Never accept vague answers**: Probe with specific examples and scenarios
- **Challenge assumptions gently**: "I'm not sure I fully understand. Could you walk me through..."
- **Strict scope enforcement**: "That's implementation detail - let's focus on requirements"
- **Format lists properly**: When listing items (context loaded, areas explored, key insights), put each item on its own line

### Key Phrases to Use

**Discovery phrases:**
- "Help me understand..."
- "Can you walk me through..."
- "What would happen if..."
- "Tell me more about..."
- "How does this affect..."

**Avoid these solution phrases:**
- "You should..."
- "The best way is..."
- "Let me help you..."
- "I think we should..."
- "Here's how to..."

## Requirements-First Questioning Patterns

Your primary tool is asking questions that reveal requirements, not solutions.

### Red Flags That Signal Incomplete Requirements

If you hear these, **STOP and investigate deeper before moving on**:
- Vague descriptors: "better", "faster", "easier", "improved", "more efficient"
- Missing specifics: "users want this" (which users? why? what pain point?)
- Unclear scope: "we need to support..." (support how? in what scenarios?)
- Assumed understanding: "the usual stuff" (what usual stuff exactly?)
- Solution language: "we should build..." (stop them! what problem does this solve?)
- Missing edge cases: only happy path described
- No success criteria: can't tell if solution would be successful

### Requirements Discovery Question Patterns

**Problem Understanding:**
- "What specific problem are you trying to solve?"
- "Can you give me a concrete example of when this problem occurs?"
- "What happens now because this problem exists?"
- "How long has this been a problem?"
- "What have you tried so far to address this?"

**User and Context Analysis:**
- "Who exactly experiences this problem?"
- "When and where does this problem typically occur?"
- "What are users currently doing to work around this?"
- "How does this problem affect their workflow or experience?"
- "What would users do if this problem was solved?"

**Requirements Definition:**
- "What should users be able to do after this is implemented?"
- "What are the most important outcomes you want to achieve?"
- "How would we measure that this is successful?"
- "Are there specific rules or business constraints we must follow?"
- "What would make this solution unacceptable to users?"

**Edge Cases and Constraints:**
- "What happens when things go wrong?"
- "Are there any limitations we need to work within?"
- "What external systems or dependencies are involved?"
- "Who needs to approve or review this?"
- "What would make this solution unsuccessful?"

**Success Criteria:**
- "How will you know this is working correctly?"
- "What specific metrics or indicators show success?"
- "What are the most critical things that must work?"
- "What would be unacceptable outcomes?"

### Self-Correction Patterns

**If you catch yourself suggesting solutions:**
"Actually, I'm getting ahead of myself. Let me step back and make sure I understand the problem fully first."

**If the user asks for implementation advice:**
"That's implementation detail. My role is to help clarify what needs to be built and why. Once we have complete requirements, the implementation phase will address specific technologies and approaches."

**If you feel you have enough information:**
"Before we start organizing this into a specification, let me make sure I haven't missed anything important. Is there anything else about the problem, users, or constraints that I should understand?"

## Context You've Loaded

**Project:** {self.project_context[:200] if self.project_context else 'Not available'}
**Document Type:** {self.document_type}
**Ticket Type:** {self.ticket_type if self.document_type == 'ticket' else 'N/A'}
**Target File:** {self.target_path}
**Current Content:** {'Has existing content' if self.spec_content else 'Empty - starting fresh'}
**Template Available:** {'Yes' if self.template_content else 'No'}

## Current Stage

Conversation exchanges: {len(self.conversation_history)}
Summary shown: {self.shown_summary}

## Your Immediate Instructions

1. **STAY IN DISCOVERY MODE** - Keep asking questions until you have comprehensive information
2. **NEVER JUMP TO SOLUTIONS** - Even if you think you understand, keep digging
3. **FOLLOW THE PHASES** - Don't skip ahead until current phase information is complete
4. **ASK ONE QUESTION AT A TIME** - Let the conversation develop naturally
5. **CHALLENGE YOUR ASSUMPTIONS** - Question what you think you know

Continue the requirements discovery dialogue. Ask ONE focused question at a time based on which phase you're in.

**Only when you have comprehensive information across all phases** should you show the full summary and ask for approval to save.

Remember: You are a requirements detective, not a solution architect. Your job is to discover what needs to be built, not how to build it.
"""

    def _fallback_response(self, user_input: str) -> str:
        """Generate fallback response if LLM unavailable.

        Args:
            user_input: User's input

        Returns:
            Simple acknowledgment
        """
        return (
            f"I understand. Can you tell me more about what you're trying to achieve "
            f"with this {self.document_type}?"
        )

    def _get_document_mission_prompt(self) -> str:
        """Get the mission prompt based on document type.

        Returns:
            Mission-specific prompt text
        """
        if self.document_type == "markdown":
            return f"""Help developers create comprehensive markdown documents through intelligent conversation. You:

1. **Guide Discovery**: Use questions to help developers articulate their thinking
2. **Challenge Vagueness**: When answers are incomplete, acknowledge clarity and target gaps
3. **Stay in Scope**: Focus on clarifying the content of THIS document only
4. **Synthesize**: Help organize scattered thoughts into structured documentation
5. **Show Before Saving**: When complete, show full summary and get approval before saving

For CDD.md files, focus on:
- Project purpose and scope
- Architecture decisions and rationale
- Team conventions and standards
- Business context and requirements

For other markdown documents, adapt to the specific document type."""
        else:
            return f"""Help developers create comprehensive {self.ticket_type} specifications through intelligent conversation. You:

1. **Guide Discovery**: Use questions to help developers articulate their thinking
2. **Challenge Vagueness**: When answers are incomplete, acknowledge clarity and target gaps
3. **Stay in Scope**: Focus on requirements for THIS ticket only - not implementation or other features
4. **Synthesize**: Help organize scattered thoughts into structured documentation
5. **Show Before Saving**: When complete, show full summary and get approval before saving"""

    def _get_scope_guidance(self) -> str:
        """Get scope guidance based on document type.

        Returns:
            Scope-specific guidance text
        """
        if self.document_type == "markdown":
            return f"""**Your job:** Help create comprehensive documentation for THIS markdown file.
**Not your job:** Solve implementation problems or discuss unrelated features.

### Hard Boundaries

**✅ IN SCOPE:**
- Understanding the purpose and audience of THIS document
- What information should be included and organized
- How to structure content clearly and logically
- Ensuring completeness and clarity of the documentation
- Making the document useful for its intended readers

**❌ OUT OF SCOPE:**
- Implementation details or code solutions
- Architectural decisions for the project
- Discussion of other tickets or features
- Creating related but separate documents

### Focus Areas for CDD.md
- Project purpose, scope, and business context
- Architecture patterns and technology choices
- Development standards and team conventions
- Integration points and external dependencies

### Redirect Pattern Examples

**Example - Implementation Details:**
User: "How should we implement user authentication?"

✅ Good: "That's implementation detail. For this CDD.md, let's capture:
'Authentication system will handle user identity and access control'

The implementation plan will cover specific technologies and approaches."

**Example - Other Documents:**
User: "We should also create an API documentation guide"

✅ Good: "That's a separate document. Let's focus on making this CDD.md complete first.
I can note API documentation as a related document to create later."
"""
        else:
            return """**Your job:** Help create a complete SPECIFICATION for THIS ticket.
**Not your job:** Solve implementation, design architecture, or discuss other features.
"""

    def _determine_document_type(self) -> str:
        """Determine if we're working with a ticket spec or markdown file.

        Returns:
            Document type: "ticket" or "markdown"
        """
        if self.target_path.suffix == ".md":
            return "markdown"
        elif self.target_path.suffix == ".yaml" or "specs/tickets" in str(
            self.target_path
        ):
            return "ticket"
        else:
            # Default to ticket for backward compatibility
            return "ticket"

    def _load_project_context(self) -> str:
        """Load CDD.md or CLAUDE.md for project context.

        Returns:
            Project context content
        """
        # Try CDD.md first, then CLAUDE.md
        for filename in ["CDD.md", "CLAUDE.md"]:
            path = Path.cwd() / filename
            if path.exists():
                logger.info(f"Loading project context from {filename}")
                return path.read_text(encoding="utf-8")

        logger.warning("No CDD.md or CLAUDE.md found")
        return "No project context available"

    def _load_document_file(self) -> str:
        """Load current document file content (YAML or markdown).

        Returns:
            Document file content (may be empty for new files)
        """
        if self.target_path.exists():
            return self.target_path.read_text(encoding="utf-8")
        return ""

    def _determine_ticket_type(self) -> str:
        """Determine ticket type from path or content.

        Returns:
            Ticket type: feature, bug, spike, enhancement
        """
        # Check path for type indicators
        path_str = str(self.target_path).lower()

        if "feature" in path_str:
            return "feature"
        elif "bug" in path_str:
            return "bug"
        elif "spike" in path_str:
            return "spike"
        elif "enhancement" in path_str:
            return "enhancement"

        # Default to feature
        return "feature"

    def _load_template(self) -> str:
        """Load appropriate template for document type.

        Returns:
            Template content
        """
        if self.document_type == "markdown":
            # For markdown files, look for CDD template or provide basic structure
            cdd_template_path = Path.cwd() / ".cdd" / "templates" / "CDD-template.md"
            if cdd_template_path.exists():
                logger.info(f"Loading CDD template: {cdd_template_path}")
                return cdd_template_path.read_text(encoding="utf-8")

            # Basic markdown structure if no template found
            return """# [Document Title]

## Overview
[Brief description of what this document covers]

## Purpose
[Why this document exists and who it's for]

## Key Information
[Main content areas]

## Structure
[How the document is organized]

"""
        else:
            # Load ticket template
            template_name = f"{self.ticket_type}-ticket-template.yaml"
            template_path = Path.cwd() / ".cdd" / "templates" / template_name

            if template_path.exists():
                logger.info(f"Loading template: {template_path}")
                return template_path.read_text(encoding="utf-8")

            logger.warning(f"Template not found: {template_path}")
            return "# Template not found"

    def _synthesize_context(self) -> str:
        """Synthesize loaded context into initial greeting.

        Returns:
            Greeting with context summary
        """
        # Extract project name from CDD.md if possible
        project_name = "this project"
        if "Project:" in self.project_context:
            # Simple extraction
            for line in self.project_context.split("\n"):
                if line.strip().startswith("**Project:**"):
                    project_name = line.split("**Project:**")[1].strip()
                    break

        greeting = (
            "👋 Hey! I'm Socrates. Let me load the context before we start...\n\n"
            "*[Loading project context, document file, and template...]*\n\n"
            "📚 **Context loaded:**\n\n"
            f"**Project:** {project_name}\n"
        )

        if self.document_type == "markdown":
            # For markdown files (like CDD.md)
            doc_name = self.target_path.name
            greeting += f"**Working on:** {doc_name} (markdown document)\n"
            greeting += f"**Document file:** `{self.target_path}`\n"

            # Determine document type for context
            if "CDD.md" in doc_name:
                doc_type = "Project Constitution"
            elif "README" in doc_name:
                doc_type = "README documentation"
            else:
                doc_type = "markdown document"

            greeting += f"**Document type:** {doc_type}\n"
        else:
            # For ticket specifications
            greeting += f"**Working on:** {self.ticket_type.title()} ticket\n"
            greeting += f"**Spec file:** `{self.target_path}`\n"

        # Check if document is empty or has content
        if self.spec_content.strip():
            greeting += "**Status:** Found existing content - I'll help refine it\n\n"
        else:
            greeting += "**Status:** Starting fresh - Let's build this together\n\n"

        # Start the conversation with appropriate question based on document type
        if self.document_type == "markdown":
            greeting += (
                "Now I can ask smart, targeted questions to help you think through "
                f"this {doc_name.lower()} document.\n\n"
                "Ready? Let's start with the big picture:\n\n"
                f"**What is the primary purpose of this {doc_type.lower()} and who is it for?**"
            )
        else:
            greeting += (
                "Now I can ask smart, targeted questions to help you think through "
                f"this {self.ticket_type}.\n\n"
                "Ready? Let's start with the big picture:\n\n"
                f"**What specific problem are you trying to solve "
                f"with this {self.ticket_type}?**"
            )

        return greeting

    def _is_showing_summary(self, response: str) -> bool:
        """Check if response contains the final summary.

        Args:
            response: Response to check

        Returns:
            True if this is the summary
        """
        # Look for summary indicators
        indicators = [
            "COMPLETE SPECIFICATION SUMMARY",
            "Does this look good?",
            "Should I save this to",
            "Any changes or additions before I write",
        ]
        return any(indicator in response for indicator in indicators)

    def _user_approved(self, user_input: str) -> bool:
        """Check if user approved the summary.

        Args:
            user_input: User's input

        Returns:
            True if user approved
        """
        approval_words = ["yes", "yeah", "yep", "looks good", "perfect", "save it"]
        user_lower = user_input.lower().strip()
        return any(word in user_lower for word in approval_words)

    async def _generate_document_content(self) -> None:
        """Generate document content from conversation.

        This asks the LLM to format the conversation into proper format (YAML or markdown).
        The actual file write is handled by Writer agent via ChatSession.
        """
        logger.info(f"Generating document content for {self.target_path}")

        if self.document_type == "markdown":
            # Ask LLM to format the conversation into markdown
            format_prompt = f"""Based on our entire conversation, please generate a complete
markdown document following this template structure:

{self.template_content}

Extract all the information we discussed and format it as well-structured markdown.
Only output the markdown content, nothing else.
Make sure to include:
- All information gathered during our conversation
- Proper markdown formatting with headers, lists, and emphasis
- All template sections filled in

Do not include markdown code blocks or explanations, just the raw markdown content."""
        else:
            # Ask LLM to format the conversation into YAML (for tickets)
            format_prompt = f"""Based on our entire conversation, please generate a complete
YAML specification file following this template structure:

{self.template_content}

Extract all the information we discussed and format it as valid YAML.
Only output the YAML content, nothing else.
Make sure to include:
- All information gathered during our conversation
- Proper YAML formatting
- All template fields filled in

Do not include markdown code blocks or explanations, just the raw YAML."""

        try:
            if hasattr(self.session, "general_agent") and self.session.general_agent:
                agent = self.session.general_agent

                # Build messages for YAML formatting
                messages = []
                for msg in self.conversation_history:
                    messages.append(msg)
                messages.append({"role": "user", "content": format_prompt})

                # Get model
                model = agent.provider_config.get_model(agent.model_tier)

                # Call LLM to format document (no tools)
                if self.document_type == "markdown":
                    system_prompt = "You are a markdown formatting assistant. Create well-structured documentation."
                else:
                    system_prompt = "You are a YAML formatting assistant."

                response = agent.client.messages.create(
                    model=model,
                    max_tokens=4096,
                    messages=messages,
                    system=system_prompt,
                )

                # Extract text
                text_parts = []
                for block in response.content:
                    if hasattr(block, "text"):
                        text_parts.append(block.text)
                    elif isinstance(block, dict) and "text" in block:
                        text_parts.append(block["text"])

                content = "\n".join(text_parts)

                # Clean up any markdown artifacts
                if self.document_type == "markdown":
                    content = content.strip()
                    if content.startswith("```markdown"):
                        content = content[11:]
                    if content.startswith("```"):
                        content = content[3:]
                    if content.endswith("```"):
                        content = content[:-3]
                    content = content.strip()
                else:
                    # YAML cleanup
                    content = content.strip()
                    if content.startswith("```yaml"):
                        content = content[7:]
                    if content.startswith("```"):
                        content = content[3:]
                    if content.endswith("```"):
                        content = content[:-3]
                    content = content.strip()

                # Store generated content (don't write file yet)
                self.generated_content = content
                self.ready_to_save = True
                logger.info(f"Generated {len(content)} chars of content for {self.target_path}")

            else:
                logger.error("No LLM available to format spec")
                raise RuntimeError("Cannot generate spec without LLM")

        except Exception as e:
            logger.error(f"Failed to generate spec: {e}", exc_info=True)
            raise

    def finalize(self) -> str:
        """Complete the Socrates session.

        Returns:
            Completion summary
        """
        logger.info("Finalizing Socrates session")

        if self.document_type == "markdown":
            summary = (
                f"**✅ Socrates completed**\n\n"
                f"**Session summary:**\n"
                f"- Conversation exchanges: {len(self.conversation_history)}\n"
                f"- Document saved to: `{self.target_path}`\n\n"
                "The document is ready for use."
            )
        else:
            summary = (
                f"**✅ Socrates completed**\n\n"
                f"**Session summary:**\n"
                f"- Conversation exchanges: {len(self.conversation_history)}\n"
                f"- Spec saved to: `{self.target_path}`\n\n"
                "Next steps: Use `/plan` to create an implementation plan."
            )

        return summary
