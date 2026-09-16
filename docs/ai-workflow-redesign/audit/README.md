# Current AI implementation audit

Source findings and offline measurements from 14 September 2026. Retained as evidence for the revised design; the superseded fixed-limit proposal is not part of this audit. No paid model calls or customer-data inspection were used.

## 2. What the code does today

### 2.1 The user's concern is valid, with an important correction

The backend currently fetches all matching trades into Python, up to the configured report limit. It does **not** send every raw trade to the model without a limit. It sends up to 60 recent detailed trades, plus a substantial analytics bundle. The prompt therefore does not grow linearly forever with trade count, but its minimum useful-data selection is poor and its token cost is not explicitly bounded.

Source: [collect and analyze](/Users/adhall/Personal/stockJournal/backend/ai.py:46), [journal_rows](/Users/adhall/Personal/stockJournal/backend/repository.py:8).

| Area | Verified current behavior | Consequence |
| --- | --- | --- |
| Retrieval | `collect()` calls `journal_rows()` before deciding how to answer. The repository loads full ORM trade objects and enriches them in Python. | A general question and a selected-trade review both pay the database/application cost of loading the scope. |
| Query planning | Only `mode=query` calls a planner. It runs after collection and narrows rows in Python. | Natural-language filters cannot reduce the initial database read. Other modes cannot request task-specific evidence. |
| Evidence | All modes receive metrics, 20 recent daily rows, setup/symbol/weekday groups, all coach checks, and up to 60 recent trades. | Small tasks inherit unrelated context; notes and groups materially increase input size. |
| Single-trade review | The selected trade is added to the common evidence bundle. | The cheapest task is not isolated to its selected trade. It can also fail when the unrelated full scope exceeds the report limit. |
| Text size | Recent notes are clipped at 1,500 characters; selected notes at 6,000 and attributes at 4,000. Selected-trade data also includes other fields, including its playbook snapshot. | Row limits and character clipping are not a total prompt-token limit. Large rule snapshots and tags also need a budget. |
| Groups | `group_rows()` returns the full metric dictionary for every group. Setup/symbol context takes the first 30, normally sorted by descending P&L. | More fields than needed; a “where am I losing?” question can miss weak groups when they fall outside the first 30. |
| Charts | Query evidence contains at most 50 groups, but the returned chart can contain every group. | Frontend/message/job payloads remain large, and model-visible coverage differs from chart coverage. |
| History | Latest 10 messages, each clipped by characters, are attached to the answer; up to four go to the query planner. | Old answers repeatedly consume input tokens; there is no shared history-token budget or persistent evidence scope. |
| Execution | LangGraph is a fixed `collect → plan → analyze → respond` chain. | Different instruction strings do not constitute different retrieval workflows. |
| Streaming | Model calls use `ainvoke`; the browser polls a job every two seconds and waits for its final result. | Users see a generic waiting indicator, not progress or partial answers. |
| Accounting | Jobs store charged credits and route snapshots, but no provider call ledger, input/output usage, or actual provider cost. | Profitability cannot be measured per feature, model, or tier. |

Sources: [AI graph](/Users/adhall/Personal/stockJournal/backend/ai.py:114), [frontend polling](/Users/adhall/Personal/stockJournal/src/lib.ts:46), [AI job model](/Users/adhall/Personal/stockJournal/backend/db.py:197), [route model](/Users/adhall/Personal/stockJournal/backend/db.py:297).

### 2.2 Inventory of every current AI feature

| Feature | Entry point | Bootstrap Standard credits | Current paid calls |
| --- | --- | ---: | ---: |
| Ask your journal / conversation | Coach chat composer | 2 | 1 |
| Draft a trade review | Trade detail modal | 1 | 1 |
| Performance summary | Coach suggestion or mode selector | 2 | 1 |
| Query and chart | Coach suggestion or mode selector | 4 | 2: planner + answer |
| Next-session preparation | Coach suggestion or mode selector | 3 | 1 |
| Detailed coaching review | Review button, finding discussion, or mode selector | 5 | 1 |

These prices are bootstrap values in [catalog.py](/Users/adhall/Personal/stockJournal/backend/catalog.py:2), not a claim about current database settings. Advanced defaults to three times the credit price, with separately configured models. Runtime routes and prices are editable by an administrator.

The 16 review checks are deterministic and free; they do not call a model. Playbook creation spends a credit under the current product policy but is also deterministic. Saving/pinning an AI result, imports, analytics, notebooks, and simulator calculations do not make generation calls. “Deep Researched Stock Analysis” is listed as upcoming, not an implemented workflow. Keep these distinctions in the UI and cost reports.

Sources: [Coach](/Users/adhall/Personal/stockJournal/src/Coach.tsx:11), [TradeDetail](/Users/adhall/Personal/stockJournal/src/Journal.tsx:49), [analytics](/Users/adhall/Personal/stockJournal/backend/analytics.py:152), [runtime routing](/Users/adhall/Personal/stockJournal/backend/runtime_settings.py:64).

### 2.3 Offline payload measurement

The experiment called the current `backend.ai.analyze()` with synthetic closed stock trades, five setups, eight symbols unless stated otherwise, and no conversation history. It measured serialized **evidence only**, excluding the system instructions, user message, planner request, and model output. Character counts are not actual token counts or costs.

| Fixture | Raw recent trades in evidence | Evidence characters |
| --- | ---: | ---: |
| Empty journal, chat | 0 | 5,626 |
| 1 trade, 200-character note | 1 | 9,124 |
| 10 trades, 200-character notes | 10 | 25,258 |
| 60 trades, 200-character notes | 60 | 61,508 |
| 100 trades, 200-character notes | 60 | 63,581 |
| 1,000 trades, 200-character notes | 60 | 67,163 |
| 1,000 trades, 1,500-character notes | 60 | 145,163 |
| 1,000 trades, selected-trade review, short notes | 60 plus selected trade | 68,259 |
| 1,000 distinct symbols, query/chart, short notes | 60 | 131,592 |

The summary, daily, and coach modes each produced the same 67,163-character evidence as chat in the short-note 1,000-trade fixture. The distinct-symbol query returned 1,000 chart groups to the frontend while exposing 50 to the model. Results are recorded in [baseline.json](/Users/adhall/Personal/stockJournal/docs/ai-workflow-redesign/baseline.json).

This establishes unnecessary payload and mismatched workflows. It does not establish your current bill, a percentage saving, or live model accuracy. Those need provider usage and evaluated responses.

### 2.4 Keep the useful foundations

Preserve the atomic wallet/job creation, request hash and idempotency key, one active job per user, tenant-scoped access, saved route snapshot, transactionally persisted messages/results, and one-time failure refunds. The worker deliberately avoids automatically replaying a paid generation. These are good foundations for the redesign.

Sources: [enqueue](/Users/adhall/Personal/stockJournal/backend/jobs.py:24), [finish](/Users/adhall/Personal/stockJournal/backend/jobs.py:95), [worker](/Users/adhall/Personal/stockJournal/backend/worker.py:15).

