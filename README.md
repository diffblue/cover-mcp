# **MCP Server for Diffblue Cover CLI**

This repository provides a **Model Context Protocol (MCP) Server**
for the Diffblue Cover CLI tool (`dcover`), making it
callable and manageable by various AI development environments that
adhere to the MCP specification (like the Gemini CLI).

## **Core Component: The MCP Server (mcp\_diffblue\_server.py)**

The Python script serves as the universal adapter for the `dcover create` command.

### **Server Logic Overview**

1. **Input:** Reads a JSON payload from stdin containing the MCP request.
2. **Context Extraction:** Extracts the required `id` and the `working_directory` (usually found in the `params.context` field).
3. **Execution:** Executes the shell command `dcover create` using the extracted working directory as the context (`cwd`).
4. **Output:** Constructs an MCP-compliant JSON response, including the execution status, return_code, stdout, and stderr.
5. **Return:** Writes the final JSON response to stdout.

## **Prerequisites**

Before configuring the server with any host environment, ensure you have the following installed:

1. **Diffblue Cover CLI:** The`dcover` command must be installed and accessible in your system's `PATH`.
   * You can verify this by running `dcover version` in your terminal.
2. **Python 3:** The MCP server script is written in Python.

## **Tool Integration and Setup**

To use this MCP server, you must provide your host AI environment (e.g., Gemini CLI, Claude Code, Windsurf, Devin) with a configuration that tells it how to invoke the Python script.

### **1. Configuration for Gemini CLI (via Extension Manifest)**

The Gemini CLI uses a JSON manifest file to register external tools. This process is straightforward and allows the model to recommend or execute the tool command directly.

#### **Step 1: Create the Extension Manifest**

Create a file named **diffblue-cover.json** in the same directory as
your Python script.
```
{
  "name": "Diffblue Cover",
  "command": "dcover_create",
  "description": "Generate unit tests using Diffblue Cover CLI.",
  "executable": "python",
  "args": ["mcp_diffblue_server.py"],
  "response_schema": {
    "type": "object",
    "properties": {
      "stdout": { "type": "string" },
      "stderr": { "type": "string" },
      "return_code": { "type": "number" }
    }
  }
}
```
|  | Field | Description |
| :---- | :---- | :---- |
|  | name | The friendly name of the tool. |
|  | command | The actual command/verb you will use in the Gemini CLI (e.g., `/dcover_create`). |
|  | executable | The program used to run the script (e.g., python). |
|  | args | Arguments passed to the executable (`mcp_diffblue_server.py`). |
|  | response\_schema | Defines the structure of the result object returned by the server. |

#### **Step 2: Install the Extension**

Assuming both files are in a folder named diffblue-extension, install
it using the Gemini CLI command:
```
# Navigate to the directory containing your extension files
cd /path/to/diffblue-extension

# Install the extension using its JSON manifest file
gemini extensions install ./diffblue-cover.json
```

#### **Usage**

You can now instruct the model to use the tool in your chat prompt:
"I need unit tests for the current working directory. Please run the Diffblue Cover tool."
The Gemini CLI will execute the tool command `/dcover\_create`.

### 2. Configuration for Claude Code

Claude Code supports external tools through MCP-compatible manifest files. By registering Diffblue Cover as a tool, you can have Claude invoke it directly during coding sessions.

#### Step 1: Create the MCP Tool Manifest

Create a file named **diffblue-cover.mcp.json** in the same directory as your Python script:

```
{
  "name": "Diffblue Cover",
  "command": "dcover_create",
  "description": "Generate unit tests using Diffblue Cover CLI.",
  "executable": "python",
  "args": ["mcp_diffblue_server.py"],
  "response_schema": {
    "type": "object",
    "properties": {
      "stdout": { "type": "string" },
      "stderr": { "type": "string" },
      "return_code": { "type": "number" }
    }
  }
}
```

| Field | Description |
| :---- | :---- |
| **name** | Friendly name for the tool. |
| **command** | The command name Claude Code will recognize, e.g., `/dcover_create`. |
| **description** | Description shown when Claude suggests or executes the tool. |
| **executable** | The runtime used to start the MCP server (`python`). |
| **args** | Arguments passed to the executable (`mcp_diffblue_server.py`). |
| **response_schema** | Defines the expected response structure from the Diffblue MCP server. |

