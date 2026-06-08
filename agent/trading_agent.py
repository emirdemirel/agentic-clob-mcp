from __future__ import annotations

import asyncio
import os
import sys

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStreamableHTTP

MCP_PORT = os.environ.get("MCP_PORT", "8000")
MCP_HOST = os.environ.get("MCP_HOST", f"http://localhost:{MCP_PORT}/mcp")

mcp_server = MCPServerStreamableHTTP(MCP_HOST)

trading_agent = Agent(
    "anthropic:claude-sonnet-4-20250514",
    instructions=(
        "You are a precise trading assistant for the ETH/USDC spot market.\n"
        "RULES:\n"
        "1. Always read the order book spread BEFORE placing any order.\n"
        "2. Confirm the exact price and quantity before execution.\n"
        "3. Report all fills and order status after placement.\n"
        "4. All prices are in USDC. All quantities are in ETH.\n"
        "5. If the user request is ambiguous, ask for clarification.\n"
        "6. Never fabricate market data. Only report what the tools return."
    ),
    toolsets=[mcp_server],
)


async def main() -> None:
    async with trading_agent:
        message_history = []
        print("Agentic CLOB Trading Agent (ETH/USDC)")
        print("Type 'quit' or 'exit' to stop.\n")

        while True:
            try:
                user_input = input("You: ")
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            if user_input.strip().lower() in ("quit", "exit"):
                print("Goodbye!")
                break

            if not user_input.strip():
                continue

            result = await trading_agent.run(user_input, message_history=message_history)
            message_history = result.all_messages()
            print(f"Agent: {result.output}\n")


if __name__ == "__main__":
    asyncio.run(main())
