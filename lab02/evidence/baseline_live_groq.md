# Lab 2 Step 1 - Baseline: the model on its own

> Live run against `groq/openai/gpt-oss-20b`, temperature 0.7, no tools, through the lab's model call (LiteLLM in the Codespace; `groq_client.py` only where LiteLLM cannot be installed).

Recorded: 2026-11-19T14:38:58+00:00  
Model source: **live**  
Questions asked: 3 x budget, 2 x factual, no tools, no loop.

The budget question was asked three times without any tools. The correct
answer is GHS 175 (`1200 - (4*185 + 3*95)`, computed by `tools.calculator`).

| # | Question | Answer | Marked | Why | Tone |
|---|---|---|---|---|---|
| B1 | Budget question (attempt 1) | You’ll spend GHS 740 on the rice (4 × 185) and GHS 285 on the oil (3 × 95), for a total of GHS 1,025. Subtracting that from your GHS 1,200 leaves you with GHS 175. | correct | GHS 175 is in the answer | confident |
| B2 | Budget question (attempt 2) | You’ll spend 4 × GHS 185 = GHS 740 on rice and 3 × GHS 95 = GHS 285 on oil, for a total of GHS 1,025. With GHS 1,200 to start, you’ll have GHS 175 left after the purchases. | correct | GHS 175 is in the answer | confident |
| B3 | Budget question (attempt 3) | You’ll spend 4 × GHS 185 = GHS 740 on rice and 3 × GHS 95 = GHS 285 on oil, for a total of GHS 1 025. Subtracting that from your GHS 1 200 leaves you with GHS 175. | correct | GHS 175 is in the answer | confident |
| F1 | What is the capital of the Bono East Region? | The capital of the Bono East Region is Techiman. It’s a key commercial hub where farmers and traders from surrounding districts bring their produce for sale and purchase. The town’s central market is a bustling spot for fresh produce, textiles, and local craf… | correct | mentions Techiman | confident |
| F2 | Which region of Ghana has Techiman as its capital? | Techiman is the capital city of the Bono East Region in Ghana. The region was created in 2019 when it was split off from the former Brong‑Ahafo Region. | **incorrect** | does not mention Bono East | confident |

**Totals.** Budget question: 3/3 correct. Factual questions: 1/2 correct.

Tone is a word-list heuristic (hedges such as "I think", "about", "roughly" count as hedged), not a judgement of truth.