#### Step 2: Register the Tool in Claude Code

Move your manifest to Claude's local MCP tools directory:
```
mv diffblue-cover.mcp.json ~/.claude/mcp/tools/
```

#### Step 3: Restart Claude Code

Restart Claude Code to detect and load the new MCP tool:
```
claude restart
```

#### Usage

Once configured, you can ask Claude Code to generate tests automatically:
> "Generate unit tests for my current project using Diffblue Cover."

Claude Code will execute the `/dcover_create` command and return the results generated by the Diffblue Cover MCP server.

### 3. Configuration for Devin

Devin supports custom MCP tools through manifest files, allowing it to execute external commands such as Diffblue Cover via its MCP infrastructure.

#### Step 1: Create the MCP Tool Manifest

Create a file named **diffblue-cover.mcp.json** in the same directory as your Python script:

```
{
  "name": "Diffblue Cover",
  "command": "dcover_create",
  "description": "Generate unit tests using Diffblue Cover CLI.",
  "executable": "python",
  "args": ["mcp_diffblue_server.py"],
  "response_schema": {
    "type": "object",
    "properties": {
      "stdout": { "type": "string" },
      "stderr": { "type": "string" },
      "return_code": { "type": "number" }
    }
  }
}
```

| Field | Description |
| :---- | :---- |
| **name** | Human-friendly name for the tool. |
| **command** | Command that Devin will recognize (e.g., `/dcover_create`). |
| **description** | Short summary of the tool’s purpose. |
| **executable** | Runtime used to start the MCP process (`python`). |
| **args** | Arguments passed to the executable (`mcp_diffblue_server.py`). |
| **response_schema** | Specifies the structure of the response returned by the MCP server. |

#### Step 2: Register the Tool in Devin

Move your manifest into Devin’s MCP directory:
```
mv diffblue-cover.mcp.json ~/.devin/mcp/tools/
```

#### Step 3: Restart Devin

Restart the Devin environment to detect and load your custom MCP tool:
```
devin restart
```

#### Usage

Once registered, you can tell Devin:
> "Generate unit tests for my current project using Diffblue Cover."

Devin will call the `/dcover_create` MCP tool and return the test output generated by Diffblue Cover.

---

### 4. Configuration for Windsurf

Windsurf also uses MCP-compatible tool manifests to integrate external utilities like Diffblue Cover.

#### Step 1: Create the MCP Tool Manifest

Save the same manifest file as **diffblue-cover.mcp.json**:
```
{
  "name": "Diffblue Cover",
  "command": "dcover_create",
  "description": "Generate unit tests using Diffblue Cover CLI.",
  "executable": "python",
  "args": ["mcp_diffblue_server.py"],
  "response_schema": {
    "type": "object",
    "properties": {
      "stdout": { "type": "string" },
      "stderr": { "type": "string" },
      "return_code": { "type": "number" }
    }
  }
}
```

| Field | Description |
| :---- | :---- |
| **name** | Human-readable tool name displayed in Windsurf. |
| **command** | The command Windsurf will execute (e.g., `/dcover_create`). |
| **description** | Visible text summarizing what the tool does. |
| **executable** | Program used to launch the Diffblue MCP server (`python`). |
| **args** | CLI arguments for the executable (`mcp_diffblue_server.py`). |
| **response_schema** | Output format that Windsurf expects from the MCP server. |

#### Step 2: Register the Tool in Windsurf

Move or copy the manifest into Windsurf’s MCP tools directory:
```
mv diffblue-cover.mcp.json ~/.windsurf/mcp/tools/
```

#### Step 3: Restart Windsurf

Reload Windsurf to register the new MCP tool:
```
windsurf restart
```

#### Usage

After setup, you can use the tool by prompting:
> "Generate unit tests for my codebase using Diffblue Cover."

Windsurf will automatically run the `/dcover_create` MCP command through the Diffblue Cover MCP server, returning results directly in your workspace.
