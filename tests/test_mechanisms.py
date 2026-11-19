"""Offline tests with a scripted model. No endpoint or key is needed."""

import json
import unittest

from steward import bfcl_env  # noqa: F401
from bfcl_eval.eval_checker.eval_runner import _evaluate_single_multi_turn_entry
from bfcl_eval.utils import load_dataset_entry, load_ground_truth_entry

from steward import agent, planner, specs, verifier


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

    def run_failed_check(self, name, answer):
        plan = {"clarify": None, "summary": [], "aliases": {},
                "effects": [{"type": "absent", "path": "ideas.txt"}]}
        asked = []

        def confirm(unmet, journal):
            asked.append(len(journal))
            return answer

        h = Scripted(name, agent.Config(preflight=True, halt_batch=True, plan=True, verify=True,
                                        confirm_undo=confirm),
                     ["[cd(folder='documents'), touch(file_name='x.txt')]", "", "", ""], [plan])
        _, meta = h.inference_multi_turn_prompting(entry(), False, True)
        fs = self.fs_state(name)
        fs.cd("documents")
        return asked, meta["steward"]["reports"][0], fs.ls()["current_directory_content"]

    def test_failed_check_keeps_changes_when_undo_is_declined(self):
        asked, report, names = self.run_failed_check("t_keep", False)
        self.assertEqual(asked, [1])
        self.assertEqual(report["verdict"], "partial")
        self.assertIn("x.txt", names)

    def test_failed_check_undoes_changes_when_approved(self):
        asked, report, names = self.run_failed_check("t_undo", True)
        self.assertEqual(asked, [1])
        self.assertEqual(report["verdict"], "rolled_back")
        self.assertNotIn("x.txt", names)

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


class Ambiguity(unittest.TestCase):
    OLD = ", ".join(f"/lab/scratch/{r}" for r in (
        "run_0211_base", "run_0218_abl", "run_0312_abl", "run_0319_base", "run_0327_abl", "run_0402_base"))

    def plan(self, aliases, readings=None):
        effects = [{"type": "exists", "path": "/lab/scratch/archive/run_0211_base"}]
        return {"clarify": None, "summary": [], "aliases": aliases, "readings": readings or {},
                "effects": effects}

    def test_vague_group_resolved_to_several_items_asks(self):
        question = planner.ambiguity(self.plan({"old runs": self.OLD}), "Move the old runs into the archive.")
        self.assertIn("run_0211_base", question)
        self.assertIn("Nothing has been changed", question)

    def test_dated_group_does_not_ask(self):
        aliases = {"March runs": "/lab/scratch/run_0312_abl, /lab/scratch/run_0319_base"}
        self.assertIsNone(planner.ambiguity(
            self.plan(aliases), "Consolidate the March runs into a new folder called 2026-03."))

    def test_planner_readings_that_disagree_ask(self):
        readings = {"old runs": [["run_0211_base", "run_0218_abl"], ["run_0211_base"]]}
        question = planner.ambiguity(self.plan({}, readings), "Archive the old runs")
        self.assertIn("run_0218_abl", question)

    def test_single_reading_does_not_ask(self):
        readings = {"ablation checkpoints folder": [["/lab/scratch/ablation_ckpts"]]}
        self.assertIsNone(planner.ambiguity(self.plan({}, readings), "Archive the ablation checkpoints folder"))

    def test_parse_plan_reads_readings(self):
        plan = planner.parse_plan(json.dumps({"readings": {"x": [["b", "a"], ["a", "b"], "c"]}}))
        self.assertEqual(plan["readings"], {"x": [["a", "b"], ["c"]]})

    def test_old_runs_request_asks_and_changes_nothing(self):
        from steward.dataset import d2
        case = next(e for e in d2()[0] if e["id"] == "multi_turn_labops_3")
        move_all = "[cd(folder='scratch'), mv(source='run_0211_base', destination='archive')]"
        h = Scripted("t_amb", agent.Config(**agent.STEWARD), [move_all, ""],
                     [self.plan({"old runs": self.OLD})])
        responses, meta = h.inference_multi_turn_prompting(case, False, True)
        report = meta["steward"]["reports"][0]
        self.assertEqual(report["verdict"], "asked")
        self.assertEqual(report["changes"], [])
        self.assertNotIn("mv(", json.dumps(responses[0]))


