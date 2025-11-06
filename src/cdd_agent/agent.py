"""Core agent conversation loop.

This module implements the main agentic loop:
1. User sends message
2. LLM processes with tool access
3. LLM decides to use tools or respond
4. If tool use: execute → feed back to LLM → loop
5. If done: return final response
"""

from typing import Any, Dict, Generator, List, Optional

import anthropic
from rich.console import Console

from .config import ConfigManager, ProviderConfig
from .tools import ToolRegistry

console = Console()


class Agent:
    """Main conversational agent with tool execution."""

    def __init__(
        self,
        provider_config: ProviderConfig,
        tool_registry: ToolRegistry,
        model_tier: str = "mid",
        max_iterations: int = 10,
    ):
        """Initialize agent.

        Args:
            provider_config: Provider configuration
            tool_registry: Registry of available tools
            model_tier: Model tier to use (small/mid/big)
            max_iterations: Maximum conversation iterations
        """
        self.provider_config = provider_config
        self.tool_registry = tool_registry
        self.model_tier = model_tier
        self.max_iterations = max_iterations
        self.messages: List[Dict[str, Any]] = []

        # Initialize Anthropic client
        self.client = anthropic.Anthropic(
            api_key=provider_config.get_api_key(),
            base_url=provider_config.base_url,
        )

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
        # Add user message to history
        self.messages.append({"role": "user", "content": user_message})

        # Get model name from tier
        model = self.provider_config.get_model(self.model_tier)

        # Agentic loop
        for iteration in range(self.max_iterations):
            console.print(
                f"[dim]Iteration {iteration + 1}/{self.max_iterations}...[/dim]"
            )

            # Call LLM with tools
            response = self.client.messages.create(
                model=model,
                max_tokens=4096,
                messages=self.messages,
                tools=self.tool_registry.get_schemas(),
                system=system_prompt or "You are a helpful AI coding assistant.",
            )

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

            else:
                console.print(
                    f"[yellow]⚠ Unexpected stop reason: {response.stop_reason}[/yellow]"
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
            Tool result in Anthropic format
        """
        console.print(f"[cyan]  → Executing: {name}({args})[/cyan]")

        try:
            result = self.tool_registry.execute(name, args)
            console.print(f"[green]  ✓ Success[/green]")

            return {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": str(result),
            }
        except Exception as e:
            console.print(f"[red]  ✗ Error: {e}[/red]")

            return {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": f"Error: {str(e)}",
                "is_error": True,
            }

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
        # Add user message to history
        self.messages.append({"role": "user", "content": user_message})

        # Get model name from tier
        model = self.provider_config.get_model(self.model_tier)

        # Agentic loop
        for iteration in range(self.max_iterations):
            yield {
                "type": "thinking",
                "content": f"Iteration {iteration + 1}/{self.max_iterations}",
            }

            # Stream LLM response
            with self.client.messages.stream(
                model=model,
                max_tokens=4096,
                messages=self.messages,
                tools=self.tool_registry.get_schemas(),
                system=system_prompt or "You are a helpful AI coding assistant.",
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

                # Add assistant response to history
                self.messages.append({"role": "assistant", "content": final_message.content})

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
                            result = self._execute_tool(block.name, block.input, block.id)
                            tool_results.append(result)

                            yield {
                                "type": "tool_result",
                                "name": block.name,
                                "result": result.get("content", ""),
                                "is_error": result.get("is_error", False),
                            }

                    # Add tool results to history
                    self.messages.append({"role": "user", "content": tool_results})

                    # Continue loop - LLM will process tool results

                elif final_message.stop_reason == "max_tokens":
                    yield {
                        "type": "error",
                        "content": "Response truncated (max tokens reached)",
                    }
                    return

                else:
                    yield {
                        "type": "error",
                        "content": f"Unexpected stop reason: {final_message.stop_reason}",
                    }
                    return

        # Max iterations reached
        yield {
            "type": "error",
            "content": f"Max iterations ({self.max_iterations}) reached",
        }

    def clear_history(self):
        """Clear conversation history."""
        self.messages = []


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

        self.client = anthropic.Anthropic(
            api_key=provider_config.get_api_key(),
            base_url=provider_config.base_url,
        )

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
