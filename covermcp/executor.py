"""Functions for interacting with system process execution."""

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
import contextlib
import time
from collections.abc import Iterator
from pathlib import Path
from subprocess import PIPE, STDOUT, CalledProcessError, Popen, TimeoutExpired
from typing import Final

CLEANUP_TIMEOUT: Final[int] = 5


def execute(command: list[str], working_dir: Path, timeout: int | None) -> Iterator[str]:
    """Execute the given command in the working directory with real-time output streaming.

    Executes a command and yields output lines as they are produced. Stdout and stderr
    are combined into a single stream. The timeout applies to the entire execution,
    not just the final wait.

    Args:
        command: The command and arguments to execute (e.g., ['dcover', 'create', '--batch'])
        working_dir: The directory to execute the command in
        timeout: Maximum time in seconds to wait for command completion, or None for no timeout

    Yields:
        str: Output lines from the command (stdout and stderr combined), with trailing
            newlines removed. Lines are yielded in real-time as the process produces them.

    Raises:
        CalledProcessError: If command returns non-zero exit code
        TimeoutExpired: If command exceeds timeout duration
        OSError: If command cannot be executed (e.g., executable not found)

    Example:
        >>> for line in execute(['echo', 'hello'], Path.cwd(), 10):
        ...     print(f"Output: {line}")
        Output: hello
    """

    process = Popen(
        command,
        cwd=working_dir,
        stdout=PIPE,
        stderr=STDOUT,
        text=True,
    )

    start_time = time.time() if timeout is not None else None

    try:
        for line in process.stdout:
            if timeout is not None and (time.time() - start_time) > timeout:
                cleanup_process(process)
                raise TimeoutExpired(command, timeout)

            yield line.rstrip("\n\r")

        if timeout is not None:
            elapsed = time.time() - start_time
            # noinspection PyTypeChecker
            remaining = max(0, timeout - elapsed)
            if remaining <= 0:
                cleanup_process(process)
                raise TimeoutExpired(command, timeout)
            process.wait(timeout=remaining)
        else:
            process.wait()

        if process.returncode != 0:
            raise CalledProcessError(process.returncode, command)

    except TimeoutExpired:
        cleanup_process(process)
        raise
    except Exception:
        if process.poll() is None:
            cleanup_process(process)
        raise


def cleanup_process(process: Popen[str]):
    """Forcefully terminate a subprocess and wait (briefly) for cleanup.

    Kills the process and waits up to CLEANUP_TIMEOUT seconds for termination.
    Suppresses timeout exceptions to avoid masking the original error during
    cleanup operations.

    Args:
        process: The subprocess to terminate.
    """
    process.kill()
    with contextlib.suppress(TimeoutExpired):
        process.wait(timeout=CLEANUP_TIMEOUT)
