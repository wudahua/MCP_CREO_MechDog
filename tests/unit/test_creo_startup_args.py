"""BUG-029 extra parametric.exe startup arguments."""

import ctypes
import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import bridge
import creo_startup

ROOT = Path(__file__).resolve().parents[2]


def load(value: object, extra: dict | None = None):
    config = {"creo_root": str(ROOT / "Creo with spaces"), "creo_session_id": ""}
    if value is not None:
        config["creo_startup_args"] = value
    if extra:
        config.update(extra)
    with patch.object(bridge, "config", return_value=config):
        return creo_startup.Settings.load()


class StartupArgumentParsingTests(unittest.TestCase):
    def test_absent_arguments_keep_the_original_command_line(self):
        self.assertEqual(load(None).args, ())

    def test_configuration_array_is_preserved_in_order(self):
        settings = load(["-g:no_graphics", "-i:rpc_input"])
        self.assertEqual(settings.args, ("-g:no_graphics", "-i:rpc_input"))

    def test_invalid_configuration_is_rejected_before_launch(self):
        for value in ("-g:no_graphics", ["ok", ""], ["ok", 1], ["ok\r\ninjected"], {"a": 1}):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "creo_startup_args"):
                load(value)


class StartupArgumentLaunchTests(unittest.TestCase):
    def settings(self, *args: str) -> creo_startup.Settings:
        return creo_startup.Settings(
            Path("C:/Creo with spaces/parametric.exe"),
            Path("C:/Creo with spaces/start.psf"),
            True,
            120,
            False,
            tuple(args),
        )

    def session(self, pid, out):
        ctypes.cast(out, ctypes.POINTER(creo_startup.wintypes.DWORD))[0] = 7
        return True

    def launch(self, settings):
        desktop = Mock()
        desktop.HWND = 42
        with (
            patch.dict(os.environ, {"SYSTEMROOT": "C:/Windows"}),
            patch.object(creo_startup.pythoncom, "CoInitialize"),
            patch.object(creo_startup.pythoncom, "CoUninitialize"),
            patch.object(creo_startup.win32com.client, "Dispatch") as dispatch,
            patch.object(
                creo_startup.win32process, "GetWindowThreadProcessId", return_value=(1, 55)
            ),
            patch.object(creo_startup, "_session", side_effect=self.session),
            patch.object(creo_startup, "windows_session", return_value=7),
            patch.object(
                creo_startup,
                "process_identity",
                return_value={"image": str(Path("C:/Windows/explorer.exe"))},
            ),
            patch.object(creo_startup, "_open", return_value=111),
            patch.object(creo_startup, "_user_sid", return_value="same-owner"),
            patch.object(creo_startup, "_close"),
        ):
            dispatch.return_value.Windows.return_value.FindWindowSW.return_value = desktop
            creo_startup.launch_creo(settings, Path("C:/working"))
        return desktop.Document.Application.ShellExecute.call_args

    def test_arguments_follow_the_psf_on_parametric(self):
        call = self.launch(self.settings("-g:no_graphics", "-i:rpc_input"))
        self.assertEqual(
            call.args[1], '"C:\\Creo with spaces\\start.psf" -g:no_graphics -i:rpc_input'
        )

    def test_no_arguments_keeps_a_single_quoted_psf(self):
        call = self.launch(self.settings())
        self.assertEqual(call.args[1], '"C:\\Creo with spaces\\start.psf"')
