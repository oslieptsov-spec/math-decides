"""DOCS.md answers to the code it documents.

An implementation companion that drifts from the implementation is worse than
no companion: it is read as authoritative.
"""
import re
import unittest
from pathlib import Path

from explainer import numbers
from gate import domain

ROOT = Path(__file__).resolve().parent.parent
DOCS = (ROOT / "DOCS.md").read_text(encoding="utf-8")


class DependencyTable(unittest.TestCase):
    def test_every_output_has_a_row(self):
        for name in domain.OUTPUTS:
            self.assertIn(f"`{name}`", DOCS, name)

    def test_the_rows_name_the_right_laws(self):
        for name, spec in domain.OUTPUTS.items():
            row = next((line for line in DOCS.splitlines()
                        if line.strip().startswith(f"| `{name}`")), None)
            self.assertIsNotNone(row, name)
            for law in spec["requires"]:
                self.assertIn(f"`{law}`", row, f"{name} is missing {law}")
            for law in set(domain.LAWS) - set(spec["requires"]):
                self.assertNotIn(f"`{law}`", row, f"{name} names {law} and must not")

    def test_the_lawless_output_is_marked(self):
        lawless = [n for n in domain.OUTPUTS if domain.has_no_law(n)]
        self.assertEqual(len(lawless), 1)
        row = next(line for line in DOCS.splitlines()
                   if line.strip().startswith(f"| `{lawless[0]}`"))
        self.assertIn("no closing relation exists", row)


class Contracts(unittest.TestCase):
    def test_every_status_is_documented(self):
        for status in domain.STATUSES:
            self.assertIn(status, DOCS, status)

    def test_the_unit_map_matches_the_code(self):
        for unit, factors in numbers.UNIT_FORMS.items():
            if unit is None:
                continue
            # The unit table lives inside a numbered list, so it is indented.
            row = next((line for line in DOCS.splitlines()
                        if line.strip().startswith(f"| `{unit}`")), None)
            self.assertIsNotNone(row, unit)
            if len(factors) > 1:
                self.assertIn("percent", row, unit)

    def test_the_canonical_precision_matches(self):
        from gate import canonical
        self.assertIn(f"{canonical.SIGNIFICANT_DIGITS} significant", DOCS)

    def test_the_minimum_rounding_floor_matches(self):
        floor = numbers.MIN_SIGNIFICANT_DIGITS_FOR_ROUNDING
        words = {2: "a single significant digit"}
        self.assertIn(words[floor], DOCS)


class Honesty(unittest.TestCase):
    REQUIRED = [
        "What is not claimed",
        "Explanation correctness",
        "Expected, unverified",
        "Documented limits",
        "membership, not comprehension",
    ]

    def test_the_limits_are_stated(self):
        for phrase in self.REQUIRED:
            self.assertIn(phrase, DOCS, phrase)

    def test_every_referenced_path_exists(self):
        """Resolved from the document, the way a reader's client resolves it."""
        base = (ROOT / "DOCS.md").parent
        for target in re.findall(r"\]\((?!https?:)([^)#]+)\)", DOCS):
            self.assertTrue((base / target).exists(), target)

    def test_the_readme_points_here(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("[DOCS.md](DOCS.md)", readme)


if __name__ == "__main__":
    unittest.main(verbosity=2)
