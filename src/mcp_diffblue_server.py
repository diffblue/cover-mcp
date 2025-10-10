#!/usr/bin/env python3
"""
MCP (Model Context Protocol) server for Diffblue Cover with tool discovery support.
Compatible with LM Studio and other MCP clients that require tool discoverability.
"""

import sys
import json
import subprocess
import os
from typing import Dict, Any, List


class DiffblueCoverMCPServer:
    """MCP server implementation for Diffblue Cover CLI integration."""
    
    def __init__(self):
        self.tools = {
            "dcover_create": {
                "name": "dcover_create",
                "description": "Generate unit tests using Diffblue Cover CLI",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "working_directory": {
                            "type": "string",
                            "description": "Working directory for running dcover create (optional)"
                        },
                        "entry_point": {
                            "type": "string",
                            "description": "Fully qualified class name to test (optional)"
                        }
                    }
                }
            }
        }
        
    def handle_initialize(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle the initialize request."""
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "diffblue-cover-mcp",
                    "version": "1.0.0"
                }
            }
        }
    
    def handle_tools_list(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle the tools/list request for tool discovery."""
        tools_list = []
        for tool_name, tool_info in self.tools.items():
            tools_list.append({
                "name": tool_info["name"],
                "description": tool_info["description"],
                "inputSchema": tool_info["inputSchema"]
            })
            
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "tools": tools_list
            }
        }
    
    def handle_tools_call(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle the tools/call request to execute a tool."""
        params = request.get("params", {})
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        
        if tool_name not in self.tools:
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32602,
                    "message": f"Unknown tool: {tool_name}"
                }
            }
        
        if tool_name == "dcover_create":
            result = self.run_dcover_create(
                tool_args.get("working_directory"),
                tool_args.get("entry_point")
            )
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2)
                        }
                    ]
                }
            }
    
    def run_dcover_create(self, working_dir: str = None, entry_point: str = None) -> Dict[str, Any]:
        """
        Executes 'dcover create' in the specified working directory.
        """
        if not working_dir:
            working_dir = os.getcwd()
            
        command = ["dcover", "create"]

        # Add entry point if provided
        if entry_point:
            command.append(entry_point)
        
        try:
            result = subprocess.run(
                command,
                cwd=working_dir,
                capture_output=True,
                text=True,
                check=False
            )
            
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode,
                "status": "success" if result.returncode == 0 else "error"
            }
            
        except FileNotFoundError:
            return {
                "stdout": "",
                "stderr": "Error: Diffblue Cover CLI ('dcover') not found. Ensure it is installed and in your PATH.",
                "return_code": 127,
                "status": "error"
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Unexpected execution error: {str(e)}",
                "return_code": 1,
                "status": "error"
            }
    
    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Route the request to the appropriate handler."""
        method = request.get("method", "")
        
        if method == "initialize":
            return self.handle_initialize(request)
        elif method == "tools/list":
            return self.handle_tools_list(request)
        elif method == "tools/call":
            return self.handle_tools_call(request)
        else:
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
    
    def run(self):
        """Main loop to handle JSON-RPC requests over stdin/stdout."""
        while True:
            try:
                # Read a line from stdin
                line = sys.stdin.readline()
                if not line:
                    break
                    
                # Parse the JSON-RPC request
                request = json.loads(line.strip())
                
                # Handle the request
                response = self.handle_request(request)
                
                # Write the response to stdout
                json.dump(response, sys.stdout)
                sys.stdout.write('\n')
                sys.stdout.flush()
                
            except json.JSONDecodeError as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {str(e)}"
                    }
                }
                json.dump(error_response, sys.stdout)
                sys.stdout.write('\n')
                sys.stdout.flush()
            except Exception as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {str(e)}"
                    }
                }
                json.dump(error_response, sys.stdout)
                sys.stdout.write('\n')
                sys.stdout.flush()


def main():
    """Entry point for the MCP server."""
    server = DiffblueCoverMCPServer()
    server.run()


if __name__ == "__main__":
    main()
