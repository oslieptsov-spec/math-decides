"""Suite tests. The table in RESULTS.md is generated from exactly this."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from attacks import cases, runner
from gate import canonical, engine, examples


class Coverage(unittest.TestCase):
    def test_ids_are_unique(self):
        ids = [case["id"] for case in cases.ALL_CASES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_both_surfaces_are_covered(self):
        surfaces = {case["surface"] for case in cases.ALL_CASES}
        self.assertEqual(surfaces, {"input", "model"})

    def test_the_suite_is_at_least_twenty_cases(self):
        self.assertGreaterEqual(len(cases.ALL_CASES), 20)


class PublishedNumbers(unittest.TestCase):
    """Every public count comes from the suite, never from a keystroke.

    Twice now a number has lived in two versions at once: a page saying 34 and
    a recording saying 33, because the recording predated a case. A count typed
    into prose is a count that will be wrong on the day someone reads it.
    """

    def test_the_recording_matches_the_suite(self):
        recording = json.loads((ROOT / "web/sabotage.json").read_text(encoding="utf-8"))
        self.assertEqual(recording["summary"]["cases"], len(cases.ALL_CASES))
        self.assertIn(f"/{len(cases.ALL_CASES)} pass", recording["headline"])

    def test_the_results_table_matches_the_suite(self):
        text = (ROOT / "attacks/RESULTS.md").read_text(encoding="utf-8")
        found = re.search(r"(\d+) of (\d+) cases blocked", text)
        self.assertIsNotNone(found, "the table lost its headline")
        self.assertEqual(int(found.group(2)), len(cases.ALL_CASES))

    def test_no_published_document_carries_a_stale_count(self):
        """Any 'n of m' or 'n/m' in what ships, where m could be a case count.

        Only tracked files: a private planning note may quote a number that was
        true when it was written, and often should. What ships may not.
        """
        import subprocess
        total = len(cases.ALL_CASES)
        tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                                 text=True).stdout.split()
        targets = [ROOT / name for name in tracked
                   if name.endswith((".md", ".html"))]
        for path in targets:
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            for numerator, denominator in re.findall(r"(\d+)\s*(?:of|/)\s*(\d+)", text):
                if 20 <= int(denominator) <= 99:
                    self.assertEqual(int(denominator), total,
                                     f"{path.name}: {numerator}/{denominator} is stale")

    def test_the_page_never_states_a_law_count_in_copy(self):
        """Counts in prose render from the domain, not from a keystroke.

        A preset read "two laws forgotten" while declaring one law of four.
        The figure had been copied off the result line, where 2 counts refused
        outputs rather than laws — a number true one line up and false where it
        landed.
        """
        import re
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        pattern = re.compile(
            r"\b(one|two|three|four|five|\d+)\s+(?:of\s+(?:the\s+)?\w+\s+)?laws\b",
            re.IGNORECASE)
        for match in pattern.finditer(html):
            self.fail(f"a law count is written into the page: {match.group(0)!r}")

    def test_the_page_never_hardcodes_the_count(self):
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        self.assertIn("r-attacks", html)
        self.assertNotIn(f"{len(cases.ALL_CASES)} attacks", html)


class Guarded(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = runner.run(post_validation=True)
        cls.summary = runner.summarise(cls.results)

    def test_every_case_is_blocked(self):
        unblocked = [r["id"] for r in self.results if not r["blocked"]]
        self.assertEqual(unblocked, [])

    def test_nothing_is_silently_released(self):
        """The statistic the suite exists to publish."""
        self.assertEqual(self.summary["silently_released"], 0)

    def test_every_block_carries_a_named_reason(self):
        for result in self.results:
            self.assertTrue(result["evidence"], result["id"])

    def test_injections_never_reach_the_receipt(self):
        for case in cases.INPUT_CASES:
            if not case.get("marker"):
                continue
            request = examples.load(case["example"])
            case["mutate"](request)
            try:
                receipt = engine.evaluate(request)
            except Exception:
                continue
            self.assertNotIn(case["marker"], canonical.dumps(receipt), case["id"])


class NegativeControl(unittest.TestCase):
    """A gate that has never blocked anything is untested policy."""

    @classmethod
    def setUpClass(cls):
        cls.results = runner.run(post_validation=False)
        cls.summary = runner.summarise(cls.results)

    def test_removing_the_guardrail_lets_attacks_through(self):
        self.assertLess(self.summary["blocked"], len(cases.ALL_CASES))

    def test_removing_the_guardrail_releases_a_withheld_output(self):
        self.assertGreater(self.summary["silently_released"], 0)
        self.assertIn("defensive_factor", self.summary["released_outputs"])

    def test_input_attacks_do_not_depend_on_the_guardrail(self):
        """Structure and schema are unaffected by switching off validation."""
        for result in self.results:
            if result["surface"] == "input":
                self.assertTrue(result["blocked"], result["id"])

    def test_the_receipt_is_never_moved_even_then(self):
        """Sabotage releases a claim about a status, never a status."""
        for case in cases.MODEL_CASES:
            receipt = engine.evaluate(examples.load(case["example"]))
            outcome = runner.run_model_case(case, post_validation=False)
            self.assertEqual(outcome["receipt_sha"], receipt["receipt_sha"], case["id"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
