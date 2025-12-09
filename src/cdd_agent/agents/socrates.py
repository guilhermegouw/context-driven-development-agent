"""Socrates Agent - Requirements gathering through Socratic dialogue.

This agent is a thinking partner that helps developers create comprehensive
specifications through intelligent conversation.

Optimized for weaker LLMs (GLM 4.6, Minimax M2) with:
- Explicit state tracking (gathered_info)
- Conversation compaction
- Condensed system prompt
- Periodic persona reinforcement
"""

import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

from ..session.base_agent import BaseAgent
from ..utils.filtered_tools import ReadOnlyToolRegistry


if TYPE_CHECKING:
    from ..session.chat_session import ChatSession

logger = logging.getLogger(__name__)

# Constants for persona maintenance
MAX_HISTORY_MESSAGES = 14  # Compact conversation when exceeds this (7 exchanges)
REMINDER_INTERVAL = 5  # Inject persona reminder every N turns

# Conversation phases for requirements gathering
PHASES = [
    "problem_discovery",  # What's the problem?
    "user_analysis",  # Who has this problem?
    "requirements",  # What should the solution do?
    "edge_cases",  # What happens when things go wrong?
    "wrap_up",  # Ready to show summary
]


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

        # Structured information tracking for weak model support
        # This makes state explicit instead of relying on model memory
        self.gathered_info: dict = {
            "phase": "problem_discovery",  # Current conversation phase
            "problem": {"description": "", "examples": [], "impact": ""},
            "users": {"who": [], "context": "", "workflow": ""},
            "requirements": {
                "must_have": [],
                "success_criteria": [],
                "constraints": [],
            },
            "edge_cases": [],
            "gaps": [],  # What we still need to ask about
            "codebase_discoveries": [],  # What we found while exploring
        }

        # Conversation tracking
        self.shown_summary: bool = False  # Have we shown the final summary?
        self.turn_count: int = 0  # Track conversation turns for reminders

        # Content handoff (for Writer agent)
        self.generated_content: str = ""  # Generated spec/doc content
        self.ready_to_save: bool = False  # Ready to hand off to Writer

        # Codebase exploration context
        self.codebase_context: dict = {
            "structure": "",  # File tree output
            "relevant_files": {},  # path -> description
            "patterns_found": [],  # Existing patterns related to topic
            "exploration_log": [],  # Track what was explored
        }

        # Exploration configuration
        self.exploration_enabled: bool = True
        self.max_tool_iterations: int = 6  # Safety guard for tool loop
        self.total_explorations: int = 0  # Track total explorations this session
        self.max_session_explorations: int = 30  # Soft limit per session

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
            spec_content = self._load_document_file()
            self.spec_content = spec_content if spec_content else ""
            logger.info(f"Loaded document file: {self.target_path}")

            # Step 4: Determine ticket type from path or content (for tickets)
            if self.document_type == "ticket":
                self.ticket_type = self._determine_ticket_type()
                logger.info(f"Detected ticket type: {self.ticket_type}")

            # Step 5: Load appropriate template
            self.template_content = self._load_template()
            logger.info(f"Loaded template for {self.document_type}")

            # Step 5.5: Explore codebase for context
            self._perform_pre_dialogue_exploration()

            # Step 6: Synthesize context and present to user
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

        Enhanced for weak model support with:
        - State tracking (gathered_info extraction)
        - Conversation compaction
        - Periodic persona reinforcement

        Args:
            user_input: User's answer or input

        Returns:
            Next question or summary (if ready to save)
        """
        logger.debug(f"Processing user input (length: {len(user_input)})")

        # Step 1: Add user message to history
        self.conversation_history.append({"role": "user", "content": user_input})
        self.turn_count += 1
        logger.debug(
            (
                f"Conversation history: {len(self.conversation_history)} "
                f"messages, turn {self.turn_count}"
            )
        )

        # Step 2: Extract information from user input (before LLM call)
        self._extract_info_from_exchange(user_input)

        # Step 3: Compact history if it's getting too long
        self._compact_conversation_history()

        # Step 4: Maybe inject persona reminder (every N turns)
        self._maybe_inject_persona_reminder()

        try:
            # Step 5: Use LLM to continue Socratic dialogue
            response = await self._conduct_dialogue(user_input)
            logger.debug(f"Generated response (length: {len(response)})")

            # Step 6: Add response to conversation history
            self.conversation_history.append({"role": "assistant", "content": response})

            # Step 7: Check if we're showing the summary (ready to save)
            if self._is_showing_summary(response):
                logger.info("Socrates is showing final summary")
                self.shown_summary = True

            # Step 8: Check if user approved summary
            # Ready to generate and hand off to Writer
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

        # === DEBUG LOGGING ===
        logger.info("=" * 60)
        logger.info("SOCRATES LLM CALL - DEBUG INFO")
        logger.info("=" * 60)
        logger.info(f"System prompt length: {len(system_prompt)} chars")
        logger.info(f"System prompt first 500 chars:\n{system_prompt[:500]}")
        logger.info("-" * 60)

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

                # === MORE DEBUG LOGGING ===
                logger.info(f"Model: {model}")
                logger.info(f"Number of messages: {len(messages)}")
                for i, msg in enumerate(messages):
                    content = msg.get("content", "")
                    if isinstance(content, str):
                        content_preview = content[:200]
                    else:
                        content_preview = str(content)[:200]
                    logger.info(
                        f"Message {i} [{msg.get('role')}]: {content_preview}..."
                    )
                logger.info("-" * 60)

                # Build request params - conditionally include tools
                enable_tools = self._should_enable_tools(user_input)
                request_params = {
                    "model": model,
                    "max_tokens": 4096,
                    "messages": messages,
                    "system": system_prompt,
                }

                if enable_tools:
                    request_params["tools"] = self.tool_registry.get_schemas()
                    logger.info("Tools ENABLED for this turn (exploration triggered)")
                else:
                    logger.info("Tools DISABLED for this turn")

                logger.info("=" * 60)

                # Make initial LLM call
                response = agent.client.messages.create(**request_params)

                # Handle tool use responses - let model explore as needed
                iteration = 0
                while (
                    response.stop_reason == "tool_use"
                    and iteration < self.max_tool_iterations
                ):
                    iteration += 1
                    logger.info(f"Tool use iteration {iteration}")

                    # Add assistant's response to messages
                    messages.append({"role": "assistant", "content": response.content})

                    # Execute tools and collect results
                    tool_results = []
                    for block in response.content:
                        if hasattr(block, "type") and block.type == "tool_use":
                            logger.info(f"Executing tool: {block.name}")
                            result = self._execute_exploration_tool(
                                block.name, block.input, block.id
                            )
                            tool_results.append(result)

                            # Log discovery and increment counter
                            self.gathered_info["codebase_discoveries"].append(
                                {
                                    "tool": block.name,
                                    "args": block.input,
                                    "turn": self.turn_count,
                                }
                            )
                            self.total_explorations += 1

                    # Add tool results as user message (content can be list)
                    messages.append(
                        {"role": "user", "content": tool_results}  # type: ignore[dict-item]
                    )

                    # Continue conversation
                    response = agent.client.messages.create(**request_params)

                # === LOG RESPONSE TYPE ===
                logger.info(f"Response type: {type(response)}")
                content_raw = getattr(response, "content", [])
                content_list: list = list(content_raw) if content_raw else []
                logger.info(f"Response content blocks: {len(content_list)}")

                # Safe block iteration - extract text from final response
                text_parts: list[str] = []
                for i, block in enumerate(content_list):
                    block_type = type(block).__name__
                    logger.info(f"Block {i} type: {block_type}")

                    if hasattr(block, "type"):
                        logger.info(f"Block {i} .type: {block.type}")

                    # Safe text extraction
                    if hasattr(block, "text"):
                        text_parts.append(str(block.text))
                    elif isinstance(block, dict) and "text" in block:
                        text_parts.append(str(block["text"]))

                # Handle empty content case
                result_text: str = "\n".join(text_parts).strip() if text_parts else ""

                logger.info(f"Final response length: {len(result_text)} chars")
                logger.info(f"Final response preview: {result_text[:300]}...")
                logger.info("=" * 60)

                return result_text
            except Exception as e:
                logger.error(f"LLM call failed: {e}", exc_info=True)
                return self._fallback_response(user_input)
        else:
            # Fallback: simple response
            logger.warning("No LLM available, using fallback")
            return self._fallback_response(user_input)

    # =========================================================================
    # On-Demand Exploration Methods
    # =========================================================================

    def _check_exploration_triggers(self, user_input: str) -> bool:
        """Detect if user input suggests exploration would help.

        Looks for keywords that indicate the user is referring to existing
        code, making assumptions, or mentioning patterns that could be verified.

        Args:
            user_input: The user's message

        Returns:
            True if exploration triggers were detected
        """
        triggers = [
            "currently",
            "right now",
            "existing",
            "already",
            "similar to",
            "like the",
            "in the",
            "the current",
            "we have",
            "we use",
            "our code",
            "the codebase",
            "look at",
            "check the",
            "see how",
            "how does",
            "where is",
            "find the",
        ]
        input_lower = user_input.lower()
        return any(trigger in input_lower for trigger in triggers)

    def _should_enable_tools(self, user_input: str) -> bool:
        """Determine if tools should be enabled for this turn.

        Considers:
        - Whether exploration is enabled
        - Current conversation phase
        - Session exploration limits
        - Whether the input suggests exploration would help

        Args:
            user_input: The user's message

        Returns:
            True if tools should be enabled for this LLM call
        """
        if not self.exploration_enabled:
            return False
        if self.gathered_info["phase"] == "wrap_up":
            return False  # No exploration during wrap-up
        if self.total_explorations >= self.max_session_explorations:
            logger.info("Session exploration limit reached")
            return False
        return self._check_exploration_triggers(user_input)

    def _execute_exploration_tool(
        self, name: str, args: dict, tool_use_id: str
    ) -> dict:
        """Execute a read-only exploration tool.

        Args:
            name: Tool name
            args: Tool arguments
            tool_use_id: Unique ID for this tool use

        Returns:
            Tool result in Anthropic format
        """
        try:
            result = self.tool_registry.execute(name, args)
            # Truncate long results to manage context
            if isinstance(result, str) and len(result) > 3000:
                result = result[:3000] + "\n[... truncated ...]"
            return {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": str(result),
            }
        except Exception as e:
            logger.error(f"Tool execution failed: {name} - {e}")
            return {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": f"Error: {e}",
                "is_error": True,
            }

    def _format_codebase_context_for_prompt(self) -> str:
        """Format codebase context for inclusion in system prompt.

        Returns:
            Formatted string summarizing codebase discoveries
        """
        if not self.codebase_context.get("relevant_files"):
            return "No codebase exploration done yet."

        lines = ["**Relevant files found:**"]
        for path, desc in list(self.codebase_context["relevant_files"].items())[:5]:
            lines.append(f"- `{path}`: {desc}")

        # Include recent discoveries from this session
        discoveries = self.gathered_info.get("codebase_discoveries", [])
        if discoveries:
            recent = discoveries[-3:]  # Last 3 discoveries
            lines.append("\n**Recent explorations:**")
            for d in recent:
                lines.append(f"- Used `{d['tool']}` on turn {d['turn']}")

        return "\n".join(lines)

    def _build_socrates_prompt(self) -> str:
        """Build condensed system prompt optimized for weak models.

        This prompt is structured and explicit, making state visible
        rather than relying on the model's memory.

        Returns:
            System prompt that guides the LLM
        """
        # Get current state for explicit injection
        phase = self.gathered_info["phase"]
        gathered = self._format_gathered_info()
        gaps = self._format_gaps()
        phase_guidance = self._get_phase_guidance(phase)
        codebase_context = self._format_codebase_context_for_prompt()

        intro = (
            "You are **Socrates**, a requirements gathering specialist who "
            "helps developers think clearly about what they want to build."
        )
        return f"""{intro}

