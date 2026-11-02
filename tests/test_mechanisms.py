"""Offline tests with a scripted model. No endpoint or key is needed."""

import json
import unittest

from steward import bfcl_env  # noqa: F401
from bfcl_eval.eval_checker.eval_runner import _evaluate_single_multi_turn_entry
from bfcl_eval.utils import load_dataset_entry, load_ground_truth_entry

from steward import agent, verifier


class Scripted(agent.StewardHandler):
    """Replays fixed model replies; plans come from a separate list."""

    def __init__(self, name, config, replies, plans=()):
        super().__init__(name, config)
        self.replies, self.plans = list(replies), list(plans)

    def _query_prompting(self, inference_data):
        return self.replies.pop(0) if self.replies else "", 0.0

    def _parse_query_response_prompting(self, api_response):
        return {"model_responses": api_response, "input_token": 0, "output_token": 0,
                "model_responses_message_for_chat_history": {"role": "assistant", "content": api_response}}

    def _plan(self, entry, history, aliases, instances, request, stats):
        from steward.planner import FALLBACK
        return self.plans.pop(0) if self.plans else dict(FALLBACK)


def entry():
    cases = load_dataset_entry("multi_turn_base", include_language_specific_hint=False)
    return next(c for c in cases if c["id"] == "multi_turn_base_2")


class Mechanisms(unittest.TestCase):
    def fs_state(self, name, case_id="multi_turn_base_2"):
        from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_utils import execute_multi_turn_func_call
        case = entry()
        _, instances = execute_multi_turn_func_call(
            [], case["initial_config"], case["involved_classes"], name, case_id)
        return instances["GorillaFileSystem"]

    def test_halt_prevents_the_stray_file_after_a_failed_cd(self):
        # The model's batch mistypes the folder, then creates the file.
        h = Scripted("t_halt", agent.Config(preflight=True, halt_batch=True),
                     ["[cd(folder='document'), touch(file_name='TeamNotes.txt')]", ""])
        responses, meta = h.inference_multi_turn_prompting(entry(), False, True)
        self.assertEqual(meta["steward"]["stats"]["blocked"], 1)
        self.assertEqual(meta["steward"]["stats"]["skipped"], 1)
        self.assertNotIn("TeamNotes.txt", self.fs_state("t_halt").ls()["current_directory_content"])
        self.assertEqual(responses[0][0], "")

    def test_without_guard_the_stray_file_appears(self):
        h = Scripted("t_noguard", agent.Config(),
                     ["[cd(folder='document'), touch(file_name='TeamNotes.txt')]", ""])
        h.inference_multi_turn_prompting(entry(), False, True)
        self.assertIn("TeamNotes.txt", self.fs_state("t_noguard").ls()["current_directory_content"])

    def test_rollback_removes_only_what_was_created(self):
        plan = {"clarify": None, "summary": [], "aliases": {},
                "effects": [{"type": "absent", "path": "ideas.txt"}]}
        h = Scripted("t_rb", agent.Config(preflight=True, halt_batch=True, plan=True, verify=True, rollback=True),
                     ["[cd(folder='documents'), touch(file_name='x.txt')]", "", "", ""], [plan])
        responses, meta = h.inference_multi_turn_prompting(entry(), False, True)
        fs = self.fs_state("t_rb")
        report = meta["steward"]["reports"][0]
        self.assertEqual(report["verdict"], "rolled_back")
        self.assertEqual(fs.pwd()["current_working_directory"], "/simona")
        fs.cd("documents")
        names = fs.ls()["current_directory_content"]
        self.assertNotIn("x.txt", names)
        self.assertIn("ideas.txt", names)

    def test_deletion_not_requested_is_refused(self):
        h = Scripted("t_del", agent.Config(preflight=True, halt_batch=True),
                     ["[cd(folder='documents')]", "[rm(file_name='ideas.txt')]", ""])
        _, meta = h.inference_multi_turn_prompting(entry(), False, True)
        self.assertEqual(meta["steward"]["stats"]["blocked"], 1)
        fs = self.fs_state("t_del")
        self.assertIn("ideas.txt", fs.ls()["current_directory_content"])

    def test_evaluator_replay_passes_on_ground_truth_calls(self):
        case = entry()
        truth = next(g for g in load_ground_truth_entry("multi_turn_base") if g["id"] == case["id"])
        replies = []
        for turn in truth["ground_truth"]:
            replies += ["[" + ", ".join(turn) + "]", ""]
        h = Scripted("t_replay", agent.Config(preflight=True, halt_batch=True, triage=True), replies)
        responses, _ = h.inference_multi_turn_prompting(entry(), False, True)
        fresh = entry()
        verdict = _evaluate_single_multi_turn_entry(
            h, case["id"], responses, truth["ground_truth"], fresh, "t_replay_score", "multi_turn_base")
        self.assertTrue(verdict["valid"], json.dumps(verdict.get("error", {}), default=str)[:500])

    def test_verifier_effects(self):
        snap = {"GorillaFileSystem": {"/a/b.txt": "hello there", "/a/d": None},
                "TicketAPI": {"ticket_queue": [{"id": 3, "title": "T", "status": "Closed"}]}}
        unmet, checked = verifier.verify([
            {"type": "exists", "path": "b.txt"},
            {"type": "absent", "path": "zzz"},
            {"type": "content_contains", "path": "b.txt", "text": "HELLO"},
            {"type": "ticket_status", "ticket_id": 3, "status": "closed"},
            {"type": "exists", "path": "missing"},
            {"type": "message_sent", "text": "uncheckable here"},
        ], snap)
        self.assertEqual(checked, 5)
        self.assertEqual(unmet, [{"type": "exists", "path": "missing"}])

    def test_grounding_drops_typos_placeholders_and_short_text(self):
        kept = verifier.grounded([
            {"type": "exists", "path": "/a/IconsArchive.txt"},
            {"type": "exists", "path": "/a/<count>.pdf"},
            {"type": "exists", "path": "/a/IdeasArchive.txt"},
            {"type": "absent", "path": "/a/run_1"},
            {"type": "message_sent", "text": "inside"},
            {"type": "content_contains", "path": "x", "text": "keep this exact text"},
            {"type": "ticket_status", "ticket_id": 1, "status": "Closed"},
        ], "copy to IdeasArchive.txt and write keep this exact text inside", {"/a/run_1": None})
        self.assertEqual([e.get("text", e.get("path", e["type"])) for e in kept],
                         ["/a/IdeasArchive.txt", "/a/run_1", "keep this exact text", "ticket_status"])


if __name__ == "__main__":
    unittest.main()
