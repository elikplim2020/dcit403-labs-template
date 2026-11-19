"""One command that produces the whole ``evidence/`` folder for Lab 2.

It runs Step 1 (baseline), the six evidence questions from Step 5 and the three
robustness drills, then writes an index (``evidence/RUN_LOG.md``) and prints the
numbers the report needs.

In the Codespace, with the course keys set::

    python run_evidence.py

On a machine with no key (rehearsal only, every file is stamped as rehearsal)::

    python run_evidence.py --scripted
"""

from __future__ import annotations

import argparse
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import baseline
from react_agent import (
    DEFAULT_MODEL_FALLBACK,
    DRILL_QUESTIONS,
    EVIDENCE_QUESTIONS,
    format_trace,
    make_live_model,
    run_agent,
    save_trace,
)
from scripted_model import make_model

DEFAULT_OUT = Path("evidence")


def load_dotenv(path: str = ".env") -> None:
    """Load KEY=VALUE lines from ``.env`` without adding a dependency.

    Existing environment variables win, so a Codespaces secret is never replaced by
    a stale ``.env`` copied from another machine.
    """
    env_file = Path(path)
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value:
            os.environ.setdefault(key, value)


def baseline_rows(model_fn, mode: str):
    """Run Step 1 with the baseline's own prompts (no tools, temperature 0.7)."""
    if mode == "scripted":
        order = [
            "baseline_budget",
            "baseline_budget",
            "baseline_budget",
            "baseline_fact_capital",
            "baseline_fact_techiman",
        ]
        replays = {name: make_model(name) for name in set(order)}
        state = {"i": 0}

        def replay(messages):
            name = order[min(state["i"], len(order) - 1)]
            state["i"] += 1
            return replays[name](messages)

        return baseline.collect(replay)
    return baseline.collect(make_live_model(temperature=0.7, stop=[]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the whole Lab 2 evidence set and write evidence/."
    )
    parser.add_argument(
        "--scripted", action="store_true",
        help="rehearse offline: replay scripted replies instead of calling a model",
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="evidence folder")
    parser.add_argument(
        "--pause", type=float, default=3.0,
        help="seconds between live runs, to stay inside the free-tier limit",
    )
    parser.add_argument("--model", help="LiteLLM model name (default: $LLM_MODEL)")
    parser.add_argument("--skip-baseline", action="store_true")
    args = parser.parse_args(argv)

    load_dotenv()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    mode = "scripted" if args.scripted else "live"
    if mode == "live" and not os.getenv("LLM_MODEL"):
        parser.error(
            "LLM_MODEL is not set. Export it (and its key), or run with --scripted "
            "for an offline rehearsal."
        )
    model_name = args.model or os.getenv("LLM_MODEL") or DEFAULT_MODEL_FALLBACK
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"Lab 2 evidence run | mode: {mode} | model: {model_name} | {stamp}\n")

    # ---- Step 1: baseline -------------------------------------------------- #
    baseline_file = out_dir / "baseline.md"
    rows = []
    if not args.skip_baseline:
        print(f"[1/3] baseline (5 questions, no tools) ...")
        rows = baseline_rows(None, mode)
        baseline_file.write_text(
            baseline.render(rows, source=mode, model_name=model_name) + "\n",
            encoding="utf-8",
        )
        budget_ok = sum(1 for r in rows if r["id"].startswith("B") and r["correct"])
        print(f"      budget question: {budget_ok}/3 correct -> {baseline_file}")

    # ---- Steps 3 to 5: the six questions plus the drills ------------------- #
    cases = list(EVIDENCE_QUESTIONS) + list(DRILL_QUESTIONS)
    records = []
    for index, case in enumerate(cases, start=1):
        case_id, scenario, question, max_steps = case
        print(f"[{index + 1}/{len(cases) + 1}] {case_id} ...")
        if mode == "scripted":
            model_fn, source, scen = make_model(scenario), "scripted", scenario
        else:
            model_fn, source, scen = make_live_model(args.model), "live", None
            if args.pause and index > 1:
                time.sleep(args.pause)
        run = run_agent(
            question,
            max_steps=max_steps,
            model_fn=model_fn,
            model_name=model_name,
            source=source,
            scenario=scen,
            echo=False,
        )
        path = save_trace(run, out_dir / f"trace_{case_id}.txt")
        print(f"      {run.status}, {run.steps} steps, tools: {run.tools_used()} -> {path}")
        records.append({"case": case_id, "run": run, "file": path.name})

    # ---- The index -------------------------------------------------------- #
    ok = sum(1 for record in records if record["run"].status == "finished")
    lines = [
        "# Lab 2 evidence index",
        "",
        f"Run: {stamp}  ",
        f"Mode: **{mode}**  ",
        f"Model: `{model_name}`  ",
        f"Traces: {len(records)} ({ok} finished with a final answer)  ",
    ]
    if mode == "scripted":
        lines += [
            "",
            "> **REHEARSAL RUN.** These traces replay `scripted_model.py`, so they show",
            "> the loop, the parser and the tools working, but the model text is not",
            "> provider output. Run `python run_evidence.py` with the course keys before",
            "> you submit, and the files in this folder are replaced with live traces.",
        ]
    lines += [
        "",
        "| Trace | Question | Status | Steps | Tools | Tokens | File |",
        "|---|---|---|---|---|---|---|",
    ]
    for record in records:
        run = record["run"]
        question = run.question.replace("|", "\\|")
        lines.append(
            f"| {record['case']} | {question} | {run.status} | {run.steps}/{run.max_steps} | "
            f"{run.tools_used()} | {run.tokens['prompt'] + run.tokens['completion']} | "
            f"[{record['file']}]({record['file']}) |"
        )
    lines += [
        "",
        "Step 1 baseline: [baseline.md](baseline.md)",
        "",
        "Status meanings: `finished` = the agent produced a final answer; "
        "`max_steps` = the step limit stopped it (drill 8, on purpose).",
        "",
    ]
    (out_dir / "RUN_LOG.md").write_text("\n".join(lines), encoding="utf-8")

    # ---- Report numbers --------------------------------------------------- #
    total_tokens = sum(
        record["run"].tokens["prompt"] + record["run"].tokens["completion"]
        for record in records
    )
    budget_ok = sum(1 for r in rows if r["id"].startswith("B") and r["correct"])
    six_ids = {case[0] for case in EVIDENCE_QUESTIONS}
    six = [record for record in records if record["case"] in six_ids]
    six_ok = sum(1 for record in six if record["run"].status == "finished")
    print("\n" + "=" * 60)
    print("REPORT NUMBERS" + ("  (REHEARSAL - not reportable)" if mode == "scripted" else ""))
    print("=" * 60)
    if rows:
        print(f"Baseline, budget question : {budget_ok}/3 correct")
        print(f"Baseline, factual         : "
              f"{sum(1 for r in rows if r['id'].startswith('F') and r['correct'])}/2 correct")
    print(f"ReAct, six questions      : {six_ok}/{len(six)} finished")
    print(f"Total tokens in traces    : {total_tokens}")
    print(f"Evidence folder           : {out_dir.resolve()}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
