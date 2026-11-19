# Live run against Groq: what worked and what failed

Recorded 2026-11-19 14:38 UTC, model `groq/openai/gpt-oss-20b`, temperature 0.
Command: `python run_evidence.py --pause 2` with `GROQ_API_KEY` and `LLM_MODEL` set.

> This note is real output from one live session, kept because the failure is worth
> reporting. The nine traces in this folder are still the rehearsal traces; the live
> traces have to be produced in the Codespace.

## What worked

**The Step 1 baseline ran against the live model and passed.**
`evidence/baseline_live_groq.md` is that run: the model answered the budget question
correctly on all three attempts (GHS 175), and answered one of the two factual
questions correctly. No tools, no loop, plain completion, temperature 0.7.

## What failed

Every ReAct run stopped on its first model call with HTTP 400. The loop reported it
cleanly instead of crashing (`STATUS: model_error`, 0 steps, `TOOLS: none`):

```text
HTTP 400: {"error":{"message":"Tool choice is none, but model called a tool",
"type":"invalid_request_error","code":"tool_use_failed",
"failed_generation":"{\"name\": \"calculator\", \"arguments\": {\"expression\":\"4*185 + 3*95\"}}"}}
```

## Why it happened

`gpt-oss-20b` is a harmony-format model: it emits structured `to=` tool calls rather
than prose when it believes a tool is available. The ReAct prompt tells it that a
tool called `calculator` exists, so on the first step it produced a native tool call
for `4*185 + 3*95`. The request declared no tools, because in the Lab 2 text protocol
the tools are words that my code parses, not functions the API provides. Groq rejects
a call to a tool that was never declared, so the request fails before any text comes
back.

In other words, the model was right about the arithmetic and wrong about the
protocol. The text protocol and native function calling are two different interfaces
to the same idea, and this is the seam between them, which is exactly what Lab 3 is
about.

## What was tried

Three variants of the same request were sent: the plain prompt, a version with the
words "Commands" instead of "Tools", and a rewritten shorter prompt. All three
produced the same 400 and the same `failed_generation`. A control call to
`llama-3.3-70b-versatile` failed for a different reason: the account has no access to
that model, so it was not a useful comparison.

## What to do in the Codespace

1. Run `python run_evidence.py` there, where `requirements.txt` provides LiteLLM. If
   the same 400 appears, the failure is the model's, not this machine's, and it should
   go into the report as a second failure.
2. If it does appear, the clean options are: switch `LLM_MODEL` to the backup
   `gemini/gemini-3.5-flash-lite`; or accept the model's native call by declaring the
   tools in the request (that is Lab 3's function calling, not Lab 2's protocol).
3. Either way, keep this note. "The model preferred its own tool interface to mine" is
   a better failure story than "my parser had a bug", and it is evidence that the
   loop's error handling works: nine runs failed and nothing crashed.
