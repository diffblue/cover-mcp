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

import logging
import shutil
import subprocess
from pathlib import Path
from unittest import mock

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from fastmcp.utilities.tests import caplog_for_fastmcp

from covermcp import server
from covermcp.server import DEFAULT_TIMEOUT


@pytest.fixture
def mock_happy_path_execution(monkeypatch):
    mock_execution = mock.Mock(return_value=iter(["line 1", "line 2"]))
    monkeypatch.setattr(server, "execute", mock_execution)
    return mock_execution


@pytest.fixture
def mock_exceptional_execution(monkeypatch):
    mock_execution = mock.Mock(side_effect=subprocess.CalledProcessError(42, "dummy exception"))
    monkeypatch.setattr(server, "execute", mock_execution)
    return mock_execution


@pytest.fixture
def mock_overridden_execution(monkeypatch):
    monkeypatch.setenv("DIFFBLUE_COVER_OPTIONS", "--foo --bar=baz")


@pytest.mark.asyncio
async def test_dcover_default_create_options(mock_happy_path_execution):
    async with Client(server.mcp) as client:
        result = await client.call_tool("create", arguments={"path": Path("path", "to", "dcover")})
        assert result is not None

        mock_happy_path_execution.assert_called_once_with(
            [str(Path("path", "to", "dcover")), "create", "--batch"],
            Path(result.data["working_directory"]),
            DEFAULT_TIMEOUT,
        )
        assert "command" in result.data

        assert "working_directory" in result.data
        assert Path(result.data["working_directory"]) == Path.cwd()

        assert "return_code" in result.data
        assert result.data["return_code"] == 0

        assert "status" in result.data
        assert result.data["status"] == "success"

        assert "output" in result.data
        assert "line 1" in result.data["output"]
        assert "line 2" in result.data["output"]


@pytest.mark.asyncio
async def test_dcover_with_entry_points(mock_happy_path_execution):
    async with Client(server.mcp) as client:
        result = await client.call_tool(
            "create",
            arguments={"path": Path("path", "to", "dcover"), "entry_points": ["entrypoint1", "entrypoint2"]},
        )
        assert result is not None

        mock_happy_path_execution.assert_called_once_with(
            [str(Path("path", "to", "dcover")), "create", "--batch", "entrypoint1", "entrypoint2"],
            Path(result.data["working_directory"]),
            DEFAULT_TIMEOUT,
        )
        assert "command" in result.data

        assert "working_directory" in result.data
        assert Path(result.data["working_directory"]) == Path.cwd()

        assert "return_code" in result.data
        assert result.data["return_code"] == 0

        assert "status" in result.data
        assert result.data["status"] == "success"

        assert "output" in result.data
        assert "line 1" in result.data["output"]
        assert "line 2" in result.data["output"]


@pytest.mark.asyncio
async def test_dcover_env_create_options(mock_overridden_execution, mock_happy_path_execution):
    async with Client(server.mcp) as client:
        result = await client.call_tool("create", arguments={"path": Path("path", "to", "dcover")})
        assert result is not None

        assert "command" in result.data

        mock_happy_path_execution.assert_called_once_with(
            [str(Path("path", "to", "dcover")), "create", "--batch", "--foo", "--bar=baz"],
            Path(result.data["working_directory"]),
            DEFAULT_TIMEOUT,
        )
        assert "working_directory" in result.data
        assert Path(result.data["working_directory"]) == Path.cwd()

        assert "return_code" in result.data
        assert result.data["return_code"] == 0

        assert "status" in result.data
        assert result.data["status"] == "success"

        assert "output" in result.data
        assert "line 1" in result.data["output"]
        assert "line 2" in result.data["output"]


@pytest.mark.asyncio
async def test_dcover_executable_not_found(mock_exceptional_execution, caplog):
    # the FastMCP server has some rich logging of errors and includes the ToolError that we deliberately throw
    # during the test. To avoid confusion we change the logging level for this test to something above ERROR
    with caplog.at_level(logging.CRITICAL, logger="fastmcp"):
        caplog_for_fastmcp(caplog)

        async with Client(server.mcp) as client:
            with pytest.raises(ToolError):
                await client.call_tool(
                    "create",
                    arguments={
                        "path": Path("path", "to", "dcover"),
                        "working_directory": Path("path", "to", "project"),
                    },
                )

    mock_exceptional_execution.assert_called_once_with(
        [str(Path("path", "to", "dcover")), "create", "--batch"], Path(Path("path", "to", "project")), 600
    )


