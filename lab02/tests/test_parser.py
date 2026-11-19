"""Tests for the ReAct parser and for the loop's failure handling (Steps 3 and 5).

The first test class records the real problem found during the build: the exact
regex the manual supplies cannot read a reply whose labels are decorated (Markdown
bold, backticks, lower case), which language models produce often. ``parse`` fixes
that by normalising the labels first, and the test proves both halves.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from react_agent import (  # noqa: E402
    ACTION_RE,
    CORRECTIVE_FORMAT,
    REPEAT_LIMIT,
    STOP,
    SYSTEM_PROMPT,
    normalise_labels,
    parse,
    run_agent,
)
from scripted_model import make_model  # noqa: E402

CANONICAL = "Thought: add the costs.\nAction: calculator\nAction Input: 4*185 + 3*95"


class StrictRegexTests(unittest.TestCase):
    """What the lab's regex does and does not accept, without normalisation."""

    def test_accepts_the_canonical_reply(self):
        match = ACTION_RE.search(CANONICAL)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "calculator")
        self.assertEqual(match.group(2).strip(), "4*185 + 3*95")

    def test_rejects_decorated_labels(self):
        # This is the failure that made the agent send corrective observations to
        # an otherwise correct model. Each string is a reply format seen in LLM
        # output: Markdown bold, backticks, lower case, and a double space.
        decorated = [
            "**Thought:** add the costs.\n**Action:** calculator\n"
            "**Action Input:** 4*185 + 3*95",
            "Thought: add the costs.\n`Action: calculator`\n`Action Input: 4*185 + 3*95`",
            "Thought: add the costs.\naction: calculator\naction input: 4*185 + 3*95",
            "Thought: add the costs.\nAction:  calculator\nAction  Input: 4*185 + 3*95",
        ]
        for reply in decorated:
            with self.subTest(reply=reply.splitlines()[1]):
                self.assertIsNone(ACTION_RE.search(reply))

    def test_normalise_then_parse_reads_them(self):
        reply = (
            "**Thought:** add the costs.\n**Action:** calculator\n"
            "**Action Input:** 4*185 + 3*95"
        )
        self.assertEqual(parse(reply), ("calculator", "4*185 + 3*95"))

    def test_normalise_keeps_the_action_input_label(self):
        # Normalising "Action:" must not damage the longer "Action Input:" label.
        self.assertIn("Action Input:", normalise_labels("action input: 2+2"))


class ParseTests(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(parse(CANONICAL), ("calculator", "4*185 + 3*95"))

    def test_multiline_action_input(self):
        reply = "Thought: x\nAction: wiki_lookup\nAction Input: Bono East\nRegion"
        action, payload = parse(reply)
        self.assertEqual(action, "wiki_lookup")
        self.assertIn("Bono East", payload)

    def test_trailing_prose_and_invented_observation_are_cut(self):
        reply = (
            "Thought: x\nAction: calculator\nAction Input: 2+2\n"
            "Observation: 4\nThought: done"
        )
        self.assertEqual(parse(reply), ("calculator", "2+2"))

    def test_finish_action(self):
        self.assertEqual(
            parse("Thought: done\nAction: finish\nAction Input: GHS 175 is left."),
            ("finish", "GHS 175 is left."),
        )

    def test_numbered_steps_are_normalised(self):
        # A second real failure: the model numbered its three lines, so the
        # "Action Input:" label no longer followed "Action: calculator" directly.
        numbered = "1. Thought: add\n2. Action: calculator\n3. Action Input: 1+1"
        self.assertIsNone(ACTION_RE.search(numbered))
        self.assertEqual(parse(numbered), ("calculator", "1+1"))

    def test_bulleted_steps_are_normalised(self):
        self.assertEqual(
            parse("- Thought: add\n- Action: calculator\n- Action Input: 1+1"),
            ("calculator", "1+1"),
        )

    def test_unusable_replies(self):
        for reply in (
            "",
            "   ",
            "The answer is GHS 175.",
            "Action: calculator\n",  # no Action Input line
            "Action: calculator\nAction Input: 1+1 but I do not trust it",  # still parses
        ):
            with self.subTest(reply=reply):
                action, _payload = parse(reply)
                if "Action Input:" in reply:
                    self.assertIsNotNone(action)
                else:
                    self.assertIsNone(action)

    def test_never_raises(self):
        for value in ("", "\n\n", "Action:", "Action Input:", "Thought: only"):
            self.assertIsInstance(parse(value), tuple)


class LoopTests(unittest.TestCase):
    """The loop must finish, recover, or stop cleanly - never crash."""

    def _run(self, scenario, max_steps=6):
        return run_agent(
            "test question",
            max_steps=max_steps,
            model_fn=make_model(scenario),
            source="scripted",
            scenario=scenario,
            echo=False,
        )

    def test_happy_path_uses_the_calculator_twice(self):
        run = self._run("budget")
        self.assertEqual(run.status, "finished")
        self.assertEqual(run.tool_counts["calculator"], 2)
        self.assertIn("175", run.answer)

    def test_unknown_tool_recovers(self):
        run = self._run("badly_worded")
        self.assertEqual(run.status, "finished")
        self.assertTrue(
            any("unknown tool 'Calculator'" in event["text"] for event in run.events)
        )

    def test_unparseable_reply_gets_a_corrective_observation(self):
        run = self._run("unparseable")
        self.assertEqual(run.status, "finished")
        self.assertTrue(any(CORRECTIVE_FORMAT in event["text"] for event in run.events))

    def test_max_steps_stops_the_run(self):
        run = self._run("never_finishes", max_steps=3)
        self.assertEqual(run.status, "max_steps")
        self.assertEqual(run.steps, 3)

    def test_repeated_call_is_intercepted(self):
        run = self._run("repeats_itself")
        self.assertEqual(run.status, "finished")
        self.assertEqual(run.tool_counts["calculator"], REPEAT_LIMIT)
        self.assertTrue(any("already called" in event["text"] for event in run.events))

    def test_model_error_is_reported_not_raised(self):
        def broken(_messages):
            raise RuntimeError("boom")

        run = run_agent("q", model_fn=broken, source="live", echo=False)
        self.assertEqual(run.status, "model_error")
        self.assertIn("boom", run.answer)

    def test_finish_without_answer_is_rejected_once(self):
        replies = iter(
            [
                "Thought: done\nAction: finish\nAction Input:",
                "Thought: done\nAction: finish\nAction Input: GHS 175.",
            ]
        )

        def model(_messages):
            return next(replies), (0, 0)

        run = run_agent("q", model_fn=model, source="scripted", echo=False)
        self.assertEqual(run.status, "finished")
        self.assertEqual(run.answer, "GHS 175.")


class PromptTests(unittest.TestCase):
    def test_prompt_names_every_tool_and_the_three_labels(self):
        for token in ("Thought:", "Action:", "Action Input:", "calculator",
                      "wiki_lookup", "finish"):
            self.assertIn(token, SYSTEM_PROMPT)

    def test_stop_sequence_protects_observations(self):
        self.assertEqual(STOP, ["Observation:"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
