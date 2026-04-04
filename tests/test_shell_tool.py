import unittest
from unittest.mock import patch

from clawlet.tools.shell import ShellTool


class ShellToolTests(unittest.TestCase):
    def test_windows_dangerous_patterns_are_blocked_in_safe_mode(self):
        tool = ShellTool(allowed_commands=["powershell"], allow_dangerous=False, use_rust_core=False)
        tool._is_windows = lambda: True

        allowed, error = tool._validate_command("powershell Remove-Item -Recurse -Force temp")

        self.assertFalse(allowed)
        self.assertIn("dangerous command pattern", error)
        self.assertIn("PowerShell", error)

    def test_allow_dangerous_keeps_whitelist_enforcement(self):
        tool = ShellTool(allowed_commands=["echo"], allow_dangerous=True, use_rust_core=False)
        tool._is_windows = lambda: True

        allowed, error = tool._validate_command("powershell Remove-Item -Recurse -Force temp")

        self.assertFalse(allowed)
        self.assertIn("not allowed", error)
        self.assertIn("powershell", error)

    def test_shell_launcher_uses_powershell_on_windows(self):
        tool = ShellTool(use_rust_core=False)
        tool._is_windows = lambda: True

        with patch("clawlet.tools.shell.shutil.which", side_effect=lambda name: "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe" if name == "powershell.exe" else None):
            self.assertEqual(
                tool._shell_launcher("Get-ChildItem"),
                [
                    "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
                    "-Command",
                    "Get-ChildItem",
                ],
            )

    def test_shell_launcher_uses_bash_on_unix(self):
        tool = ShellTool(use_rust_core=False)
        tool._is_windows = lambda: False

        self.assertEqual(tool._shell_launcher("pwd"), ["/bin/bash", "-lc", "pwd"])

    def test_windows_shell_mode_detects_operator_tokens(self):
        tool = ShellTool(use_rust_core=False)
        tool._is_windows = lambda: True

        args = tool._split_command("git status > out.txt")

        self.assertTrue(tool._needs_shell_interpreter(args))
        self.assertEqual(tool._extract_segment_commands(args), ["git"])

    def test_windows_shell_launcher_requires_powershell(self):
        tool = ShellTool(use_rust_core=False)
        tool._is_windows = lambda: True

        with patch("clawlet.tools.shell.shutil.which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "PowerShell was not found"):
                tool._shell_launcher("Get-ChildItem")


if __name__ == "__main__":
    unittest.main()
