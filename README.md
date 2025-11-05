# **MCP Server for Diffblue Cover CLI**

This repository provides a **Model Context Protocol (MCP) Server** for the Diffblue Cover CLI tool (`dcover`), making
it callable and manageable by various AI development environments that adhere to the MCP specification (like the
Gemini CLI).

## **Core Component: The MCP Server `covermcp/server.py`**

The Python script serves as the universal adapter for the `dcover create` command.

## **Prerequisites**

Before configuring the server with any host environment, ensure you have the following installed:

1. **Diffblue Cover CLI:** The`dcover` command must be installed and accessible in your system's `PATH`.
    * You can verify this by running `dcover version` in your terminal.
2. **uv:** A Python project and package manager (https://docs.astral.sh/uv/)

## **Installing the MCP server**

The project uses [FastMCP](https://gofastmcp.com/getting-started/welcome) to develop and deploy the MCP server. To
install this server, you can use `uv run fastmcp install claude-code --server-spec main.py` (for example), other 
LLM tools are supported out of the box:

```bash
$ uv run fastmcp install --help
Usage: fastmcp install COMMAND

Install MCP servers in various clients and formats.

╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ claude-code     Install an MCP server in Claude Code.                                                                  │
│ claude-desktop  Install an MCP server in Claude Desktop.                                                               │
│ cursor          Install an MCP server in Cursor.                                                                       │
│ gemini-cli      Install an MCP server in Gemini CLI.                                                                   │
│ mcp-json        Generate MCP configuration JSON for manual installation.                                               │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

This command will install the MCP server for _all_ projects, which you may not want. If this is the case, then you can
be targeted in your installation if you use the `mcp-json` option to augment a `.mcp.json` file in the project:

```json
{
  "mcpServers": {
    "Diffblue Cover": {
      "command": "uv",
      "args": [
        "run",
        "--with",
        "fastmcp",
        "fastmcp",
        "run",
        "/path/to/cover-mcp/main.py"
      ]
    }
  }
}
```

This also allows you to specify environment variables. Currently, there are two that you can specify:

* `DIFFBLUE_COVER_CLI` : the location of the installed `dcover` command line
* `DIFFBLUE_COVER_OPTIONS` : use these `dcover` options as well as those supplied by the LLM

To use these variables in the `.mcp.json` file above, you would do so like this:

```json
{
  "mcpServers": {
    "Diffblue Cover": {
      "command": "uv",
      "args": [
        "run",
        "--with",
        "fastmcp",
        "fastmcp",
        "run",
        "/path/to/cover-mcp/main.py"
      ],
      "env": {
        "DIFFBLUE_COVER_CLI": "/path/to/dcover",
        "DIFFBLUE_COVER_OPTIONS": "--verbose --active-profiles=test"
      }
    }
  }
}
```

This will run the equivalent to `/path/to/dcover --batch create <entry points provided by the LLM> --verbose --active-profiles=test`

**Note:** No attempt is made to disambiguate the options provided options. 

## **Developmental Notes**

FastMCP contains a tool called "MCP Inspector" which can be used to interact with the MCP server without needing the
LLM interaction. To run this developmental server, you can use `uv run fastmcp dev`. The configuration lives in the
file `fastmcp.json` which provides (among other things) the entry point for the server.

```bash
$ uv run fastmcp dev --help    
Usage: fastmcp dev [OPTIONS] [ARGS]

Run an MCP server with the MCP Inspector for development.

╭─ Parameters ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ SERVER-SPEC --server-spec  Python file to run, optionally with :object suffix, or None to auto-detect fastmcp.json      │
│ --with-editable            Directory containing pyproject.toml to install in editable mode (can be used multiple times) │
│ --with                     Additional packages to install (can be used multiple times)                                  │
│ --inspector-version        Version of the MCP Inspector to use                                                          │
│ --ui-port                  Port for the MCP Inspector UI                                                                │
│ --server-port              Port for the MCP Inspector Proxy server                                                      │
│ --python                   Python version to use (e.g., 3.10, 3.11)                                                     │
│ --with-requirements        Requirements file to install dependencies from                                               │
│ --project                  Run the command within the given project directory                                           │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

### **Project Layout**

The project and the dependencies are managed by `uv`, see the [documentation](https://docs.astral.sh/uv/) for the
usage instructions.

### **Running Tests**

There are unit tests (in the `test` directory) which you can run with `uv run coverage run -m pytest` and then get a
coverage report with `uv run coverage report --omit "test/*"` (python includes the coverage of the test files by
default -- not that useful).

### **Linting/Formatting**

To run the linter, run `uv run ruff check`. If successful, you will see a message "All checks passed!". If not, you
should address the issues picked up. More information can be found at
the [Ruff Linter Documentation](https://docs.astral.sh/ruff/linter/)

To format the code, run `uv run ruff format`, this should be run before committing any changes. More information can be
found at the [Ruff Formatter Documentation](https://docs.astral.sh/ruff/formatter/).

## *References*

* https://gofastmcp.com/
* https://docs.astral.sh/uv/
* https://docs.astral.sh/ruff/
