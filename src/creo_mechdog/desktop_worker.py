"""Run the native worker through the interactive Explorer desktop.

An MCP host may place its child processes in a Job Object. A worker started with
``subprocess`` inherits that job; when the Toolkit channel is unavailable in that
context the probe returns ``PRO_TK_BAD_CONTEXT`` (-4) even though Creo is healthy.
``Shell.Application`` runs inside explorer.exe, which is outside the host job, so
a worker started through it keeps the desktop process context instead.

Nothing here selects or closes Creo; the module only starts a worker and returns
its captured output and exit code. Explorer starts a Python helper directly;
only the worker's environment overrides are stored in the temporary request.
"""

from __future__ import annotations

import ctypes
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from ctypes import wintypes
from pathlib import Path
from typing import Iterator

import pythoncom
import pywintypes
import win32com.client
import win32process
import win32security

POLL_SECONDS = 0.05
# Only these child-only adjustments are needed on top of the desktop environment.
ENV_KEYS = ("PATH", "PRO_COMM_MSG_EXE", "MECHDOG_CREO_SESSION_ID")
LICENSE_KEY = "PTC_D_LICENSE_FILE"

_kernel = ctypes.WinDLL("kernel32", use_last_error=True)


class DesktopUnavailable(RuntimeError):
    """The interactive Explorer cannot start a worker for this host."""


def _api(name: str, arguments: tuple, result: type):
    function = getattr(_kernel, name)
    function.argtypes = arguments
    function.restype = result
    return function


_open = _api("OpenProcess", (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD), wintypes.HANDLE)
_close = _api("CloseHandle", (wintypes.HANDLE,), wintypes.BOOL)
_session = _api(
    "ProcessIdToSessionId", (wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)), wintypes.BOOL
)
_image = _api(
    "QueryFullProcessImageNameW",
    (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)),
    wintypes.BOOL,
)


def _session_id() -> int:
    value = wintypes.DWORD()
    if not _session(os.getpid(), ctypes.byref(value)):
        raise ctypes.WinError(ctypes.get_last_error())
    return value.value


def _same_session(pid: int) -> bool:
    value = wintypes.DWORD()
    return bool(_session(pid, ctypes.byref(value))) and value.value == _session_id()


def _image_path(pid: int) -> str | None:
    handle = _open(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    try:
        name = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(name))
        if not _image(handle, 0, name, ctypes.byref(size)):
            return None
        return name.value
    finally:
        _close(handle)


def _user_sid(pid: int) -> str | None:
    handle = _open(0x1000, False, pid)
    if not handle:
        return None
    try:
        token = win32security.OpenProcessToken(handle, 8)  # TOKEN_QUERY
        try:
            return win32security.ConvertSidToStringSid(
                win32security.GetTokenInformation(token, win32security.TokenUser)[0]
            )
        finally:
            token.Close()
    finally:
        _close(handle)


@contextmanager
def _explorer_shell() -> Iterator[object]:
    """Return the Shell.Application object hosted by this desktop's Explorer."""
    pythoncom.CoInitialize()
    desktop = None
    try:
        desktop = (
            win32com.client.Dispatch("Shell.Application").Windows().FindWindowSW(0, 0, 8, 0, 1)
        )
        if desktop is None:
            raise DesktopUnavailable("The interactive Explorer desktop is unavailable")
        tid, pid = win32process.GetWindowThreadProcessId(desktop.HWND)
        if not tid or pid <= 0:
            raise DesktopUnavailable(
                "Cannot verify the interactive Explorer window from this desktop"
            )
        if not _same_session(pid):
            raise DesktopUnavailable("Explorer belongs to another Windows session")
        expected = Path(os.environ["SYSTEMROOT"]) / "explorer.exe"
        image = _image_path(pid)
        if not image or os.path.normcase(image) != os.path.normcase(str(expected)):
            raise DesktopUnavailable("Cannot verify the interactive Explorer process")
        if _user_sid(pid) != _user_sid(os.getpid()):
            raise DesktopUnavailable("Explorer belongs to another user")
        yield desktop.Document.Application
    except pywintypes.com_error as exc:
        raise DesktopUnavailable(
            f"Explorer launch request failed (HRESULT={exc.hresult})"
        ) from None
    finally:
        desktop = None
        pythoncom.CoUninitialize()


