"""Run with:  python -m unittest discover -s tests -v
No internet or API key needed: these tests check the rules, not the language model."""
import os
import sys
import unittest

os.environ.pop("GROQ_API_KEY", None)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent import Agent, keyword_topic, normalize, protocol_text, urgent_topic  # noqa: E402
from knowledge import TOPICS  # noqa: E402


class KnowledgeBaseTests(unittest.TestCase):
    def test_every_topic_is_complete(self):
        for tid, t in TOPICS.items():
            with self.subTest(topic=tid):
                self.assertTrue(t["steps"], "needs steps")
                self.assertTrue(t["sources"], "needs at least one source")
                self.assertTrue(t["avoid"], "needs a 'do not' list")
                self.assertIn(t["review"], ("sourced", "verify"))
                for step in t["steps"]:
                    self.assertTrue(step["title"] and step["text"])
                for q in t["triage"]:
                    if q.get("switch"):
                        self.assertIn(q["switch"], TOPICS)

    def test_no_us_number_anywhere(self):
        for tid, t in TOPICS.items():
            blob = protocol_text(tid)
            self.assertNotIn("911", blob)
            self.assertNotIn("999", blob)

    def test_no_dangerous_myths_recommended(self):
        # These may appear only inside a "Don't ..." line
        for tid, t in TOPICS.items():
            for s in t["steps"]:
                low = s["text"].lower()
                for bad in ("apply ice directly", "suck out", "apply butter", "tight tourniquet"):
                    self.assertNotIn(bad, low)


class RoutingTests(unittest.TestCase):
    CASES = {
        "my friend cut his hand and it is bleeding a lot": "bleeding",
        "I burned my arm with boiling water": "burn",
        "he is choking on a piece of chicken": "choking",
        "a cobra bit my father in the field": "snakebite",
        "stray dog bit my son on the leg": "animal_bite",
        "she twisted her ankle playing football": "fracture",
        "pesticide splashed in his eye": "chemical",
        "he has crushing chest pain and sweating": "heart_attack",
        "my mother's face is drooping and her speech is slurred": "stroke",
        "my brother is having a fit": "seizure",
        "bee sting and her throat is swelling": "anaphylaxis",
        "I can't breathe and my inhaler is not helping": "asthma",
        "he has been working in the sun and is confused and not sweating": "heatstroke",
        "she touched a live wire": "electric",
        "he passed out": "unresponsive",
    }

    def test_free_text_routing(self):
        for text, expected in self.CASES.items():
            with self.subTest(text=text):
                self.assertEqual(keyword_topic(text), expected)

    def test_urgent_pattern_beats_everything(self):
        self.assertEqual(urgent_topic("he fell and is not breathing"), "cpr")
        a = Agent()
        a.perceive("snake bite and he is not breathing")
        self.assertEqual(a.topic, "cpr")

    def test_gibberish_asks_for_clarification(self):
        a = Agent()
        self.assertFalse(a.perceive("something is wrong"))
        self.assertEqual(a.choose_action()["kind"], "clarify")

    def test_cute_is_not_cut(self):
        self.assertIsNone(keyword_topic("what a cute puppy"))


