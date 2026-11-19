# Lab 2 - Architectures: A ReAct Agent From Scratch

A ReAct agent for a Makola Market trader, in plain Python with no agent framework.
The model writes `Thought` / `Action` / `Action Input`; this code parses it, runs
the tool, feeds the result back as an `Observation`, and repeats until `finish` or
the step limit.

| File | What it is | Manual step |
|---|---|---|
| `tools.py` | `calculator` (AST evaluator, never `eval`) and `wiki_lookup` (Wikipedia summary API) | Step 2 |
| `react_agent.py` | the prompt, the parser, the loop, the error handling, the trace writer | Steps 3 and 4 |
| `baseline.py` | the model alone, no tools, three budget attempts and two factual questions | Step 1 |
| `scripted_model.py` | deterministic stand-in for the model, for offline rehearsal and tests | - |
| `groq_client.py` | the same model interface against Groq's HTTP API, used only where LiteLLM cannot be installed | - |
| `run_evidence.py` | one command that regenerates the whole `evidence/` folder | Steps 1, 4, 5 |
| `concept_check.md` | answers to the four concept-check questions | Part A (independent) |
| `tests/` | 35 unit tests: tools, parser, loop failure handling | Steps 2, 3, 5 |
| `evidence/` | baseline, nine traces, and `RUN_LOG.md` (the index) | Deliverables |
| `report/` | the lab report (`DCIT403_Lab02_22237205.docx` and `.pdf`) and the script that builds it | Section 3 of the manual |

## What is still yours to fill in

1. `report/DCIT403_Lab02_22237205.docx` and its PDF: the **lab repository link** and
   the **team repository link plus one line of contribution** are still highlighted in
   yellow. Section 6 of the report is the project link.
2. `evidence/`: run `python run_evidence.py` once in the Codespace so the nine traces
   and the baseline become live (see section 1), then re-read the traces before you
   submit them.
3. `AI_USE_LOG.md` at the repository root, if the course requires it (manual section 4).
   It is not in this folder.

## 1. Run it for real (Codespace)

```bash
cat .env                                  # LLM_MODEL=groq/openai/gpt-oss-20b
python tools.py                           # Step 2 checkpoint: both tools, no model
python -m unittest discover -s tests -v   # 35 tests
python baseline.py                        # Step 1, writes evidence/baseline.md
python react_agent.py --question "I have GHS 1,200. I want 4 bags of rice at GHS 185 each and 3 gallons of oil at GHS 95 each. How much will I have left?"
python run_evidence.py                    # Steps 1, 4 and 5: all six traces + drills
```

`run_evidence.py` overwrites every file in `evidence/` with a live run: the
`MODEL SOURCE: scripted rehearsal` banner disappears and each trace header shows
the real model name, real token counts and real timings.

## 2. Run it with no key (rehearsal)

```bash
python react_agent.py --scenario budget       # replay one scripted scenario
python react_agent.py --list-scripts          # every scenario
python run_evidence.py --scripted             # the whole evidence folder, replayed
```

The files in `evidence/` in this folder were produced in rehearsal mode: the text
that plays the model comes from `scripted_model.py`, so **the loop, the parser, the
tools, the timings and the Wikipedia observations are real, but the model's words
are replayed, not provider output.** Each of those files carries a banner saying so.
Run section 1 once in the Codespace before you submit, and the banners go away.

## 3. How the loop meets the checkpoints

| Checkpoint | Where it is shown |
|---|---|
| Step 2: tools correct, calculator rejects unsafe input | `python tools.py`; `tests/test_tools.py` |
| Step 3: one reply parsed into action and input | `tests/test_parser.py::ParseTests` |
| Step 4: budget question answered, calculator called | `evidence/trace_1_budget.txt` |
| Step 5: five questions, none crash, all traces saved | `evidence/trace_2` to `trace_6` |
| Step 5: robustness (unknown tool, unparseable reply, max steps) | `evidence/trace_6`, `trace_7`, `trace_8`, `trace_9` |

## 4. Design decisions worth defending in the viva

* **The model decides, the code computes.** Every arithmetic result in the traces
  comes from `tools.calculator`; the model only chooses the expression. The
  baseline in `evidence/baseline.md` shows why that matters.
* **`stop=["Observation:"]`.** The model cannot write its own observation, so no
  hallucinated tool result can enter the conversation. It also ends the reply at
  the point where the loop takes over.
* **The parser is normalised, not widened.** `ACTION_RE` is exactly the lab's
  regex. Decoration that models add (Markdown bold, backticks, lower case, numbered
  steps) is stripped first, in `normalise_labels`. Two real failures are recorded
  as tests: Markdown bold and numbered steps both defeat the bare regex.
* **Every failure is an observation, not an exception.** Unknown tool names,
  unreadable replies, empty `finish`, the same call three times, the step limit and
  even a model outage all end as text the loop or the user can act on.
* **One Retry on rate limits.** HTTP 429 waits 2 s, then 4 s; the third failure
  ends the run with a clear message instead of a traceback.

## 5. Known limits

* **A live run against Groq's `gpt-oss-20b` failed in the ReAct loop.** The model tried
  a native tool call and the API rejected it with `tool_use_failed`, because the text
  protocol declares no tools. The baseline in the same session worked. Full record:
  `evidence/live_groq_attempt.md`. If the Codespace shows the same 400, switch
  `LLM_MODEL` to the backup and write it up as the second failure.
* `calculator` covers `+ - * /` and unary minus only. Powers (`2 ** 10`) and
  percentages return `Error: Unsupported expression` on purpose: every added
  operator is added attack surface. Percentage questions are a good stretch task.
* `wiki_lookup` needs the network. Offline it returns
  `Error: could not reach Wikipedia (...)` and the agent is expected to say so.
* Scripted mode cannot test prompt quality: it replays fixed replies, so a live run
  is the only evidence of how the model actually behaves.

## 6. Stretch tasks (not done here)

Add `convert_currency(amount, from_cur, to_cur)` with a fixed rate table; count
tokens per question (already printed in each trace); add a reactive shortcut that
calls `calculator` directly when the question contains only numbers and operators.
