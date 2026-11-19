"""Step 1 - the baseline: the same model with no tools and no loop.

The budget question is asked three times, untouched, and the two factual questions
are asked once each. Every answer is marked correct or incorrect, so the ReAct
agent that follows can be compared with the model on its own.

Live (needs ``LLM_MODEL`` and a provider key)::

    python baseline.py                       # writes evidence/baseline.md
    python baseline.py --print               # also echo each answer

Offline rehearsal, no key and no provider call::

    python baseline.py --scripted
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from scripted_model import make_model
from react_agent import DEFAULT_MODEL_FALLBACK, make_live_model

BARE_SYSTEM = (
    "You are a helpful assistant for a market trader in Accra, Ghana. "
    "Answer in two or three sentences."
)

# The question the whole lab is built around, and the two factual questions.
BUDGET_QUESTION = (
    "I have GHS 1,200. I want 4 bags of rice at GHS 185 each and 3 gallons of oil "
    "at GHS 95 each. How much will I have left?"
)
FACT_QUESTIONS = [
    ("What is the capital of the Bono East Region?", "techiman", "Techiman"),
    ("Which region of Ghana has Techiman as its capital?", "bono east", "Bono East"),
]

# Ground truth for the budget question, computed by the tool, not by hand.
BUDGET_ANSWER = 175
BUDGET_EXPRESSION = "1200 - (4*185 + 3*95)"

HEDGES = ("i think", "i believe", "probably", "perhaps", "not sure", "might be",
          "around", "about ", "roughly", "approximately")
NUMBER_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def numbers_in(text: str) -> list[float]:
    """Every number in a reply, with thousands separators removed."""
    found = []
    for raw in NUMBER_RE.findall(text or ""):
        try:
            found.append(float(raw.replace(",", "")))
        except ValueError:
            continue
    return found


def sounds_confident(text: str) -> str:
    """Classify the tone of an answer with a transparent word list.

    The manual asks whether a factual answer "sounds confident, whether or not it is
    right". This is a heuristic, not a judgement of truth: hedging words win.
    """
    lowered = (text or "").lower()
    return "hedged" if any(word in lowered for word in HEDGES) else "confident"


def collapse(text: str, limit: int = 260) -> str:
    """One table cell: no newlines, no pipes, and not too long."""
    flat = re.sub(r"\s+", " ", (text or "").strip()).replace("|", "\\|")
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "\u2026"


def ask(question: str, model_fn) -> str:
    """One plain completion: system prompt plus the question. No tools, no loop."""
    messages = [
        {"role": "system", "content": BARE_SYSTEM},
        {"role": "user", "content": question},
    ]
    try:
        text, _usage = model_fn(messages)
    except Exception as exc:  # noqa: BLE001 - the baseline must report a failure
        return f"[model call failed: {type(exc).__name__}: {exc}]"
    return (text or "").strip()


def collect(model_fn) -> list[dict]:
    """Run the five baseline questions and mark each answer."""
    rows = []
    for attempt in range(1, 4):
        answer = ask(BUDGET_QUESTION, model_fn)
        got = numbers_in(answer)
        correct = BUDGET_ANSWER in got or str(BUDGET_ANSWER) in answer
        rows.append(
            {
                "id": f"B{attempt}",
                "question": "Budget question (attempt %d)" % attempt,
                "answer": answer,
                "correct": correct,
                "because": (
                    "GHS 175 is in the answer"
                    if correct
                    else "GHS 175 does not appear (numbers found: %s)"
                    % (", ".join(f"{n:g}" for n in got) or "none")
                ),
                "tone": sounds_confident(answer),
            }
        )
    for index, (question, needle, label) in enumerate(FACT_QUESTIONS, start=1):
        answer = ask(question, model_fn)
        correct = needle in answer.lower()
        rows.append(
            {
                "id": f"F{index}",
                "question": question,
                "answer": answer,
                "correct": correct,
                "because": (
                    f"mentions {label}" if correct else f"does not mention {label}"
                ),
                "tone": sounds_confident(answer),
            }
        )
    return rows


def render(rows: list[dict], *, source: str, model_name: str) -> str:
    """The markdown baseline record saved as ``evidence/baseline.md``."""
    budget = [r for r in rows if r["id"].startswith("B")]
    facts = [r for r in rows if r["id"].startswith("F")]
    budget_ok = sum(1 for r in budget if r["correct"])
    facts_ok = sum(1 for r in facts if r["correct"])

    if source == "scripted":
        banner = (
            "> **REHEARSAL RUN - NOT SUBMITTABLE.** These answers are replayed from\n"
            "> `scripted_model.py`, a deterministic stand-in, because this machine has\n"
            "> no `LLM_MODEL` key. Re-run `python run_evidence.py` in the Codespace to\n"
            "> replace this file with real model output before you submit.\n"
        )
    else:
        banner = (
            f"> Live run against `{model_name}`, temperature 0.7, no tools, through the "
            f"lab's model call (LiteLLM in the Codespace; `groq_client.py` only where "
            f"LiteLLM cannot be installed).\n"
        )

    lines = [
        "# Lab 2 Step 1 - Baseline: the model on its own",
        "",
        banner,
        f"Recorded: {datetime.now(timezone.utc).isoformat(timespec='seconds')}  ",
        f"Model source: **{source}**  ",
        f"Questions asked: 3 x budget, {len(facts)} x factual, no tools, no loop.",
        "",
        "The budget question was asked three times without any tools. The correct",
        "answer is GHS 175 (`%s`, computed by `tools.calculator`)." % BUDGET_EXPRESSION,
        "",
        "| # | Question | Answer | Marked | Why | Tone |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        mark = "correct" if row["correct"] else "**incorrect**"
        lines.append(
            f"| {row['id']} | {row['question']} | {collapse(row['answer'])} | "
            f"{mark} | {row['because']} | {row['tone']} |"
        )
    lines += [
        "",
        f"**Totals.** Budget question: {budget_ok}/{len(budget)} correct. "
        f"Factual questions: {facts_ok}/{len(facts)} correct.",
        "",
        "Tone is a word-list heuristic (hedges such as \"I think\", \"about\", "
        "\"roughly\" count as hedged), not a judgement of truth.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lab 2 Step 1 baseline, no tools.")
    parser.add_argument(
        "--scripted", action="store_true",
        help="rehearse offline with scripted replies instead of calling a model",
    )
    parser.add_argument("--model", help="LiteLLM model name (default: $LLM_MODEL)")
    parser.add_argument(
        "--out", default="evidence/baseline.md", help="where to write the record"
    )
    parser.add_argument("--print", dest="echo", action="store_true", help="echo answers")
    args = parser.parse_args(argv)

    if args.scripted:
        # One replay per question, in the order the questions are asked, so the
        # three budget attempts get the three scripted budget answers in turn.
        order = [
            "baseline_budget",
            "baseline_budget",
            "baseline_budget",
            "baseline_fact_capital",
            "baseline_fact_techiman",
        ]
        replays = {name: make_model(name) for name in set(order)}
        state = {"i": 0}

        def model_fn(messages):
            name = order[min(state["i"], len(order) - 1)]
            state["i"] += 1
            return replays[name](messages)

        source, model_name = "scripted", "scripted_model.py"
    else:
        model_fn = make_live_model(args.model, temperature=0.7, stop=[])
        source = "live"
        model_name = getattr(model_fn, "model_name", "") or DEFAULT_MODEL_FALLBACK

    rows = collect(model_fn)
    if args.echo:
        for row in rows:
            print(f"\n[{row['id']}] {row['question']}\n{row['answer']}\n"
                  f"-> {'correct' if row['correct'] else 'incorrect'} ({row['because']})")

    text = render(rows, source=source, model_name=model_name)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    print(text)
    print(f"[saved] {out}")
    if source == "scripted":
        print(
            "NOTE: rehearsal only. Run this again in the Codespace with LLM_MODEL "
            "set to record the real baseline.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
