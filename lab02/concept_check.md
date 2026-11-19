# Lab 2: Architectures: A ReAct Agent From Scratch: Concept Check

Answers in my own words, written before the Wednesday session. They feed Section 2
of the lab report. Trace references are to the files in `evidence/`.

## Q1. Classify a thermostat, a chess engine and a ReAct agent as reactive, deliberative or hybrid, with one reason each.

**Thermostat: reactive.** It has one condition-action rule, "if the room is colder
than the setting, switch the heater on", and it fires on the current reading. It
keeps no history, builds no plan and cannot weigh two options: there is nothing to
deliberate about, and doing it fast is the whole point.

**Chess engine: deliberative.** Before it moves it builds an internal model of the
game (the search tree), evaluates positions several moves ahead and only then picks
an action. It is buying better decisions with time: the deeper the search, the
slower the move. It also keeps state across the whole game, which a reactive agent
does not.

**ReAct agent: hybrid.** Its Thought line is deliberation: in
`evidence/trace_1_budget.txt` the agent states a plan ("total cost first", then
"subtract it from the budget") before it acts. Its Action / Observation lines are
reactive: each step reacts to the newest observation, and the model re-decides from
scratch rather than following a fixed plan. So it plans in small deliberate steps
and reacts to every percept, which is exactly the definition of a hybrid. Underneath,
the loop itself is a BDI-style cycle: beliefs are the observations, the desire is the
trader's question, the intention is the one-step plan in the Thought.

## Q2. In the trace above, which lines are percepts, and which are actions?

**Percepts** are what the agent receives: the question ("I have GHS 1,200 ...") and
each **Observation** line, `1025`, then `175`. When the agent uses `wiki_lookup`,
the Wikipedia extract is a percept too (`evidence/trace_2_maize_both_tools.txt`,
step 3). The percept sequence is the whole `messages` list sent to the model on each
turn.

**Actions** are the model's choices: `Action: calculator` with
`Action Input: 4*185 + 3*95`, the second `calculator` call with `1200 - 1025`, and
`Action: finish` with the final answer. The effect of an action (the arithmetic, the
HTTP request) is carried out by my code, not by the model: the model only writes
text that names the action.

A **Thought** is neither. It is internal deliberation: the model talking to itself,
which is why the loop never parses it and never shows it to a tool.

## Q3. Why do we pass `stop=["Observation:"]` when calling the model?

Because the observation belongs to the code, not to the model. Without the stop
sequence a model will happily continue past `Action Input:` and write an
`Observation: 1025` of its own, invented. The loop would then either duplicate the
real observation or, worse, act on a fabricated tool result. Stopping at
`Observation:` makes that impossible: the reply ends where the code takes over, and
the only observation in the conversation is the one `run_tool` produced.

Two side effects are also useful. The reply is shorter, which keeps the
tokens-per-minute budget of the free tier breathing, and the parser sees a reply that
ends cleanly after `Action Input:` instead of prose about a result that has not
happened yet. My parser still cuts anything after an `Observation:` that slips
through, so the protection does not depend on the API honouring `stop`.

## Q4. Map the trace above to the BDI terms belief, desire and intention.

**Beliefs**: what the agent holds true about the world at that moment. In the trace,
after step 1 the beliefs are "rice costs 4 x 185, oil costs 3 x 95, the total is
GHS 1,025"; after step 2, "the remainder is GHS 175". The beliefs are updated by
percepts, and the whole conversation is the belief base: it is what the model is
given on the next turn.

**Desire**: the goal the trader wants achieved, "know how much money is left from
GHS 1,200 after the shopping". A desire is a wish, not yet a commitment, and it does
not change during the run.

**Intention**: the plan the agent commits to in order to satisfy that desire, which
is the one it writes in the Thought: "get the total cost, then subtract it from the
budget". Each Action is one execution step of that intention. If an observation
contradicted it (for example the calculator returned an error), the intention would
be revised, and that re-planning is the BDI cycle running inside a single ReAct loop.

The finish action is the point where the intention is discharged and the desire is
met. `max_steps` is the fallback for when deliberation never terminates, which is
why the BDI loop needs a step limit as much as the ReAct loop does.
