"""Typing in the Ask box works in every guide: answers, 'done', news about the situation."""
import os, sys, unittest
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.pop("GROQ_API_KEY", None)
import integration  # noqa: F401  (installs the patches)
from agent import Agent


def agent_at(topic, tri=None, step=None):
    a = Agent(); a.start(topic)
    if tri is not None:
        a.tri_i = tri
    elif step is not None:
        a.tri_i = len(a.choose_action() and __import__("knowledge").TOPICS[topic]["triage"])
        a.step_i = step
    return a


def title(a):
    return a.choose_action().get("title")


class AnswersByTyping(unittest.TestCase):
    def test_yes_to_question(self):
        a = agent_at("bleeding", tri=0); a.ask("yes")
        self.assertTrue(a.escalated); self.assertEqual(a.tri_i, 1)

    def test_no_to_question(self):
        a = agent_at("bleeding", tri=0); a.ask("no")
        self.assertFalse(a.escalated); self.assertEqual(a.tri_i, 1)

    def test_no_with_explanation(self):
        a = agent_at("bleeding", tri=0); a.ask("no it is only a small cut")
        self.assertFalse(a.escalated); self.assertEqual(a.tri_i, 1)

    def test_describing_a_danger_sign_answers_yes(self):
        a = agent_at("stroke", tri=0); a.ask("his face is drooping on one side")
        self.assertIn("Face weakness", a.reasons)

    def test_burn_on_hand_is_a_red_flag(self):
        a = agent_at("burn", tri=0); a.ask("it is on her hand")
        self.assertIn("Large or high-risk burn", a.reasons)

    def test_questions_are_not_taken_as_answers(self):
        a = agent_at("bleeding", tri=0); out = a.ask("can I wash it first?")
        self.assertEqual(a.tri_i, 0); self.assertTrue(out["answer"])

    def test_checkin_yes_and_worse(self):
        a = agent_at("choking", step=4); self.assertEqual(a.choose_action()["kind"], "checkin")
        a.ask("it is not better"); self.assertTrue(a.escalated)

    def test_unresponsive_breathing_normally_is_yes(self):
        a = agent_at("unresponsive", tri=0); a.ask("he is breathing normally")
        self.assertEqual(a.topic, "unresponsive"); self.assertFalse(a.escalated and "Unresponsive" in " ".join(a.reasons[1:]))
        self.assertEqual(a.tri_i, 1)


class ProgressByTyping(unittest.TestCase):
    def test_done_moves_next(self):
        a = agent_at("burn", step=0); a.ask("done")
        self.assertEqual(a.step_i, 1)

    def test_seizure_stopped_jumps(self):
        a = agent_at("seizure", step=1); a.ask("the seizure stopped")
        self.assertEqual(title(a), "When the jerking stops")

    def test_choking_object_out_goes_to_checkin(self):
        a = agent_at("choking", step=1); a.ask("he coughed it out")
        self.assertEqual(a.choose_action()["kind"], "checkin")

    def test_anaphylaxis_no_improvement(self):
        a = agent_at("anaphylaxis", step=1); a.ask("no improvement")
        self.assertEqual(title(a), "Second dose")

    def test_electric_power_off(self):
        a = agent_at("electric", step=1); a.ask("I switched off the power")
        self.assertEqual(title(a), "Check once it is safe")

    def test_electric_still_touching(self):
        a = agent_at("electric", step=2); a.ask("he is still touching the wire")
        self.assertEqual(title(a), "Don't touch them yet"); self.assertIn("Ongoing electrical danger", a.reasons)

    def test_bleeding_soaked_through(self):
        a = agent_at("bleeding", step=2); a.ask("blood is coming through the cloth")
        self.assertEqual(title(a), "If blood soaks through")

    def test_asthma_inhaler_not_working(self):
        a = agent_at("asthma", step=1); a.ask("the inhaler is not working")
        self.assertEqual(title(a), "Still not better?")


class NewDangerAndWorse(unittest.TestCase):
    def test_new_danger_sign_during_steps(self):
        a = agent_at("burn", step=1); a.ask("the skin looks white and charred")
        self.assertIn("Possible deep burn", a.reasons)

    def test_getting_worse_adds_red_flag(self):
        a = agent_at("fracture", step=1); a.ask("he is getting worse")
        self.assertTrue(a.escalated)

    def test_collapse_goes_to_unconscious_guide_which_checks_breathing(self):
        for topic in ("choking", "heart_attack", "anaphylaxis", "snakebite", "electric", "burn"):
            a = agent_at(topic, step=1); a.ask("he collapsed")
            self.assertEqual(a.topic, "unresponsive", topic)
            self.assertIn("breathing normally", a.choose_action()["text"])

    def test_collapse_in_other_guides_goes_to_unresponsive(self):
        a = agent_at("burn", step=1); a.ask("she fainted")
        self.assertEqual(a.topic, "unresponsive")

    def test_negated_collapse_ignored(self):
        a = agent_at("burn", step=1); a.ask("he is not unconscious")
        self.assertEqual(a.topic, "burn")