## CORE PRINCIPLES

1. **Be a thinking partner, not an interrogator** - Help users articulate
   their ideas, don't grill them
2. **Move forward, not in circles** - Once something is understood, progress
   to the next topic
3. **Accept implicit answers** - If the user's response implies an answer,
   don't ask for explicit confirmation
4. **Know when to stop** - A simple feature doesn't need 20 questions

## STRICT RULES

❌ **FORBIDDEN:**
- Suggesting solutions or implementations
- Asking about something the user already answered (even implicitly)
- Asking "why is X inconvenient?" when the inconvenience is obvious
- Drilling deeper when you have enough information to move on

✅ **REQUIRED:**
- Progress the conversation forward with each question
- Ask about genuinely NEW aspects, not variations of previous questions
- Use ✅ to acknowledge, use ❓ for your question
- Move to the next phase when current phase is sufficiently understood

## CURRENT STATE

**Phase:** {phase}
**Turn:** {self.turn_count}
**Document:** {self.target_path}

### What We Know:
{gathered}

### Possible Areas to Explore (choose wisely - skip if already answered):
{gaps}

## CODEBASE CONTEXT

{codebase_context}

## EXPLORATION TOOLS

You have READ-ONLY tools to explore the codebase when needed:
- `read_file`: Read a specific file's contents
- `grep_files`: Search for patterns across files
- `glob_files`: Find files matching a pattern
- `list_files`: List directory contents

