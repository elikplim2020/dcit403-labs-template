"""Lab 2 - a ReAct agent built from scratch, with no framework.

The agent is a loop, not a model call. Each turn the model writes a Thought, an
Action and an Action Input; this file parses that text, runs the tool, appends the
result as an Observation and calls the model again, until the action is ``finish``
or the step limit is reached.

Run it against the real model (needs ``LLM_MODEL`` and a key)::

    python react_agent.py --question "I have GHS 1,200. I want 4 bags of rice at GHS 185 each and 3 gallons of oil at GHS 95 each. How much will I have left?"

Rehearse offline, with no key and no network calls to a provider::

    python react_agent.py --scenario budget

Run the six evidence questions and save every trace::

    python react_agent.py --all --save-dir evidence

See also ``run_evidence.py``, which produces the whole evidence folder.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from scripted_model import make_model, scenarios
from tools import TOOLS, run_tool

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

DEFAULT_MODEL_FALLBACK = "groq/openai/gpt-oss-20b"  # used when LLM_MODEL is unset
DEFAULT_MAX_STEPS = 6
REPEAT_LIMIT = 2  # the same call allowed twice; the third time it is intercepted
STOP = ["Observation:"]  # the model may not write its own observations
TEMPERATURE = 0.0

SYSTEM_PROMPT = """You answer questions for a trader at Makola Market in Accra, Ghana.

You work in steps. On every step you write exactly three lines, in this order, and nothing else:

Thought: <one sentence of reasoning about the question or the observation you have just received>
Action: <one of: calculator, wiki_lookup, finish>
Action Input: <one line of text for the tool, or the final answer if Action is finish>

Tools you can use:
- calculator: evaluates one arithmetic expression, for example 4*185 + 3*95. Use it for every calculation. Never do arithmetic yourself.
- wiki_lookup: returns the Wikipedia summary for a title, for example Bono East Region. Use it for facts about places, people and organisations.
- finish: ends the task. Action Input is the final answer to the trader, in plain words.

Rules:
- Write one Thought, one Action and one Action Input per step. Never write an Observation yourself: it is supplied to you.
- Use a tool instead of guessing. If a tool returns an error or no page, say plainly what you could not find.
- Keep the final answer short: two or three sentences.
- If the question is badly worded, say in your Thought how you read it, then answer that.
"""

# The parser from the manual: action name, then a new line, then action input.
ACTION_RE = re.compile(r"Action:\s*(\w+)\s*\nAction Input:\s*(.*)", re.DOTALL)

# Sent back when a reply carries no usable Action line.
CORRECTIVE_FORMAT = (
    "I could not read your last reply as a step. Reply with exactly these three "
    "lines and nothing else:\n"
    "Thought: <your reasoning>\n"
    "Action: <calculator | wiki_lookup | finish>\n"
    "Action Input: <one line>"
)

# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #

# A model often numbers its steps ("1. Thought:", "2. Action:") or bullet-points
# them. The numbering sits between the labels and breaks the canonical regex.
_ENUMERATOR = re.compile(
    r"(?im)^[ \t]*(?:\d+[.)]|[-*\u2022])[ \t]*(?=(?:thought|action(?:\s+input)?|observation)\s*:)"
)

_LABEL_NORMALISERS = (
    (re.compile(r"(?i)\bthought\s*:"), "Thought:"),
    (re.compile(r"(?i)\baction\s+input\s*:"), "Action Input:"),
    (re.compile(r"(?i)\baction\s*:"), "Action:"),
    (re.compile(r"(?i)\bobservation\s*:"), "Observation:"),
)


def normalise_labels(text: str) -> str:
    """Make label spelling and decoration uniform before parsing.

    Models decorate labels: ``**Action:** calculator``, ```Action:``, ``ACTION :
    calculator``, ``2. Action:``, ``Action Input:`` with a double space. The
    canonical regex rejects all of those, so the decoration is removed here instead
    of widening the regex that the lab asks us to write.
    """
    text = text.replace("\r\n", "\n").replace("**", "").replace("`", "")
    text = _ENUMERATOR.sub("", text)
    for pattern, replacement in _LABEL_NORMALISERS:
        text = pattern.sub(replacement, text)
    return text


