"""MCP server for Diffblue Cover test generation.

This module provides a FastMCP server that exposes Diffblue Cover's test generation
capabilities through the Model Context Protocol. It allows LLMs to invoke Diffblue Cover
to automatically generate unit tests for Java projects.

The server exposes a 'create' tool that wraps the dcover CLI, providing configurable
test generation with options for fuzzing, verification, and batch processing.

Environment Variables:
    DIFFBLUE_COVER_CLI: Path to the dcover executable (optional if dcover is on PATH)
    DIFFBLUE_COVER_OPTIONS: Override options for the create command
"""

#  Copyright 2025 Diffblue
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Annotated, Any, Final

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from covermcp import executor

# Configuration constants
# These define environment variable names and default values for Diffblue Cover execution.

DIFFBLUE_COVER_CLI: Final[
    Annotated[str, "The name of the environment variable containing the path to the Diffblue Cover CLI"]
] = "DIFFBLUE_COVER_CLI"

DIFFBLUE_COVER_OPTIONS: Final[
    Annotated[
        str,
        (
            "The name of the environment variable containing options for the create command, "
            "overriding those obtained by the LLM"
        ),
    ]
] = "DIFFBLUE_COVER_OPTIONS"

DEFAULT_WORKING_DIRECTORY: Final[Annotated[Path, "The path to the root of the project"]] = Path.cwd()
DEFAULT_TIMEOUT: Final[
    Annotated[int, "The default timeout (in seconds) for us to wait for the dcover process to finish"]
] = 600

# make the executor function type easier to read and understand
ExecutorFunc: type = Callable[[list[str], Path, int | None], Iterator[str]]

# module-level to allow for testing the arguments supplied to dcover.
execute: Annotated[ExecutorFunc, "How to execute system commands."] = executor.execute

# module-level to allow fastmcp to find the configured server.
mcp: Annotated[FastMCP[Any], "The global MCP server"] = FastMCP("DiffblueCover")


@mcp.tool()
# Ignore "too many parameters for a method" check
async def create(  # noqa: PLR0913
        path: Annotated[str | None, "The path to the dcover executable"] = None,
        working_directory: Annotated[Path, "The directory containing the project"] = DEFAULT_WORKING_DIRECTORY,
        dcover_timeout: Annotated[
            int | None, "The maximum time in seconds to wait for dcover to create tests."
        ] = DEFAULT_TIMEOUT,
        entry_points: Annotated[
            list[str] | None,
            "The list of package names, class names, and/or methods to write tests for. "
            "The entries here should be fully qualified, in other words you must include "
            "the package and class names when specifying a method name.",
        ] = None,
        ctx: Annotated[Context | None, "The MCP Server Context"] = None,
) -> object:
    """Invoke Diffblue Cover to generate unit tests for Java code.

    This tool executes the dcover CLI to automatically generate JUnit tests for the
    specified Java classes, methods, or packages. It supports various configuration
    options to control the test generation process.

    Args:
        path: Path to the dcover executable. If not provided, searches system PATH
            and the DIFFBLUE_COVER_CLI environment variable.
        working_directory: Root directory of the Java project to test. Defaults to
            the current working directory.
        dcover_timeout: Maximum execution time in seconds. Defaults to 600. Set to None
            for no timeout (not recommended).
        entry_points: List of fully-qualified Java targets (packages, classes, or methods)
            to generate tests for. Examples: ['com.example.MyClass',
            'com.example.MyClass.myMethod']. If None, tests entire project.
        ctx: MCP server context for logging and progress reporting (auto-injected by FastMCP).

    Returns:
        dict: Execution result containing:
            - return_code (int): Exit code (0 for success)
            - status (str): "success" if completed without errors
            - output (str): Complete stdout/stderr from dcover
            - command (list[str]): The exact command that was executed
            - working_directory (Path): Directory where command was run

    Raises:
        ToolError: If dcover executable not found, command fails, or timeout exceeded.
            The error includes the partial output collected before failure.

    Note:
        If DIFFBLUE_COVER_OPTIONS environment variable is set, it overrides all
        option parameters (batch, skip_verification, etc.) except path, working_directory,
        timeout, and entry_points.

        This tool requires a valid Diffblue Cover license. See:
        https://docs.diffblue.com/features/cover-cli/commands-and-arguments#create-tests
    """

    # We'll assume that the path and directories exist

    path = find_dcover_executable(path)

    command = [path, "create", "--batch"]

    options = os.getenv(DIFFBLUE_COVER_OPTIONS)
    if options is not None and len(options) > 0:
        await ctx.debug(f"{DIFFBLUE_COVER_OPTIONS} provided in environment variable")
        command.extend(shlex.split(options))

    entry_points = [x.strip() for x in entry_points if x.strip()] if entry_points else []
    if entry_points:
        command.extend(entry_points)

    cmd = " ".join(command)
    await ctx.debug(f"Running: {cmd}")
    await ctx.debug(f"Working directory: {working_directory}")
    await ctx.debug(f"Timeout: {dcover_timeout}s")

    output_lines = []
    try:
        for line in execute(command, working_directory, dcover_timeout):
            output_lines.append(line)
            await ctx.debug(line)
            await ctx.report_progress(progress=len(output_lines))
        return {
            "return_code": 0,
            "status": "success",
            "output": "\n".join(output_lines),
            "command": command,
            "working_directory": working_directory,
        }
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        raise ToolError(str(e), "\n".join(output_lines)) from e


def find_dcover_executable(provided: str | None) -> str:
    """Locate the dcover executable using multiple discovery strategies.

    Searches for the dcover CLI executable in the following priority order:
    1. The explicitly provided path parameter
    2. System PATH (via shutil.which)
    3. DIFFBLUE_COVER_CLI environment variable

    Args:
        provided: Explicit path to dcover executable, or None to search automatically.

    Returns:
        str: Absolute or relative path to the dcover executable.

    Raises:
        ToolError: If dcover cannot be found through any method.

    Example:
        >>> find_dcover_executable("/opt/diffblue/dcover")
        '/opt/diffblue/dcover'
        >>> find_dcover_executable(None)  # Falls back to PATH search
        '/usr/local/bin/dcover'
    """
    environment = os.getenv(DIFFBLUE_COVER_CLI)
    path = shutil.which("dcover")

    for p in [provided, path, environment]:
        if p is None or not p:
            continue
        return p
    raise ToolError(
        "Cannot find dcover executable. "
        "Ensure dcover is in PATH, provide explicit path, "
        f"or set {DIFFBLUE_COVER_CLI} environment variable."
    )