class UsingTheLanguageModel(unittest.TestCase):
    def test_free_sentence_answered_by_model_when_rules_do_not_match(self):
        a = agent_at("stroke", tri=0)
        with mock.patch.object(integration.llm, "enabled", return_value=True), \
             mock.patch.object(integration.llm, "chat_json", return_value={"answer": "yes"}):
            a.ask("one corner of his mouth is hanging lower")
        self.assertIn("Face weakness", a.reasons)

    def test_unsure_model_falls_back_to_normal_answer(self):
        a = agent_at("stroke", tri=0)
        with mock.patch.object(integration.llm, "enabled", return_value=True), \
             mock.patch.object(integration.llm, "chat_json", return_value={"answer": "unsure"}), \
             mock.patch.object(integration.llm, "chat", return_value=None):
            a.ask("he looks tired")
        self.assertEqual(a.tri_i, 0)


class NewsAndQuestionTogether(unittest.TestCase):
    def test_electric_still_touching_what_to_do(self):
        a = agent_at("electric", step=2)
        out = a.ask("hes still touching the electric wir, what to do?")
        self.assertEqual(title(a), "Don't touch them yet")
        self.assertIn("Ongoing electrical danger", a.reasons)
        self.assertIn("Don't touch them yet", out["answer"])
        self.assertIn("Call 112", out["answer"])

    def test_news_during_questions_then_what_to_do(self):
        a = agent_at("electric", tri=0)
        out = a.ask("he is still touching the wire, what should I do?")
        self.assertIn("Ongoing electrical danger", a.reasons)
        self.assertIn("Don't touch them yet", out["answer"])

    def test_plain_what_to_do_gives_current_step(self):
        a = agent_at("burn", step=1)
        out = a.ask("what to do?")
        self.assertIn("Cool the burn", out["answer"])

    def test_question_with_no_news_unchanged(self):
        a = agent_at("burn", step=1)
        a.ask("can I put ice on it?")
        self.assertEqual(a.step_i, 1)

    def test_mixed_message_passes_screen_to_the_model(self):
        a = agent_at("electric", step=2)
        seen = {}
        def fake_chat(messages, **kw):
            seen["system"] = messages[0]["content"]
            return "Do not touch him. Switch off the power or push him away with dry wood. Call 112."
        with mock.patch.object(integration.llm, "enabled", return_value=True), \
             mock.patch.object(integration.llm, "chat", side_effect=fake_chat), \
             mock.patch.object(integration.llm, "chat_json", return_value=None):
            out = a.ask("he is still touching the wire, what do I do?")
        self.assertIn("Don't touch them yet", seen["system"])
        self.assertIn("Ongoing electrical danger", seen["system"])
        self.assertEqual(out["via"], "groq")


class NotBreathingMidGuide(unittest.TestCase):
    def test_typed_in_electric_guide_skips_the_checks(self):
        a = agent_at("electric", step=1)
        a.ask("hes not touching the power source anymore but is not breathing")
        self.assertEqual(a.topic, "cpr")
        self.assertEqual(title(a), "Push hard and fast")
        self.assertTrue(a.escalated)
        self.assertIn("Call 112", a.notice)

    def test_server_shortcut_path_also_skips(self):
        a = agent_at("burn", step=1)
        a.start("cpr", via="emergency-pattern")          # what server.py does for an urgent phrase
        self.assertEqual(title(a), "Push hard and fast")

    def test_fresh_start_from_home_box_begins_at_check_and_call(self):
        a = Agent()
        a.start("cpr", via="emergency-pattern")
        self.assertEqual(title(a), "Check and call")

    def test_collapse_replan_from_choking_still_starts_at_the_beginning(self):
        a = agent_at("choking", tri=0)
        a.answer_triage(True)                            # "collapsed?" -> yes -> CPR via the protocol
        self.assertEqual(a.topic, "cpr")
        self.assertEqual(title(a), "Check and call")

    def test_back_returns_to_check_and_call(self):
        a = agent_at("electric", step=1)
        a.ask("he is not breathing")
        for _ in range(5):
            a.prev_step()
        self.assertEqual(title(a), "Check and call")


if __name__ == "__main__":
    unittest.main()