def parse(text: str) -> tuple[str | None, str | None]:
    """Return ``(action, action_input)`` from one model reply.

    ``(None, None)`` means the reply cannot be used: the loop then sends a
    corrective observation rather than raising. Any ``Observation:`` the model
    wrote anyway is cut, because observations belong to the code.
    """
    if not isinstance(text, str) or not text.strip():
        return None, None
    match = ACTION_RE.search(normalise_labels(text))
    if not match:
        return None, None
    action = match.group(1).strip()
    payload = match.group(2).strip()
    payload = re.split(r"(?i)\bObservation\s*:", payload, maxsplit=1)[0].strip()
    payload = payload.strip().strip("`").strip()
    return action, payload


# --------------------------------------------------------------------------- #
# Model call
# --------------------------------------------------------------------------- #

def _usage_counts(usage) -> tuple[int, int]:
    """Read prompt and completion token counts from a LiteLLM usage object or dict."""
    if usage is None:
        return 0, 0
    get = usage.get if isinstance(usage, dict) else lambda k, d=None: getattr(usage, k, d)
    return int(get("prompt_tokens", 0) or 0), int(get("completion_tokens", 0) or 0)


def _as_counts(usage) -> tuple[int, int]:
    """Accept either a ``(prompt, completion)`` pair or a LiteLLM usage object."""
    if isinstance(usage, tuple) and len(usage) == 2:
        return int(usage[0]), int(usage[1])
    return _usage_counts(usage)


def make_litellm_model(
    model: str = "",
    *,
    verbose: bool = False,
    temperature: float = TEMPERATURE,
    stop: list[str] | None = None,
):
    """Return a ``model_fn`` that calls LiteLLM, with a retry on rate limits.

    ``stop`` defaults to ``["Observation:"]``, which is what the ReAct loop needs.
    The Step 1 baseline passes ``stop=None`` and a higher temperature, because it
    must behave like a plain chat completion.
    """
    import os

    model_name = model or os.getenv("LLM_MODEL") or DEFAULT_MODEL_FALLBACK
    from litellm import completion  # imported late so the module imports without it
    stop_sequences = STOP if stop is None else stop

    def model_fn(messages):
        last_error = None
        for attempt in range(3):
            try:
                kwargs = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": temperature,
                }
                if stop_sequences:
                    kwargs["stop"] = stop_sequences
                response = completion(**kwargs)
                text = response.choices[0].message.content or ""
                usage = _usage_counts(getattr(response, "usage", None))
                if verbose:
                    print(f"    [live:{model_name}] {usage[0]}+{usage[1]} tokens")
                return text, usage
            except Exception as exc:  # noqa: BLE001 - retry limits, surface the rest
                last_error = exc
                message = str(exc)
                retryable = "429" in message or "RateLimit" in type(exc).__name__
                if not retryable or attempt == 2:
                    raise
                pause = 2 ** (attempt + 1)  # 2 s, then 4 s
                print(f"    [rate limit] waiting {pause}s and retrying", file=sys.stderr)
                time.sleep(pause)
        raise last_error  # pragma: no cover - the loop above always returns or raises

    model_fn.model_name = model_name  # type: ignore[attr-defined]
    return model_fn


def make_live_model(
    model: str = "", *, verbose: bool = False, temperature: float = TEMPERATURE,
    stop: list[str] | None = None,
):
    """Return the best available live model function.

    LiteLLM is the course path (``requirements.txt`` installs it). On a machine
    without LiteLLM, the small Groq client in ``groq_client.py`` speaks the same
    interface, so the loop, parser and tools are unchanged.
    """
    try:
        import litellm  # noqa: F401
    except ImportError:
        from groq_client import make_groq_model

        return make_groq_model(
            model, verbose=verbose, temperature=temperature, stop=stop
        )
    return make_litellm_model(
        model, verbose=verbose, temperature=temperature, stop=stop
    )


# --------------------------------------------------------------------------- #
# The loop
# --------------------------------------------------------------------------- #

