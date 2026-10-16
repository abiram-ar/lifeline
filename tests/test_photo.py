"""Run with:  python -m unittest discover -s tests -v   (no internet or key needed)"""
import os
import sys
import unittest

os.environ.pop("GROQ_API_KEY", None)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import integration  # noqa: E402,F401  (agent upgrades)
import trauma  # noqa: E402,F401  (registers the topic)
import vision  # noqa: E402
from agent import Agent, keyword_topic  # noqa: E402
from knowledge import TOPICS  # noqa: E402


def obs(**kw):
    base = {"person_visible": True, "person_position": "unclear", "scene": "unclear", "vehicle_involved": False,
            "helmet_on": "unclear", "visible_bleeding": "none", "visible_bone_or_deformity": False,
            "visible_burn": False, "snake_visible": False, "appears_unresponsive": "unclear", "danger_in_scene": []}
    base.update(kw)
    return base


class TraumaTopicTests(unittest.TestCase):
    def test_topic_is_registered_and_complete(self):
        t = TOPICS["major_trauma"]
        self.assertTrue(t["steps"] and t["avoid"] and t["sources"] and t["always_escalate"])
        for q in t["triage"]:
            self.assertIn(q["switch"], TOPICS)
        for s in t["steps"]:
            if s.get("alt"):
                self.assertIn(s["alt"]["switch"], TOPICS)

    def test_never_tells_you_to_remove_helmet_or_move_person(self):
        joined = " ".join(s["title"] + ". " + s["text"] for s in TOPICS["major_trauma"]["steps"]).lower()
        self.assertIn("do not take off a helmet", joined)
        self.assertIn("do not move them", joined)

    def test_text_routing_for_crash(self):
        self.assertEqual(keyword_topic("there was a bike crash and he is lying on the road"), "major_trauma")
        self.assertNotEqual(keyword_topic("I accidentally burned my hand"), "major_trauma")

    def test_not_breathing_in_trauma_goes_to_cpr(self):
        a = Agent()
        a.start("major_trauma", via="photo")
        self.assertTrue(a.escalated)
        a.answer_triage(False)                 # "breathing normally?" -> No
        self.assertEqual(a.topic, "cpr")

    def test_watch_breathing_button_goes_to_cpr(self):
        a = Agent()
        a.start("major_trauma")
        a.answer_triage(True)
        for _ in range(len(a.steps()) - 1):
            a.next_step()
        self.assertIsNotNone(a.choose_action()["alt"])
        a.take_alt()
        self.assertEqual(a.topic, "cpr")


class RoutingTests(unittest.TestCase):
    def test_bike_crash_person_lying_helmet(self):
        r = vision.route(obs(scene="road_crash", vehicle_involved=True, person_position="lying_on_ground", helmet_on="yes"))
        self.assertEqual(r["topic"], "major_trauma")

    def test_vehicle_plus_lying_without_scene_label_still_trauma(self):
        self.assertEqual(vision.route(obs(vehicle_involved=True, person_position="lying_on_ground"))["topic"], "major_trauma")

    def test_fall_lying_is_trauma_but_standing_fall_is_not_assumed(self):
        self.assertEqual(vision.route(obs(scene="fall", person_position="lying_on_ground"))["topic"], "major_trauma")
        self.assertIsNone(vision.route(obs(scene="fall", person_position="standing"))["topic"])

    def test_crash_beats_bleeding_and_adds_reasons(self):
        r = vision.route(obs(scene="road_crash", visible_bleeding="heavy", appears_unresponsive="yes", danger_in_scene=["traffic"]))
        self.assertEqual(r["topic"], "major_trauma")
        self.assertEqual(len(r["reasons"]), 3)

    def test_other_routes(self):
        self.assertEqual(vision.route(obs(scene="fire_or_burn"))["topic"], "burn")
        self.assertEqual(vision.route(obs(visible_burn=True))["topic"], "burn")
        self.assertEqual(vision.route(obs(scene="chemical"))["topic"], "chemical")
        self.assertEqual(vision.route(obs(visible_bleeding="heavy"))["topic"], "bleeding")
        self.assertEqual(vision.route(obs(visible_bone_or_deformity=True))["topic"], "fracture")
        self.assertEqual(vision.route(obs(snake_visible=True))["topic"], "snakebite")

    def test_snake_without_person_does_not_start_a_guide(self):
        r = vision.route(obs(snake_visible=True, person_visible=False))
        self.assertIsNone(r["topic"])
        self.assertIn("away", r["message"])

    def test_unclear_photo_asks_user_instead_of_guessing(self):
        self.assertIsNone(vision.route(obs())["topic"])
        self.assertIsNone(vision.route(obs(scene="other"))["topic"])