**USE TOOLS WHEN** the user mentions:
- Existing code ("the current implementation...", "how we currently...")
- Assumptions to verify ("we probably have...", "I assume...")
- Related patterns ("similar to how we do X", "like the existing...")

**WHEN SHARING DISCOVERIES:**
- Say: "I found [pattern] in [file] - does this relate to what you're building?"
- Say: "Looking at your codebase, you already have [X] - should this work similarly?"
- Say: "I see [X] in your code - is this the behavior you want to extend?"

**NEVER:**
- Suggest implementations or how to code it
- Write implementation plans
- Recommend specific code patterns to use

You gather REQUIREMENTS. Exploration helps you ask better questions.

## CONVERSATION FLOW GUIDANCE

{phase_guidance}

## RESPONSE FORMAT

✅ **Clear:** [What you understood - be comprehensive, capture everything they said]

❓ [ONE question about something genuinely NEW and valuable to know]

## EXAMPLES OF GOOD vs BAD PROGRESSION

### ✅ GOOD - Moving Forward:
User: "I want a /clear command to reset chat history so models don't get
confused"

✅ **Clear:** You want a /clear command that resets the chat history.
The purpose is to prevent model confusion when context gets too large.

❓ Who will use this command - is it for all users or primarily developers
during long sessions?

### ❌ BAD - Redundant Drilling:
User: "I want a /clear command to reset chat history so models don't get
confused"

✅ **Clear:** You want a /clear command.

❓ What specific problem does model confusion cause?

❌ This is redundant! The user already said why - to prevent confusion.
Don't ask them to re-explain.

### ✅ GOOD - Accepting Implicit Answers:
User: "Right now users have to close the terminal and restart"

✅ **Clear:** The current workaround requires closing and restarting the
terminal, which adds friction.

❓ Should the /clear command reset everything, or should some context be
preserved (like settings or user preferences)?

### ❌ BAD - Asking the Obvious:
User: "Right now users have to close the terminal and restart"

✅ **Clear:** Users must close and restart the terminal.

❓ What is inconvenient about having to close and restart?

❌ This is condescending! The inconvenience is self-evident - extra steps = friction.

## KNOWING WHEN TO WRAP UP

For simple features (like a /clear command), you need:
- What it does (clear chat history) ✓
- Why it's needed (prevent confusion, fresh start) ✓
- Who uses it (users during long sessions) ✓
- Basic behavior (what gets cleared) ✓

You do NOT need to ask 15 questions about edge cases for a simple utility command.

**After 3-5 productive exchanges on a simple feature, consider showing the summary.**

## WRAP UP

When you have sufficient understanding, show:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 SPECIFICATION SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Organized summary of what we know]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Does this capture everything? Ready to save to {self.target_path}?

