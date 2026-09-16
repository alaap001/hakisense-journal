# General trade reviews retain individual evidence

Verified 15 September 2026.

## Reported request

A read-only inspection of the saved “tell me about my last 90 trades” job confirmed:

- The selected cohort contained 90 trades.
- The coordinator requested only metrics and setup groups.
- Zero individual records and zero notes were sent to the writer.
- The writer used 1,509 input tokens. Both calls together used 3,115 input tokens.
- This was a planning error, not the context-size fallback. Successful jobs clear their checkpoints; the persisted coordinator response and result coverage provided the diagnosis.

## Corrected behavior

- Review intent requires record evidence with notes and saved rules. Metrics requests become records (which already include exact metrics); groups/checks remain alongside a deduplicated record request for the same cohort.
- A specific calculation can still use metrics only. Concepts still retrieve no trades.
- Explicit count and comparison-cohort constraints remain in effect before detail retrieval.
- Full records are preferred when they fit. Tests cover 20, 90 and 200 complete records. Eighty is a fallback target, not a cap.
- When full records do not fit, retain 80 examples per large cohort with full-population metrics, using period endpoints, extreme results and examples across outcome/setup/emotion groups. This is not a statistical sample. Smaller cohorts keep all their records.
- Further pressure uses labelled note/rule excerpts. The exceptional metrics-only fallback remains if the record table itself cannot fit the remaining authorized allowance. Coverage accurately distinguishes full, sampled, excerpted and aggregate evidence.
- The writer is told that realized-position and open-position counts overlap for partially closed positions, to keep R multiples unitless, and not to invent combined totals for illustrative subsets lacking supplied aggregate metrics.
- Public API responses omit internal coverage. Worker logs include retrieved/included counts and representation without journal text.

## Validation

`python -m unittest tests.test_ai_workflows -q`: 32 tests passed. Added checks inspect the actual mocked provider input, not only the retrieval count: exact IDs, notes, individual P&L, risk/R, full-cohort metrics and exclusion of unrelated older trades. The fallback fixture keeps 80 varied records and unchanged metrics for all 200. Existing scope/isolation, credits, continuation and streaming checks passed.

`python -m unittest tests.test_ai_provider -q`: 4 tests passed.

One live Standard review used a synthetic 500-trade journal: 410 unrelated older trades and the requested 90 recent trades. The outbound writer payload contained exactly the 90 recent IDs, their notes, rules, individual P&L and R values. It returned a nonempty answer in two calls, using 21,777 input / 2,250 output tokens total and settling 3 credits. No customer trades or wallet were used. This verifies evidence delivery and completion, not comprehensive correctness of every generated trading observation. Inspection of that answer prompted the final instruction tightening for example-subset arithmetic and unitless R; that prompt wording was not subjected to another paid run.

Reproduce explicitly with `python scripts/verify_ai_review_evidence.py --run`. The command uses an isolated temporary SQLite database and writes its synthetic report to `/tmp/hakisense-review-evidence-live.json`. Provider token totals and credit charges depend on the generated response and note content, so the observed totals are not fixed prices for 90 trades.

The local API, frontend and worker were restarted after the change. No database migration is required.
