import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("privacy_check", Path(__file__).resolve().parents[1] / "scripts" / "privacy_check.py")
privacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(privacy)


class PrivacyTests(unittest.TestCase):
    def test_patterns_detect_values_without_echoing_them(self):
        values = ["ghp" + "_" + "A" * 36, "/" + "Users" + "/" + "person" + "/project", "person" + "@" + "example.test", "138" + "1234" + "5678"]
        for value in values:
            self.assertTrue(privacy.scan(value))

    def test_binary_private_files_and_symlink_policy(self):
        self.assertTrue(privacy.inspect("private/input.txt", b"text"))
        self.assertTrue(privacy.inspect("report.docx", b"text"))
        self.assertTrue(privacy.inspect("input.txt", b"\0"))
        self.assertEqual(privacy.inspect("README.md", b"project documentation"), [])
