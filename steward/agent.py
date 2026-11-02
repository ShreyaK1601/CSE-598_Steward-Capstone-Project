"""Agent loop as a BFCL model handler, plus the reliable endpoint layer all systems share.

BFCL scores a run by replaying the logged calls, so the logged steps here contain exactly
the calls that executed. Blocked and skipped calls are never logged; rollback calls are.
"""

import json
import time
from copy import deepcopy
from dataclasses import dataclass
from typing import Callable, Optional

from steward import bfcl_env  # noqa: F401
from bfcl_eval.constants.default_prompts import (
    DEFAULT_USER_PROMPT_FOR_ADDITIONAL_FUNCTION_PROMPTING,
    MAXIMUM_STEP_LIMIT,
)
from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_utils import (
    execute_multi_turn_func_call,
    is_empty_execute_response,
)
from bfcl_eval.model_handler.api_inference.qwen import QwenAPIHandler

from steward import planner, probes, specs, triage, verifier

MODEL = "qwen3-235b-a22b-instruct-2507"
MAX_ATTEMPTS = 7


class ReliableHandler(QwenAPIHandler):
    """Stock Qwen handler with real retries and a per-repeat seed, used by every system."""

    def __init__(self, run_name, seed=None):
        super().__init__(MODEL, 0.001, MODEL, False)
        self.model_name_underline_replaced = run_name
        self.seed = seed
        self.endpoint_retries = 0

    def _with_retries(self, fn):
        for attempt in range(MAX_ATTEMPTS):
            try:
                return fn()
            except Exception:
                if attempt == MAX_ATTEMPTS - 1:
                    raise
                self.endpoint_retries += 1
                time.sleep(min(2 ** attempt * 3, 90))

    def _query_prompting(self, inference_data):
        inference_data["inference_input_log"] = {"message": repr(inference_data["message"])}
        extra = {"seed": self.seed} if self.seed is not None else {}

        def call():
            response, _ = self.generate_with_backoff(
                messages=inference_data["message"], model=self.model_name, stream=True,
                stream_options={"include_usage": True}, **extra,
            )
            # Read the whole stream here so a dropped connection is retried as well.
            started = time.time()
            return list(response), time.time() - started

        started = time.time()
        chunks, _ = self._with_retries(call)
        return chunks, time.time() - started


@dataclass
class Config:
    state_brief: bool = False
    preflight: bool = False
    halt_batch: bool = False
    triage: bool = False
    plan: bool = False
    clarify: bool = False
    verify: bool = False
    rollback: bool = False
    empty_reprompt: bool = False
    naive_retry: int = 0
    approve: Optional[Callable] = None
    on_event: Optional[Callable] = None


STEWARD = dict(state_brief=True, preflight=True, halt_batch=True, triage=True, plan=True,
               clarify=True, verify=True, rollback=True, empty_reprompt=True)


