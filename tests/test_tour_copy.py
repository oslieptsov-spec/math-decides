"""The two rules that keep the tour readable to a stranger.

A card that explains the plot but not the screen leaves a judge staring at a
column of statuses and a Latin enum. So the copy is data, and the rules about
it are checked rather than remembered.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COPY = json.loads((ROOT / "web/tour.json").read_text(encoding="utf-8"))
SCENES = COPY["scenes"]
LAYERS = ("l1", "l2", "l3")


def first_sentence(text):
    return re.split(r"(?<=[.!?])\s", text.strip())[0]


class Structure(unittest.TestCase):
    def test_every_scene_has_three_layers(self):
        for scene in SCENES:
            for layer in LAYERS:
                self.assertTrue(scene.get(layer, "").strip(), f"{scene['id']}.{layer}")
            self.assertTrue(scene.get("title", "").strip(), scene["id"])

    def test_the_tour_and_the_copy_have_the_same_scenes(self):
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        for scene in SCENES:
            self.assertIn(f"copy: '{scene['id']}'", html, scene["id"])


class FirstSentenceIsPlain(unittest.TestCase):
    """Trade words appear once the reader already has a picture, never before."""

    def test_no_trade_word_opens_a_card(self):
        for scene in SCENES:
            opening = first_sentence(scene["l1"]).lower()
            for word in COPY["forbidden_in_first_sentence"]:
                self.assertNotIn(word, opening,
                                 f"{scene['id']}: {word!r} in the first sentence")

    def test_the_trade_words_do_still_appear(self):
        """Plain is not the same as vague: precision lives in the third layer."""
        body = " ".join(scene["l3"].lower() for scene in SCENES)
        for word in ("deterministic", "schema", "provenance"):
            self.assertIn(word, body, word)


class TermLadder(unittest.TestCase):
    """No term is used before the scene that introduces it."""

    def test_terms_arrive_in_order(self):
        for term, introduced_at in COPY["ladder"].items():
            pattern = re.compile(rf"\b{term}s?\b", re.IGNORECASE)
            for index, scene in enumerate(SCENES, start=1):
                text = " ".join(scene[layer] for layer in LAYERS) + " " + scene["title"]
                if pattern.search(text):
                    self.assertGreaterEqual(
                        index, introduced_at,
                        f"{scene['id']}: {term!r} used before scene {introduced_at}")

    def test_the_receipt_analogy_is_introduced_once(self):
        analogy = [scene["id"] for scene in SCENES
                   if "store receipt" in " ".join(scene[l] for l in LAYERS).lower()]
        self.assertEqual(analogy, ["receipt"])


class NoCountIsWrittenByHand(unittest.TestCase):
    """Including the one that greets the visitor."""

    def test_the_step_count_is_not_written_into_the_page(self):
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        found = re.search(r"\b(one|two|three|four|five|six|seven|eight|\d+)\s+steps\b",
                          html, re.IGNORECASE)
        self.assertIsNone(found, f"a step count is written into the page: "
                                 f"{found.group(0) if found else ''}")

    def test_the_page_renders_it_from_the_scene_list(self):
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        self.assertIn("NUMBER_WORDS[TOUR.length]", html)

    """Every figure in the copy is a placeholder the page fills from the domain."""

    ALLOWED = {"three", "one"}   # the three walls, and "one screen"

    def test_no_digits_in_copy(self):
        for scene in SCENES:
            for layer in LAYERS:
                found = re.findall(r"(?<!\{)\b\d+\b(?!\})", scene[layer])
                self.assertEqual(found, [], f"{scene['id']}.{layer}: {found}")

    def test_placeholders_are_known(self):
        known = {"missing", "total", "declared", "computed", "refused", "attacks"}
        for scene in SCENES:
            for layer in LAYERS:
                for name in re.findall(r"\{(\w+)\}", scene[layer]):
                    self.assertIn(name, known, f"{scene['id']}.{layer}: {name}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
