"""BUG-030 hidden worker launch through the interactive Explorer desktop."""

import contextlib
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import desktop_worker

ROOT = Path(__file__).resolve().parents[2]
COMMAND = [r"C:\repo\build\creo_worker.exe", "status", "2"]


class LauncherScriptTests(unittest.TestCase):
    def build(self, env=None, command=None):
        (ROOT / ".tmp").mkdir(exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix="desktop_worker_", dir=ROOT / ".tmp"))
        self.addCleanup(shutil.rmtree, directory, True)
        script = desktop_worker._launcher(
            directory, command or COMMAND, Path(r"C:\repo\build"), env or {"PATH": "a;b"}
        )
        return directory, script

    def test_script_sets_only_child_environment_and_captures_output(self):
        directory, script = self.build({"PATH": "a;b", "PRO_COMM_MSG_EXE": r"C:\repo\p.exe"})
        self.assertIsNotNone(script)
        text = script.read_text(encoding="utf-8")
        self.assertIn('set "PATH=a;b"', text)
        self.assertIn('set "PRO_COMM_MSG_EXE=C:\\repo\\p.exe"', text)
        self.assertNotIn("PTC_D_LICENSE_FILE", text)
        self.assertIn('cd /d "C:\\repo\\build"', text)
        self.assertIn(f'1>"{directory / "stdout.txt"}"', text)
        self.assertIn(f'2>"{directory / "stderr.txt"}"', text)
        self.assertIn("status 2", text)
        self.assertIn("%ERRORLEVEL%", text)
        self.assertIn(b"\r\n", script.read_bytes())

    def test_percent_is_escaped_for_batch(self):
        _, script = self.build({"PATH": "C:\\100%"})
        self.assertIn('set "PATH=C:\\100%%"', script.read_text(encoding="utf-8"))

    def test_license_environment_that_cannot_be_reproduced_is_refused(self):
        _, script = self.build({"PATH": "a", "PTC_D_LICENSE_FILE": r"C:\private\license.dat"})
        self.assertIsNone(script)

    def test_unquotable_values_are_refused(self):
        _, script = self.build({"PATH": 'a"b'})
        self.assertIsNone(script)


class DesktopRunTests(unittest.TestCase):
    def parent(self):
        (ROOT / ".tmp").mkdir(exist_ok=True)
        target = Path(tempfile.mkdtemp(prefix="desktop_runs_", dir=ROOT / ".tmp"))
        self.addCleanup(shutil.rmtree, target, True)
        return target

    def execute(self, payload: dict):
        shell = Mock()

        def run(exe, params, cwd, verb, show):
            Path(cwd, "stdout.txt").write_bytes(payload["stdout"])
            Path(cwd, "stderr.txt").write_bytes(payload["stderr"])
            Path(cwd, "exit.txt").write_text(payload["code"], encoding="utf-8")
            return None

        shell.ShellExecute.side_effect = run
        return patch.object(
            desktop_worker, "_explorer_shell", return_value=contextlib.nullcontext(shell)
        )

    def test_result_is_read_back_and_temporary_directory_is_removed(self):
        parent = self.parent()
        payload = {"stdout": b'{"connected":true}', "stderr": b"warn", "code": "0"}
        with self.execute(payload):
            result = desktop_worker.run(COMMAND, ROOT / "build", {"PATH": "a"}, 5, parent)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, payload["stdout"])
        self.assertEqual(result.stderr, payload["stderr"])
        self.assertEqual(list(parent.iterdir()), [])

    def test_missing_result_file_times_out_without_claiming_a_result(self):
        parent = self.parent()
        shell = Mock()
        with patch.object(
            desktop_worker, "_explorer_shell", return_value=contextlib.nullcontext(shell)
        ):
            self.assertIsNone(
                desktop_worker.run(COMMAND, ROOT / "build", {"PATH": "a"}, 0.1, parent)
            )
        shell.ShellExecute.assert_called_once()

    def test_unavailable_desktop_returns_none(self):
        parent = self.parent()
        with patch.object(
            desktop_worker,
            "_explorer_shell",
            side_effect=desktop_worker.DesktopUnavailable("no desktop"),
        ):
            self.assertIsNone(desktop_worker.run(COMMAND, ROOT / "build", {"PATH": "a"}, 1, parent))
        self.assertEqual(list(parent.iterdir()), [])

    def test_non_numeric_exit_code_is_ignored(self):
        parent = self.parent()
        payload = {"stdout": b"", "stderr": b"", "code": "boom"}
        with self.execute(payload):
            self.assertIsNone(desktop_worker.run(COMMAND, ROOT / "build", {"PATH": "a"}, 5, parent))

    def test_shell_is_hidden_and_uses_cmd_with_the_launcher(self):
        parent = self.parent()
        shell = Mock()
        with patch.object(
            desktop_worker, "_explorer_shell", return_value=contextlib.nullcontext(shell)
        ):
            desktop_worker.run(COMMAND, ROOT / "build", {"PATH": "a"}, 5, parent)
        call = shell.ShellExecute.call_args
        self.assertEqual(call.args[0], str(Path(os.environ["SYSTEMROOT"]) / "System32/cmd.exe"))
        self.assertEqual(call.args[3:], ("open", 0))
        self.assertIn("launch.cmd", call.args[1])
