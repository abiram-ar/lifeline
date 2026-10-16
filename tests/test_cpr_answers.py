"""Typing about breathing while the CPR guide is open should act on the 'Check breathing' step."""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.pop("GROQ_API_KEY", None)
import integration  # noqa: F401  (installs the patches)
from agent import Agent


def cpr_at(step):
    a = Agent(); a.start("cpr"); a.step_i = step
    return a


class CprTyping(unittest.TestCase):
    def test_not_breathing_on_check_step_moves_to_compressions(self):
        a = cpr_at(1)
        out = a.ask("hes not breathing")
        self.assertEqual(a.topic, "cpr")
        self.assertEqual(a.choose_action()["title"], "Push hard and fast")
        self.assertIn("compressions", out["answer"])

    def test_not_breathing_on_first_step_also_skips_to_compressions(self):
        a = cpr_at(0); a.ask("he stopped breathing")
        self.assertEqual(a.choose_action()["title"], "Push hard and fast")

    def test_gasping_is_not_normal_breathing(self):
        a = cpr_at(1); a.ask("he is gasping")
        self.assertEqual(a.choose_action()["title"], "Push hard and fast")

    def test_not_breathing_later_does_not_go_back(self):
        a = cpr_at(4); out = a.ask("still not breathing")
        self.assertEqual(a.choose_action()["title"], "Use the AED")
        self.assertIn("Keep going", out["answer"])

    def test_breathing_normally_takes_recovery_branch(self):
        a = cpr_at(1); a.ask("hes breathing normally")
        self.assertEqual(a.topic, "unresponsive")

    def test_breathing_normally_works_from_a_later_step(self):
        a = cpr_at(2); a.ask("he started breathing")
        self.assertEqual(a.topic, "unresponsive")

    def test_not_breathing_normally_is_not_taken_as_ok(self):
        a = cpr_at(1); a.ask("he is not breathing normally")
        self.assertEqual(a.topic, "cpr")
        self.assertEqual(a.choose_action()["title"], "Push hard and fast")

    def test_other_questions_still_answered_normally(self):
        a = cpr_at(2); out = a.ask("can I give them water?")
        self.assertEqual(a.topic, "cpr")
        self.assertEqual(a.step_i, 2)
        self.assertTrue(out["answer"])

    def test_from_another_guide_still_switches_to_cpr(self):
        a = Agent(); a.start("burn"); a.ask("he stopped breathing")
        self.assertEqual(a.topic, "cpr")


if __name__ == "__main__":
    unittest.main()
