# Lab 2 evidence index

Run: 2026-11-19T14:42:05+00:00  
Mode: **scripted**  
Model: `groq/openai/gpt-oss-20b`  
Traces: 9 (8 finished with a final answer)  

> **REHEARSAL RUN.** These traces replay `scripted_model.py`, so they show
> the loop, the parser and the tools working, but the model text is not
> provider output. Run `python run_evidence.py` with the course keys before
> you submit, and the files in this folder are replaced with live traces.

| Trace | Question | Status | Steps | Tools | Tokens | File |
|---|---|---|---|---|---|---|
| 1_budget | I have GHS 1,200. I want 4 bags of rice at GHS 185 each and 3 gallons of oil at GHS 95 each. How much will I have left? | finished | 3/6 | calculator(2) | 0 | [trace_1_budget.txt](trace_1_budget.txt) |
| 2_maize_both_tools | I have GHS 500. I want 3 bags of maize at GHS 90 each and I must pay GHS 120 for transport. How much is left, and what is the capital of the Bono East Region? | finished | 4/6 | calculator(2), wiki_lookup(1) | 0 | [trace_2_maize_both_tools.txt](trace_2_maize_both_tools.txt) |
| 3_price_both_tools | Six bags of rice cost GHS 1,140 in total. What is the price of one bag, and what does Wikipedia say about Kintampo? | finished | 3/6 | calculator(1), wiki_lookup(1) | 0 | [trace_3_price_both_tools.txt](trace_3_price_both_tools.txt) |
| 4_wiki_missing | What does Wikipedia say about the Zxqv Market Traders Association of Ghana, and what is Makola Market? | finished | 3/6 | wiki_lookup(2) | 0 | [trace_4_wiki_missing.txt](trace_4_wiki_missing.txt) |
| 5_no_tool | Greet a trader at Makola Market and wish them good sales today, in one sentence. | finished | 1/3 | none | 0 | [trace_5_no_tool.txt](trace_5_no_tool.txt) |
| 6_badly_worded | me get 1200 cedis want buy rice four bag 185 each how much remain | finished | 3/6 | calculator(1) | 0 | [trace_6_badly_worded.txt](trace_6_badly_worded.txt) |
| 7_unparseable_reply | I have GHS 1,200, 4 bags of rice at GHS 185 and 3 gallons of oil at GHS 95. What is left? | finished | 3/6 | calculator(1) | 0 | [trace_7_unparseable_reply.txt](trace_7_unparseable_reply.txt) |
| 8_max_steps | Check that the calculator still works for me. | max_steps | 3/3 | calculator(3) | 0 | [trace_8_max_steps.txt](trace_8_max_steps.txt) |
| 9_repeat_guard | What is the total cost of 4 bags of rice at GHS 185 each and 3 gallons of oil at GHS 95 each? | finished | 5/6 | calculator(2) | 0 | [trace_9_repeat_guard.txt](trace_9_repeat_guard.txt) |

Step 1 baseline: [baseline.md](baseline.md)

Status meanings: `finished` = the agent produced a final answer; `max_steps` = the step limit stopped it (drill 8, on purpose).
