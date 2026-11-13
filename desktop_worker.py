"""Run the native worker through the interactive Explorer desktop.

An MCP host may place its child processes in a Job Object. A worker started with
``subprocess`` inherits that job; when the Toolkit channel is unavailable in that
context the probe returns ``PRO_TK_BAD_CONTEXT`` (-4) even though Creo is healthy.
``Shell.Application`` runs inside explorer.exe, which is outside the host job, so
a worker started through it keeps the desktop process context instead.

Nothing here selects or closes Creo; the module only starts a worker and returns
its captured output and exit code. Environment values are passed as a temporary
batch script; the license value is never written to disk.
"""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import time
import uuid
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
        _, pid = win32process.GetWindowThreadProcessId(desktop.HWND)
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


def _escape(value: str) -> str | None:
    """Batch-safe literal; None when the value cannot be expressed safely."""
    if '"' in value or "\r" in value or "\n" in value:
        return None
    return value.replace("%", "%%")


def _launcher(directory: Path, command: list[str], cwd: Path, env: dict[str, str]) -> Path | None:
    """Write the hidden launcher; return None when the environment cannot be reproduced."""
    lines = ["@echo off", "setlocal enableextensions"]
    for key in ENV_KEYS:
        value = env.get(key)
        if not value:
            continue
        escaped = _escape(value)
        if escaped is None:
            return None
        lines.append(f'set "{key}={escaped}"')
    license_value = env.get(LICENSE_KEY)
    if license_value and license_value != os.environ.get(LICENSE_KEY):
        # Writing the caller's license value to disk would persist a license
        # location that the desktop already resolves on its own; use a direct run.
        return None
    working = _escape(str(cwd))
    executable = _escape(command[0])
    if working is None or executable is None:
        return None
    lines.append(f'cd /d "{working}"')
    arguments = subprocess.list2cmdline(command[1:])
    redirections = []
    for name in ("stdout.txt", "stderr.txt"):
        target = _escape(str(directory / name))
        if target is None:
            return None
        redirections.append(f'{1 if name == "stdout.txt" else 2}>"{target}"')
    code_target = _escape(str(directory / "exit.txt"))
    if code_target is None:
        return None
    parts = [f'"{executable}"', *([arguments] if arguments else []), *redirections]
    lines.append(" ".join(parts))
    lines.append(f'>"{code_target}" echo %ERRORLEVEL%')
    lines.append("exit /b 0")
    script = directory / "launch.cmd"
    script.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8", newline="")
    return script


def run(
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    timeout: float,
    parent: Path,
) -> subprocess.CompletedProcess[bytes] | None:
    """Start ``command`` hidden via Explorer; None when that path is unavailable.

    The caller keeps its direct-launch result either way: this helper is a
    diagnostic escape hatch, not a replacement for the normal worker start.
    """
    if os.name != "nt" or not command:
        return None
    parent.mkdir(parents=True, exist_ok=True)
    directory = parent / uuid.uuid4().hex
    directory.mkdir()
    try:
        script = _launcher(directory, command, cwd, env)
        if script is None:
            return None
        with _explorer_shell() as shell:
            shell.ShellExecute(
                str(Path(os.environ["SYSTEMROOT"]) / "System32/cmd.exe"),
                subprocess.list2cmdline(["/d", "/c", str(script)]),
                str(directory),
                "open",
                0,
            )
        code_path = directory / "exit.txt"
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if code_path.is_file():
                break
            time.sleep(POLL_SECONDS)
        else:
            return None
        try:
            returncode = int(code_path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return None
        stdout = (directory / "stdout.txt").read_bytes()
        stderr = (directory / "stderr.txt").read_bytes()
        return subprocess.CompletedProcess(command, returncode, stdout, stderr)
    except (DesktopUnavailable, OSError, pywintypes.error):
        return None
    finally:
        shutil.rmtree(directory, ignore_errors=True)
