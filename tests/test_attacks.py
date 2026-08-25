"""Suite tests. The table in RESULTS.md is generated from exactly this."""
import unittest

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