class FlowTests(unittest.TestCase):
    def test_choking_collapse_replans_to_cpr(self):
        a = Agent()
        a.start("choking")
        a.answer_triage(True)
        self.assertEqual(a.topic, "cpr")
        self.assertTrue(a.escalated)
        self.assertIn("Switched", a.notice)

    def test_unresponsive_not_breathing_goes_to_cpr(self):
        a = Agent()
        a.start("unresponsive")
        a.answer_triage(False)          # "breathing normally?" -> No
        self.assertEqual(a.topic, "cpr")

    def test_unresponsive_breathing_gets_recovery_position(self):
        a = Agent()
        a.start("unresponsive")
        a.answer_triage(True)           # breathing normally
        self.assertEqual(a.topic, "unresponsive")
        self.assertEqual(a.choose_action()["kind"], "step")

    def test_infant_choking_uses_baby_steps(self):
        a = Agent()
        a.perceive("my baby is choking")
        self.assertTrue(a.infant and a.escalated)
        a.answer_triage(False)
        first = a.choose_action()
        self.assertIn("face-down", first["text"])
        joined = " ".join(s["text"] for s in a.steps()).lower()
        self.assertNotIn("abdominal thrusts: stand", joined)

    def test_snakebite_always_escalated_and_no_checkin(self):
        a = Agent()
        a.start("snakebite")
        self.assertTrue(a.escalated)
        for _ in TOPICS["snakebite"]["triage"]:
            a.answer_triage(False)
        for _ in a.steps():
            a.next_step()
        self.assertEqual(a.choose_action()["kind"], "done")

    def test_failed_checkin_escalates(self):
        a = Agent()
        a.start("bleeding")
        a.answer_triage(False); a.answer_triage(False)
        for _ in a.steps():
            a.next_step()
        self.assertEqual(a.choose_action()["kind"], "checkin")
        a.answer_checkin(False)
        self.assertTrue(a.escalated)

    def test_successful_checkin_resolves(self):
        a = Agent()
        a.start("burn")
        for _ in range(3):
            a.answer_triage(False)
        for _ in a.steps():
            a.next_step()
        a.answer_checkin(True)
        self.assertTrue(a.resolved and not a.escalated)

    def test_back_button(self):
        a = Agent()
        a.start("snakebite")
        for _ in range(2):
            a.answer_triage(False)
        a.next_step(); a.next_step()
        a.prev_step()
        self.assertEqual(a.step_i, 1)


class TypoAndBranchTests(unittest.TestCase):
    def test_common_misspellings_still_route(self):
        self.assertEqual(keyword_topic(normalize("my roomate is chocking on a chicken leg")), "choking")
        self.assertEqual(keyword_topic(normalize("he is bleding badly")), "bleeding")
        self.assertIsNone(keyword_topic(normalize("I was scolded and I like chocolate")))

    def test_cpr_breathing_branch_is_reachable(self):
        a = Agent()
        a.start("cpr")
        a.next_step()                                   # now on "Check breathing"
        self.assertIsNotNone(a.choose_action()["alt"])
        a.take_alt()
        self.assertEqual(a.topic, "unresponsive")
        self.assertEqual(a.choose_action()["kind"], "step")     # triage question skipped
        self.assertEqual(a.choose_action()["title"], "Open the airway")

    def test_not_breathing_inside_cpr_gets_a_useful_reply(self):
        a = Agent()
        a.start("cpr")
        out = a.ask("he is not breathing")
        self.assertIn("compressions", out["answer"])


class ViewTests(unittest.TestCase):
    def test_view_has_step_titles_for_operator_script(self):
        a = Agent()
        a.start("burn")
        v = a.view()
        self.assertEqual(len(v["step_titles"]), len(TOPICS["burn"]["steps"]))
        self.assertEqual(Agent().view()["step_titles"], [])


class AskTests(unittest.TestCase):
    def test_offline_answer_comes_from_protocol(self):
        a = Agent()
        a.start("snakebite")
        out = a.ask("should I apply a tourniquet?")
        self.assertEqual(out["via"], "rules")
        self.assertIn("tourniquet", out["answer"].lower())

    def test_offline_unknown_question_refers_to_operator(self):
        a = Agent()
        a.start("burn")
        out = a.ask("what is the capital of France")
        self.assertIn("112", out["answer"])

    def test_dose_guard_blocks_invented_doses(self):
        proto = protocol_text("heart_attack")
        self.assertFalse(Agent._answer_is_safe("Give 500 mg of paracetamol.", proto))
        self.assertTrue(Agent._answer_is_safe("Only if the operator says so, chew one aspirin.", proto))


if __name__ == "__main__":
    unittest.main()