## YOUR TASK NOW

Read the conversation carefully. Ask a question that:
1. Is NOT something already answered (even implicitly)
2. Moves the conversation FORWARD to new ground
3. Is genuinely useful for understanding the feature

If you've covered the basics for a simple feature,
show the summary instead.
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
            intro_text = (
                "Help developers create comprehensive markdown documents "
                "through intelligent conversation. You:"
            )
            return f"""{intro_text}

1. **Guide Discovery**: Use questions to help developers articulate their
   thinking
2. **Challenge Vagueness**: When answers are incomplete, acknowledge clarity
   and target gaps
3. **Stay in Scope**: Focus on clarifying the content of THIS document only
4. **Synthesize**: Help organize scattered thoughts into structured
   documentation
5. **Show Before Saving**: When complete, show full summary and get approval
   before saving

For CDD.md files, focus on:
- Project purpose and scope
- Architecture decisions and rationale
- Team conventions and standards
- Business context and requirements

For other markdown documents, adapt to the specific document type."""
        else:
            intro = (
                f"Help developers create comprehensive {self.ticket_type} "
                "specifications through intelligent conversation. You:"
            )
            return f"""{intro}

1. **Guide Discovery**: Use questions to help developers articulate their
   thinking
2. **Challenge Vagueness**: When answers are incomplete, acknowledge clarity
   and target gaps
3. **Stay in Scope**: Focus on requirements for THIS ticket only - not
   implementation or other features
4. **Synthesize**: Help organize scattered thoughts into structured
   documentation
5. **Show Before Saving**: When complete, show full summary and get approval
   before saving"""

    def _get_scope_guidance(self) -> str:
        """Get scope guidance based on document type.

        Returns:
            Scope-specific guidance text
        """
        if self.document_type == "markdown":
            job = (
                "**Your job:** Help create comprehensive documentation for "
                "THIS markdown file."
            )
            not_job = (
                "**Not your job:** Solve implementation problems or discuss "
                "unrelated features."
            )
            return f"""{job}
{not_job}

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

✅ Good: "That's a separate document. Let's focus on making this CDD.md
complete first. I can note API documentation as a related document to create
later."
"""
        else:
            job = (
                "**Your job:** Help create a complete SPECIFICATION for THIS " "ticket."
            )
            not_job = (
                "**Not your job:** Solve implementation, design architecture, "
                "or discuss other features."
            )
            return f"""{job}
{not_job}
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

    # =========================================================================
    # Codebase Exploration Methods
    # =========================================================================

    def _scan_codebase_structure(self) -> str:
        """Scan codebase structure using tree command.

        Returns:
            Tree output showing file structure
        """
        try:
            # Use tree command with reasonable depth and exclusions
            result = subprocess.run(
                [
                    "tree",
                    "-L",
                    "4",  # 4 levels deep
                    "-I",
                    "__pycache__|node_modules|.git|.venv|venv|*.pyc|.pytest_cache|.mypy_cache|dist|build|*.egg-info",
                    "--noreport",  # Don't show file count
                    str(Path.cwd()),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                tree_output = result.stdout
                logger.info(f"Scanned codebase: {len(tree_output)} chars")

                # Truncate if too long
                if len(tree_output) > 4000:
                    lines = tree_output.split("\n")[:150]
                    tree_output = "\n".join(lines) + "\n[... truncated ...]"

                return tree_output
            else:
                logger.warning(f"tree command failed: {result.stderr}")
                return self._fallback_scan_structure()

        except FileNotFoundError:
            logger.warning("tree command not found, using fallback")
            return self._fallback_scan_structure()
        except subprocess.TimeoutExpired:
            logger.warning("tree command timed out")
            return self._fallback_scan_structure()
        except Exception as e:
            logger.error(f"Error scanning codebase: {e}")
            return self._fallback_scan_structure()

    def _fallback_scan_structure(self) -> str:
        """Fallback codebase scan using Python when tree is unavailable.

        Returns:
            Simple directory listing
        """
        output_lines = []
        root = Path.cwd()

        exclude_dirs = {
            "__pycache__",
            "node_modules",
            ".git",
            ".venv",
            "venv",
            ".pytest_cache",
            ".mypy_cache",
            "dist",
            "build",
        }

        def scan_dir(path: Path, prefix: str = "", depth: int = 0):
            if depth > 3:  # Max 4 levels
                return

            try:
                items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name))
                for i, item in enumerate(items):
                    if item.name.startswith(".") and item.name not in [".cdd"]:
                        continue
                    if item.name in exclude_dirs:
                        continue
                    if item.suffix == ".pyc":
                        continue

                    is_last = i == len(items) - 1
                    connector = "└── " if is_last else "├── "
                    output_lines.append(f"{prefix}{connector}{item.name}")

                    if item.is_dir():
                        extension = "    " if is_last else "│   "
                        scan_dir(item, prefix + extension, depth + 1)
            except PermissionError:
                pass

        output_lines.append(str(root.name))
        scan_dir(root)

        result = "\n".join(output_lines[:150])  # Limit lines
        logger.info(f"Fallback scan: {len(result)} chars")
        return result

    def _find_relevant_files_for_topic(self) -> dict[str, str]:
        """Find files likely relevant to the spec based on keywords.

        Returns:
            Dict of file_path -> brief content description
        """
        relevant: dict[str, str] = {}

        # Extract keywords from spec content or target path
        keywords: set[str] = set()

        # Get text to search from spec content or path
        text_to_search = self.spec_content or ""
        if self.target_path:
            text_to_search += f" {self.target_path.stem}"

        # Common feature-related words to look for
        for word in text_to_search.lower().split():
            if len(word) > 3 and word.isalpha():
                keywords.add(word)

        # Also add specific tech terms if present
        tech_terms = [
            "cli",
            "command",
            "session",
            "chat",
            "agent",
            "tool",
            "config",
            "socrates",
            "planner",
            "executor",
        ]
        for term in tech_terms:
            if term in text_to_search.lower():
                keywords.add(term)

        if not keywords:
            logger.info("No keywords found for file search")
            return relevant

        logger.debug(f"Searching for files with keywords: {keywords}")

        # Search in src directory
        src_dir = Path.cwd() / "src"
        if not src_dir.exists():
            src_dir = Path.cwd()

        try:
            for py_file in src_dir.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue

                # Check if filename matches any keyword
                filename_lower = py_file.stem.lower()
                if any(kw in filename_lower for kw in keywords):
                    rel_path = py_file.relative_to(Path.cwd())
                    relevant[str(rel_path)] = "Filename matches keywords"
                    continue

                # Quick scan of file content (first 50 lines)
                try:
                    with open(py_file, "r", encoding="utf-8") as f:
                        head = "".join(f.readline() for _ in range(50))

                    # Check for keyword matches in docstrings/comments
                    head_lower = head.lower()
                    matching_kw = [kw for kw in keywords if kw in head_lower]
                    if len(matching_kw) >= 2:  # At least 2 keyword matches
                        rel_path = py_file.relative_to(Path.cwd())
                        relevant[str(rel_path)] = (
                            f"Contains: {', '.join(matching_kw[:3])}"
                        )
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Error finding relevant files: {e}")

        # Limit to most relevant files
        if len(relevant) > 10:
            relevant = dict(list(relevant.items())[:10])

        logger.info(f"Found {len(relevant)} potentially relevant files")
        return relevant

    def _perform_pre_dialogue_exploration(self) -> None:
        """Scan codebase before starting dialogue.

        Gathers context about:
        - Project structure
        - Files related to the ticket topic
        - Existing patterns that might be relevant

        Results are stored in self.codebase_context for use during dialogue.
        """
        logger.info("Performing pre-dialogue codebase exploration...")

        # 1. Scan structure
        self.codebase_context["structure"] = self._scan_codebase_structure()

        # 2. Find relevant files
        self.codebase_context["relevant_files"] = self._find_relevant_files_for_topic()

        # 3. Log exploration summary
        num_files = len(self.codebase_context["relevant_files"])
        logger.info(f"Pre-dialogue exploration: {num_files} relevant files found")

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

        # Include codebase discoveries if any were found
        if self.codebase_context.get("relevant_files"):
            num_files = len(self.codebase_context["relevant_files"])
            greeting += f"🔍 **Related code found:** {num_files} relevant files\n"
            for path, desc in list(self.codebase_context["relevant_files"].items())[:3]:
                greeting += f"  - `{path}`: {desc}\n"
            if num_files > 3:
                greeting += f"  - *...and {num_files - 3} more*\n"
            greeting += "\n"

        # Start the conversation with appropriate question based on document type
        if self.document_type == "markdown":
            greeting += (
                "Now I can ask smart, targeted questions to help you think "
                f"through this {doc_name.lower()} document.\n\n"
                "Ready? Let's start with the big picture:\n\n"
                f"**What is the primary purpose of this {doc_type.lower()} "
                "and who is it for?**"
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
            "SPECIFICATION SUMMARY",
            "COMPLETE SPECIFICATION SUMMARY",
            "Does this look good?",
            "Should I save this to",
            "Ready to save to",
            "Does this capture everything?",
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
        approval_words = [
            "yes",
            "yeah",
            "yep",
            "looks good",
            "perfect",
            "save it",
        ]
        user_lower = user_input.lower().strip()
        return any(word in user_lower for word in approval_words)

    async def _generate_document_content(self) -> None:
        """Generate document content from conversation.

        This asks the LLM to format the conversation into proper format
        (YAML or markdown). The actual file write is handled by Writer agent
        via ChatSession.
        """
        logger.info(f"Generating document content for {self.target_path}")

        if self.document_type == "markdown":
            # Ask LLM to format the conversation into markdown
            intro = (
                "Based on our entire conversation, please generate a complete "
                "markdown document following this template structure:"
            )
            format_prompt = f"""{intro}

