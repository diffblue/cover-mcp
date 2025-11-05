"""Run the MCP server, allowing LLMs (e.g. Claude) to interact with the tools defined in the covermcp module."""

from covermcp.server import mcp

if __name__ == "__main__":
    mcp.run()
