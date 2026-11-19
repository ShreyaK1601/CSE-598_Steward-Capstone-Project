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


class CompleteVerification(unittest.TestCase):
    MARCH = {"phrase": "the March runs", "folder": "/lab/scratch", "pattern": "run_03*",
             "action": "move", "destination": "/lab/scratch/2026-03"}

    def lab_case(self, index):
        from steward.dataset import d2
        return next(e for e in d2()[0] if e["id"] == f"multi_turn_labops_{index}")

    def plan(self, effects, groups=()):
        return {"clarify": None, "summary": [], "aliases": {}, "readings": {},
                "groups": list(groups), "effects": effects}

    def test_group_pattern_expands_to_every_matching_item(self):
        from steward.dataset import LAB_CONFIG
        from steward import probes
        from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_utils import execute_multi_turn_func_call
        _, inst = execute_multi_turn_func_call([], LAB_CONFIG, ["GorillaFileSystem"], "t_expand", "lab_0")
        fs = probes.snapshot(inst)["GorillaFileSystem"]
        # The planner's own list names only two of the three March runs.
        plan = self.plan([{"type": "exists", "path": "/lab/scratch/2026-03/run_0312_abl"},
                          {"type": "exists", "path": "/lab/scratch/2026-03/run_0319_base"}], [self.MARCH])
        planner.expand_groups(plan, fs)
        self.assertEqual(plan["items"]["the March runs"], ["run_0312_abl", "run_0319_base", "run_0327_abl"])
        self.assertIn({"type": "exists", "path": "/lab/scratch/2026-03/run_0327_abl"}, plan["effects"])
        self.assertIn({"type": "absent", "path": "/lab/scratch/run_0327_abl"}, plan["effects"])

    def test_match_all_pattern_is_ignored(self):
        plan = self.plan([], [dict(self.MARCH, pattern="*")])
        planner.expand_groups(plan, {"/lab/scratch/run_0312_abl": None})
        self.assertEqual(plan["effects"], [])

    def test_missed_march_run_is_reported_not_verified(self):
        # The November 1 failure: two of three runs moved, reported "Done and verified".
        moves = ("[cd(folder='scratch'), mkdir(dir_name='2026-03'), "
                 "mv(source='run_0312_abl', destination='2026-03'), "
                 "mv(source='run_0319_base', destination='2026-03')]")
        plan = self.plan([{"type": "exists", "path": "/lab/scratch/2026-03"}], [self.MARCH])
        case = self.lab_case(0)
        case["question"] = case["question"][:1]
        h = Scripted("t_march", agent.Config(**dict(agent.STEWARD, rollback=False)),
                     [moves, "", ""], [plan])
        _, meta = h.inference_multi_turn_prompting(case, False, True)
        report = meta["steward"]["reports"][0]
        self.assertEqual(report["verdict"], "partial")
        self.assertIn("run_0327_abl", report["text"])

    def test_unrequested_change_is_reported(self):
        before = {"GorillaFileSystem": {"/lab/a.txt": "x", "/lab/b.txt": "y", "/lab/arc": None}}
        after = {"GorillaFileSystem": {"/lab/arc": None, "/lab/arc/a.txt": "x", "/lab/arc/b.txt": "y"}}
        effects = [{"type": "exists", "path": "/lab/arc/a.txt"}]
        self.assertEqual(verifier.unexpected(effects, before, after), ["/lab/arc/b.txt", "/lab/b.txt"])

    def test_extra_message_is_reported(self):
        before = {"MessageAPI": {"inbox": []}}
        after = {"MessageAPI": {"inbox": [{"USR001": "a"}, {"USR002": "b"}]}}
        effects = [{"type": "message_sent", "text": "b"}]
        self.assertEqual(len(verifier.unexpected(effects, before, after)), 1)

    def test_message_is_held_after_a_failed_turn(self):
        case = self.lab_case(0)
        missing = self.plan([{"type": "exists", "path": "/lab/scratch/2026-03/run_0312_abl"}])
        notify = self.plan([{"type": "message_sent", "text": "March runs are now in scratch/2026-03."}])
        send = "[send_message(receiver_id='USR003', message='March runs are now in scratch/2026-03.')]"
        h = Scripted("t_hold", agent.Config(**dict(agent.STEWARD, rollback=False)),
                     ["", "", send, ""], [missing, notify])
        _, meta = h.inference_multi_turn_prompting(case, False, True)
        self.assertEqual(meta["steward"]["stats"].get("held_messages"), 1)
        self.assertEqual(meta["steward"]["reports"][0]["verdict"], "partial")
        self.assertFalse(any("MessageAPI.inbox" in c for c in meta["steward"]["reports"][1]["changes"]))