class StewardHandler(ReliableHandler):
    """Observe-act loop with preflight, journal, triage, verification and rollback."""

    def __init__(self, run_name, config, seed=None):
        super().__init__(run_name, seed)
        self.cfg = config

    def emit(self, kind, **data):
        if self.cfg.on_event:
            self.cfg.on_event(kind, data)

    def _execute(self, calls, ctx):
        return execute_multi_turn_func_call(
            calls, ctx["config"], ctx["classes"], self.model_name_underline_replaced,
            ctx["id"], long_context=ctx["long_context"], is_evaL_run=False,
        )

    def _plan(self, entry, history, aliases, instances, request, stats):
        tools = [f["name"] for f in entry["function"]]
        prompt = planner.plan_prompt(history, aliases, probes.brief(instances), tools, request)
        stats["probes"] += 1

        def call():
            response = self.client.chat.completions.create(
                model=self.model_name, temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            return response

        response = self._with_retries(call)
        if response.usage:
            stats["planner_input_tokens"] += response.usage.prompt_tokens
            stats["planner_output_tokens"] += response.usage.completion_tokens
        return planner.parse_plan(response.choices[0].message.content)

    def _run_batch(self, calls, instances_ctx, turn_text, journal, created, stats):
        """Run one model step. Returns (results, executed calls, instances)."""
        results, executed = [], []
        instances = instances_ctx["instances"]
        halted = False
        for call in calls:
            if halted:
                results.append("Skipped: an earlier call in this step failed. "
                               "Re-issue this call if it is still needed.")
                stats["skipped"] += 1
                continue
            name, args, owner = specs.parse_call(call, instances)
            if self.cfg.preflight and name:
                stats["probes"] += 1
                reason = specs.preflight(name, args, owner, instances, turn_text, created)
                if reason:
                    stats["blocked"] += 1
                    self.emit("blocked", call=call, reason=reason)
                    results.append(json.dumps({"error": f"Preflight blocked, not executed: {reason}"}))
                    halted = self.cfg.halt_batch
                    continue
            undo, new_name = (None, None)
            if name in specs.MUTATING and args is not None:
                try:
                    undo, new_name = specs.inverse(name, args, instances)
                except (KeyError, TypeError):
                    undo, new_name = None, None
            at = probes.cwd(instances)
            output, instances = self._execute([call], instances_ctx)
            instances_ctx["instances"] = instances
            result = output[0]
            executed.append(call)
            failed = triage.is_error(result)
            self.emit("tool", call=call, result=result)
            if failed:
                stats["tool_errors"] += 1
                if self.cfg.triage:
                    kind, repair = triage.classify(result)
                    stats["triage"][kind] = stats["triage"].get(kind, 0) + 1
                    result = f"{result} [{kind} error. {repair}]"
                halted = self.cfg.halt_batch
            elif name in specs.MUTATING:
                journal.append({"call": call, "cwd": at, "undo": undo,
                                "provenance": "created" if new_name else "pre-existing"})
                if new_name:
                    created.add(new_name)
            results.append(result)
        return results, executed

    def _rollback(self, journal, ctx, start_cwd):
        """Undo this turn's journal in reverse. Returns (executed calls, entries with no inverse)."""
        executed, stuck = [], []

        def go(target):
            here = probes.cwd(ctx["instances"]).strip("/").split("/")
            there = target.strip("/").split("/")
            common = 0
            while common < min(len(here), len(there)) and here[common] == there[common]:
                common += 1
            moves = ["cd(folder='..')"] * (len(here) - common)
            moves += [f"cd(folder={p!r})" for p in there[common:]]
            if moves:
                self._execute(moves, ctx)
                executed.extend(moves)

        for entry in reversed(journal):
            if not entry["undo"]:
                stuck.append(entry["call"])
                continue
            if entry["cwd"]:
                go(entry["cwd"])
            self._execute(entry["undo"], ctx)
            executed.extend(entry["undo"])
        if start_cwd:
            go(start_cwd)
        return executed, stuck

    def inference_multi_turn_prompting(self, test_entry, include_input_log, exclude_state_log):
        cfg = self.cfg
        holdout = test_entry.get("missed_function", {})
        category = test_entry["id"].rsplit("_", 1)[0]
        ctx = {
            "config": test_entry.get("initial_config", {}),
            "classes": test_entry["involved_classes"],
            "id": test_entry["id"],
            "long_context": "long_context" in category,
        }
        _, ctx["instances"] = self._execute([], ctx)

        stats = {"probes": 0, "blocked": 0, "skipped": 0, "tool_errors": 0, "triage": {},
                 "planner_input_tokens": 0, "planner_output_tokens": 0, "repairs": 0,
                 "reprompts": 0, "rollbacks": 0}
        input_tokens, output_tokens, latency, all_response, all_log = [], [], [], [], []
        reports, history, aliases, created = [], [], {}, set()
        carry_note = ""
        force_quit = False

        inference_data = self._pre_query_processing_prompting(test_entry)

        for turn_idx, message in enumerate(test_entry["question"]):
            if str(turn_idx) in holdout:
                message = [{"role": "user",
                            "content": DEFAULT_USER_PROMPT_FOR_ADDITIONAL_FUNCTION_PROMPTING.format(
                                functions=holdout[str(turn_idx)])}]
            message = deepcopy(message)
            request = " ".join(m["content"] for m in message if m["role"] == "user")
            before = probes.snapshot(ctx["instances"])
            start_cwd = probes.cwd(ctx["instances"])
            turn_response, turn_in, turn_out, turn_latency = [], [], [], []
            turn_log = {"begin_of_turn_query": message}
            journal = []
            plan = None
            all_response.append(turn_response)
            input_tokens.append(turn_in)
            output_tokens.append(turn_out)
            latency.append(turn_latency)
            all_log.append(turn_log)

            if cfg.plan and str(turn_idx) not in holdout:
                plan = self._plan(test_entry, history, aliases, ctx["instances"], request, stats)
                proposed = len(plan["effects"])
                plan["effects"] = verifier.grounded(
                    plan["effects"], " ".join(history + [request]),
                    probes.snapshot(ctx["instances"]).get("GorillaFileSystem", {}))
                plan["effects_dropped"] = proposed - len(plan["effects"])
                aliases.update(plan["aliases"])
                turn_log["plan"] = plan
                self.emit("plan", plan=plan)

            history.append(request)

            if plan and cfg.approve and not plan["clarify"] and not cfg.approve(plan):
                reports.append({"turn": turn_idx, "verdict": "not_approved", "changes": [],
                                "text": "Plan not approved. Nothing was changed."})
                self.emit("report", report=reports[-1])
                continue

            if plan and plan["clarify"] and cfg.clarify:
                question = plan["clarify"]
                inference_data["message"].extend(message)
                inference_data["message"].append({"role": "assistant", "content": question})
                # Plain text is ignored by the evaluator's decoder, so no call is recorded.
                turn_response.append(question)
                reports.append({"turn": turn_idx, "verdict": "asked", "changes": [],
                                "text": f"Nothing changed. Question for you: {question}"})
                self.emit("report", report=reports[-1])
                continue

            if cfg.state_brief:
                note = "\n\n[Current state, read just now]\n" + probes.brief(ctx["instances"])
                if carry_note:
                    note += "\n" + carry_note
                if aliases:
                    note += f"\nKnown aliases: {json.dumps(aliases)}"
                if plan and plan["summary"]:
                    note += "\nPlan: " + " ".join(plan["summary"])
                stats["probes"] += 1
                message[-1]["content"] += note
            carry_note = ""
            inference_data["message"].extend(message)

            step, repaired, reprompted, retries, turn_calls = 0, False, False, 0, 0
            last_failed = False
            while True:
                step_log = []
                turn_log[f"step_{step}"] = step_log
                api_response, query_latency = self._query_prompting(inference_data)
                data = self._parse_query_response_prompting(api_response)
                raw = data["model_responses"]
                inference_data = self._add_assistant_message_prompting(inference_data, data)
                turn_in.append(data["input_token"])
                turn_out.append(data["output_token"])
                turn_latency.append(query_latency)
                step_log.append({"role": "assistant", "content": raw})

                try:
                    calls = self.decode_execute(raw, has_tool_call_tag=False)
                    if is_empty_execute_response(calls):
                        calls = None
                except Exception:
                    calls = None

                if calls is None:
                    turn_response.append(raw)
                    # The model has stopped. Decide whether the turn is really over.
                    if cfg.naive_retry and last_failed and retries < cfg.naive_retry:
                        retries += 1
                        last_failed = False
                        inference_data["message"].append(
                            {"role": "user", "content": "The last call failed. Try again."})
                        step += 1
                        continue
                    wants_change = bool(plan and plan["effects"])
                    if cfg.empty_reprompt and not turn_calls and wants_change and not reprompted:
                        reprompted = True
                        stats["reprompts"] += 1
                        inference_data["message"].append({"role": "user", "content": (
                            "No function was called, but the request needs action. Current state:\n"
                            + probes.brief(ctx["instances"]))})
                        step += 1
                        continue
                    if cfg.verify and plan:
                        stats["probes"] += 1
                        unmet, _ = verifier.verify(plan["effects"], probes.snapshot(ctx["instances"]))
                        if unmet and not repaired:
                            repaired = True
                            stats["repairs"] += 1
                            self.emit("verify", unmet=unmet)
                            step_log.append({"role": "handler_log", "content": f"verifier unmet: {unmet}"})
                            inference_data["message"].append({"role": "user", "content": (
                                f"Verification found these expected effects unmet: {json.dumps(unmet)}. "
                                "Current state:\n" + probes.brief(ctx["instances"]) +
                                "\nCall the functions needed to fix this. If the request is in fact "
                                "complete, return no function call.")})
                            step += 1
                            continue
                    break

                data["model_responses_decoded"] = calls
                results, executed = self._run_batch(
                    calls, ctx, request, journal, created, stats)
                turn_calls += len(executed)
                turn_response.append("[" + ", ".join(executed) + "]" if executed else "")
                step_log.append({"role": "handler_log", "content": "decoded",
                                 "model_response_decoded": calls, "executed": executed})
                for result in results:
                    step_log.append({"role": "tool", "content": result})
                for call, result in zip(executed, results):
                    history.append(f"called {call}, result: {str(result)[:300]}")
                last_failed = any(triage.is_error(r.split(" [")[0]) for r in results)
                if cfg.naive_retry and last_failed and retries < cfg.naive_retry:
                    retries += 1
                    results = results[:-1] + [results[-1] + " Try again."]
                inference_data = self._add_execution_results_prompting(inference_data, results, data)

                step += 1
                if step > MAXIMUM_STEP_LIMIT:
                    force_quit = True
                    step_log.append({"role": "handler_log",
                                     "content": f"Forced to quit after {MAXIMUM_STEP_LIMIT} steps."})
                    break

            after = probes.snapshot(ctx["instances"])
            report = self._finish_turn(plan, journal, ctx, start_cwd, before, after, turn_idx,
                                       turn_response, stats)
            if report["verdict"] in ("rolled_back", "partial"):
                carry_note = f"Note: the previous turn did not complete. {report['text']}"
            reports.append(report)
            turn_log["report"] = report
            self.emit("report", report=report)
            if force_quit:
                break

        metadata = {
            "input_token_count": input_tokens,
            "output_token_count": output_tokens,
            "latency": latency,
            "inference_log": all_log,
            "steward": {"stats": stats, "reports": reports,
                        "journal_created": sorted(created),
                        "endpoint_retries": self.endpoint_retries},
        }
        return all_response, metadata

    def _finish_turn(self, plan, journal, ctx, start_cwd, before, after, turn_idx, turn_response, stats):
        """Decide the verdict, roll back if needed, and report what actually changed."""
        cfg = self.cfg
        if not (cfg.verify and plan):
            return {"turn": turn_idx, "verdict": "unverified",
                    "changes": probes.diff(before, after), "text": ""}
        unmet, checked = verifier.verify(plan["effects"], after)
        stuck = []
        verdict = "verified" if checked and not unmet else "unverified"
        if unmet:
            verdict = "partial"
            if cfg.rollback and journal:
                undone, stuck = self._rollback(journal, ctx, start_cwd)
                if undone:
                    stats["rollbacks"] += 1
                    turn_response.append("[" + ", ".join(undone) + "]")
                    verdict = "rolled_back"
                    self.emit("rollback", calls=undone, stuck=stuck)
            after = probes.snapshot(ctx["instances"])
        changes = probes.diff(before, after)
        parts = {
            "verified": f"Done and verified ({checked} expected effects checked).",
            "unverified": "Finished, but no expected effect could be checked; please review.",
            "partial": f"NOT complete. Unmet: {json.dumps(unmet)}.",
            "rolled_back": f"NOT complete. Unmet: {json.dumps(unmet)}. This turn's changes were undone.",
        }
        text = parts[verdict]
        if stuck:
            text += f" Could not undo: {stuck}."
        text += " Changes: " + ("; ".join(changes) if changes else "none") + "."
        return {"turn": turn_idx, "verdict": verdict, "changes": changes, "text": text,
                "unmet": unmet, "stuck": stuck}


def make_handler(system, run_name, seed=None):
    if system == "b0":
        return ReliableHandler(run_name, seed)
    if system == "steward":
        return StewardHandler(run_name, Config(**STEWARD), seed)
    if system == "steward_norollback":
        return StewardHandler(run_name, Config(**dict(STEWARD, rollback=False)), seed)
    if system == "guard_only":
        return StewardHandler(run_name, Config(preflight=True, halt_batch=True, triage=True), seed)
    raise ValueError(f"unknown system {system}")