{self.template_content}

Extract all the information we discussed and format it as well-structured markdown.
Only output the markdown content, nothing else.
Make sure to include:
- All information gathered during our conversation
- Proper markdown formatting with headers, lists, and emphasis
- All template sections filled in

Do not include markdown code blocks or explanations, just the raw markdown content."""
        else:
            # Get today's date for the ticket
            from datetime import date

            today = date.today().isoformat()

            # Ask LLM to format the conversation into YAML (for tickets)
            intro = "Based on our conversation, generate a YAML specification " "file."
            format_prompt = f"""{intro}

TEMPLATE:
{self.template_content}

STRICT RULES - YOU MUST FOLLOW THESE:

1. **ONLY include information explicitly discussed** - Do NOT invent or
   assume details
2. **Delete sections not covered** - If we didn't discuss frontend, remove
   that section entirely
3. **Leave fields empty if not discussed** - Use "" for strings, [] for lists
4. **Never estimate** - Leave priority and effort empty unless the user specified them
5. **Use today's date** - created: {today}, updated: {today}
6. **This is a CLI tool** - There is no web frontend, no page refresh, no browser UI

WHAT TO INCLUDE:
- Title: Based on what the user wants to build
- User story: Only what the user explicitly said about who/what/why
- Acceptance criteria: Only criteria the user mentioned or confirmed
- Implementation scope: Only technical areas we actually discussed
- Technical considerations: Only if the user mentioned specific technical concerns

