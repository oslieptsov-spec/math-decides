"""The README answers to the same sources the page does.

Five times a figure in this project has lived in two versions at once. A
README is where that happens last and hurts most: it is the document a judge
reads instead of running anything.
"""
import json
import re
import unittest
from pathlib import Path

from attacks import cases
from gate import domain

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")


class Numbers(unittest.TestCase):
    def test_the_attack_total_is_the_suite(self):
        self.assertIn(f"blocked            {len(cases.ALL_CASES)}/{len(cases.ALL_CASES)}",
                      README)
        self.assertIn(f"These {len(cases.ALL_CASES)} attacks", README)

    def test_the_surface_split_is_the_suite(self):
        inputs = sum(1 for c in cases.ALL_CASES if c["surface"] == "input")
        models = len(cases.ALL_CASES) - inputs
        self.assertIn(f"{len(cases.ALL_CASES)} ({inputs} input, {models} model)", README)

    def test_the_control_matches_the_recording(self):
        recording = json.loads((ROOT / "web/sabotage.json").read_text(encoding="utf-8"))
        summary = recording["summary"]
        self.assertIn(f"blocked            {summary['blocked']}/{summary['cases']}",
                      README)
        self.assertIn(f"silently released  {summary['silently_released']}", README)
        passed = summary["cases"] - summary["blocked"]
        # The sentence opens with a word; the check should not care which.
        spelled = {10: "Ten", 11: "Eleven", 12: "Twelve", 13: "Thirteen",
                   14: "Fourteen", 15: "Fifteen", 16: "Sixteen",
                   17: "Seventeen", 18: "Eighteen", 19: "Nineteen",
                   20: "Twenty"}
        wanted = [f"{passed} attacks reach the consumer"]
        if passed in spelled:
            wanted.append(f"{spelled[passed]} attacks reach the consumer")
        self.assertTrue(any(phrase in README for phrase in wanted), wanted)

    WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}

    def test_the_domain_counts_match(self):
        laws, outputs = len(domain.LAWS), len(domain.OUTPUTS)
        self.assertIn(f"{self.WORDS[laws].capitalize()} laws, "
                      f"{self.WORDS[outputs]}\noutputs", README)

    def test_the_test_count_is_current(self):
        """Counted from the files, not from a subprocess that would run us."""
        total = sum(len(re.findall(r"^    def test_", path.read_text(encoding="utf-8"),
                                   re.M))
                    for path in sorted((ROOT / "tests").glob("test_*.py")))
        self.assertIn(f"make test         # {total} tests", README)


class Claims(unittest.TestCase):
    """The sections a reader is owed, and the one sentence that must survive."""

    REQUIRED = [
        "What is proven here, and what is not claimed",
        "not claimed",
        "Acceptance rate",
        "not** a ranking",
        "Adapt it to your domain",
        "NVIDIA Open Model License",
        "MIT",
        "Inspiration",
    ]

    def test_required_sections(self):
        for phrase in self.REQUIRED:
            self.assertIn(phrase, README, phrase)

    def test_the_licence_file_exists(self):
        self.assertTrue((ROOT / "LICENSE").exists())
        self.assertIn("MIT License", (ROOT / "LICENSE").read_text(encoding="utf-8"))

    def test_every_linked_path_exists(self):
        for target in re.findall(r"\]\((?!https?:)([^)#]+)\)", README):
            self.assertTrue((ROOT / target).exists(), target)

    def test_the_one_permitted_mention_is_prior_art(self):
        """The affiliation is not reproduced; the citation stands alone."""
        self.assertEqual(README.lower().count("ssrn"), 2)   # link text and URL
        self.assertNotIn("Scientific Analytics", README)


if __name__ == "__main__":
    unittest.main(verbosity=2)
