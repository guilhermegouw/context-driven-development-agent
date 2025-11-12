"""Core agent conversation loop.

This module implements the main agentic loop:
1. User sends message
2. LLM processes with tool access
3. LLM decides to use tools or respond
4. If tool use: execute → feed back to LLM → loop
5. If done: return final response
"""

import time
from typing import Any, Dict, Generator, List, Optional

from rich.console import Console

from .approval import ApprovalManager
from .config import ProviderConfig
from .context import ContextLoader
from .logging import get_logger
from .tools import ToolRegistry
from .utils.execution_state import ExecutionMode

console = Console()
logger = get_logger("agent")

# Background tools that should be handled specially
BACKGROUND_TOOLS = {
    "run_bash_background",
    "get_background_status",
    "interrupt_background_process", 
    "get_background_output",
    "list_background_processes"
}


# Enhanced system prompt for pair coding
PAIR_CODING_SYSTEM_PROMPT = """You are Huyang, an expert AI coding assistant.

## Critical Rules
1. NEVER read the same file twice
2. NEVER run the same command twice
3. Use minimal tools - check conversation history first

## MARKDOWN FORMATTING RULES (MANDATORY)

**ALWAYS use these styles:**
✅ Headers: `# Header`, `## Subheader`, `### Section` (markdown style)
✅ Lists: Use `-` or `*` for bullets, `1.` for numbered lists
✅ Emphasis: Use `**bold**` and `*italic*` sparingly
✅ Code: Use backticks for `inline code` and triple backticks for blocks

**NEVER use these styles:**
❌ Underline headers (like `Header\n======` or `Section\n------`)
❌ Excessive decorative elements
❌ ASCII art boxes or borders
❌ Multiple blank lines (max 1 blank line between sections)

## Response Format Examples

GOOD response format:
```
# Task Complete

I've updated the authentication system with the following changes:

- Modified `src/auth.py` (lines 45-67): Added OAuth token refresh
- Created `tests/test_auth.py`: Added 5 new test cases
- Updated `README.md`: Added OAuth setup instructions

All tests are passing. The token refresh happens automatically when tokens expire.
```

BAD response format:
```
Task Complete
=============

I've updated the authentication system with the following changes:


* Modified src/auth.py (lines 45-67): Added OAuth token refresh


* Created tests/test_auth.py: Added 5 new test cases


* Updated README.md: Added OAuth setup instructions


All tests are passing. The token refresh happens automatically when tokens expire.
```

## Tool Usage Examples

### Example 1: Simple verification task
User: "Check if the lazy loading is already implemented in cli.py"

BAD (too many tools):
- read_file('cli.py')
- grep_files('lazy', 'cli.py')
- grep_files('import', 'cli.py')
- run_bash('grep -n lazy cli.py')  ← redundant!
- read_file('cli.py')  ← already read!

GOOD (minimal tools):
- read_file('cli.py')
- Response: "Yes, lazy loading is already implemented at lines 126, 151, 181."

### Example 2: Implementation task
User: "Add lazy loading to AuthManager import"

GOOD approach:
- read_file('cli.py')
- grep_files('AuthManager', 'cli.py')  ← find all usages
- edit_file('cli.py', ...) ← make the change
- Response: "Done. Moved AuthManager import inside auth commands at lines X, Y."

### Example 3: Exploration task
User: "How does authentication work?"

GOOD approach:
- list_files('.')  ← see structure
- read_file('auth.py')
- Response with explanation

## Tools Available
- read_file(path), write_file(path, content), edit_file(path, old, new)
- list_files(path), glob_files(pattern), grep_files(pattern, file_pattern)
- run_bash(command), git_status(), git_diff(file)

## Keep It Simple
- Verification tasks: 1-2 tools
- Small changes: 2-4 tools
- Large features: 5-10 tools
- If using >10 tools, you're doing too much"""


