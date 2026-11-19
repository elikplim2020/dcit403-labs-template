"""A deterministic stand-in for the language model, used offline and in tests.

Why this file exists
--------------------
The real agent calls a model through LiteLLM. That needs ``LLM_MODEL`` and a
provider key (see the Free Model Access Guide). Without them the loop, the parser,
the tools and every error path can still be exercised: this module replays a
scripted list of agent replies, one per model call, keyed by scenario name.

What it is **not**
------------------
It is not a model and it does not reason. Every trace produced with it is stamped
``MODEL SOURCE: scripted rehearsal`` at the top. Rehearsal traces are for
development, unit tests and teaching the loop; the evidence you submit must come
from ``python run_evidence.py`` with a real key, which stamps ``MODEL SOURCE: live``.

The scripts below are written in the exact Thought / Action / Action Input format
that ``react_agent.SYSTEM_PROMPT`` demands, including one deliberately malformed
reply so the recovery path can be tested without waiting for a model to misbehave.
"""

from __future__ import annotations

# Each scenario is a list of replies, consumed in order.
# The last reply of a well-behaved scenario is always a finish.
SCRIPTS: dict[str, list[str]] = {
    # ---- Step 4: the budget question (calculator only) --------------------- #
    "budget": [
        "Thought: I need the total cost first: 4 bags of rice at GHS 185 plus "
        "3 gallons of oil at GHS 95.\n"
        "Action: calculator\n"
        "Action Input: 4*185 + 3*95",
        "Thought: The total cost is GHS 1,025. Now I subtract that from the "
        "GHS 1,200 budget.\n"
        "Action: calculator\n"
        "Action Input: 1200 - 1025",
        "Thought: I have the answer.\n"
        "Action: finish\n"
        "Action Input: You will have GHS 175 left from your GHS 1,200.",
    ],
    # ---- Step 5, question 1: needs both tools ----------------------------- #
    "both_tools_maize": [
        "Thought: First the cost of the maize: 3 bags at GHS 90 each.\n"
        "Action: calculator\n"
        "Action Input: 3*90",
        "Thought: That is GHS 270 for maize. The transport is GHS 120, so I "
        "subtract both from the GHS 500.\n"
        "Action: calculator\n"
        "Action Input: 500 - 270 - 120",
        "Thought: I still need the capital of the Bono East Region. I will look "
        "it up rather than guess.\n"
        "Action: wiki_lookup\n"
        "Action Input: Bono East Region",
        "Thought: The summary names the capital as Techiman, and I have the money "
        "answer. I can finish.\n"
        "Action: finish\n"
        "Action Input: You have GHS 110 left after the maize and the transport. "
        "The capital of the Bono East Region is Techiman.",
    ],
    # ---- Step 5, question 2: needs both tools, division ------------------- #
    "both_tools_price": [
        "Thought: The price of one bag is the total divided by six.\n"
        "Action: calculator\n"
        "Action Input: 1140/6",
        "Thought: One bag costs GHS 190. Now I need a short fact about Kintampo.\n"
        "Action: wiki_lookup\n"
        "Action Input: Kintampo",
        "Thought: I have both answers, so I can finish.\n"
        "Action: finish\n"
        "Action Input: One bag costs GHS 190. Kintampo is a town in the Bono East "
        "Region, known for the Kintampo waterfalls.",
    ],
    # ---- Step 5, question 3: a page that does not exist ------------------ #
    "wiki_missing": [
        "Thought: The trader asks about a traders association, so I should look it "
        "up instead of guessing.\n"
        "Action: wiki_lookup\n"
        "Action Input: Zxqv Market Traders Association of Ghana",
        "Thought: No page was found. I will try the general market article before "
        "giving up on the fact.\n"
        "Action: wiki_lookup\n"
        "Action Input: Makola Market",
        "Thought: I have no page for the association, so I must say so plainly "
        "instead of inventing a fact.\n"
        "Action: finish\n"
        "Action Input: There is no Wikipedia page for that association, so I cannot "
        "confirm it. Makola Market in Accra is a large open-air market where "
        "traders sell foodstuffs, cloth and household goods.",
    ],
    # ---- Step 5, question 4: no tool needed ------------------------------ #
    "no_tool": [
        "Thought: This only needs a sentence of friendly text, so no tool is "
        "needed and I can finish now.\n"
        "Action: finish\n"
        "Action Input: Good morning, and may you have good sales at Makola Market "
        "today.",
    ],
    # ---- Step 5, question 5: badly worded, then self-corrected ----------- #
    "badly_worded": [
        "Thought: The wording is broken, but it looks like 4 bags of rice at "
        "GHS 185 each from GHS 1,200, so I read it as 1200 - 4*185.\n"
        "Action: Calculator\n"
        "Action Input: 1200 - 4*185",
        "Thought: The action name was rejected as unknown, so I must use the exact "
        "name calculator.\n"
        "Action: calculator\n"
        "Action Input: 1200 - 4*185",
        "Thought: The sum gives GHS 460 left. I can finish.\n"
        "Action: finish\n"
        "Action Input: Reading your question as 4 bags of rice at GHS 185 each from "
        "GHS 1,200, you will have GHS 460 left.",
    ],
    # ---- Robustness drill 1: a reply with no Action line at all ---------- #
    "unparseable": [
        "I think the answer is that the trader will have GHS 175 left, because 4 "
        "times 185 is 740 and 3 times 95 is 285.",
        "Thought: I forgot the required format. I will use the calculator as the "
        "prompt asks.\n"
        "Action: calculator\n"
        "Action Input: 1200 - (4*185 + 3*95)",
        "Thought: That confirms GHS 175, so I can finish in the required format.\n"
        "Action: finish\n"
        "Action Input: You will have GHS 175 left.",
    ],
    # ---- Robustness drill 2: a model that never finishes ----------------- #
    "never_finishes": [
        "Thought: I will add one more small number to check the calculator.\n"
        "Action: calculator\n"
        "Action Input: 1 + 1",
        "Thought: Let me check another sum while I am here.\n"
        "Action: calculator\n"
        "Action Input: 2 + 2",
        "Thought: One more check cannot hurt.\n"
        "Action: calculator\n"
        "Action Input: 3 + 3",
        "Thought: One more.\n"
        "Action: calculator\n"
        "Action Input: 4 + 4",
        "Thought: One last check.\n"
        "Action: calculator\n"
        "Action Input: 5 + 5",
    ],
    # ---- Robustness drill 3: the same call over and over ----------------- #
    "repeats_itself": [
        "Thought: I need the total cost.\n"
        "Action: calculator\n"
        "Action Input: 4*185 + 3*95",
        "Thought: I need the total cost.\n"
        "Action: calculator\n"
        "Action Input: 4*185 + 3*95",
        "Thought: I need the total cost.\n"
        "Action: calculator\n"
        "Action Input: 4*185 + 3*95",
        "Thought: I need the total cost.\n"
        "Action: calculator\n"
        "Action Input: 4*185 + 3*95",
        "Thought: I have the cost now.\n"
        "Action: finish\n"
        "Action Input: The total cost is GHS 1,025.",
    ],
    # ---- Step 1 baseline: the model alone, no tools ---------------------- #
    # Rehearsal answers are prose in the model's own voice, with no tool calls,
    # exactly as a bare chat completion behaves.
    "baseline_budget": [
        "Let us do it step by step. 4 bags at GHS 185 each is 4 x 185 = GHS 740. "
        "3 gallons at GHS 95 each is 3 x 95 = GHS 285. Together that is "
        "GHS 1,025. You have GHS 1,200, so you will have GHS 175 left.",
        "4 x 185 = 740 and 3 x 95 = 285, so the shopping costs 1,025. "
        "1,200 minus 1,025 leaves about 165 cedis.",
        "The rice costs GHS 740. The oil costs GHS 285. The total is GHS 1,025. "
        "From GHS 1,200 you will have GHS 175 remaining.",
    ],
    "baseline_fact_capital": [
        "The capital of the Bono East Region is Techiman.",
        "Techiman is the capital of the Bono East Region, and it is also a major "
        "market town.",
    ],
    "baseline_fact_techiman": [
        "Techiman is the capital of the Bono East Region in Ghana.",
    ],
}


def make_model(scenario: str, *, verbose: bool = False):
    """Return a ``model_fn(messages) -> (text, usage)`` that replays ``scenario``.

    The returned callable matches the interface ``react_agent`` expects from
    LiteLLM, so no code in the agent changes between rehearsal and a live run.
    """
    if scenario not in SCRIPTS:
        raise KeyError(
            f"unknown scripted scenario {scenario!r}; choose from {sorted(SCRIPTS)}"
        )
    replies = list(SCRIPTS[scenario])
    state = {"i": 0}

    def model_fn(messages):  # noqa: ARG001 - messages are deliberately ignored
        if state["i"] < len(replies):
            text = replies[state["i"]]
        else:
            # A script that runs out behaves like a model that stops cooperating:
            # it returns text with no Action line, and the loop's parser handles it.
            text = "I have nothing further to add."
        state["i"] += 1
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        if verbose:
            print(f"    [scripted:{scenario}] reply {state['i']}/{len(replies)}")
        return text, usage

    return model_fn


def scenarios() -> list[str]:
    """Scenario names, for ``--help`` and for the evidence runner."""
    return sorted(SCRIPTS)
