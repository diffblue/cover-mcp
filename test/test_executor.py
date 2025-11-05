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

from pathlib import Path
from subprocess import CalledProcessError, TimeoutExpired
from unittest.mock import Mock, patch

import pytest

from covermcp.executor import cleanup_process, execute


@pytest.fixture
def mock_streaming_popen(monkeypatch):
    mock_process = Mock()

    mock_process.stdout = iter(["line 1\n", "line 2\n", "line 3\n"])
    mock_process.returncode = 0
    mock_process.poll = Mock(return_value=None)
    mock_process.wait = Mock()

    mock_popen = Mock(return_value=mock_process)
    monkeypatch.setattr("covermcp.executor.Popen", mock_popen)

    return mock_popen, mock_process


@pytest.fixture
def mock_failed_streaming_popen(monkeypatch):
    mock_process = Mock()
    mock_process.stdout = iter(["error line 1\n", "error line 2\n"])
    mock_process.returncode = 1
    mock_process.poll = Mock(return_value=1)
    mock_process.wait = Mock()

    mock_popen = Mock(return_value=mock_process)
    monkeypatch.setattr("covermcp.executor.Popen", mock_popen)

    return mock_popen, mock_process


def test_execute_successful_command(mock_streaming_popen):
    mock_popen, mock_process = mock_streaming_popen

    command = ["echo", "hello"]
    working_dir = Path("/tmp")
    timeout = 600

    result = list(execute(command, working_dir, timeout))

    assert result == ["line 1", "line 2", "line 3"]

    mock_popen.assert_called_once_with(
        command,
        cwd=working_dir,
        stdout=-1,
        stderr=-2,
        text=True,
    )

    mock_process.wait.assert_called_once()


def test_execute_successful_command_no_timeout(mock_streaming_popen):
    mock_popen, mock_process = mock_streaming_popen

    command = ["echo", "hello"]
    working_dir = Path("/tmp")

    result = list(execute(command, working_dir, None))

    assert result == ["line 1", "line 2", "line 3"]
    mock_process.wait.assert_called_once_with()


def test_execute_failed_command(mock_failed_streaming_popen):
    mock_popen, mock_process = mock_failed_streaming_popen

    command = ["false"]
    working_dir = Path("/tmp")

    with pytest.raises(CalledProcessError) as exc_info:
        list(execute(command, working_dir, 600))

    assert exc_info.value.returncode == 1
    assert exc_info.value.cmd == command

    mock_process.wait.assert_called_once()


def test_execute_strips_newlines(monkeypatch):
    mock_process = Mock()
    mock_process.stdout = iter(["line 1\n", "line 2\r\n", "line 3"])
    mock_process.returncode = 0
    mock_process.wait = Mock()

    mock_popen = Mock(return_value=mock_process)
    monkeypatch.setattr("covermcp.executor.Popen", mock_popen)

    result = list(execute(["test"], Path("/tmp"), 600))

    assert result == ["line 1", "line 2", "line 3"]


def test_execute_with_empty_output(monkeypatch):
    mock_process = Mock()
    mock_process.stdout = iter([])
    mock_process.returncode = 0
    mock_process.wait = Mock()

    mock_popen = Mock(return_value=mock_process)
    monkeypatch.setattr("covermcp.executor.Popen", mock_popen)

    result = list(execute(["true"], Path("/tmp"), 600))

    assert result == []


def test_execute_preserves_empty_lines(monkeypatch):
    mock_process = Mock()
    mock_process.stdout = iter(["line 1\n", "\n", "line 3\n"])
    mock_process.returncode = 0
    mock_process.wait = Mock()

    mock_popen = Mock(return_value=mock_process)
    monkeypatch.setattr("covermcp.executor.Popen", mock_popen)

    result = list(execute(["test"], Path("/tmp"), 600))

    assert result == ["line 1", "", "line 3"]


def test_execute_timeout_after_streaming(monkeypatch):
    mock_process = Mock()
    mock_process.stdout = iter(["line 1\n"])
    mock_process.wait = Mock(side_effect=TimeoutExpired(["test"], 5))
    mock_process.poll = Mock(return_value=None)

    mock_popen = Mock(return_value=mock_process)
    monkeypatch.setattr("covermcp.executor.Popen", mock_popen)

    mock_cleanup = Mock()
    monkeypatch.setattr("covermcp.executor.cleanup_process", mock_cleanup)

    start_time = 1000.0
    with patch("covermcp.executor.time.time", return_value=start_time), pytest.raises(TimeoutExpired):
        list(execute(["test"], Path("/tmp"), 600))

    mock_cleanup.assert_called_once()