@dataclass
class Run:
    """One complete run of the agent, and everything needed to print or save it."""

    question: str
    answer: str = ""
    status: str = "running"  # finished | max_steps | model_error
    scenario: str | None = None
    model_name: str = ""
    source: str = "live"  # live | scripted
    max_steps: int = DEFAULT_MAX_STEPS
    started: str = ""
    elapsed_s: float = 0.0
    events: list[dict] = field(default_factory=list)
    tool_counts: Counter = field(default_factory=Counter)
    tokens: Counter = field(default_factory=Counter)

    @property
    def steps(self) -> int:
        """Number of model turns used."""
        return sum(1 for event in self.events if event["type"] == "assistant")

    def tools_used(self) -> str:
        if not self.tool_counts:
            return "none"
        return ", ".join(f"{name}({n})" for name, n in sorted(self.tool_counts.items()))


def run_agent(
    question: str,
    *,
    max_steps: int = DEFAULT_MAX_STEPS,
    model_fn=None,
    model_name: str = "",
    source: str = "live",
    scenario: str | None = None,
    echo: bool = True,
) -> Run:
    """Run the ReAct loop for one question and return the full run.

    Failures are handled, never raised, so that one bad reply cannot end the run:

    * a reply with no usable Action line   -> corrective observation, next step
    * an unknown tool name                 -> corrective observation, next step
    * ``finish`` with an empty answer      -> corrective observation, next step
    * the same call three times            -> corrective observation, next step
    * ``max_steps`` reached                -> the run stops with a plain message
    * the model call itself failing        -> the run stops with a plain message
    """
    run = Run(
        question=question,
        max_steps=max_steps,
        model_name=model_name,
        scenario=scenario,
        source=source,
        started=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    call_counts: Counter = Counter()
    started = time.perf_counter()

    def observe(text: str, *, tool: str | None = None, ms: float | None = None) -> None:
        run.events.append({"type": "observation", "text": text, "tool": tool, "ms": ms})
        messages.append({"role": "assistant", "content": last_reply})
        messages.append({"role": "user", "content": f"Observation: {text}"})

    last_reply = ""
    for step in range(1, max_steps + 1):
        if echo:
            print(f"\n--- step {step} / {max_steps} ---")
        try:
            last_reply, usage = model_fn(messages)
        except Exception as exc:  # noqa: BLE001 - a model outage must end cleanly
            run.status = "model_error"
            run.answer = (
                f"The model call failed ({type(exc).__name__}: {exc}). "
                "Check LLM_MODEL, the API key and the free-tier limits, then retry."
            )
            run.events.append({"type": "notice", "text": run.answer})
            break

        prompt_tokens, completion_tokens = _as_counts(usage)
        run.tokens["prompt"] += prompt_tokens
        run.tokens["completion"] += completion_tokens
        run.events.append(
            {
                "type": "assistant",
                "text": last_reply.strip(),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }
        )
        if echo:
            print(last_reply.strip())

        action, payload = parse(last_reply)
        if action is None:
            observe(CORRECTIVE_FORMAT)
            if echo:
                print(f"\n[observation]\n{CORRECTIVE_FORMAT}")
            continue

        what = (action, payload)
        call_counts[what] += 1

        if action == "finish":
            if not payload:
                observe(
                    "'finish' needs the final answer in Action Input. Reply with "
                    "the answer on the Action Input line."
                )
                continue
            run.answer = payload
            run.status = "finished"
            break

        if call_counts[what] > REPEAT_LIMIT:
            observe(
                f"You have already called {action} with {payload!r} "
                f"{REPEAT_LIMIT} times. Use a different input, or finish with the "
                "answer you have."
            )
            continue

        began = time.perf_counter()
        observation = run_tool(action, payload)
        took = (time.perf_counter() - began) * 1000
        if action in TOOLS:
            run.tool_counts[action] += 1
        run.events.append(
            {"type": "observation", "text": observation, "tool": action, "ms": took}
        )
        messages.append({"role": "assistant", "content": last_reply})
        messages.append({"role": "user", "content": f"Observation: {observation}"})
        if echo:
            print(f"\n[observation from {action}]\n{observation}")
    else:
        # The for/else branch: no finish, so the step limit ended the run.
        run.status = "max_steps"
        last = run.events[-1].get("text", "") if run.events else ""
        run.answer = (
            f"I stopped after {max_steps} steps without reaching a final answer. "
            f"Last thing I saw: {last[:200]}"
        )
        run.events.append({"type": "notice", "text": run.answer})

    run.elapsed_s = time.perf_counter() - started
    return run


# --------------------------------------------------------------------------- #
# Trace output
# --------------------------------------------------------------------------- #

BANNER = "=" * 72


def format_trace(run: Run) -> str:
    """Render a run as the text trace saved in ``evidence/``."""
    if run.source == "scripted":
        source_line = (
            f"scripted rehearsal  ({run.scenario} in scripted_model.py - "
            "no provider call, not submittable evidence)"
        )
    else:
        source_line = (
            f"live  ({run.model_name or DEFAULT_MODEL_FALLBACK} through the lab's model "
            "call: LiteLLM in the Codespace, groq_client.py where LiteLLM is absent)"
        )

    lines = [
        BANNER,
        "DCIT 403 Lab 2 - ReAct agent trace",
        f"Question     : {run.question}",
        f"MODEL SOURCE : {source_line}",
        f"Started      : {run.started}",
        f"Step limit   : {run.max_steps}",
        BANNER,
    ]
    step = 0
    for event in run.events:
        if event["type"] == "assistant":
            step += 1
            tokens = ""
            if event.get("prompt_tokens") or event.get("completion_tokens"):
                tokens = (
                    f"  [{event['prompt_tokens']} prompt + "
                    f"{event['completion_tokens']} completion tokens]"
                )
            lines.append(f"\n--- step {step}{tokens} ---")
            lines.append(event["text"])
        elif event["type"] == "observation":
            label = "OBSERVATION"
            if event.get("tool"):
                label = f"OBSERVATION (from {event['tool']}, {event.get('ms') or 0:.0f} ms)"
            lines.append(f"\n[{label}]")
            lines.append(event["text"])
        else:
            lines.append(f"\n[NOTE]\n{event['text']}")

    lines += [
        "",
        BANNER,
        f"STATUS       : {run.status}",
        f"STEPS        : {run.steps} of {run.max_steps}",
        f"TOOLS        : {run.tools_used()}",
        f"TOKENS       : {run.tokens['prompt']} prompt + "
        f"{run.tokens['completion']} completion = "
        f"{run.tokens['prompt'] + run.tokens['completion']} total",
        f"ELAPSED      : {run.elapsed_s:.1f} s",
        f"FINAL ANSWER : {run.answer}",
        BANNER,
    ]
    return "\n".join(lines)


def save_trace(run: Run, path: Path) -> Path:
    """Write a trace file, creating the evidence folder if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_trace(run) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# The six evidence questions and the three robustness drills
# --------------------------------------------------------------------------- #

EVIDENCE_QUESTIONS: list[tuple[str, str, str, int]] = [
    (
        "1_budget",
        "budget",
        "I have GHS 1,200. I want 4 bags of rice at GHS 185 each and 3 gallons "
        "of oil at GHS 95 each. How much will I have left?",
        6,
    ),
    (
        "2_maize_both_tools",
        "both_tools_maize",
        "I have GHS 500. I want 3 bags of maize at GHS 90 each and I must pay "
        "GHS 120 for transport. How much is left, and what is the capital of the "
        "Bono East Region?",
        6,
    ),
    (
        "3_price_both_tools",
        "both_tools_price",
        "Six bags of rice cost GHS 1,140 in total. What is the price of one bag, "
        "and what does Wikipedia say about Kintampo?",
        6,
    ),
    (
        "4_wiki_missing",
        "wiki_missing",
        "What does Wikipedia say about the Zxqv Market Traders Association of "
        "Ghana, and what is Makola Market?",
        6,
    ),
    (
        "5_no_tool",
        "no_tool",
        "Greet a trader at Makola Market and wish them good sales today, in one "
        "sentence.",
        3,
    ),
    (
        "6_badly_worded",
        "badly_worded",
        "me get 1200 cedis want buy rice four bag 185 each how much remain",
        6,
    ),
]

DRILL_QUESTIONS: list[tuple[str, str, str, int]] = [
    (
        "7_unparseable_reply",
        "unparseable",
        "I have GHS 1,200, 4 bags of rice at GHS 185 and 3 gallons of oil at "
        "GHS 95. What is left?",
        6,
    ),
    (
        "8_max_steps",
        "never_finishes",
        "Check that the calculator still works for me.",
        3,
    ),
    (
        "9_repeat_guard",
        "repeats_itself",
        "What is the total cost of 4 bags of rice at GHS 185 each and 3 gallons "
        "of oil at GHS 95 each?",
        6,
    ),
]


def _pick_model(args, scenario: str | None = None):
    """Build the model function and the label/source pair for this run."""
    if scenario:
        return make_model(scenario, verbose=args.verbose), "", "scripted", scenario
    model_name = args.model or DEFAULT_MODEL_FALLBACK
    return make_live_model(args.model, verbose=args.verbose), model_name, "live", None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Lab 2 ReAct agent: a loop, a parser and two tools.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "scenarios for --scenario/--scripted:\n  " + "\n  ".join(scenarios())
        ),
    )
    parser.add_argument("-q", "--question", help="the trader's question")
    parser.add_argument(
        "-s", "--scenario", "--scripted", dest="scenario", metavar="NAME",
        help="rehearse offline with a scripted reply list instead of calling a model",
    )
    parser.add_argument(
        "-a", "--all", action="store_true",
        help="run the six evidence questions (and, with --drills, the drills)",
    )
    parser.add_argument(
        "--drills", action="store_true", help="with --all, also run the robustness drills"
    )
    parser.add_argument("--model", help="LiteLLM model name (default: $LLM_MODEL)")
    parser.add_argument(
        "--max-steps", type=int, default=DEFAULT_MAX_STEPS, help="hard step limit"
    )
    parser.add_argument("--save", metavar="PATH", help="write the trace to this file")
    parser.add_argument(
        "--save-dir", metavar="DIR", help="with --all, write trace_<id>.txt here"
    )
    parser.add_argument("--quiet", action="store_true", help="do not echo the trace")
    parser.add_argument("--verbose", action="store_true", help="show token and retry lines")
    parser.add_argument("--list-scripts", action="store_true", help="list scenarios and exit")
    args = parser.parse_args(argv)

    if args.list_scripts:
        print("\n".join(scenarios()))
        return 0

    echo = not args.quiet

    # ---- batch mode -------------------------------------------------------- #
    if args.all:
        if not args.scenario:
            import os

            if not os.getenv("LLM_MODEL"):
                parser.error(
                    "LLM_MODEL is not set, so there is no model to call. Either "
                    "export LLM_MODEL (and its key), or rehearse offline with: "
                    "python react_agent.py --all --scenario budget"
                )
        cases = list(EVIDENCE_QUESTIONS) + (list(DRILL_QUESTIONS) if args.drills else [])
        failures = 0
        for case_id, default_scenario, question, max_steps in cases:
            # Rehearsing: replay this case's own script. Live: no scenario at all.
            scenario = default_scenario if args.scenario else None
            model_fn, model_name, source, scen = _pick_model(args, scenario)
            print(f"\n{BANNER}\n{case_id}: {question}\n{BANNER}")
            run = run_agent(
                question,
                max_steps=max_steps,
                model_fn=model_fn,
                model_name=model_name,
                source=source,
                scenario=scen,
                echo=echo,
            )
            failures += run.status != "finished"
            print(f"\n[status: {run.status}] {run.answer}")
            if args.save_dir:
                path = save_trace(run, Path(args.save_dir) / f"trace_{case_id}.txt")
                print(f"[saved] {path}")
        print(f"\n{len(cases)} runs, {failures} without a final answer")
        return 0

    # ---- single question --------------------------------------------------- #
    question = args.question
    if not question and args.scenario:
        # Rehearsing a scenario without a question uses that scenario's own question.
        default = {scen: q for _id, scen, q, _steps in
                   EVIDENCE_QUESTIONS + DRILL_QUESTIONS}
        question = default.get(args.scenario)
        if question:
            print(f"[rehearsal question] {question}\n")
    if not question:
        parser.error("give --question, or --all, or --scenario NAME")
    model_fn, model_name, source, scen = _pick_model(args, args.scenario)

    run = run_agent(
        question,
        max_steps=args.max_steps,
        model_fn=model_fn,
        model_name=model_name,
        source=source,
        scenario=scen,
        echo=echo,
    )
    if not echo:
        print(format_trace(run))
    print(f"\nSTATUS {run.status} | {run.steps} steps | tools: {run.tools_used()}")
    print(f"ANSWER {run.answer}")
    if args.save:
        print(f"[saved] {save_trace(run, Path(args.save))}")
    return 0 if run.status == "finished" else 1


if __name__ == "__main__":
    raise SystemExit(main())