class Guard(unittest.TestCase):
    """The unintended changes observed in the Milestone 2 runs, replayed against the guard."""

    def state(self, dataset, case_id, calls=()):
        from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_utils import execute_multi_turn_func_call
        from steward.dataset import DATASETS
        case = {e["id"]: e for e in DATASETS[dataset]()[0]}[case_id]
        tag = f"g_{case_id}_{len(calls)}"
        _, instances = execute_multi_turn_func_call(
            list(calls), case["initial_config"], case["involved_classes"], tag, case_id)
        return case, instances

    def check(self, instances, call, text, prev="", created=()):
        name, args, owner = specs.parse_call(call, instances)
        return specs.preflight(name, args, owner, instances, text, set(created), prev)

    def test_remove_it_does_not_delete_a_file_never_named(self):
        # base_41: "removing it" meant the message; Steward deleted the notes file.
        case, inst = self.state("d1", "multi_turn_base_41", ["cd(folder='initial_directory')"])
        texts = [q[-1]["content"] for q in case["question"]]
        self.assertIn("refused", self.check(inst, "rm(file_name='notes')", texts[1], texts[0]))

    def test_unnamed_folder_is_not_deleted(self):
        # miss_param_38: "remove it and the directory" before the folder was named.
        case, inst = self.state("d3", "multi_turn_miss_param_38")
        text = case["question"][0][-1]["content"]
        self.assertIn("refused", self.check(inst, "rmdir(dir_name='BackupResearch')", text))

    def test_same_name_in_several_folders_asks_which(self):
        case, inst = self.state("d3", "multi_turn_miss_param_38", ["cd(folder='BackupResearch')"])
        text = case["question"][0][-1]["content"]
        reason = self.check(inst, "rm(file_name='findings_report')", text)
        self.assertIn("places", reason)

    def test_named_file_in_named_folder_may_be_deleted(self):
        case, inst = self.state("d3", "multi_turn_miss_param_38", ["cd(folder='SuperResearch')"])
        texts = [q[-1]["content"] for q in case["question"]]
        self.assertIsNone(self.check(inst, "rm(file_name='findings_report')", texts[1], texts[0]))

    def test_files_inside_a_named_folder_may_be_deleted(self):
        case, inst = self.state("d1", "multi_turn_base_46", ["cd(folder='Drafts')"])
        text = case["question"][0][-1]["content"]
        self.assertIsNone(self.check(inst, "rm(file_name='DylanProject.txt')", text))

    def test_new_file_request_does_not_overwrite_an_existing_one(self):
        # base_10: asked for a new notes.md; Steward overwrote the existing one.
        case, inst = self.state("d1", "multi_turn_base_10", ["cd(folder='workspace')"])
        text = case["question"][2][-1]["content"]
        self.assertIn("refused", self.check(inst, "echo(content='x', file_name='notes.md')", text))

    def test_unnamed_existing_file_is_not_overwritten(self):
        # miss_param_2: asked to draft a document; Steward wrote over ideas.txt.
        case, inst = self.state("d3", "multi_turn_miss_param_2", ["cd(folder='documents')"])
        text = case["question"][0][-1]["content"]
        self.assertIn("refused", self.check(inst, "echo(content='x', file_name='ideas.txt')", text))

    def test_writing_into_a_file_steward_created_is_allowed(self):
        case, inst = self.state("d3", "multi_turn_miss_param_2", ["cd(folder='documents')"])
        self.assertIsNone(self.check(inst, "echo(content='x', file_name='ideas.txt')",
                                     "write x into the new file", created={"ideas.txt"}))


if __name__ == "__main__":
    unittest.main()
