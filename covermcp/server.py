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


@mcp.prompt("write tests")
def write_tests() -> list[dict]:
    """Provide system prompt for Java unit test writing guidance.

    Establishes LLM context as a Java unit testing expert to improve
    test generation quality and suggestions.

    Returns:
        list[dict]: System role message defining the assistant's expertise.
    """
    return [
        {
            "role": "system",
            "content": "You are a helpful assistant highly skilled at writing unit tests for java code.",
        },
    ]


@mcp.resource(
    "data://config",
    description="Provides the configuration options for creating tests with Diffblue Cover.",
    mime_type="application/json",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
def create_options() -> dict:
    """Provide comprehensive dcover CLI option documentation.

    Exposes 50+ dcover configuration options covering test frameworks,
    mocking, coverage, build systems, and Spring configurations. Enables
    LLMs to discover and use dcover features intelligently.

    Returns:
        dict: Mapping of CLI option names to descriptions. Keys can be
            passed directly to dcover via the create tool's args parameter.

    Note:
        Exposed at URI "data://config". Marked read-only and idempotent
        for efficient caching.
    """
    return {
        "--active-profiles": "The comma separated list of profiles to use where creating Spring tests. Not providing a "
                             "value will use the default profile.",
        "--allow-jni": "The comma separated list of additional JNI library name prefixes that should be usable within "
                       "the sandbox when creating and evaluating tests. JNI library names are the strings supplied in "
                       "calls to System.loadLibrary(...). By default only JDK provided libraries are allowed. ",
        "--annotate-suppress-warnings": "Adds the @SuppressWarning annotation to methods with the given tags, for "
                                        'example: "--annotate-suppress-warnings=unused,rawtypes", would produce '
                                        '@SuppressWarnings({"unused","rawtypes"})',
        "--batch": "Do not display progress bars. Automatically enabled when environment variable CI=true, or when "
                   "using the Cover MCP server.",
        "--class-name-template=<template>": "How test classes are named, where Cover will attempt to insert Tests. "
                                            "The same template must be used in dcover create and dcover validate "
                                            "executions. Available replacements: ${CLASS} - the name of the class "
                                            "under test. Default: ${CLASS}DiffblueTest, Tip: Quote or escape "
                                            "templates to stop your shell mangling them.",
        "--compliance-level=<value>": "By default dcover automatically detects the Java compliance value, or falls "
                                      "back to 1.8. Use this option to set a specific level from 3 to 17.",
        "--cover-all-enums": "Attempt to generate tests using all possible values for enum types used as a parameter, "
                             "or to generate test cases that cause the method-under-test to return all possible values "
                             "of enum types. (This will happen even if this provides no additional line coverage.) ",
        "--report-file=<report>": "Location of the JSON-formatted test-writing summary report.",
        "--coverage-reports": "Once test creation has completed, run JaCoCo commands to get separate coverage reports "
                              "for the Diffblue and the non-Diffblue tests. All tests that follow the naming pattern "
                              "(e.g. *DiffblueTest.java) are considered, not just the tests that were created in the "
                              "current run. By default, the reports are placed in .diffblue/reports/. This option is "
                              "incompatible with --class-name-template. The command to create the JaCoCo reports can "
                              "be customised using a custom DiffblueBuild.yaml configuration.",
        "--classpath=<value>": "A ':' separated list of directories and JAR archives to search for class files.",
        "--test-output-dir=<value>": "Directory where the Diffblue tests are written.",
        "--define=<String=String>": "Set system properties to be applied when running tests.",
        "--[no-]descriptive-test-names": "Use descriptive test names.",
        "--diffblue-class-name-template=<template>": "How the Diffblue test classes are named. Contents will be "
                                                     "treated as MaintainedByDiffblue. The same template must be used "
                                                     "in dcover create and dcover validate executions. Available "
                                                     "replacements: "
                                                     "${CLASS} - the name of the class under test."
                                                     "Default: ${CLASS}DiffblueTest Tip: Quote or escape templates to "
                                                     "stop your shell mangling them.",
        "--disable-sandbox": "Uses a more permissive security manager policy for the methods under test. Use with "
                             "caution: This allows the execution of potentially unsafe code during test creation, "
                             "which may damage your system environment.",
        "--preflight": "Check that the project's environment is ready to run Diffblue Cover.",
        "--exclude=<entryPointExclusions>": "Package/class/method to exclude from test-writing. For example, with the "
                                            "specification: dcover create --exclude='com.example.*.model.*' Diffblue "
                                            "Cover will exclude all classes in a model package.",
        "--environment=<String=String>": "Set environment variables to be applied when running dcover.",
        "--exclude-method=<methodExclusions>": "Methods that should not be used in tests. For example, with the "
                                               "specification: dcover create --exclude-method='com.example.*. model.*' "
                                               "Diffblue Cover test will not make any calls to methods in the model "
                                               "package. Environment: DIFFBLUE_EXCLUDE_METHOD",
        "--exclude-modules=<module>[, <module>...]": "Exclude specified modules from the discovered module list. "
                                                     "Environment: DIFFBLUE_EXCLUDE_MODULES",
        "--exclude-trivial-methods": "Do not write tests for trivial methods.",
        "--gradle": "Make Cover prefer the use of Gradle build system.",
        "--help": "Show this help message and exit.",
        "--include-modules=<module>[, <module>...]": "Include only specified modules from the discovered module list. "
                                                     "Environment: DIFFBLUE_INCLUDE_MODULES",
        "--keep-partial-tests": "Keep all created tests, even partial tests. These tests may prevent your project from "
                                "compiling successfully. The provided tests may include tests without assertions, "
                                "non-compiling tests, non-deterministic tests, tests that throw, and tests that "
                                "violate the security policy.",
        "--location=<value>": "The location in Reports where the uploaded project will be placed.",
        "--maven": "Make Cover prefer the use of Maven build system.",
        "--max-assertions-per-test=<value>": "Set the maximum number of assertions generated per test. "
                                             "Environment: DIFFBLUE_MAX_ASSERTIONS_PER_TEST",
        "--method-name-template=<template>": "Tell dcover how to name test methods. "
                                             "Available replacements: "
                                             "${INNER} - the name of the inner class for the method under test, "
                                             "or blank. "
                                             "${UNIT} - a summary of the methods under test. "
                                             "${METHOD} - the name of the first method under test. "
                                             "${GIVEN} - a summary of the conditions before testing, or blank if no "
                                             "summary is available. ${WHEN} - a summary of the conditions under test, "
                                             "or blank if no summary is available. "
                                             "${THEN} - summary of the test's consequences, or blank if no summary is "
                                             "available. "
                                             "${_} - an underscore, or a blank string if there are no values to "
                                             "separate. Default: test${INNER}${UNIT}${_}${GIVEN}${_}${WHEN}${_}${THEN} "
                                             "For example, given an inner class Foo with an equals(Object) and "
                                             "hashCode() implementation, a test method might be named "
                                             "testFooEqualsAndHashCode_whenOtherIsEqual_thenRet urnEqual(). "
                                             "Tip: Quote or escape templates to stop your shell mangling them.",
        "--mock=<value>[, <value>...]": "Prefixes of package/class to mock using Mockito.mock(). The class containing "
                                        "the method under test is never mocked. Non-void, non-private instance methods "
                                        "are stubbed with when(). thenReturn().",
        "--mock-construction=<value>[, <value>...]": "Fully qualified names of classes for which to mock constructors "
                                                     "using Mockito.mockConstruction. This feature is available with "
                                                     "Mockito 3.5.0 and above, when using the inline mock maker. "
                                                     "Constructors of the method under test will not be mocked.",
        "--mock-method-returns": "Make Cover to be more willing to accept returning mock values from mocked methods. "
                                 "This may allow Cover to write more tests for code which has complex class "
                                 "dependencies, however it may also degrade coverage for code where business logic is "
                                 "complex.",
        "--mock-static=<value>[, <value>...]": "Names of classes to mock using Mockito. mockStatic(). This feature is "
                                               "available with Mockito 3.4.0 and above, when inline mocking is "
                                               "enabled. If the method under test is static its class will not be "
                                               "mocked.",
        "--name=<value>": "Name of reports bundle. Defaults to the current timestamp, or the latest commit hash when "
                          "used within Git.",
        "--new-jacoco-coverage": "Only create tests that add coverage to the project.",
        "--no-spring-boot-tests": "[Beta] When enabled, tests will not use Spring Boot for dependency injection, "
                                  "instead falling back to other mechanisms such as Mockito's @InjectMocks if "
                                  "available.",
        "--no-spring-tests": "When enabled, tests will not use Spring contexts for dependency injection",
        "--output-comments": "Used to suppress the // Arrange, // Act, and // Assert comments in tests written by "
                             "Diffblue Cover (set to false). Default is true (show comments).",
        "--patch-only=<value>": "Specifies a patch file to have dcover only create tests for the code changes covered "
                                "by the patch and classes that call classes in the patch. For a multi-module project, "
                                "generate the patch at the root of the project and provide the absolute path to the "
                                "patch file, using `--working-directory` with the relative path to the module. The "
                                "same patch file can be used for each module.",
        "--project-name=<value>": "Name of the project shown in Reports of the project being uploaded.",
        "--fix-build": "Perform refactorings to fix issues found while attempting to create tests.",
        "--report-password=<value>": "Password for authentication when uploading Diffblue Cover Reports. Password can "
                                     "alternatively be set via the environment variable, "
                                     "DIFFBLUE_COVER_REPORTS_PASSWORD",
        "--report-username=<value>": "Username for authentication when uploading Diffblue Cover Reports. Username can "
                                     "alternatively be set via the environment variable, "
                                     "DIFFBLUE_COVER_REPORTS_USERNAME",
        "--resume-from-module=<module>": "Resume iteration from the specified module. "
                                         "Environment: DIFFBLUE_RESUME_FROM_MODULE",
        "--spring-configuration=<value>[, <value>...]": "The Spring configuration classes to use in tests.",
        "--spring-integration-tests": "Tests created for Spring components will use mocking only for Repository "
                                      "dependencies. All other dependencies will be resolved by Spring directly. Not "
                                      "applied when creating tests for @Controller classes.",
        "--strict": "Forces the strict definition of all project environment options by you - Diffblue Cover will not "
                    "attempt to make an automated selection. For example, if multiple testing frameworks are "
                    "configured for your project then running with this option will lead to an error, unless you "
                    "define which testing framework Cover should use when writing tests. Without this option, Cover "
                    "would choose one of the testing frameworks for you, and proceed.",
        "--testing-framework=<testFrameworkArgument>": "dcover automatically determines the current version of the "
                                                       "testing framework in use. This option allows you to specify "
                                                       "the framework from 'junit-4.7' to 'junit-5.8', or 'testng'. You"
                                                       " can also specify 'junit-4' (any version of JUnit 4) and "
                                                       "'junit-5' (any version of JUnit 5)",
        "--upload[=<URL>]": "URL of a Cover Reports server to upload reports to.",
        "--version": "Print version information and exit.",
        "--verbose": "Display more detailed information.",
        "--preflight-without-tests": "During the preflight checks, dcover will run the existing tests. To disable that "
                                     "behavior specify this option",
        "--working-directory=<value>": "Set the working directory for running dcover. "
                                       "Environment: DIFFBLUE_WORKING_DIRECTORY",
    }  # fmt: skip


async def _run_dcover_command(
    ctx: Context,
    path: str | None,
    subcommand: str,
    passthrough_args: list[str] | None,
    working_directory: Path,
    dcover_timeout: int | None,
    **kwargs: Any,
) -> object:
    """Internal helper to execute any dcover command, stream output, and handle errors.

    Args:
        ctx: MCP server context for logging.
        path: Path to the dcover executable.
        subcommand: The dcover subcommand to run (e.g., "create", "refactor").
        passthrough_args: A list of additional arguments from the user/LLM.
        working_directory: The project directory to run in.
        dcover_timeout: The maximum execution time in seconds.
        **kwargs: Tool-specific keyword arguments (e.g., entry_points, dry_run).

    Returns:
        A dictionary containing the execution result.

    Raises:
        ToolError: If the command fails, times out, or dcover is not found.
    """

    # We'll assume that the path and directories exist
    path = find_dcover_executable(path)

    # Build the core command
    command = [path, subcommand, "--batch"]

    # --- Start: Tool-specific argument processing ---
    # Process kwargs from the wrapper tool into a list of CLI strings
    tool_args = []
    if subcommand == "create":
        entry_points = kwargs.get("entry_points")
        if entry_points:
            tool_args.extend([x.strip() for x in entry_points if x.strip()])

    elif subcommand == "refactor":
        if kwargs.get("dry_run"):
            tool_args.append("--dry-run")

    elif subcommand == "issues":
        if (limit := kwargs.get("limit")) is not None:
            tool_args.extend(["--limit", str(limit)])
        if (skip := kwargs.get("skip")) is not None:
            tool_args.extend(["--skip", str(skip)])
        if kwargs.get("prompt"):
            tool_args.append("--prompt")
        if (cover_json := kwargs.get("cover_json")) is not None:
            tool_args.extend(["--cover-json", cover_json])
        if kwargs.get("dry_run"):
            tool_args.append("--dry-run")
    # --- End: Tool-specific argument processing ---

    command.extend(tool_args)

    # Add passthrough arguments from the LLM
    if passthrough_args:
        await ctx.debug(f"{passthrough_args} provided by LLM")
        command.extend(passthrough_args)

    # Add options from the environment variable
    options = os.getenv(DIFFBLUE_COVER_OPTIONS)
    if options:
        await ctx.debug(f"{DIFFBLUE_COVER_OPTIONS} provided in environment variable")
        command.extend(shlex.split(options))

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


@mcp.tool()
# Ignore "too many parameters for a method" and "too many positional arguments" check
async def create(  # noqa: PLR0913,PLR0917
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
    args: Annotated[list[str] | None, "The options to pass to dcover"] = None,
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
        args: Additional arguments to pass to dcover. Defaults to None.
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
    return await _run_dcover_command(
        ctx=ctx,
        path=path,
        subcommand="create",
        passthrough_args=args,
        working_directory=working_directory,
        dcover_timeout=dcover_timeout,
        entry_points=entry_points,
    )


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


@mcp.tool()
# Ignore "too many parameters for a method" and "too many positional arguments" check
async def refactor(  # noqa: PLR0913
    path: Annotated[str | None, "The path to the dcover executable"] = None,
    working_directory: Annotated[Path, "The directory containing the project"] = DEFAULT_WORKING_DIRECTORY,
    dcover_timeout: Annotated[
        int | None, "The maximum time in seconds to wait for dcover to create tests."
    ] = DEFAULT_TIMEOUT,
    dry_run: Annotated[bool, "Run preflight checks only (aliased as --preflight)"] = False,
    args: Annotated[list[str] | None, "The additional options to pass to dcover refactor"] = None,
    ctx: Annotated[Context | None, "The MCP Server Context"] = None,
) -> object:
    """Invoke Diffblue Cover to refactor the project (aliased as 'fix-build').

    This tool executes the `dcover refactor` command to apply automated
    refactorings, such as fixing build issues or adding missing dependencies.

    Args:
        path: Path to the dcover executable. If not provided, searches system PATH
            and the DIFFBLUE_COVER_CLI environment variable.
        working_directory: Root directory of the Java project to test. Defaults to
            the current working directory.
        dcover_timeout: Maximum execution time in seconds. Defaults to 600. Set to None
            for no timeout (not recommended).
        dry_run: If True, passes the '--dry-run' flag to check for readiness
            without applying changes.
        args: Additional arguments to pass to dcover. Defaults to None.
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
    """
    return await _run_dcover_command(
        ctx=ctx,
        path=path,
        subcommand="refactor",
        passthrough_args=args,
        working_directory=working_directory,
        dcover_timeout=dcover_timeout,
        dry_run=dry_run,
    )


@mcp.tool()
# Ignore "too many parameters for a method" and "too many positional arguments" check
async def issues(  # noqa: PLR0913,PLR0917
    path: Annotated[str | None, "The path to the dcover executable"] = None,
    working_directory: Annotated[Path, "The directory containing the project"] = DEFAULT_WORKING_DIRECTORY,
    dcover_timeout: Annotated[
        int | None, "The maximum time in seconds to wait for dcover to create tests."
    ] = DEFAULT_TIMEOUT,
    limit: Annotated[int | None, "Limit the number of issues to output"] = None,
    skip: Annotated[int | None, "Skip the first N issues"] = None,
    prompt: Annotated[bool, "Output suggested prompt for each actionable issue"] = False,
    cover_json: Annotated[str | None, "Path to a JSON-formatted test-writing summary report"] = None,
    dry_run: Annotated[bool, "Run preflight checks only (aliased as --preflight)"] = False,
    args: Annotated[list[str] | None, "The additional options to pass to dcover issues"] = None,
    ctx: Annotated[Context | None, "The MCP Server Context"] = None,
) -> object:
    """Invoke Diffblue Cover to identify project issues.

    This tool executes the `dcover issues` command to output a prioritized
    list of project issues that may prevent test generation.

    Args:
        path: Path to the dcover executable. If not provided, searches system PATH
            and the DIFFBLUE_COVER_CLI environment variable.
        working_directory: Root directory of the Java project to test. Defaults to
            the current working directory.
        dcover_timeout: Maximum execution time in seconds. Defaults to 600. Set to None
            for no timeout (not recommended).
        limit: Limit the number of issues to output.
        skip: Skip the first N issues from the report.
        prompt: If True, outputs a suggested prompt for each actionable issue.
        cover_json: Location of the JSON-formatted test-writing summary report.
        dry_run: If True, passes the '--dry-run' flag to check for readiness.
        args: Additional arguments to pass to dcover. Defaults to None.
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
    """
    return await _run_dcover_command(
        ctx=ctx,
        path=path,
        subcommand="issues",
        passthrough_args=args,
        working_directory=working_directory,
        dcover_timeout=dcover_timeout,
        limit=limit,
        skip=skip,
        prompt=prompt,
        cover_json=cover_json,
        dry_run=dry_run,
    )