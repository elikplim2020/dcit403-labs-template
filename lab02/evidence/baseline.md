# Lab 2 Step 1 - Baseline: the model on its own

> **REHEARSAL RUN - NOT SUBMITTABLE.** These answers are replayed from
> `scripted_model.py`, a deterministic stand-in, because this machine has
> no `LLM_MODEL` key. Re-run `python run_evidence.py` in the Codespace to
> replace this file with real model output before you submit.

Recorded: 2026-11-19T14:42:05+00:00  
Model source: **scripted**  
Questions asked: 3 x budget, 2 x factual, no tools, no loop.

The budget question was asked three times without any tools. The correct
answer is GHS 175 (`1200 - (4*185 + 3*95)`, computed by `tools.calculator`).

| # | Question | Answer | Marked | Why | Tone |
|---|---|---|---|---|---|
| B1 | Budget question (attempt 1) | Let us do it step by step. 4 bags at GHS 185 each is 4 x 185 = GHS 740. 3 gallons at GHS 95 each is 3 x 95 = GHS 285. Together that is GHS 1,025. You have GHS 1,200, so you will have GHS 175 left. | correct | GHS 175 is in the answer | confident |
| B2 | Budget question (attempt 2) | 4 x 185 = 740 and 3 x 95 = 285, so the shopping costs 1,025. 1,200 minus 1,025 leaves about 165 cedis. | **incorrect** | GHS 175 does not appear (numbers found: 4, 185, 740, 3, 95, 285, 1025, 1200, 1025, 165) | hedged |
| B3 | Budget question (attempt 3) | The rice costs GHS 740. The oil costs GHS 285. The total is GHS 1,025. From GHS 1,200 you will have GHS 175 remaining. | correct | GHS 175 is in the answer | confident |
| F1 | What is the capital of the Bono East Region? | The capital of the Bono East Region is Techiman. | correct | mentions Techiman | confident |
| F2 | Which region of Ghana has Techiman as its capital? | Techiman is the capital of the Bono East Region in Ghana. | correct | mentions Bono East | confident |

**Totals.** Budget question: 2/3 correct. Factual questions: 2/2 correct.

Tone is a word-list heuristic (hedges such as "I think", "about", "roughly" count as hedged), not a judgement of truth.