def test_find_dcover_executable(monkeypatch):
    monkeypatch.setenv("DIFFBLUE_COVER_CLI", str(Path("path", "to", "env", "dcover")))

    with monkeypatch.context() as m:
        m.setattr(shutil, "which", lambda *args: str(Path("path", "to", "system", "dcover")))
        assert server.find_dcover_executable("foo") == "foo"
        assert server.find_dcover_executable(None) == str(Path("path", "to", "system", "dcover"))

    with monkeypatch.context() as m:
        m.setattr(shutil, "which", lambda *args: "")
        assert server.find_dcover_executable(None) == str(Path("path", "to", "env", "dcover"))

    with monkeypatch.context() as m:
        m.setattr(shutil, "which", lambda *args: None)
        assert server.find_dcover_executable(None) == str(Path("path", "to", "env", "dcover"))

    monkeypatch.delenv("DIFFBLUE_COVER_CLI", raising=False)
    with monkeypatch.context() as m:
        m.setattr(shutil, "which", lambda *args: None)
        with pytest.raises(ToolError):
            server.find_dcover_executable(None)


@pytest.mark.asyncio
async def test_dcover_refactor_command(mock_happy_path_execution):
    async with Client(server.mcp) as client:
        result = await client.call_tool("refactor", arguments={"path": Path("path", "to", "dcover")})
        assert result is not None

        mock_happy_path_execution.assert_called_once_with(
            [str(Path("path", "to", "dcover")), "refactor", "--batch"],
            Path(result.data["working_directory"]),
            DEFAULT_TIMEOUT,
        )
        assert "command" in result.data
        assert "line 1" in result.data["output"]
        assert "line 2" in result.data["output"]


@pytest.mark.asyncio
async def test_dcover_refactor_command_with_dry_run(mock_happy_path_execution):
    async with Client(server.mcp) as client:
        result = await client.call_tool("refactor", arguments={"path": Path("path", "to", "dcover"), "dry_run": True})
        assert result is not None

        mock_happy_path_execution.assert_called_once_with(
            [str(Path("path", "to", "dcover")), "refactor", "--batch", "--dry-run"],
            Path(result.data["working_directory"]),
            DEFAULT_TIMEOUT,
        )
        assert "command" in result.data
        assert "--dry-run" in result.data["command"]


@pytest.mark.asyncio
async def test_dcover_issues_command(mock_happy_path_execution):
    async with Client(server.mcp) as client:
        result = await client.call_tool("issues", arguments={"path": Path("path", "to", "dcover")})
        assert result is not None

        mock_happy_path_execution.assert_called_once_with(
            [str(Path("path", "to", "dcover")), "issues", "--batch"],
            Path(result.data["working_directory"]),
            DEFAULT_TIMEOUT,
        )
        assert "command" in result.data
        assert "line 1" in result.data["output"]
        assert "line 2" in result.data["output"]


@pytest.mark.asyncio
async def test_dcover_issues_command_with_all_args(mock_happy_path_execution):
    async with Client(server.mcp) as client:
        arguments = {
            "path": Path("path", "to", "dcover"),
            "limit": 10,
            "skip": 5,
            "prompt": True,
            "cover_json": "/tmp/report.json",
            "dry_run": True,
        }
        result = await client.call_tool("issues", arguments=arguments)
        assert result is not None

        expected_command = [
            str(Path("path", "to", "dcover")),
            "issues",
            "--batch",
            "--limit",
            "10",
            "--skip",
            "5",
            "--prompt",
            "--cover-json",
            "/tmp/report.json",
            "--dry-run",
        ]

        mock_happy_path_execution.assert_called_once_with(
            expected_command,
            Path(result.data["working_directory"]),
            DEFAULT_TIMEOUT,
        )
        assert result.data["command"] == expected_command
