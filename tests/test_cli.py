import io
import os
import unittest
from contextlib import redirect_stdout

from fontmetricslint.cli import main

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def run_cli(args):
    out = io.StringIO()
    with redirect_stdout(out):
        status = main(args)
    return status, out.getvalue()


class IgnoreFlagTests(unittest.TestCase):
    def test_no_ignore_flag_reports_everything(self):
        path = os.path.join(FIXTURES_DIR, "broken.afm")
        status, output = run_cli([path])
        self.assertIn("W001", output)
        self.assertEqual(status, 1)

    def test_comma_separated_codes_are_suppressed(self):
        path = os.path.join(FIXTURES_DIR, "broken.afm")
        status, output = run_cli(["--ignore", "W001,W002,W003", path])
        self.assertNotIn("W001", output)
        self.assertNotIn("W002", output)
        self.assertNotIn("W003", output)
        self.assertIn("E004", output)
        self.assertEqual(status, 1)

    def test_repeated_flags_combine(self):
        path = os.path.join(FIXTURES_DIR, "broken.afm")
        status, output = run_cli(
            ["--ignore", "W001", "--ignore", "W002", "--ignore", "W003", path]
        )
        self.assertNotIn("W001", output)
        self.assertNotIn("W002", output)
        self.assertNotIn("W003", output)

    def test_ignoring_the_only_error_gives_clean_exit(self):
        path = os.path.join(FIXTURES_DIR, "bad_bbox.afm")
        status, output = run_cli(["--ignore", "E006", path])
        self.assertEqual(output, "")
        self.assertEqual(status, 0)


if __name__ == "__main__":
    unittest.main()
