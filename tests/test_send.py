import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import send  # noqa: E402


class SendTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name, content):
        path = self.tmp / name
        path.write_text(content, encoding="utf-8")
        return path

    def run_cli(self, csv_text, template_text, output_dir="out/nested"):
        csv_path = self.write("recipients.csv", csv_text)
        template_path = self.write("template.txt", template_text)
        out = self.tmp / output_dir
        rc = send.main(
            [
                "--recipient-list", str(csv_path),
                "--payload-template", str(template_path),
                "--output-dir", str(out),
            ]
        )
        return rc, out


class RenderTests(SendTestCase):
    def test_renders_one_file_per_recipient_and_creates_output_dir(self):
        rc, out = self.run_cli(
            "Ada Lovelace,ada@example.com\nAlan Turing,alan@example.net\n",
            "Hi {FULL_NAME}!\n",
        )
        self.assertEqual(rc, 0)
        self.assertEqual(
            sorted(p.name for p in out.iterdir()),
            ["ada@example.com.txt", "alan@example.net.txt"],
        )
        self.assertEqual((out / "ada@example.com.txt").read_text(), "Hi Ada Lovelace!\n")
        self.assertEqual((out / "alan@example.net.txt").read_text(), "Hi Alan Turing!\n")

    def test_existing_output_dir_is_reused(self):
        (self.tmp / "out").mkdir()
        rc, out = self.run_cli("Ada,ada@example.com\n", "x", output_dir="out")
        self.assertEqual(rc, 0)
        self.assertTrue((out / "ada@example.com.txt").exists())

    def test_quoted_name_with_comma_and_whitespace_trimmed(self):
        rc, out = self.run_cli('"Hopper, Grace" ,  grace@example.org \n', "{FULL_NAME}")
        self.assertEqual(rc, 0)
        self.assertEqual((out / "grace@example.org.txt").read_text(), "Hopper, Grace")

    def test_placeholder_variants_and_literal_braces(self):
        rendered = send.render("{FULL_NAME} / { FULL_NAME } / {} / {not a var} / {{x}}", "Ada")
        self.assertEqual(rendered, "Ada / Ada / {} / {not a var} / {{x}}")

    def test_name_with_backslashes_is_inserted_literally(self):
        self.assertEqual(send.render("{FULL_NAME}", r"A\1\g<0>"), r"A\1\g<0>")

    def test_blank_lines_are_skipped(self):
        rc, out = self.run_cli("\nAda,ada@example.com\n\n", "x")
        self.assertEqual(rc, 0)
        self.assertEqual(len(list(out.iterdir())), 1)

    def test_file_names_are_sanitized(self):
        self.assertEqual(send.output_filename("Ada@Example.com"), "ada@example.com.txt")
        self.assertEqual(send.output_filename("a/../b@x.com"), "a_.._b@x.com.txt")


class ValidationTests(SendTestCase):
    def assertFails(self, csv_text, template_text, message):
        with self.assertRaises(send.InputError) as ctx:
            send.run(
                self.write("r.csv", csv_text),
                self.write("t.txt", template_text),
                self.tmp / "out",
            )
        self.assertIn(message, str(ctx.exception))
        self.assertFalse((self.tmp / "out").exists(), "nothing should be written on error")

    def test_unsupported_variable(self):
        self.assertFails("Ada,ada@example.com\n", "Hi {FIRST_NAME}", "{FIRST_NAME}")

    def test_wrong_column_count(self):
        self.assertFails("Ada,ada@example.com,extra\n", "x", "expected 2 columns")

    def test_invalid_email(self):
        self.assertFails("Ada,not-an-email\n", "x", "invalid email")

    def test_empty_name(self):
        self.assertFails(" ,ada@example.com\n", "x", "full name is empty")

    def test_duplicate_email_case_insensitive(self):
        self.assertFails("A,ada@example.com\nB,ADA@example.com\n", "x", "duplicate email")

    def test_empty_recipient_list(self):
        self.assertFails("\n\n", "x", "no recipients")


class CliTests(SendTestCase):
    def test_script_end_to_end(self):
        out = self.tmp / "rendered"
        result = subprocess.run(
            [
                sys.executable, str(ROOT / "send.py"),
                "--recipient-list", str(ROOT / "examples" / "recipients.csv"),
                "--payload-template", str(ROOT / "examples" / "newsletter.txt"),
                "--output-dir", str(out),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Rendered 3 email(s)", result.stderr)
        self.assertIn("Hi Ada Lovelace,", (out / "ada@example.com.txt").read_text())

    def test_missing_file_reports_error(self):
        result = subprocess.run(
            [
                sys.executable, str(ROOT / "send.py"),
                "--recipient-list", str(self.tmp / "missing.csv"),
                "--payload-template", str(self.tmp / "missing.txt"),
                "--output-dir", str(self.tmp / "out"),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stderr.startswith("error:"))

    def test_missing_required_argument(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "send.py")], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--recipient-list", result.stderr)


if __name__ == "__main__":
    unittest.main()