class ValidationTests(unittest.TestCase):
    def test_garbage_values_become_unclear(self):
        o = vision.normalise({"scene": "alien_invasion", "visible_bleeding": 7, "person_visible": "yes",
                              "danger_in_scene": ["fire", "ufo"], "helmet_on": "YES"})
        self.assertEqual(o["scene"], "unclear")
        self.assertEqual(o["visible_bleeding"], "unclear")
        self.assertFalse(o["person_visible"])            # only a real JSON true counts
        self.assertEqual(o["danger_in_scene"], ["fire"])
        self.assertEqual(o["helmet_on"], "yes")

    def test_extract_json_handles_noise(self):
        self.assertEqual(vision.extract_json('<think>hmm</think>```json\n{"a": 1}\n```'), {"a": 1})
        self.assertIsNone(vision.extract_json("no json here"))
        self.assertIsNone(vision.extract_json(""))

    def test_no_key_gives_clear_error(self):
        with self.assertRaises(vision.VisionError):
            vision.analyse("data:image/jpeg;base64,AAAA")

    def test_describe_is_plain_english(self):
        lines = vision.describe(obs(scene="road_crash", vehicle_involved=True, person_position="lying_on_ground", helmet_on="yes"))
        self.assertTrue(any("lying" in l for l in lines))
        self.assertTrue(any("leave it on" in l for l in lines))


def burn_obs(**kw):
    return obs(scene="fire_or_burn", visible_burn=True, burn_location="face_hands_feet_genitals_or_joint",
               burn_appearance="blistered", **kw)


class PhotoAnswerTests(unittest.TestCase):
    def start_burn_from_photo(self, o):
        a = Agent()
        a.start("burn", via="photo")
        a.photo_auto = vision.auto_answers("burn", o)
        return a

    def test_photo_answers_visible_questions_and_skips_them(self):
        a = self.start_burn_from_photo(burn_obs())
        act = a.choose_action()                       # Q1 answered Yes by photo -> now on Q2 (electric/chemical)
        self.assertEqual(act["kind"], "triage")
        self.assertIn("electricity", act["text"])
        self.assertTrue(a.escalated)                  # hand burn = high-risk
        a.answer_triage(False)                        # user answers Q2 = No
        nxt = a.choose_action()                       # Q3 (skin colour) was answered by the photo -> straight to steps
        self.assertEqual(nxt["kind"], "step")
        self.assertEqual(len(a.view()["photo_notes"]), 2)

    def test_photo_never_answers_what_it_cannot_see(self):
        a = self.start_burn_from_photo(burn_obs())
        a.choose_action()
        self.assertIn("electricity", a.choose_action()["text"])      # still asked

    def test_unclear_photo_answers_nothing(self):
        self.assertEqual(vision.auto_answers("burn", obs(scene="fire_or_burn", visible_burn=True)), {})

    def test_charred_skin_is_answered_yes(self):
        ans, _ = vision.auto_answer("burn", "Does the skin look white, leathery or charred?", obs(burn_appearance="white_leathery_or_charred"))
        self.assertTrue(ans)

    def test_heavy_bleeding_photo_answers_first_bleeding_question(self):
        a = Agent()
        a.start("bleeding", via="photo")
        a.photo_auto = vision.auto_answers("bleeding", obs(visible_bleeding="heavy"))
        self.assertTrue(a.choose_action()["kind"] == "triage" and a.escalated)
        self.assertIn("pale", a.choose_action()["text"])             # Q2 (pallor) can't be seen: still asked

    def test_start_over_clears_photo_state(self):
        a = self.start_burn_from_photo(burn_obs())
        a.choose_action()
        a.start("burn")                                              # "Not right? Ask me all the questions"
        self.assertEqual(a.photo_notes, [])
        self.assertIn("face, hands", a.choose_action()["text"])


class InterruptTests(unittest.TestCase):
    CPR_PHRASES = ["he stopped breathing", "she is not breathing", "person isnt breathing", "he is not breathng",
                   "the person stopped breathing suddenly", "no pulse", "he doesn't breathe"]

    def test_cpr_phrases_interrupt_any_guide(self):
        for p in self.CPR_PHRASES:
            with self.subTest(p=p):
                self.assertEqual(integration.detect_interrupt(p, "burn"), "cpr")

    def test_collapse_goes_to_unconscious_guide(self):
        for p in ["he collapsed", "she passed out", "he is unconscious", "he went limp", "he won't wake up"]:
            with self.subTest(p=p):
                self.assertEqual(integration.detect_interrupt(p, "burn"), "unresponsive")

    def test_negation_and_ordinary_questions_do_not_interrupt(self):
        for p in ["he is not unconscious", "can I give water", "he is breathing normally", "should I move him"]:
            with self.subTest(p=p):
                self.assertIsNone(integration.detect_interrupt(p, "burn"))

    def test_no_pointless_switch_when_already_there(self):
        self.assertIsNone(integration.detect_interrupt("he is not breathing", "cpr"))
        self.assertIsNone(integration.detect_interrupt("he collapsed", "unresponsive"))

    def test_ask_box_switches_mid_questions(self):
        a = Agent()
        a.start("burn")                                  # on the first quick-check question
        out = a.ask("the person stopped breathing")
        self.assertEqual(a.topic, "cpr")
        self.assertIn("Switching", out["answer"])
        self.assertTrue(a.escalated)

    def test_ask_box_collapse_then_breathing_question(self):
        a = Agent()
        a.start("snakebite")
        a.ask("he just collapsed")
        self.assertEqual(a.topic, "unresponsive")
        self.assertIn("breathing normally", a.choose_action()["text"])


if __name__ == "__main__":
    unittest.main()