def test_execute_timeout_with_no_remaining_time(monkeypatch):
    mock_process = Mock()
    mock_process.stdout = iter(["line 1\n"])
    mock_process.poll = Mock(return_value=None)

    mock_popen = Mock(return_value=mock_process)
    monkeypatch.setattr("covermcp.executor.Popen", mock_popen)

    mock_cleanup = Mock()
    monkeypatch.setattr("covermcp.executor.cleanup_process", mock_cleanup)

    start_time = 1000.0
    times = [start_time, start_time + 0.1, start_time + 600.1]
    with patch("covermcp.executor.time.time", side_effect=times), pytest.raises(TimeoutExpired) as exc_info:
        list(execute(["test"], Path("/tmp"), 600))

    assert exc_info.value.timeout == 600  # noqa: PLR2004
    mock_cleanup.assert_called_with(mock_process)


def test_execute_cleans_up_on_exception(monkeypatch):
    mock_process = Mock()

    def failing_generator():
        yield "line 1\n"
        raise RuntimeError("Simulated error")

    mock_process.stdout = failing_generator()
    mock_process.poll = Mock(return_value=None)

    mock_popen = Mock(return_value=mock_process)
    monkeypatch.setattr("covermcp.executor.Popen", mock_popen)

    mock_cleanup = Mock()
    monkeypatch.setattr("covermcp.executor.cleanup_process", mock_cleanup)

    with pytest.raises(RuntimeError, match="Simulated error"):
        list(execute(["test"], Path("/tmp"), 600))

    mock_cleanup.assert_called_once_with(mock_process)


def test_execute_cleanup_only_if_process_running(monkeypatch):
    mock_process = Mock()

    def failing_generator():
        yield "line 1\n"
        raise RuntimeError("Simulated error")

    mock_process.stdout = failing_generator()
    mock_process.poll = Mock(return_value=0)

    mock_popen = Mock(return_value=mock_process)
    monkeypatch.setattr("covermcp.executor.Popen", mock_popen)

    mock_cleanup = Mock()
    monkeypatch.setattr("covermcp.executor.cleanup_process", mock_cleanup)

    with pytest.raises(RuntimeError):
        list(execute(["test"], Path("/tmp"), 600))

    mock_cleanup.assert_not_called()


def test_cleanup_process_kills_and_waits():
    mock_process = Mock()
    mock_process.kill = Mock()
    mock_process.wait = Mock()

    cleanup_process(mock_process)

    mock_process.kill.assert_called_once()
    mock_process.wait.assert_called_once_with(timeout=5)


def test_cleanup_process_handles_timeout_gracefully():
    mock_process = Mock()
    mock_process.kill = Mock()
    mock_process.wait = Mock(side_effect=TimeoutExpired(["test"], 5))

    cleanup_process(mock_process)

    mock_process.kill.assert_called_once()
    mock_process.wait.assert_called_once()


def test_execute_with_very_long_lines(monkeypatch):
    mock_process = Mock()
    long_line = "x" * 10000
    mock_process.stdout = iter([f"{long_line}\n"])
    mock_process.returncode = 0
    mock_process.wait = Mock()

    mock_popen = Mock(return_value=mock_process)
    monkeypatch.setattr("covermcp.executor.Popen", mock_popen)

    result = list(execute(["test"], Path("/tmp"), 600))

    assert result == [long_line]


def test_execute_with_unicode_output(monkeypatch):
    mock_process = Mock()
    mock_process.stdout = iter(["Hello 世界\n", "Emoji: 🎉\n"])
    mock_process.returncode = 0
    mock_process.wait = Mock()

    mock_popen = Mock(return_value=mock_process)
    monkeypatch.setattr("covermcp.executor.Popen", mock_popen)

    result = list(execute(["test"], Path("/tmp"), 600))

    assert result == ["Hello 世界", "Emoji: 🎉"]