class IrreversibleWarning(unittest.TestCase):
    MOVE = "[cd(folder='scratch'), mv(source='config.yaml', destination='archive')]"

    def run_move(self, name, answer):
        from steward.dataset import d2
        case = next(e for e in d2()[0] if e["id"] == "multi_turn_labops_4")
        asked = []

        def confirm(call):
            asked.append(call)
            return answer

        h = Scripted(name, agent.Config(preflight=True, halt_batch=True, confirm_irreversible=confirm),
                     [self.MOVE, ""])
        _, meta = h.inference_multi_turn_prompting(case, False, True)
        return asked, meta

    def test_declined_move_into_a_folder_does_not_run(self):
        asked, meta = self.run_move("t_irr_no", False)
        self.assertEqual(asked, ["mv(source='config.yaml', destination='archive')"])
        self.assertEqual(meta["steward"]["stats"]["declined"], 1)
        self.assertEqual(meta["steward"]["reports"][0]["changes"], [])

    def test_approved_move_runs(self):
        asked, meta = self.run_move("t_irr_yes", True)
        self.assertEqual(len(asked), 1)
        self.assertIn("created /lab/scratch/archive/config.yaml", meta["steward"]["reports"][0]["changes"])

    def test_reversible_calls_are_not_questioned(self):
        from steward.dataset import d2
        case = next(e for e in d2()[0] if e["id"] == "multi_turn_labops_5")
        asked = []
        h = Scripted("t_irr_touch", agent.Config(preflight=True, confirm_irreversible=asked.append),
                     ["[cd(folder='scratch'), touch(file_name='STATUS.txt')]", ""])
        h.inference_multi_turn_prompting(case, False, True)
        self.assertEqual(asked, [])

    def test_plan_lists_moves_that_cannot_be_undone(self):
        plan = {"effects": [{"type": "absent", "path": "/lab/scratch/run_0312_abl"},
                            {"type": "exists", "path": "/lab/scratch/2026-03/run_0312_abl"},
                            {"type": "absent", "path": "/lab/scratch/notes.txt"},
                            {"type": "exists", "path": "/lab/scratch/notes_march.txt"}]}
        self.assertEqual(planner.irreversible(plan),
                         ["/lab/scratch/run_0312_abl -> /lab/scratch/2026-03/"])


class Reporting(unittest.TestCase):
    def test_read_only_turn_reports_no_change_not_review(self):
        from steward.dataset import d2
        case = next(e for e in d2()[0] if e["id"] == "multi_turn_labops_9")
        case["question"] = case["question"][:1]
        plan = {"clarify": None, "summary": [], "aliases": {}, "readings": {}, "groups": [], "effects": []}
        h = Scripted("t_ro", agent.Config(**dict(agent.STEWARD, rollback=False)),
                     ["[cd(folder='scratch'), wc(file_name='notes.txt', mode='l')]", "3 lines."], [plan])
        _, meta = h.inference_multi_turn_prompting(case, False, True)
        report = meta["steward"]["reports"][0]
        self.assertEqual(report["verdict"], "no_change")
        self.assertNotIn("review", report["text"])

    def test_disclosure_counts(self):
        from steward import stats
        rows = [{"id": "a", "passed": "0", "verdicts": "verified|unchecked"},
                {"id": "b", "passed": "0", "verdicts": "asked|verified"},
                {"id": "c", "passed": "1", "verdicts": "verified"}]
        claims = {"a": "discloses_problem", "b": "discloses_problem", "c": "claims_complete"}
        # Steward: a vague report on a failed case is still undisclosed; a question is disclosure.
        self.assertEqual(stats.disclosure(rows, claims, True), (0, 1))
        # Baselines have no verdicts, so the judge's label decides.
        self.assertEqual(stats.disclosure(rows, {"a": "claims_complete", "b": "no_report"}, False), (1, 2))


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