def _launcher(
    directory: Path, command: list[str], cwd: Path, env: dict[str, str], deadline: float
) -> Path:
    if env.get(LICENSE_KEY) and env[LICENSE_KEY] != os.environ.get(LICENSE_KEY):
        raise DesktopUnavailable("Desktop launch cannot transfer a different license environment")
    request = directory / "request.json"
    request.write_text(
        json.dumps(
            {
                "command": command,
                "cwd": str(cwd),
                "env": {key: env[key] for key in ENV_KEYS if env.get(key)},
                "deadline": deadline,
            }
        ),
        encoding="utf-8",
    )
    return request


def _run_request(request: Path) -> None:
    directory = request.parent
    value = json.loads(request.read_text(encoding="utf-8"))
    remaining = value["deadline"] - time.monotonic()
    if remaining <= 0:
        return
    try:
        with (
            (directory / "stdout.txt").open("wb") as stdout,
            (directory / "stderr.txt").open("wb") as stderr,
        ):
            process = subprocess.run(
                value["command"],
                cwd=value["cwd"],
                env={**os.environ, **value["env"]},
                stdout=stdout,
                stderr=stderr,
                timeout=remaining,
                creationflags=subprocess.CREATE_NO_WINDOW,
                check=False,
            )
        result = {"returncode": process.returncode}
    except subprocess.TimeoutExpired:
        result = {"error": "Desktop worker exceeded the probe budget"}
    except (OSError, ValueError) as exc:
        result = {"error": f"Desktop worker could not start ({type(exc).__name__})"}
    temporary = directory / "result.tmp"
    temporary.write_text(json.dumps(result), encoding="utf-8")
    temporary.replace(directory / "result.json")


def launch_detached_command(command: list[str], *, cwd: Path) -> None:
    """Start a fire-and-forget process via Explorer outside the host Job Object."""
    if os.name != "nt" or not command:
        raise DesktopUnavailable("Desktop launch needs Windows and a command")
    try:
        with _explorer_shell() as shell:
            shell.ShellExecute(
                command[0],
                subprocess.list2cmdline(command[1:]),
                str(cwd),
                "open",
                0,
            )
    except pywintypes.error as exc:
        raise DesktopUnavailable(
            f"Explorer detached launch failed (HRESULT={exc.hresult})"
        ) from None


def run(
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    timeout: float,
    parent: Path,
) -> subprocess.CompletedProcess[bytes]:
    """Start the worker hidden via Explorer and return its captured process result."""
    if os.name != "nt" or not command:
        raise DesktopUnavailable("Desktop launch needs Windows and a worker command")
    directory = None
    try:
        parent.mkdir(parents=True, exist_ok=True)
        directory = Path(tempfile.mkdtemp(dir=parent))
        deadline = time.monotonic() + timeout
        request = _launcher(directory, command, cwd, env, deadline)
        with _explorer_shell() as shell:
            shell.ShellExecute(
                sys.executable,
                subprocess.list2cmdline(["-I", str(Path(__file__).resolve()), str(request)]),
                str(directory),
                "open",
                0,
            )
        result_path = directory / "result.json"
        while not result_path.is_file():
            if time.monotonic() >= deadline:
                raise DesktopUnavailable("Desktop worker did not publish a result before timeout")
            time.sleep(POLL_SECONDS)
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if isinstance(result, dict) and isinstance(result.get("error"), str):
            raise DesktopUnavailable(result["error"])
        if not isinstance(result, dict) or type(result.get("returncode")) is not int:
            raise DesktopUnavailable("Desktop worker published an invalid process result")
        stdout = (directory / "stdout.txt").read_bytes()
        stderr = (directory / "stderr.txt").read_bytes()
        return subprocess.CompletedProcess(command, result["returncode"], stdout, stderr)
    except (OSError, ValueError, pywintypes.error) as exc:
        raise DesktopUnavailable(
            f"Desktop launch result unavailable ({type(exc).__name__})"
        ) from None
    finally:
        if directory is not None:
            try:
                shutil.rmtree(directory)
            except Exception as exc:
                logging.getLogger(__name__).warning(
                    "Could not clean up desktop worker scratch directory (%s)", type(exc).__name__
                )


if __name__ == "__main__":
    _run_request(Path(sys.argv[1]))