class Agent:
    """Main conversational agent with tool execution."""

    def __init__(
        self,
        provider_config: ProviderConfig,
        tool_registry: ToolRegistry,
        model_tier: str = "mid",
        max_iterations: int = 10,
        approval_manager: Optional[ApprovalManager] = None,
        enable_context: bool = True,
        execution_mode: ExecutionMode = ExecutionMode.NORMAL,
    ):
        """Initialize agent.

        Args:
            provider_config: Provider configuration
            tool_registry: Registry of available tools
            model_tier: Model tier to use (small/mid/big)
            max_iterations: Maximum conversation iterations
            approval_manager: Optional approval manager for tool execution safety
            enable_context: Whether to load hierarchical context files (default: True)
            execution_mode: Execution mode (NORMAL or PLAN for read-only)
        """
        self.provider_config = provider_config
        self.tool_registry = tool_registry
        self.model_tier = model_tier
        self.max_iterations = max_iterations
        self.approval_manager = approval_manager
        self.enable_context = enable_context
        self.execution_mode = execution_mode
        self.messages: List[Dict[str, Any]] = []

        # Lazy Anthropic client - will be initialized when first needed
        self._client = None
        self._provider_config = provider_config

        # Initialize context loader
        self.context_loader = ContextLoader() if enable_context else None

        # Load project context once at initialization
        self.project_context = self.load_project_context()

        # Build system prompt (project context will be injected into first message)
        self.system_prompt = PAIR_CODING_SYSTEM_PROMPT

        # Background process tracking for agent context awareness
        self.background_processes: Dict[str, Dict[str, Any]] = {}  # Track active background processes
        self.background_process_counter = 0 # Counter for unique process IDs
        
        # Create background executor reference for easy access
        from .background_executor import get_background_executor
        self.background_executor = get_background_executor

    @property
    def client(self):
        """Lazy initialization of Anthropic client.

        The Anthropic SDK is only imported and initialized when actually needed,
        not when the Agent class is instantiated. This saves ~707ms startup time.

        Supports both OAuth (Claude Pro/Max plans) and API key authentication:
        - OAuth: Automatically refreshes tokens when they expire (< 5 min remaining)
        - API Key: Uses static API key from configuration

        Returns:
            Initialized Anthropic client
        """
        if self._client is None:
            try:
                logger.debug("Initializing Anthropic client")
                import anthropic

                # Check if OAuth is configured
                if self._provider_config.oauth:
                    logger.debug("Using OAuth authentication")
                    import asyncio
                    import time

                    from .oauth import AnthropicOAuth

                    oauth_config = self._provider_config.oauth

                    # Check if token needs refresh (< 5 minutes remaining)
                    if time.time() >= (oauth_config.expires_at - 300):
                        logger.info("OAuth token expiring soon, refreshing...")
                        oauth_handler = AnthropicOAuth()
                        new_tokens = asyncio.run(
                            oauth_handler.refresh_access_token(
                                oauth_config.refresh_token
                            )
                        )

                        if new_tokens:
                            logger.info("OAuth token refreshed successfully")
                            # Update config with new tokens
                            oauth_config.access_token = new_tokens["access_token"]
                            oauth_config.expires_at = new_tokens["expires_at"]
                            if "refresh_token" in new_tokens:
                                oauth_config.refresh_token = new_tokens["refresh_token"]

                            # Save updated tokens to config file
                            # Note: This loads, updates, and saves the entire config
                            from .config import ConfigManager

                            config_manager = ConfigManager()
                            settings = config_manager.load()
                            # Find and update the provider with OAuth
                            for provider_name, provider_cfg in settings.providers.items():
                                if provider_cfg.oauth == oauth_config:
                                    settings.providers[provider_name].oauth = oauth_config
                                    break
                            config_manager.save(settings)
                            logger.debug("Updated OAuth tokens saved to config")
                        else:
                            logger.warning(
                                "Failed to refresh OAuth token - using existing token"
                            )

                    # Initialize client with OAuth access token
                    # OAuth requires Bearer token in Authorization header, not x-api-key
                    import httpx

                    # Custom transport that removes x-api-key and adds OAuth headers
                    class OAuthTransport(httpx.HTTPTransport):
                        def __init__(self, access_token: str, *args, **kwargs):
                            super().__init__(*args, **kwargs)
                            self.access_token = access_token

                        def handle_request(self, request: httpx.Request) -> httpx.Response:
                            # Remove x-api-key header if present
                            if "x-api-key" in request.headers:
                                del request.headers["x-api-key"]

                            # Add OAuth Bearer token
                            request.headers["Authorization"] = f"Bearer {self.access_token}"

                            # Add required OAuth beta header
                            request.headers["anthropic-beta"] = (
                                "oauth-2025-04-20,claude-code-20250219,"
                                "interleaved-thinking-2025-05-14,fine-grained-tool-streaming-2025-05-14"
                            )

                            return super().handle_request(request)

                    # Create custom httpx client with OAuth transport
                    http_client = httpx.Client(
                        transport=OAuthTransport(oauth_config.access_token),
                        timeout=600.0,
                    )

                    self._client = anthropic.Anthropic(
                        api_key="dummy-key-will-be-replaced",  # Will be removed by transport
                        base_url=self._provider_config.base_url,
                        max_retries=5,
                        timeout=600.0,
                        http_client=http_client,
                    )
                    logger.info(
                        "Anthropic client initialized with OAuth authentication"
                    )
                else:
                    # Fallback to API key authentication
                    logger.debug("Using API key authentication")
                    self._client = anthropic.Anthropic(
                        api_key=self._provider_config.get_api_key(),
                        base_url=self._provider_config.base_url,
                        max_retries=5,  # Increase from default 2 to handle overloaded errors
                        timeout=600.0,  # 10 minutes timeout for long-running requests
                    )
                    logger.info("Anthropic client initialized successfully")
            except ImportError as e:
                logger.error("Failed to import anthropic SDK", exc_info=True)
                raise ImportError(
                    "Failed to import anthropic. Please install it with: "
                    "pip install anthropic"
                ) from e
            except Exception as e:
                logger.error(f"Error initializing Anthropic client: {e}", exc_info=True)
                raise
        return self._client

    def load_project_context(self) -> str:
        """Load hierarchical context files.

        Uses ContextLoader to load and merge contexts from:
        - Global: ~/.cdd/CDD.md or ~/.claude/CLAUDE.md
        - Project: CDD.md or CLAUDE.md at project root

        Context priority (recency bias): Global → Project

        Returns:
            Merged context string, or fallback message if no context found
        """
        # If context loading is disabled, return placeholder
        if not self.enable_context or not self.context_loader:
            return "Context loading disabled (--no-context flag)."

        # Load and merge hierarchical contexts
        context = self.context_loader.load_context()

        # Return context or fallback message
        if context:
            return context
        return "No context files found (create ~/.cdd/CDD.md or ./CDD.md)."

    def run(self, user_message: str, system_prompt: Optional[str] = None) -> str:
        """Run conversation with user message.

        This is the main agentic loop:
        - Send message to LLM with tools
        - If LLM wants to use tools: execute them
        - Feed tool results back to LLM
        - Repeat until LLM is done

        Args:
            user_message: User's input message
            system_prompt: Optional system prompt for context

        Returns:
            Final text response from LLM

        Raises:
            RuntimeError: If max iterations reached
        """
        # Inject project context into first message only (not into system prompt)
        # This prevents repeating 8KB+ of context on every API call
        if len(self.messages) == 0 and self.project_context:
            enhanced_message = f"{self.project_context}\n\n{'─' * 80}\n\n{user_message}"
        else:
            enhanced_message = user_message

        # Add user message to history
        self.messages.append({"role": "user", "content": enhanced_message})

        # Get model name from tier
        model = self.provider_config.get_model(self.model_tier)

        # Agentic loop
        for iteration in range(self.max_iterations):
            console.print(
                f"[dim]Iteration {iteration + 1}/{self.max_iterations}...[/dim]"
            )

            # Manage context window before each LLM call
            self._manage_context_window()

            # Filter tools based on execution mode
            read_only = self.execution_mode.is_read_only()

            # Log API request details for debugging
            logger.debug(
                f"API request: model={model}, "
                f"messages_count={len(self.messages)}, "
                f"tools_count={len(self.tool_registry.get_schemas(read_only=read_only))}, "
                f"execution_mode={self.execution_mode.value}"
            )

            # Call LLM with tools
            try:
                # When using OAuth, exclude risk_level field (Anthropic OAuth API rejects custom fields)
                include_risk = not bool(self._provider_config.oauth)

                response = self.client.messages.create(
                    model=model,
                    max_tokens=4096,
                    messages=self.messages,
                    tools=self.tool_registry.get_schemas(
                        include_risk_level=include_risk, read_only=read_only
                    ),
                    system=system_prompt or self.system_prompt,
                )
                logger.debug(f"API response: stop_reason={response.stop_reason}")
            except Exception as e:
                logger.error(
                    f"API call failed: {e}",
                    exc_info=True,
                )
                logger.debug(f"Messages at time of error: {self.messages}")
                raise

            # Check stop reason
            if response.stop_reason == "end_turn":
                # LLM is done, extract text response
                return self._extract_text(response)

            elif response.stop_reason == "tool_use":
                # LLM wants to use tools
                console.print("[cyan]🔧 Agent using tools...[/cyan]")

                # Add assistant's response to history
                self.messages.append({"role": "assistant", "content": response.content})

                # Execute all tool calls
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = self._execute_tool(block.name, block.input, block.id)
                        tool_results.append(result)

                # Add tool results to history
                self.messages.append({"role": "user", "content": tool_results})

                # Loop continues - LLM will process tool results

            elif response.stop_reason == "max_tokens":
                console.print(
                    "[yellow]⚠ Response truncated (max tokens reached)[/yellow]"
                )
                return self._extract_text(response)

            elif response.stop_reason is None:
                # Some providers (like MiniMax M2) return None as stop_reason
                # This is valid - treat it as end_turn
                logger.debug(f"Stop reason is None, treating as end_turn")
                return self._extract_text(response)

            else:
                # Log unexpected stop reasons but don't show warning to user
                logger.warning(
                    f"Unexpected stop reason: {response.stop_reason}, treating as end_turn"
                )
                return self._extract_text(response)

        raise RuntimeError(
            f"Max iterations ({self.max_iterations}) reached without completion"
        )

    def _execute_tool(self, name: str, args: dict, tool_use_id: str) -> dict:
        """Execute a tool and return result.

        Args:
            name: Tool name
            args: Tool arguments
            tool_use_id: ID from LLM's tool_use block

        Returns:
            Tool result in Anthropic format with enriched metadata
        """
        # Format tool announcement with friendly display
        announcement = self._format_tool_announcement(name, args)
        console.print(f"[cyan]  → {announcement}[/cyan]")

        # Check approval if approval manager is configured
        if self.approval_manager:
            try:
                risk_level = self.tool_registry.get_risk_level(name)
                approved = self.approval_manager.should_approve(name, args, risk_level)

                if not approved:
                    console.print("[yellow]  ⚠ User denied tool execution[/yellow]")
                    return {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": "Tool execution denied by user",
                        "is_error": True,
                    }
            except Exception as e:
                logger.error(
                    f"Approval check failed for tool '{name}': {e}", exc_info=True
                )
                console.print(f"[red]  ✗ Approval error: {e}[/red]")
                return {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": f"Approval check failed: {str(e)}",
                    "is_error": True,
                }

        try:
            logger.debug(f"Executing tool '{name}' with args: {args}")
            result = self.tool_registry.execute(name, args)
            console.print("[green]  ✓ Success[/green]")
            logger.info(f"Tool '{name}' executed successfully")

            # Check if this is a background tool and handle specially
            if name in BACKGROUND_TOOLS:
                enriched_result = self._handle_background_tool_result(
                    name, args, result, tool_use_id
                )
            else:
                # Enrich result with metadata for better LLM understanding
                enriched_result = self._enrich_tool_result(name, args, result)

            # Ensure content is a valid string (not bytes, not None, not other types)
            if not isinstance(enriched_result, str):
                enriched_result = str(enriched_result)

            # Truncate extremely large tool results to prevent API errors
            # Some providers (like custom GLM endpoints) have stricter limits
            MAX_TOOL_RESULT_SIZE = 50000  # ~50K characters should be safe
            if len(enriched_result) > MAX_TOOL_RESULT_SIZE:
                truncated_size = MAX_TOOL_RESULT_SIZE - 500  # Leave room for message
                enriched_result = (
                    f"{enriched_result[:truncated_size]}\n\n"
                    f"... [TRUNCATED: {len(enriched_result) - truncated_size} more characters]"
                )
                logger.warning(
                    f"Tool '{name}' result truncated from {len(result)} to {MAX_TOOL_RESULT_SIZE} chars"
                )

            return {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": enriched_result,
            }
        except Exception as e:
            logger.error(f"Tool '{name}' execution failed: {e}", exc_info=True)
            logger.debug(f"Failed tool args: {args}")
            console.print(f"[red]  ✗ Error: {e}[/red]")

            return {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": f"Error: {str(e)}",
                "is_error": True,
            }

    def _abbreviate_path(self, path: str, max_parts: int = 3) -> str:
        """Abbreviate file path to show only last N components.

        Args:
            path: Full file path
            max_parts: Maximum number of path components to show (default: 3)

        Returns:
            Abbreviated path (e.g., "src/cdd_agent/agent.py")
        """
        if not path or path == "?":
            return path

        # Handle relative paths like "." or ".."
        if path in (".", ".."):
            return path

        # Split path into components
        parts = path.split("/")

        # If path is already short enough, return as-is
        if len(parts) <= max_parts:
            return path

        # Return last max_parts components
        abbreviated = "/".join(parts[-max_parts:])

        # Add "..." prefix if we truncated
        return f".../{abbreviated}"

    def _format_tool_announcement(self, tool_name: str, args: dict) -> str:
        """Format tool execution announcement for console.

        Makes tool announcements more readable by showing key info
        instead of raw dict arguments. File paths are abbreviated to
        show only the last 3 components for better readability.

        Args:
            tool_name: Name of the tool
            args: Tool arguments

        Returns:
            Formatted announcement string
        """
        if tool_name == "read_file":
            path = args.get("path", "?")
            short_path = self._abbreviate_path(path)
            return f"📖 Reading: {short_path}"

        elif tool_name == "write_file":
            path = args.get("path", "?")
            short_path = self._abbreviate_path(path)
            return f"📝 Writing: {short_path}"

        elif tool_name == "edit_file":
            path = args.get("path", "?")
            short_path = self._abbreviate_path(path)
            return f"✏️  Editing: {short_path}"

        elif tool_name == "list_files":
            path = args.get("path", ".")
            short_path = self._abbreviate_path(path)
            return f"📁 Listing: {short_path}"

        elif tool_name == "glob_files":
            pattern = args.get("pattern", "?")
            return f"🔍 Finding files: {pattern}"

        elif tool_name == "grep_files":
            pattern = args.get("pattern", "?")
            file_pattern = args.get("file_pattern", "**/*")
            return f"🔎 Searching: '{pattern}' in {file_pattern}"

        elif tool_name == "run_bash":
            command = args.get("command", "?")
            # Truncate long commands
            if len(command) > 50:
                command = command[:47] + "..."
            return f"⚡ Running: {command}"

        elif tool_name == "git_status":
            return "📊 Git status"

        elif tool_name == "git_diff":
            path = args.get("file_path", "")
            if path:
                short_path = self._abbreviate_path(path)
                return f"📊 Git diff: {short_path}"
            return "📊 Git diff (all changes)"

        elif tool_name == "git_log":
            max_commits = args.get("max_commits", 10)
            return f"📊 Git log (last {max_commits} commits)"

        # Background tool announcements
        elif tool_name == "run_bash_background":
            command = args.get("command", "?")
            # Truncate long commands
            if len(command) > 50:
                command = command[:47] + "..."
            return f"🚀 Starting background process: {command}"

        elif tool_name == "get_background_status":
            process_id = args.get("process_id", "?")
            # Show abbreviated process ID
            short_id = process_id[:12] if len(process_id) > 12 else process_id
            return f"📊 Checking background process: {short_id}..."

        elif tool_name == "interrupt_background_process":
            process_id = args.get("process_id", "?")
            short_id = process_id[:12] if len(process_id) > 12 else process_id
            return f"⏹ Interrupting background process: {short_id}..."

        elif tool_name == "get_background_output":
            process_id = args.get("process_id", "?")
            lines = args.get("lines", 50)
            short_id = process_id[:12] if len(process_id) > 12 else process_id
            return f"📄 Retrieving output from {short_id}... (last {lines} lines)"

        elif tool_name == "list_background_processes":
            return "📋 Listing all background processes"

        # Default: show tool name and args
        return f"Executing: {tool_name}({args})"

    def _enrich_tool_result(self, tool_name: str, args: dict, result: Any) -> str:
        """Add context to tool results for better LLM understanding.

        Enriches tool results with metadata like file paths, line counts,
        match statistics, etc. to help the LLM better synthesize information.

        Args:
            tool_name: Name of the tool that was executed
            args: Arguments passed to the tool
            result: Raw result from tool execution

        Returns:
            Enriched result string with metadata
        """
        result_str = str(result)

        if tool_name == "read_file":
            # Add file metadata
            path = args.get("path", "unknown")
            line_count = len(result_str.splitlines())
            char_count = len(result_str)

            return (
                f"File: {path}\n"
                f"Lines: {line_count} | Characters: {char_count}\n"
                f"{'─' * 60}\n"
                f"{result_str}"
            )

        elif tool_name == "write_file":
            # Already has good metadata from tool, just add separator
            path = args.get("path", "unknown")
            return f"📝 {result_str}\n\nFile written: {path}"

        elif tool_name == "edit_file":
            # Already has good metadata, add separator
            path = args.get("path", "unknown")
            return f"✏️  {result_str}\n\nFile edited: {path}"

        elif tool_name == "glob_files":
            # Extract count from result or count lines
            lines = result_str.splitlines()
            # First line usually has "Found X files"
            if lines and "Found" in lines[0]:
                return result_str  # Already well formatted
            else:
                file_count = len([line for line in lines if line.strip()])
                return f"Glob search results ({file_count} files):\n{result_str}"

        elif tool_name == "grep_files":
            # Extract match count or count matches
            lines = result_str.splitlines()
            if lines and "Found" in lines[0]:
                return result_str  # Already well formatted
            else:
                # Count matches (lines with file:line_num format)
                match_count = len(
                    [line for line in lines if ":" in line and line.startswith(" ")]
                )
                return f"Search results ({match_count} matches):\n{result_str}"

        elif tool_name == "list_files":
            # Add directory info
            path = args.get("path", ".")
            items = result_str.splitlines()
            item_count = len(items)

            if "(empty directory)" in result_str:
                return f"Directory: {path}\nStatus: Empty"

            dirs = len([i for i in items if "📁" in i])
            files = len([i for i in items if "📄" in i])

            return (
                f"Directory: {path}\n"
                f"Items: {item_count} total ({dirs} directories, "
                f"{files} files)\n"
                f"{'─' * 60}\n"
                f"{result_str}"
            )

        elif tool_name == "git_status":
            # Add context about git state
            if "clean" in result_str.lower():
                return f"✓ {result_str}"
            elif "Not a git repository" in result_str:
                return f"⚠ {result_str}"
            else:
                change_count = len(result_str.splitlines()) - 1
                return (
                    f"Git repository status ({change_count} changes):\n" f"{result_str}"
                )

        elif tool_name == "git_diff":
            # Add context about diff
            if "No changes" in result_str:
                return f"✓ {result_str}"
            else:
                lines = result_str.splitlines()
                additions = len([line for line in lines if line.startswith("+")])
                deletions = len([line for line in lines if line.startswith("-")])
                return (
                    f"Git diff (+{additions} additions, -{deletions} "
                    f"deletions):\n{result_str}"
                )

        elif tool_name == "run_bash":
            # Add command context
            command = args.get("command", "unknown")
            lines = result_str.splitlines()
            line_count = len(lines)

            return (
                f"Command: {command}\n"
                f"Output ({line_count} lines):\n"
                f"{'─' * 60}\n"
                f"{result_str}"
            )

        # Default: return as-is for unknown tools
        return result_str

    def _register_background_process(self, process_id: str, command: str) -> None:
        """Register a background process with the agent for context awareness.
        
        Args:
            process_id: Unique identifier for the background process
            command: Command being executed
        """
        self.background_processes[process_id] = {
            "process_id": process_id,
            "command": command,
            "start_time": time.time(),
            "status": "starting",
            "args": {}  # Tool arguments used
        }
        
        self.background_process_counter += 1
        logger.info(f"Agent registered background process: {process_id[:12]}... for command: {command[:100]}")

    def _get_background_process(self, process_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a background process.
        
        Args:
            process_id: Process identifier
            
        Returns:
            Process information dict or None if not found
        """
        return self.background_processes.get(process_id)

    def _list_background_processes(self) -> List[Dict[str, Any]]:
        """List all tracked background processes.
        
        Returns:
            List of process information dictionaries
        """
        return list(self.background_processes.values())

    def _handle_background_tool_result(self, tool_name: str, args: dict, result: str, tool_use_id: str) -> str:
        """Handle results from background tools with enhanced context.
        
        Args:
            tool_name: Name of the background tool
            args: Arguments passed to the tool
            result: Result from tool execution
            tool_use_id: Tool use ID from LLM
            
        Returns:
            Enhanced result string with process information
        """
        if tool_name == "run_bash_background":
            # Extract process ID from result
            import re
            command = args.get("command", "unknown")
            match = re.search(r'Background process started: (\w+-\w+-\w+-\w+-\w+)', result)

            if match:
                process_id = match.group(1)

                # Register process with agent
                self._register_background_process(process_id, command)

                # Return enhanced result with context
                return (
                    f"🚀 Background process started: {process_id[:12]}...\n"
                    f"Command: {command}\n\n"
                    f"{result}"
                )
            else:
                # Failed to start background process
                return (
                    f"❌ Failed to start background process\n"
                    f"Command: {command}\n\n"
                    f"{result}"
                )
        
        elif tool_name in ["get_background_status", "get_background_output", "list_background_processes"]:
            # These tools work with existing processes, add process context
            process_info = None
            
            if tool_name == "get_background_status" or tool_name == "get_background_output":
                process_id = args.get("process_id")
                process_info = self._get_background_process(process_id)
            elif tool_name == "list_background_processes":
                from .background_executor import get_background_executor
                executor = get_background_executor()
                processes = executor.list_all_processes()
                if processes:
                    process_info = {
                        "count": len(processes),
                        "running": len([p for p in processes if p.status.value == "running"]),
                        "completed": len([p for p in processes if p.status.value == "completed"])
                    }
            
            # Enhance result with process context
            if process_info:
                if tool_name == "get_background_status":
                    enriched_result = (
                        f"📊 Process Status: {process_info.get('process_id', 'unknown')}\n"
                        f"Status: {process_info.get('status', 'unknown')}\n"
                        f"Command: {process_info.get('command', 'unknown')}\n"
                        f"Runtime: {time.time() - process_info.get('start_time', time.time()):.1f}s\n"
                        f"{'─' * 40}\n"
                        f"{result}"
                    )
                elif tool_name == "get_background_output":
                    enriched_result = (
                        f"📄 Process Output: {process_info.get('process_id', 'unknown')}\n"
                        f"Command: {process_info.get('command', 'unknown')}\n"
                        f"Status: {process_info.get('status', 'unknown')}\n"
                        f"{'─' * 40}\n"
                        f"{result}"
                    )
                elif tool_name == "list_background_processes":
                    active_count = process_info.get("count", 0)
                    running_count = process_info.get("running", 0)
                    completed_count = process_info.get("completed", 0)
                    
                    enriched_result = (
                        f"📋 Background Processes Summary\n"
                        f"Total: {active_count}\n"
                        f"Running: {running_count}\n"
                        f"Completed: {completed_count}\n"
                        f"{'─' * 40}\n"
                        f"{result}"
                    )
                
                return enriched_result
            
        # Default: return as-is for unknown background tools
        return result

    def _calculate_conversation_size(self) -> int:
        """Calculate total character count of conversation, including nested content.

        Properly handles list content (tool_result blocks) by recursively
        counting all string content, not just the string representation.

        Returns:
            Total character count
        """
        total = 0
        for msg in self.messages:
            content = msg.get("content", "")

            if isinstance(content, str):
                total += len(content)
            elif isinstance(content, list):
                # Handle tool_result blocks and other list content
                for item in content:
                    if isinstance(item, dict):
                        # Count all string values in the dict
                        for value in item.values():
                            if isinstance(value, str):
                                total += len(value)
                    elif isinstance(item, str):
                        total += len(item)

        return total

    def _manage_context_window(self, max_messages: int = 100, max_chars: int = 500000):
        """Prune old messages to stay within context limits.

        Strategy:
        - Keep first message (often contains important context)
        - Keep last N messages (recent context)
        - Compress middle messages (summarize tool results)
        - Drop middle messages if still too large

        This prevents the conversation history from growing unbounded and
        eventually hitting API context limits.

        Args:
            max_messages: Maximum number of messages to keep (default: 16)
                         Balanced to avoid over-compaction while staying under provider limits.
                         Previous value of 10 caused too-frequent compaction overhead.
            max_chars: Maximum total character count for all messages (default: 60K)
                       Increased from 40K to reduce compaction frequency while staying safe
        """
        # Check both message count and character size
        total_chars = self._calculate_conversation_size()
        logger.debug(f"Context check: {len(self.messages)} messages, {total_chars} chars (limits: {max_messages} msgs, {max_chars} chars)")

        # If under both limits, no action needed
        if len(self.messages) < max_messages and total_chars <= max_chars:
            return

        # If over limits, just log it (compaction disabled - testing without it)
        if total_chars > max_chars or len(self.messages) >= max_messages:
            logger.warning(
                f"Context limits reached ({len(self.messages)} msgs, {total_chars} chars) - compaction disabled for testing"
            )
            # self._compact_conversation()  # DISABLED to test behavior without compaction
            return

    def _compact_conversation(self):
        """Compact conversation history by summarizing old exchanges.

        Similar to Claude Code's /compact command, this:
        1. Keeps the initial user message (important context)
        2. Keeps the last 4 messages (recent context)
        3. Summarizes middle messages (compress tool results)

        This is more intelligent than simple pruning - it preserves
        the essence of what was done without keeping all the details.
        """
        if len(self.messages) <= 6:
            # Too short to compact meaningfully
            return

        # Keep first message and last 4 messages
        first_message = self.messages[0]
        last_messages = self.messages[-4:]
        middle_messages = self.messages[1:-4]

        # Generate summary of middle messages
        summary_parts = []
        tools_used = set()

        for msg in middle_messages:
            content = msg.get("content", "")

            # Extract tool names from tool_result blocks
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        # Extract tool name from the previous assistant message
                        # For now, just note that tools were used
                        tools_used.add("tools")

            # For assistant messages, extract text content
            if msg.get("role") == "assistant":
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "")
                            if text and len(text) > 100:
                                # Keep first sentence or 100 chars
                                summary_parts.append(text[:100] + "...")
                elif isinstance(content, str) and content:
                    if len(content) > 100:
                        summary_parts.append(content[:100] + "...")

        # Create compact summary message
        summary_text = "Previous conversation summary:\n"
        if tools_used:
            summary_text += "- Used various tools to analyze and modify code\n"
        if summary_parts:
            summary_text += "- Key actions: " + "; ".join(summary_parts[:3]) + "\n"
        summary_text += f"[{len(middle_messages)} messages compacted]"

        # Create summary message
        summary_message = {
            "role": "user",
            "content": summary_text
        }

        # Replace message history
        old_count = len(self.messages)
        self.messages = [first_message, summary_message] + last_messages

        # Calculate size reduction
        old_size = sum(len(str(msg.get("content", ""))) for msg in middle_messages)
        new_size = len(summary_text)

        logger.info(
            f"Compacted {old_count} messages to {len(self.messages)} "
            f"(saved ~{old_size - new_size} chars)"
        )
        console.print(
            f"[dim]💾 Conversation compacted: {old_count} → {len(self.messages)} messages "
            f"(saved ~{(old_size - new_size) / 1024:.1f}KB)[/dim]"
        )

    def compact(self):
        """Manually trigger conversation compaction (like Claude Code's /compact).

        This is the public API for manual compaction that can be called
        from slash commands or user requests.
        """
        if len(self.messages) <= 6:
            console.print("[yellow]⚠ Conversation too short to compact (need at least 6 messages)[/yellow]")
            return False

        self._compact_conversation()
        return True

    def _extract_text(self, response) -> str:
        """Extract text content from response.

        Args:
            response: Anthropic API response

        Returns:
            Text content as string
        """
        text_parts = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)

        return "\n".join(text_parts) if text_parts else ""

    def stream(
        self, user_message: str, system_prompt: Optional[str] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """Stream conversation with user message.

        Similar to run() but yields chunks as they arrive for real-time display.

        Yields:
            Dict with 'type' and data:
            - {'type': 'text', 'content': str} - Text chunk from LLM
            - {'type': 'tool_use', 'name': str, 'args': dict} - Tool being called
            - {'type': 'tool_result', 'name': str, 'result': str} - Tool result
            - {'type': 'thinking', 'content': str} - Status messages
            - {'type': 'error', 'content': str} - Error messages

        Args:
            user_message: User's input message
            system_prompt: Optional system prompt for context
        """
        # Inject project context into first message only (not into system prompt)
        # This prevents repeating 8KB+ of context on every API call
        if len(self.messages) == 0 and self.project_context:
            enhanced_message = f"{self.project_context}\n\n{'─' * 80}\n\n{user_message}"
        else:
            enhanced_message = user_message

        # Add user message to history
        self.messages.append({"role": "user", "content": enhanced_message})

        # Get model name from tier
        model = self.provider_config.get_model(self.model_tier)

        # Agentic loop
        for iteration in range(self.max_iterations):
            yield {
                "type": "thinking",
                "content": f"Iteration {iteration + 1}/{self.max_iterations}",
            }

            # Manage context window before each LLM call
            self._manage_context_window()

            # Filter tools based on execution mode
            read_only = self.execution_mode.is_read_only()

            # Log API request details for debugging
            logger.debug(
                f"Streaming API request: model={model}, "
                f"messages_count={len(self.messages)}, "
                f"tools_count={len(self.tool_registry.get_schemas(read_only=read_only))}, "
                f"execution_mode={self.execution_mode.value}"
            )

            # Stream LLM response
            try:
                # When using OAuth, exclude risk_level field (Anthropic OAuth API rejects custom fields)
                include_risk = not bool(self._provider_config.oauth)

                with self.client.messages.stream(
                    model=model,
                    max_tokens=4096,
                    messages=self.messages,
                    tools=self.tool_registry.get_schemas(
                        include_risk_level=include_risk, read_only=read_only
                    ),
                    system=system_prompt or self.system_prompt,
                ) as stream:
                    # Accumulate response
                    accumulated_text = []
                    accumulated_tool_uses = []

                    for event in stream:
                        # Text delta - stream it immediately
                        if event.type == "content_block_delta":
                            if hasattr(event.delta, "text"):
                                chunk = event.delta.text
                                accumulated_text.append(chunk)
                                yield {"type": "text", "content": chunk}

                        # Tool use - accumulate and announce
                        elif event.type == "content_block_start":
                            if hasattr(event.content_block, "type"):
                                if event.content_block.type == "tool_use":
                                    tool_use = {
                                        "id": event.content_block.id,
                                        "name": event.content_block.name,
                                        "input": {},
                                    }
                                    accumulated_tool_uses.append(tool_use)
                                    yield {
                                        "type": "tool_use",
                                        "name": event.content_block.name,
                                    }

                        # Tool input delta - accumulate
                        elif event.type == "content_block_delta":
                            if hasattr(event.delta, "partial_json"):
                                # Update the last tool use input (streaming JSON)
                                if accumulated_tool_uses:
                                    # We'll get the full input at message_stop
                                    pass

                    # Get final message
                    final_message = stream.get_final_message()
                    logger.debug(
                        f"Streaming API response: "
                        f"stop_reason={final_message.stop_reason}"
                    )

                    # Add assistant response to history
                    self.messages.append(
                        {"role": "assistant", "content": final_message.content}
                    )

                    # Check stop reason
                    if final_message.stop_reason == "end_turn":
                        # Done!
                        return

                    elif final_message.stop_reason == "tool_use":
                        # Execute tools
                        tool_results = []
                        for block in final_message.content:
                            if block.type == "tool_use":
                                # Execute and yield result
                                result = self._execute_tool(
                                    block.name, block.input, block.id
                                )
                                tool_results.append(result)

                                yield {
                                    "type": "tool_result",
                                    "name": block.name,
                                    "result": result.get("content", ""),
                                    "is_error": result.get("is_error", False),
                                }

                        # Add tool results to history
                        self.messages.append({"role": "user", "content": tool_results})

                        # Log tool results for debugging
                        logger.debug(
                            f"Added {len(tool_results)} tool result(s) to conversation history"
                        )

                        # Continue loop - LLM will process tool results

                    elif final_message.stop_reason == "max_tokens":
                        yield {
                            "type": "error",
                            "content": "Response truncated (max tokens reached)",
                        }
                        return

                    elif final_message.stop_reason is None:
                        # Some providers (like MiniMax M2) return None as stop_reason
                        # This is valid - treat it as end_turn
                        logger.debug(f"Stop reason is None, treating as end_turn")
                        return

                    else:
                        # Log unexpected stop reasons but don't treat as error
                        logger.warning(
                            f"Unexpected stop reason: {final_message.stop_reason}, treating as end_turn"
                        )
                        return
            except Exception as e:
                # Check if this is an overloaded error (529)
                error_message = str(e)
                is_overloaded = "overloaded" in error_message.lower() or "529" in error_message

                logger.error(
                    f"Streaming API call failed: {e}",
                    exc_info=True,
                )
                logger.debug(f"Messages at time of error: {self.messages}")

                # Provide helpful error message
                if is_overloaded:
                    yield {
                        "type": "error",
                        "content": (
                            "⚠️ Anthropic API is temporarily overloaded (all 5 retry attempts failed).\n\n"
                            "This is a service-level issue, not related to your request size.\n"
                            "Please try again in a few moments."
                        ),
                    }
                else:
                    yield {
                        "type": "error",
                        "content": f"API error: {error_message}",
                    }
                return

        # Max iterations reached
        yield {
            "type": "error",
            "content": f"Max iterations ({self.max_iterations}) reached",
        }

    def run_with_reflection(
        self, user_message: str, system_prompt: Optional[str] = None
    ) -> str:
        """Run conversation with post-execution reflection summary.

        Similar to run() but adds an optional reflection summary at the end
        if the task involved significant tool usage. The reflection provides:
        - What was accomplished
        - Files that were modified
        - Potential issues or areas needing attention
        - Suggested next steps

        Args:
            user_message: User's input message
            system_prompt: Optional system prompt for context

        Returns:
            Final text response with optional reflection summary appended
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

        Reflection is useful when the agent has used multiple tools,
        indicating a complex task that would benefit from a summary.

        Returns:
            True if tools were used extensively (>2 tool calls)
        """
        # Count how many times tools were used
        tool_count = sum(
            1
            for msg in self.messages
            if msg.get("role") == "assistant"
            and any(
                b.get("type") == "tool_use"
                for b in (
                    msg.get("content", [])
                    if isinstance(msg.get("content"), list)
                    else []
                )
            )
        )

        # Reflect if we executed tools multiple times
        return tool_count > 2

    def _get_reflection(self) -> str:
        """Ask LLM to reflect on what was accomplished.

        Sends a reflection prompt to the LLM asking it to summarize
        the work that was just completed.

        Returns:
            Brief summary of accomplishments, files modified, and next steps
        """
        reflection_prompt = """You just completed a task. Please provide a \
brief summary:

1. What was accomplished
2. Files that were modified (with paths)
3. Potential issues or areas needing attention
4. Suggested next steps

Keep it concise (3-5 bullet points)."""

        # Make a quick non-streaming call for reflection
        self.messages.append({"role": "user", "content": reflection_prompt})

        model = self.provider_config.get_model(self.model_tier)

        try:
            response = self.client.messages.create(
                model=model,
                max_tokens=500,
                messages=self.messages,
                system="You are summarizing your previous work.",
            )

            return self._extract_text(response)
        except Exception as e:
            # If reflection fails, just skip it
            console.print(f"[yellow]⚠ Reflection skipped: {e}[/yellow]")
            return ""

    def clear_history(self):
        """Clear conversation history."""
        self.messages = []

    def set_execution_mode(self, mode: ExecutionMode):
        """Set execution mode (for runtime toggling).

        Args:
            mode: ExecutionMode (NORMAL or PLAN)
        """
        self.execution_mode = mode
        logger.debug(f"Execution mode changed to: {mode.value}")


class SimpleAgent:
    """Simplified agent for quick testing (no tool use)."""

    def __init__(self, provider_config: ProviderConfig, model_tier: str = "mid"):
        """Initialize simple agent.

        Args:
            provider_config: Provider configuration
            model_tier: Model tier to use
        """
        self.provider_config = provider_config
        self.model_tier = model_tier

        # Lazy Anthropic client - will be initialized when first needed
        self._client = None

    @property
    def client(self):
        """Lazy initialization of Anthropic client.

        Returns:
            Initialized Anthropic client
        """
        if self._client is None:
            try:
                import anthropic

                self._client = anthropic.Anthropic(
                    api_key=self.provider_config.get_api_key(),
                    base_url=self.provider_config.base_url,
                    max_retries=5,  # Increase from default 2 to handle overloaded errors
                    timeout=600.0,  # 10 minutes timeout for long-running requests
                )
            except ImportError as e:
                raise ImportError(
                    "Failed to import anthropic. Please install it with: "
                    "pip install anthropic"
                ) from e
        return self._client

    def run(self, user_message: str, system_prompt: Optional[str] = None) -> str:
        """Simple conversation without tools.

        Args:
            user_message: User's message
            system_prompt: Optional system prompt

        Returns:
            LLM response
        """
        model = self.provider_config.get_model(self.model_tier)

        response = self.client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": user_message}],
            system=system_prompt or "You are a helpful assistant.",
        )

        # Extract text
        for block in response.content:
            if block.type == "text":
                return block.text

        return ""