WHAT TO EXCLUDE:
- Anything you're "assuming" or "inferring"
- Generic placeholder text
- Made-up estimates or priorities
- Frontend/UI sections for CLI tools
- Confirmation dialogs or features not requested

Output ONLY valid YAML, no markdown code blocks or explanations."""

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
                    system_prompt = (
                        "You are a markdown formatting assistant. Create "
                        "well-structured documentation. Only include "
                        "information explicitly provided - never invent "
                        "details."
                    )
                else:
                    system_prompt = (
                        "You are a YAML formatting assistant. Your job is to "
                        "accurately capture ONLY what was discussed - never "
                        "add, assume, or invent information. If something "
                        "wasn't discussed, leave it empty or delete the "
                        "section."
                    )

                response = agent.client.messages.create(
                    model=model,
                    max_tokens=4096,
                    messages=messages,
                    system=system_prompt,
                )

                # Extract text with safe handling
                content_blocks = getattr(response, "content", [])
                text_parts = []
                for block in content_blocks or []:
                    if hasattr(block, "text"):
                        text_parts.append(block.text)
                    elif isinstance(block, dict) and "text" in block:
                        text_parts.append(block["text"])

                content = "\n".join(text_parts) if text_parts else ""

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
                logger.info(
                    f"Generated {len(content)} chars of content for {self.target_path}"
                )

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

    # =========================================================================
    # State Tracking Methods (for weak model support)
    # =========================================================================

    def _detect_current_phase(self) -> str:
        """Determine which phase we're in based on gathered info.

        Returns:
            Current phase name from PHASES
        """
        info = self.gathered_info

        # Phase 1: Problem - need description and at least one example
        if not info["problem"]["description"] or not info["problem"]["examples"]:
            return "problem_discovery"

        # Phase 2: Users - need to know who has the problem
        if not info["users"]["who"]:
            return "user_analysis"

        # Phase 3: Requirements - need must_haves and success criteria
        if (
            not info["requirements"]["must_have"]
            or not info["requirements"]["success_criteria"]
        ):
            return "requirements"

        # Phase 4: Edge cases - need at least 2
        if len(info["edge_cases"]) < 2:
            return "edge_cases"

        # Ready for wrap-up
        return "wrap_up"

    def _extract_info_from_exchange(
        self, user_input: str, assistant_response: str = ""
    ):
        """Extract key information from the latest exchange.

        Uses pattern matching to identify and store information.
        This makes state explicit instead of relying on model memory.

        Args:
            user_input: User's message
            assistant_response: Assistant's response (optional)
        """
        user_lower = user_input.lower()
        info = self.gathered_info

        # Feature request indicators (positive framing - "I want to add X")
        feature_indicators = [
            "want to add",
            "want to create",
            "want to implement",
            "need a",
            "need to add",
            "add a",
            "create a",
            "implement",
            "build a",
            "make a",
            "i want",
            "we need",
            "should have",
        ]

        # Problem description indicators (negative framing - "X is broken")
        problem_indicators = [
            "problem",
            "issue",
            "bug",
            "broken",
            "doesn't work",
            "can't",
            "cannot",
            "failing",
            "error",
            "wrong",
            "confused",
            "confusing",
            "cluttered",
            "slow",
            "frustrating",
        ]

        # Capture feature requests as problem descriptions too
        is_feature_request = any(phrase in user_lower for phrase in feature_indicators)
        is_problem_statement = any(word in user_lower for word in problem_indicators)

        # First substantive response should always be captured as
        # problem/feature description
        is_first_response = self.turn_count <= 2 and not info["problem"]["description"]

        if is_feature_request or is_problem_statement or is_first_response:
            if not info["problem"]["description"]:
                info["problem"]["description"] = user_input[:300]
            elif len(user_input) > 50:  # Substantial addition
                info["problem"]["description"] += f" | {user_input[:200]}"

        # Example indicators
        example_indicators = [
            "example",
            "for instance",
            "like when",
            "specifically",
            "for example",
            "such as",
            "e.g.",
            "happens when",
        ]
        if any(phrase in user_lower for phrase in example_indicators):
            example = user_input[:200]
            if example not in info["problem"]["examples"]:
                info["problem"]["examples"].append(example)

        # Impact indicators
        impact_indicators = [
            "affects",
            "impact",
            "causes",
            "results in",
            "leads to",
            "because of this",
            "costs",
            "loses",
            "wastes",
        ]
        if any(phrase in user_lower for phrase in impact_indicators):
            if not info["problem"]["impact"]:
                info["problem"]["impact"] = user_input[:200]

        # User type indicators
        user_types = [
            "users",
            "customers",
            "developers",
            "admins",
            "managers",
            "team",
            "clients",
            "employees",
            "visitors",
            "members",
        ]
        for user_type in user_types:
            if user_type in user_lower and user_type not in info["users"]["who"]:
                info["users"]["who"].append(user_type)

        # Context indicators
        context_indicators = [
            "when they",
            "while",
            "during",
            "in the",
            "at work",
            "on mobile",
            "on desktop",
            "daily",
            "weekly",
        ]
        if any(phrase in user_lower for phrase in context_indicators):
            if not info["users"]["context"]:
                info["users"]["context"] = user_input[:200]

        # Requirement indicators (must-have)
        requirement_indicators = [
            "should",
            "must",
            "need to",
            "has to",
            "require",
            "want to",
            "able to",
            "allow",
            "enable",
        ]
        if any(phrase in user_lower for phrase in requirement_indicators):
            req = user_input[:200]
            if req not in info["requirements"]["must_have"]:
                info["requirements"]["must_have"].append(req)

        # Success criteria indicators
        success_indicators = [
            "success",
            "done when",
            "complete when",
            "works if",
            "accomplished",
            "finished",
            "achieved",
            "goal is",
        ]
        if any(phrase in user_lower for phrase in success_indicators):
            criteria = user_input[:200]
            if criteria not in info["requirements"]["success_criteria"]:
                info["requirements"]["success_criteria"].append(criteria)

        # Constraint indicators
        constraint_indicators = [
            "can't",
            "cannot",
            "must not",
            "limitation",
            "constraint",
            "restriction",
            "budget",
            "deadline",
        ]
        if any(phrase in user_lower for phrase in constraint_indicators):
            constraint = user_input[:200]
            if constraint not in info["requirements"]["constraints"]:
                info["requirements"]["constraints"].append(constraint)

        # Edge case indicators
        edge_case_indicators = [
            "what if",
            "edge case",
            "error",
            "fail",
            "wrong",
            "invalid",
            "timeout",
            "offline",
            "empty",
            "null",
        ]
        if any(phrase in user_lower for phrase in edge_case_indicators):
            edge_case = user_input[:200]
            if edge_case not in info["edge_cases"]:
                info["edge_cases"].append(edge_case)

        # Update phase based on new information
        info["phase"] = self._detect_current_phase()

        # Update gaps
        self._update_gaps()

        logger.debug(
            f"Extracted info - Phase: {info['phase']}, Gaps: {len(info['gaps'])}"
        )

    def _update_gaps(self):
        """Identify what information is still missing.

        This helps guide the model on what to ask about next.
        """
        gaps = []
        info = self.gathered_info

        # Problem gaps
        if not info["problem"]["description"]:
            gaps.append("Problem description not clear")
        if not info["problem"]["examples"]:
            gaps.append("No concrete examples of the problem")
        if not info["problem"]["impact"]:
            gaps.append("Impact/consequences not understood")

        # User gaps
        if not info["users"]["who"]:
            gaps.append("Users not identified")
        if not info["users"]["context"]:
            gaps.append("User context/workflow not clear")

        # Requirements gaps
        if not info["requirements"]["must_have"]:
            gaps.append("Core requirements not defined")
        if not info["requirements"]["success_criteria"]:
            gaps.append("Success criteria not established")

        # Edge case gaps
        if len(info["edge_cases"]) < 2:
            gaps.append("Edge cases need more exploration")

        info["gaps"] = gaps

    def _format_gathered_info(self) -> str:
        """Format gathered information for inclusion in prompt.

        Returns:
            Formatted string of gathered information
        """
        info = self.gathered_info
        lines = []

        # Problem section
        if info["problem"]["description"]:
            lines.append(f"**Problem:** {info['problem']['description'][:150]}...")
        if info["problem"]["examples"]:
            examples = ", ".join(ex[:50] for ex in info["problem"]["examples"][:3])
            lines.append(f"**Examples:** {examples}")
        if info["problem"]["impact"]:
            lines.append(f"**Impact:** {info['problem']['impact'][:100]}")

        # Users section
        if info["users"]["who"]:
            lines.append(f"**Users:** {', '.join(info['users']['who'])}")
        if info["users"]["context"]:
            lines.append(f"**Context:** {info['users']['context'][:100]}")

        # Requirements section
        if info["requirements"]["must_have"]:
            reqs = "; ".join(r[:50] for r in info["requirements"]["must_have"][:3])
            lines.append(f"**Requirements:** {reqs}")
        if info["requirements"]["success_criteria"]:
            criteria = "; ".join(
                c[:50] for c in info["requirements"]["success_criteria"][:3]
            )
            lines.append(f"**Success criteria:** {criteria}")
        if info["requirements"]["constraints"]:
            constraints = "; ".join(
                c[:50] for c in info["requirements"]["constraints"][:3]
            )
            lines.append(f"**Constraints:** {constraints}")

        # Edge cases
        if info["edge_cases"]:
            cases = "; ".join(e[:40] for e in info["edge_cases"][:3])
            lines.append(f"**Edge cases:** {cases}")

        if not lines:
            return "No information gathered yet - start by asking about the problem."

        return "\n".join(lines)

    def _format_gathered_info_brief(self) -> str:
        """Format gathered information briefly for compaction summary.

        Returns:
            Brief summary string
        """
        info = self.gathered_info
        parts = []

        if info["problem"]["description"]:
            parts.append("problem identified")
        if info["users"]["who"]:
            parts.append(f"{len(info['users']['who'])} user types")
        if info["requirements"]["must_have"]:
            parts.append(f"{len(info['requirements']['must_have'])} requirements")
        if info["edge_cases"]:
            parts.append(f"{len(info['edge_cases'])} edge cases")

        return ", ".join(parts) if parts else "minimal info"

    def _format_gaps(self) -> str:
        """Format gaps for inclusion in prompt.

        Returns:
            Formatted string of gaps to fill
        """
        gaps = self.gathered_info.get("gaps", [])
        if not gaps:
            return "All major areas covered - consider showing summary."

        return "\n".join(f"- {gap}" for gap in gaps[:5])

    def _get_phase_guidance(self, phase: str) -> str:
        """Get specific guidance for current phase.

        Args:
            phase: Current conversation phase

        Returns:
            Phase-specific guidance text
        """
        guidance = {
            "problem_discovery": """**PHASE: Problem/Feature Understanding**
