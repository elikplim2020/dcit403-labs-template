"""Tests for the two tools (Step 2 checkpoint, plus the safety cases).

Run from the ``lab02`` folder::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import TOOLS, calculator, run_tool, wiki_lookup  # noqa: E402


class CalculatorTests(unittest.TestCase):
    def test_arithmetic(self):
        cases = {
            "4*185 + 3*95": "1025",
            "1200 - 1025": "175",
            "1140/6": "190",
            "(2+3)*4": "20",
            "-5 + 10": "5",
            "0.5 * 8": "4",
        }
        for expr, expected in cases.items():
            with self.subTest(expr=expr):
                self.assertEqual(calculator(expr), expected)

    def test_thousands_separator(self):
        # A trader writes "1,200"; commas are removed before parsing.
        self.assertEqual(calculator("1,200 - 1,025"), "175")

    def test_whole_floats_are_shown_as_integers(self):
        self.assertEqual(calculator("1140/6"), "190")  # not "190.0"

    def test_rejects_code_not_arithmetic(self):
        for expr in (
            "__import__('os').system('dir')",
            "open('secret.txt').read()",
            "[1,2,3][0]",
            "'a' * 3",
            "x + 1",
            "print(1)",
            "2 ** 10",  # power is deliberately not in the whitelist
        ):
            with self.subTest(expr=expr):
                self.assertTrue(calculator(expr).startswith("Error"), expr)

    def test_division_by_zero_is_reported(self):
        self.assertEqual(calculator("1/0"), "Error: division by zero")

    def test_empty_and_overlong(self):
        self.assertEqual(calculator("   "), "Error: empty expression")
        self.assertTrue(calculator("1+" * 80).startswith("Error"))

    def test_never_raises(self):
        # Whatever the model sends must come back as text, never as an exception.
        for value in ("", "1/0", "abc", "1+", "((1+2)"):
            self.assertIsInstance(calculator(value), str)


class WikiLookupTests(unittest.TestCase):
    """These tests use the live Wikipedia API, so they skip when it is unreachable."""

    @staticmethod
    def _skip_if_offline(result: str) -> None:
        if result.startswith("Error: could not reach Wikipedia"):
            raise unittest.SkipTest("Wikipedia is unreachable from this machine")

    def test_found_page_returns_extract(self):
        result = wiki_lookup("Bono East Region")
        self._skip_if_offline(result)
        self.assertIn("Ghana", result)
        self.assertLessEqual(len(result), 803)  # 800 plus the ellipsis

    def test_missing_page_is_a_message_not_an_exception(self):
        result = wiki_lookup("Zxqv Market Traders Association of Ghana")
        self._skip_if_offline(result)
        self.assertTrue(result.startswith("No Wikipedia page"))

    def test_empty_title(self):
        self.assertTrue(wiki_lookup("  ").startswith("Error"))

    def test_quoted_title_is_cleaned(self):
        # Models often wrap titles in quotes; the quotes must not reach the URL.
        result = wiki_lookup('"Bono East Region"')
        self._skip_if_offline(result)
        self.assertIn("Ghana", result)


class RunToolTests(unittest.TestCase):
    def test_dispatch(self):
        self.assertEqual(run_tool("calculator", "2+2"), "4")

    def test_unknown_tool_returns_corrective_text(self):
        result = run_tool("Calculator", "2+2")
        self.assertIn("unknown tool 'Calculator'", result)
        self.assertIn("Did you mean 'calculator'", result)
        self.assertIn("calculator, wiki_lookup", result)

    def test_registry_matches_prompt(self):
        # finish is handled by the loop; the registry holds the two real tools.
        self.assertEqual(sorted(TOOLS), ["calculator", "wiki_lookup"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