Understand what they want to build or fix. Once you know the WHAT and WHY, move on.
Good questions (pick ONE that hasn't been answered):
- What would this feature/fix do?
- Why is this needed? What's the current pain point?
- Can you give a quick example of when this would be used?

⚠️ If the user already explained what and why, SKIP to the next phase.""",
            "user_analysis": """**PHASE: User Context**
Quick check on who uses this and when. Don't over-analyze for simple features.
Good questions (pick ONE if relevant):
- Who will use this? (all users, admins, developers?)
- In what situations would they use it?

⚠️ For simple utility features, this can be brief or skipped.""",
            "requirements": """**PHASE: Behavior Clarification**
Clarify what the feature should actually do. Focus on behavior, not implementation.
Good questions (pick ONE that adds value):
- What should happen when they use this?
- Should anything be preserved/remembered, or is it a clean reset?
- Any confirmation needed, or should it just work?

⚠️ Don't ask about edge cases for simple features.""",
            "edge_cases": """**PHASE: Edge Cases (only for complex features)**
Only ask about edge cases for complex features with many moving parts.
For simple utilities (like /clear), SKIP this phase entirely.

If needed, ask ONE question about:
- Error handling (what if something goes wrong?)
- Boundary conditions (empty state, huge data, etc.)

⚠️ Simple features don't need extensive edge case analysis.""",
            "wrap_up": """**PHASE: Wrap Up**
You have enough information. Show the summary now.
- Present organized specification summary
- Ask for approval before saving
- Keep it concise for simple features""",
        }

        return guidance.get(phase, guidance["problem_discovery"])

    # =========================================================================
    # Conversation Management Methods
    # =========================================================================

    def _extract_text_from_tool_results(self, content: list | str) -> str:
        """Extract text content from tool_result blocks.

        Tool results are stored as lists of dicts in conversation history.
        This method extracts readable text for information extraction.

        Args:
            content: Either a string or list of tool_result dicts

        Returns:
            Combined text content for information extraction
        """
        if isinstance(content, str):
            return content

        texts = []
        for item in content:
            if isinstance(item, dict) and "content" in item:
                # Truncate each tool result to avoid overly long extractions
                text = str(item["content"])[:500]
                texts.append(text)

        return " | ".join(texts)

    def _compact_conversation_history(self):
        """Compact conversation history when it gets too long.

        Strategy:
        - Keep first 2 messages (context loading)
        - Keep last 8 messages (recent context)
        - Middle messages are "absorbed" into gathered_info
        """
        if len(self.conversation_history) <= MAX_HISTORY_MESSAGES:
            return  # No compaction needed

        logger.info(
            f"Compacting conversation from {len(self.conversation_history)} messages"
        )

        # Extract info from middle messages before removing them
        middle_start = 2
        middle_end = len(self.conversation_history) - 8

        for i in range(middle_start, middle_end, 2):
            if i + 1 < len(self.conversation_history):
                user_msg = self.conversation_history[i].get("content", "")
                asst_msg = self.conversation_history[i + 1].get("content", "")

                # Handle tool_result blocks in messages
                user_msg = self._extract_text_from_tool_results(user_msg)
                asst_msg = self._extract_text_from_tool_results(asst_msg)

                self._extract_info_from_exchange(user_msg, asst_msg)

        # Keep first 2 + last 8
        first_messages = self.conversation_history[:2]
        recent_messages = self.conversation_history[-8:]

        # Add a summary message in between
        gathered_brief = self._format_gathered_info_brief()
        summary_msg = {
            "role": "assistant",
            "content": f"[Previous discussion summarized - gathered: {gathered_brief}]",
        }

        self.conversation_history = first_messages + [summary_msg] + recent_messages
        logger.info(f"Compacted to {len(self.conversation_history)} messages")

    def _maybe_inject_persona_reminder(self):
        """Inject persona reminder every N turns to prevent drift.

        This is especially important for weaker models that lose
        track of their role after many exchanges.
        """
        if self.turn_count > 0 and self.turn_count % REMINDER_INTERVAL == 0:
            phase = self.gathered_info["phase"]
            gaps = self.gathered_info.get("gaps", [])
            gaps_str = ", ".join(gaps[:3]) if gaps else "none identified"

            reminder = f"""[SOCRATES REMINDER]
You are Socrates - requirements gatherer only.
❌ Do NOT suggest solutions or implementations
✅ Ask about: problems, users, requirements, edge cases
Current phase: {phase}
Gaps to fill: {gaps_str}
Continue with ONE question about the gaps."""

            # Insert as user message (some models handle system mid-conversation poorly)
            self.conversation_history.append({"role": "user", "content": reminder})
            logger.debug(f"Injected persona reminder at turn {self.turn_count}")
