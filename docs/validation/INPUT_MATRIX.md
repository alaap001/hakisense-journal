# Input validation matrix

Planning snapshot, 13 September 2026. Requirements are proposed behavior; current declarations are source evidence, not fresh runtime verification. See [VALIDATION_PLAN.md](../../VALIDATION_PLAN.md) for decisions and implementation order.

Every field also follows BASE-001 through BASE-004. The JSON catalog contains complete bindings and acceptance cases.

## Sign up, sign in and password recovery

Scope: **current**. Sources: `src/Auth.tsx`, `src/authClient.ts`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `auth.name` | current | Sign-up display name: trim; 1–100 Unicode characters; not only whitespace. | AUTH-001 |
| `auth.email` | current | Trim surrounding whitespace; validate a complete email, maximum 254 characters. Do not invent mailbox rules or strip + aliases. | AUTH-001 |
| `auth.password` | current | Sign-up/reset 8–128 characters. Login accepts existing nonempty passwords up to provider-compatible cap. Never trim, case-fold, log or silently truncate passwords. | AUTH-001 |
| `auth.mode` | current | login/signup/forgot/recovery only; choose the fields required by the active mode. | AUTH-001, AUTH-002 |
| `auth.code` | current | Auth callback code handled only by Supabase; reject expired/invalid/already-used callbacks with a recoverable screen. | AUTH-001, AUTH-002 |
| `auth.redirect` | current | Allow only this origin and known internal destinations; reject external redirects and unsafe schemes. | AUTH-001, AUTH-002 |

## Broker accounts

Scope: **current**. Sources: `src/Settings.tsx`, `backend/journal_routes.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `account.name` | current | Trimmed 1–100; warn about case-insensitive duplicate names within this user. | ACC-001, REC-002 |
| `account.broker` | current | Known broker ID/display-name mapping or explicit Other / manual; preserve historical inactive broker references. | ACC-001 |
| `account.currency` | current | INR reporting; cannot relabel existing amounts by editing this field. | ACC-001, UI-002 |
| `account.initial_balance` | current | Finite decimal >=0; 0 is valid and produces unavailable return-on-capital ratios. Not a hard cap on derivative notional. | ACC-001, ACC-002 |
| `account.color` | current | A six-digit #RRGGBB color only. | ACC-001 |

## Personal profile

Scope: **current**. Sources: `src/Settings.tsx`, `backend/journal_routes.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `profile.display_name` | current | Same trimmed 1–100 name rule as sign-up. | ACC-001 |
| `profile.email` | current | Read-only display; authenticated provider identity is authoritative. | Schema + base rules |
| `profile.currency` | current | Read-only INR reporting label. | Schema + base rules |
| `profile.timezone` | current | Read-only Asia/Kolkata; display is not authority for parsing stored timestamps. | Schema + base rules |

## Trade create/update, AI note append and imported rows

Scope: **current**. Sources: `src/Journal.tsx`, `backend/schemas.py`, `backend/analytics.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `trade.account_id` | current | Required owned account ID; recheck at write time. | IMP-005 |
| `trade.symbol` | current | Trim/uppercase a search term, 1–40; resolve to an exact instrument rather than trusting free text. | INS-001, INS-004, INS-008, IMP-005 |
| `trade.asset_type` | current | Existing Stocks/Options/Futures/Crypto/Indices enum; must match the resolved instrument and segment. | INS-001, INS-002, INS-003, INS-005, IMP-005, UI-002 |
| `trade.exchange` | current | Supported venue enum plus valid instrument listing; Crypto is currently a category, not a specific venue. | INS-001, INS-002, IMP-005 |
| `trade.segment` | current | Use the instrument compatibility matrix; not just membership of the segment list. | INS-001, INS-002, IMP-005 |
| `trade.expiry` | current | Strict calendar date for expiring contracts; optional otherwise; no automatic weekday or current-lot assumption. | INS-002, INS-004, INS-005, INS-006, TIME-001, TIME-004, META-002, IMP-005 |
| `trade.strike` | current | Positive decimal for options only, tied to the actual listed contract. | INS-002, INS-005, INS-007, PRICE-002, META-002, IMP-005 |
| `trade.option_type` | current | CE/PE for options; null for non-options. Never derive Long/Short from CE/PE. | INS-002, INS-005, META-002, IMP-005 |
| `trade.lot_size` | current | Positive integer from metadata applicable to the contract and trade date; manual values require provenance. | INS-004, INS-005, INS-006, QTY-002, IMP-005 |
| `trade.side` | current | Long/Short describes exposure to the selected instrument price; quantity stays positive. | POS-003, RISK-001, FEE-004, IMP-005 |
| `trade.status` | current | Open/Closed/Partial/Canceled with explicit field consistency; no silent discarding of fills. | POS-001, POS-002, FEE-003, IMP-005, UI-002 |
| `trade.entry_price` | current | Positive finite decimal for a filled trade. Planned unfilled orders need a separate context. | INS-007, INS-008, POS-002, POS-003, POS-004, PRICE-001, PRICE-002, RISK-001, RISK-003, FEE-002, FEE-004, IMP-005 |
| `trade.exit_price` | current | Finite nonnegative for closed/partial fills; zero requires explicit worthless-expiry/write-off/settlement evidence. | INS-007, INS-008, POS-001, POS-003, POS-004, PRICE-001, PRICE-002, FEE-002, FEE-004, IMP-005 |
| `trade.mark_price` | current | Optional finite nonnegative, with timestamp/source planned; null means unknown, not zero. | PRICE-001, PRICE-002, IMP-005 |
| `trade.quantity` | current | Positive decimal, integral shares for ordinary equities and whole valid lots for Indian F&O; crypto uses pair precision. Corporate-action fractional holdings require an explicit adjustment context. | ACC-002, QTY-001, QTY-002, QTY-003, POS-001, POS-002, POS-004, RISK-003, FEE-002, IMP-005 |
| `trade.closed_quantity` | current | 0 for Open; total quantity for Closed; strictly between for Partial; exact decimal comparisons. | QTY-002, POS-001, POS-004, RISK-003, FEE-002, FEE-004, IMP-005 |
| `trade.multiplier` | current | Positive instrument-specific unit factor; exactly 1 when NSE/BSE equity/F&O quantity is already in units. | ACC-002, INS-006, QTY-002, QTY-003, FEE-002, IMP-005 |
| `trade.entry_time` | current | Required valid execution timestamp; bare user/broker timestamps interpreted as IST only after format/source is known. | INS-006, POS-002, TIME-001, TIME-002, TIME-003, TIME-004, IMP-005 |
| `trade.exit_time` | current | Required when quantity is realized; cannot precede entry; equal timestamps are valid at available source precision. | INS-006, POS-001, TIME-001, TIME-002, TIME-003, TIME-004, IMP-005 |
| `trade.commission` | current | Finite INR decimal >=0; default 0 explicitly; brokerage excludes amounts already in fees. | POS-002, POS-003, FEE-001, FEE-002, FEE-003, FEE-004, FEE-005, IMP-005 |
| `trade.fees` | current | Finite INR decimal >=0; require fee-scope definition to avoid doubling entry/exit charges. | INS-008, POS-002, POS-003, FEE-001, FEE-002, FEE-003, FEE-004, FEE-005, IMP-005 |
| `trade.stop_loss` | current | Optional price >=0; flag unexpected direction in historical records, distinguish original and trailed stops. | PRICE-001, RISK-001, RISK-003, IMP-005 |
| `trade.target_price` | current | Optional price >=0; distinguish original plan and current bracket before directional blocking. | PRICE-001, RISK-001, IMP-005 |
| `trade.risk_amount` | current | Optional positive INR amount; compare with price-distance risk as warning, not an automatic overwrite. | RISK-003, RISK-005, IMP-005 |
| `trade.planned_entry` | current | Optional positive price; planned versus actual difference is valid slippage. | PRICE-001, IMP-005 |
| `trade.setup` | current | Trimmed <=100; known playbook ID proposed, or explicit custom label; prevent blank/duplicate labels. | META-001, IMP-005 |
| `trade.emotion` | current | Known mood list or versioned legacy value, <=50. | META-001, IMP-005 |
| `trade.rating` | current | Integer 1–5; omitted uses explicit default 3, not zero. | META-001, IMP-005 |
| `trade.notes` | current | Plain text/allowed Markdown <=10,000 chars; preserve user writing and render safely. | META-001, IMP-005 |
| `trade.tags` | current | At most 30 nonempty unique trimmed strings of <=100 chars; do not split a valid JSON array incorrectly. | META-001, IMP-005, IMP-007 |
| `trade.attributes` | current | JSON object, <=16,000 encoded UTF-8 bytes; proposed depth/key caps; reject prototype keys and nonfinite values. | META-001, META-002, IMP-005, IMP-007 |
| `trade.mfe` | current | Optional finite nonnegative INR excursion, not price points or percentage; define gross/net/time-window semantics. | RISK-003, IMP-005 |
| `trade.mae` | current | Same unit and observation window as MFE; not a signed loss field. | RISK-003, IMP-005 |

## Instrument metadata needed to implement reliable validation

Scope: **proposed**. Sources: `backend/markets.py`, `backend/schemas.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `instrument.instrument_id` | proposed | Stable identity for a security/contract/pair, not a user-entered display label. | INS-001, INS-006 |
| `instrument.underlying_id` | proposed | Parent index/equity for derivatives; distinct from contract identity. | INS-001, INS-006 |
| `instrument.instrument_kind` | proposed | equity/ETF/index_reference/index_future/index_option/stock_future/stock_option/commodity_future/commodity_option/crypto_spot/crypto_linear_derivative/crypto_inverse_derivative. | INS-001, INS-006 |
| `instrument.aliases` | proposed | Exact normalized aliases scoped by venue and validity dates; prefix matches are never conclusive. | INS-001, INS-006 |
| `instrument.valid_from` | proposed | Effective timestamp/date for metadata; do not apply new specifications to old trades. | INS-001, INS-004, INS-006 |
| `instrument.valid_until` | proposed | After valid_from when provided; preserve past revisions. | INS-001, INS-004, INS-006 |
| `instrument.tick_size` | proposed | Positive decimal per effective contract; aggregated average fill prices are not forced to an exchange tick. | INS-001, INS-006, INS-007 |
| `instrument.quantity_step` | proposed | Positive decimal/integer step in explicit units. | INS-001, INS-006 |
| `instrument.lot_size` | proposed | Positive integer when lot-traded; point-in-time authoritative metadata. | INS-001, INS-006 |
| `instrument.price_currency` | proposed | Original quote currency, separate from INR reporting. | INS-001, INS-006 |
| `instrument.quantity_unit` | proposed | shares/underlying_units/contracts/base_asset; explicit and compatible with multiplier. | INS-001, INS-006 |
| `instrument.contract_multiplier` | proposed | Positive decimal with named economic unit; not a guessed conversion. | INS-001, INS-006 |
| `instrument.settlement_type` | proposed | cash/physical/linear/inverse and known pricing formula. | INS-001, INS-006, INS-008 |
| `instrument.source` | proposed | Official/provider/manual source with fetched_at and verification status. | INS-001, INS-004, INS-006, TIME-003 |

## Context needed for ambiguous trade checks

Scope: **proposed**. Sources: `backend/schemas.py`, `backend/analytics.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `trade_extension.quantity_unit` | proposed | Required explicit input unit before conversion; preserve original broker quantity. | QTY-003 |
| `trade_extension.fills` | proposed | Ordered entry/exit executions with unique source IDs, quantities, price, timestamp and charges; necessary for scale-in/out accuracy. | INS-007, POS-004 |
| `trade_extension.fee_scope` | proposed | total_record/realized_only/per_fill; do not assume for imported partial trades. | FEE-001, FEE-003 |
| `trade_extension.fee_components` | proposed | Brokerage, tax/levy, funding, interest, settlement and other costs with currency and no double counting. Negative rebates/corrections need a separate signed adjustment type. | FEE-001, FEE-005 |
| `trade_extension.price_currency` | proposed | Original quote currency; never assume INR merely because reporting is INR. | INS-008 |
| `trade_extension.fx_rate` | proposed | Positive dated conversion rate with source; entry/exit/fees need the appropriate rate for each amount. | INS-008 |
| `trade_extension.fx_as_of` | proposed | Timestamp for the conversion source; stale/unknown conversion flagged. | INS-008 |
| `trade_extension.stop_kind` | proposed | original/current_trailing; historical breached plans remain valid history. | RISK-001, RISK-002 |
| `trade_extension.mark_as_of` | proposed | Timestamp and source for supplied marks; unknown marks do not become realized P&L. | Schema + base rules |
| `trade_extension.settlement_reason` | proposed | worthless_expiry/cash_settlement/physical_settlement/write_off/normal_fill; required for exceptional zero price. | PRICE-001, TIME-004 |
| `trade_extension.source_trade_id` | proposed | Broker execution identity for reliable deduplication, scoped to account/venue. | IMP-006 |
| `trade_extension.record_version` | proposed | Optimistic concurrency token for updates. | Schema + base rules |
| `trade_extension.warning_acknowledgements` | proposed | Server-bound warning IDs, input hash, policy version and expiry; no client-provided severity overrides. | Schema + base rules |
| `trade_extension.record_context` | proposed | executed_trade/reference/practice/adjustment/draft. Reference index and synthetic practice data excluded from real execution P&L. | INS-003 |
| `trade_extension.instrument_override_reason` | proposed | Audited manual metadata correction; cannot override a known instrument conflict or access control. | Schema + base rules |
| `trade_extension.instrument_id` | proposed | Resolved exact instrument/contract ID, linked to the metadata revision used during validation. | Schema + base rules |

## Global scope, journal search, filters and exports

Scope: **current**. Sources: `src/WorkspaceApp.tsx`, `src/Journal.tsx`, `backend/schemas.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `filters.account_id` | current | Empty means all owned accounts; otherwise valid owned ID. | FILTER-001 |
| `filters.start` | current | Optional strict YYYY-MM-DD interpreted as first instant of that IST date. | TIME-001, FILTER-001 |
| `filters.end` | current | Optional strict YYYY-MM-DD; inclusive day mapped to next-day exclusive instant; start <= end. | TIME-001, FILTER-001 |
| `filters.symbol` | current | Bounded trimmed search string <=40; substring search is not an instrument classification decision. | FILTER-001 |
| `filters.asset_type` | current | Empty or supported enum. | FILTER-001 |
| `filters.side` | current | Empty/Long/Short. | FILTER-001 |
| `filters.status` | current | Empty or supported status. | FILTER-001 |
| `filters.setup` | current | Bounded <=100 exact normalized label/owned ID. | FILTER-001 |
| `filters.emotion` | current | Empty or known enum/legacy value. | FILTER-001 |
| `filters.tag` | current | Bounded <=100 exact tag. | FILTER-001 |
| `filters.outcome` | current | Empty/win/loss/breakeven; based on fee-adjusted P&L. | FILTER-001 |

## Journal and shared selectors

Scope: **current**. Sources: `src/Journal.tsx`, `src/WorkspaceApp.tsx`, `src/Select.tsx`, `src/SuggestInput.tsx`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `journal_ui.date_mode` | current | all/7/30/90/365/custom; custom dates validated as a pair. | FILTER-001, UI-001 |
| `journal_ui.sort` | current | date/pnl/symbol only. | UI-001 |
| `journal_ui.page` | current | Positive bounded integer; reset/clamp on filter changes or result shrink. | FILTER-001, UI-001 |
| `journal_ui.saved_view_id` | current | Owned saved view; validate its stored filters again on load. | UI-001 |
| `journal_ui.ai_draft` | current | Nonempty draft plus existing notes must stay <=10,000 chars; append to current record version after review. | META-001, AI-003, UI-001 |
| `journal_ui.option_search` | current | Bounded string; no request or paid action just for searching; preserve no-selection/disabled-option behavior. | UI-001 |

## Chart grouping, pivot controls and AI query plans

Scope: **current**. Sources: `src/Analytics.tsx`, `backend/schemas.py`, `backend/ai.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `query_plan.dimension` | current | Known dimension enum from QueryPlan. | META-002, FILTER-002, AI-003 |
| `query_plan.metric` | current | Known metric enum from QueryPlan; no arbitrary SQL or expressions. | META-002, FILTER-002, AI-003 |
| `query_plan.filters` | current | Reuse full filter validation, including ownership. | META-002, FILTER-001, FILTER-002, AI-003 |

## Position-sizing inputs

Scope: **mixed**. Sources: `src/Analytics.tsx`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `risk_calculator.balance` | current | Finite decimal >=0; keep blank distinct from 0. | ACC-002, RISK-004 |
| `risk_calculator.risk_percent` | current | Finite 0–100 inclusive; warning threshold proposed at 5%, not a risk recommendation. | RISK-004, RISK-005 |
| `risk_calculator.entry` | current | Positive price. | RISK-004 |
| `risk_calculator.stop` | current | Nonnegative, different from entry; side/instrument metadata needed for direction and valid lot rounding. | RISK-004 |
| `risk_calculator.multiplier` | current | Positive decimal; explicit instrument unit. | RISK-004 |
| `risk_calculator.instrument_id` | proposed | Proposed addition for lot size, step and quote-currency correctness. | RISK-004 |
| `risk_calculator.side` | proposed | Proposed Long/Short to validate stop direction; do not infer direction from a negative number. | RISK-004 |
| `risk_calculator.metric_search` | current | Bounded string; empty shows all metrics. | RISK-004, FILTER-002 |

## AI request form and task context

Scope: **current**. Sources: `src/Coach.tsx`, `backend/jobs.py`, `backend/schemas.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `ai.message` | current | Trim only for emptiness; require meaningful non-whitespace input <=12,000 chars. | AI-001 |
| `ai.mode` | current | Known enabled task code, with a configured backend route. | AI-001 |
| `ai.expected_credits` | current | Integer 0–100,000; must equal the live backend task cost before reserving. | AI-001, AI-002 |
| `ai.thread_id` | current | Optional owned conversation ID, not an arbitrary client bucket. | AI-001 |
| `ai.trade_id` | current | Required owned ID for a trade_note task; reject inappropriate or conflicting task context. | AI-001 |
| `ai.filters` | current | Reuse full filter rules, even when supplied by AI. | AI-001 |

## Generic record endpoint and kind selector

Scope: **current**. Sources: `backend/schemas.py`, `backend/journal_routes.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `record_envelope.data` | current | Object <=200,000 current encoded-size cap; replace generic permissiveness with a per-kind typed shape. | REC-001 |
| `record_envelope.kind` | current | note/playbook/goal/dividend/pin/template/saved_filter only on generic routes. Internal simulation must not be creatable through this route. | REC-001 |

## Notebook and calendar daily reviews

Scope: **current**. Sources: `src/Notes.tsx`, `src/Calendar.tsx`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `note.title` | current | Trimmed 1–200 chars. | REC-001, AI-003 |
| `note.date` | current | Valid YYYY-MM-DD; future dates allowed as planning notes, not execution timestamps. | TIME-001, TIME-002, REC-001, AI-003 |
| `note.mood` | current | Focused/Confident/Neutral/Anxious/FOMO/Revenge or explicitly migrated legacy values. | REC-001, AI-003 |
| `note.body` | current | Non-whitespace Markdown/plain text 1–50,000 chars within the envelope byte cap. | REC-001, AI-003 |
| `note.search` | current | Bounded <=200 string; missing body/title must not crash filtering. | REC-001, AI-003 |

## Strategy playbooks

Scope: **current**. Sources: `src/Notes.tsx`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `playbook.title` | current | Trimmed 1–100 to match trade.setup; warn on duplicate normalized names. | REC-001, REC-002 |
| `playbook.description` | current | Optional plain text/Markdown <=10,000 chars. | REC-001 |
| `playbook.checklist` | current | List <=100 nonempty trimmed entries, each <=500 chars; split lines explicitly. Duplicate conditions warn. | REC-001 |

## Trading process goals

Scope: **current**. Sources: `src/Notes.tsx`, `backend/journal_routes.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `goal.title` | current | Trimmed 1–200 chars. | REC-001 |
| `goal.metric` | current | reviewed/process/count/net_pnl/win_rate. | REC-001, REC-003 |
| `goal.target` | current | reviewed/count: positive integer. process/win_rate: >0 and <=100. net_pnl: positive finite INR decimal, no arbitrary upper business cap. | REC-001, REC-003 |

## Expected and received investment income

Scope: **current**. Sources: `src/Notes.tsx`, `backend/journal_routes.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `dividend.symbol` | current | Resolved eligible security or explicit manual income source, not an index derivative by default. | REC-001, REC-004 |
| `dividend.account_id` | current | Owned account. | REC-001, REC-004 |
| `dividend.date` | current | Valid YYYY-MM-DD; Received in the future warns, Expected in the future is normal. | TIME-001, TIME-002, REC-001, REC-004 |
| `dividend.amount` | current | Positive finite net INR amount; zero is a placeholder warning, negative requires an adjustment record. | FEE-005, REC-001, REC-004 |
| `dividend.status` | current | Received/Expected only. | REC-001, REC-004 |

## Pinned charts and AI insights

Scope: **current**. Sources: `src/Analytics.tsx`, `src/Coach.tsx`, `backend/journal_routes.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `pin.title` | current | Trimmed 1–200 chars. | REC-001, AI-003 |
| `pin.body` | current | Optional safe Markdown <=50,000; body or chart required. | REC-001, REC-005, AI-003 |
| `pin.chart` | current | Typed dimension/metric/rows; max 1,000 rows; finite numeric cells or null; labels <=200; reject active content. | FILTER-002, REC-001, REC-005, AI-003 |
| `pin.filters` | current | Reuse filters; snapshot is labelled with saved time and scope, not live recalculation. | FILTER-001, REC-001, AI-003 |

## Broker mapping templates

Scope: **current**. Sources: `src/Import.tsx`, `backend/journal_routes.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `template.title` | current | Trimmed 1–100; duplicate-name warning. | REC-001, REC-002, IMP-002 |
| `template.mapping` | current | Allowed trade-field keys to actual unique source headers; validate again for each file. | REC-001, IMP-002 |
| `template.defaults` | current | Allowlisted TradeInput defaults; exclude account/user IDs, credits, role and server-derived fields. Contract-dependent defaults must be reviewed per row. | REC-001, IMP-002 |

## Saved journal views

Scope: **current**. Sources: `src/Journal.tsx`, `backend/journal_routes.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `saved_filter.title` | current | Trimmed 1–100; duplicate-name warning. | REC-001, REC-002 |
| `saved_filter.filters` | current | Reuse typed Filters; hidden JSON cannot smuggle an account ID from another user. | FILTER-001, REC-001 |

## Dashboard visibility, reorder and pins

Scope: **current**. Sources: `src/Dashboard.tsx`, `backend/journal_routes.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `dashboard.order` | current | Array containing each supported widget ID once; known migration handles newly added/retired widgets. | FILTER-002, REC-005, UI-002 |
| `dashboard.hidden` | current | Unique subset of supported widget IDs; empty permitted. | FILTER-002, REC-005, UI-002 |
| `dashboard.pin_id` | current | Owned pin record ID when removing or opening a saved insight. | FILTER-002, REC-005, UI-002 |
| `dashboard.dragged_widget` | current | Known widget ID with in-range target position; invalid drag must not insert an empty widget. | FILTER-002, REC-005, UI-002 |

## Stored user preferences

Scope: **current**. Sources: `backend/journal_routes.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `preferences.currency` | current | Server-fixed INR. | REC-005 |
| `preferences.timezone` | current | Server-fixed Asia/Kolkata. | REC-005 |
| `preferences.language` | current | Allowlisted supported language; currently en. Unknown language must not become arbitrary persisted data. | REC-005 |

## Trade and candle file upload

Scope: **mixed**. Sources: `src/Import.tsx`, `src/Simulator.tsx`, `backend/importer.py`, `backend/security.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `import_file.file` | current | CSV/TSV/XLSX only with content validation; current compressed limit 15 MiB, XLSX expansion 60 MiB and 2,000 members. | IMP-001 |
| `import_file.filename` | current | Untrusted display-only basename; bounded length; extension alone does not establish format. | IMP-001 |
| `import_file.sheet` | proposed | Current reader uses active sheet; proposed explicit selection when multiple nonempty sheets exist. | IMP-001 |
| `import_file.encoding` | current | UTF-8/UTF-8 BOM currently; unsupported encoding produces a clear error, not guessed corrupted symbols. | IMP-001 |
| `import_file.headers` | current | 1–100 nonempty unique normalized columns; reject duplicate/blank headers and inconsistent row widths. | IMP-001, IMP-002 |
| `import_file.cells` | current | Bounded 20,000 characters each; no executing macros/formulas/external links. | IMP-001, IMP-007 |
| `import_file.date_format` | proposed | Proposed explicit source profile; resolve day-first/ISO and date-only limitations before commit. | IMP-001, IMP-003, IMP-004 |
| `import_file.quantity_unit` | proposed | Proposed explicit units/lots/contracts per file/profile; do not guess from the header contracts. | QTY-003, IMP-001, IMP-004 |
| `import_file.currency` | proposed | Proposed source quote/fee currency; $ or USDT cannot simply be stripped and called INR. | IMP-001, IMP-004 |

## Trade import preview and commit

Scope: **mixed**. Sources: `backend/journal_routes.py`, `backend/importer.py`, `src/Import.tsx`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `import_payload.account_id` | current | Owned account. | IMP-005 |
| `import_payload.rows` | current | 1–20,000 structured rows; source-row IDs preserved; each row goes through the same trade validator. | IMP-003, IMP-004, IMP-005, IMP-006 |
| `import_payload.mapping` | current | Trade field allowlist -> actual unique file columns; required fields mapped or given safe explicit defaults. | IMP-002, IMP-003, IMP-005 |
| `import_payload.defaults` | current | Typed partial TradeInput; never override supplied row values silently. | IMP-002, IMP-005 |
| `import_payload.template_id` | current | Owned template selection; inspect compatibility with the uploaded file. | IMP-005 |
| `import_payload.warning_acknowledgements` | proposed | Proposed per-row/data-hash acknowledgement; revalidate at commit. | IMP-005 |
| `import_payload.preview_id` | proposed | Proposed server-bound file/account/mapping/policy/catalog snapshot reference. | IMP-005, IMP-006 |

## Replay source and contract

Scope: **current**. Sources: `src/Simulator.tsx`, `backend/journal_routes.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `simulation_create.candles` | current | Array of 5–50,000 OHLC candles; omitted means explicit synthetic practice, not fallback for a malformed empty upload. | INS-002, SIM-001, SIM-003 |
| `simulation_create.symbol` | current | Bounded resolved symbol or clearly labelled practice instrument. | INS-002, SIM-003 |
| `simulation_create.source` | current | Bounded <=200 plain-text source description, not an executable filename/URL. | INS-002, SIM-003 |
| `simulation_create.asset_type` | current | Same instrument compatibility rules as trades. | INS-002, INS-003, SIM-003 |
| `simulation_create.exchange` | current | Same venue validation. | INS-002, SIM-003 |
| `simulation_create.segment` | current | Same contract/segment validation. | INS-002, SIM-003 |
| `simulation_create.lot_size` | current | Same effective lot metadata. | INS-002, SIM-003 |
| `simulation_create.expiry` | current | Same expiry validation with candle execution dates. | INS-002, SIM-003 |
| `simulation_create.strike` | current | Same option-strike rules. | INS-002, SIM-003 |
| `simulation_create.option_type` | current | CE/PE only for options. | INS-002, SIM-003 |
| `simulation_create.initial_balance` | current | Currently server-set ₹100,000; if exposed later, finite >=0 and separate from real account capital. | INS-002, SIM-003 |

## Uploaded OHLCV row

Scope: **current**. Sources: `src/Simulator.tsx`, `backend/journal_routes.py`, `backend/simulator.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `candle.time` | current | Valid zoned instant; strictly increasing unique timestamps; no silent reorder; inferred IST must be shown. | PRICE-001, TIME-001, SIM-001 |
| `candle.open` | current | Positive finite decimal. | PRICE-001, SIM-001 |
| `candle.high` | current | Finite positive, >= open, close and low. | PRICE-001, SIM-001 |
| `candle.low` | current | Finite positive, <= open, close and high. | PRICE-001, SIM-001 |
| `candle.close` | current | Positive finite decimal. | PRICE-001, SIM-001 |
| `candle.volume` | current | Optional finite nonnegative; pair/venue units explicit; null means unknown, not zero. | PRICE-001, SIM-001 |

## Replay trade controls

Scope: **current**. Sources: `src/Simulator.tsx`, `backend/journal_routes.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `simulation_action.action` | current | step/open/close/bracket only; typed discriminated payload by action. | SIM-002 |
| `simulation_action.side` | current | Long/Short; relevant only for open. | SIM-002 |
| `simulation_action.quantity` | current | Positive, valid unit/lot step; no silent default for missing required open order quantity. | QTY-001, QTY-002, SIM-002 |
| `simulation_action.multiplier` | current | Positive and matching instrument metadata. | QTY-002, SIM-002 |
| `simulation_action.fees` | current | Nonnegative INR with explicit scope; opening fees not recharged on close/bracket. | FEE-001, SIM-002 |
| `simulation_action.stop_loss` | current | Optional nonnegative bracket; original order uses entry/current executable price; trailing update compared with current price. | RISK-002, SIM-002 |
| `simulation_action.target_price` | current | Same bracket-context distinction; null explicitly clears. | RISK-002, SIM-002 |
| `simulation_action.count` | current | Integer 1–100, only for step. | SIM-002, SIM-003 |

## Replay selectors and export

Scope: **current**. Sources: `src/Simulator.tsx`, `backend/journal_routes.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `simulation_ui.session_id` | current | Owned saved session, including action/export paths. | SIM-002, UI-001 |
| `simulation_ui.timeframe` | current | 1/5/15/60 bars. Aggregated chart display cannot change execution data. | SIM-002, UI-001 |
| `simulation_ui.indicator` | current | none/sma. | SIM-002, UI-001 |
| `simulation_ui.speed` | current | 1600/900/450 ms; display speed cannot skip validation or submit duplicate actions. | SIM-002, UI-001 |
| `simulation_ui.export_account` | current | Currently server chooses/creates a practice account; future explicit selector must be owned and practice-only. | INS-003, SIM-002, UI-001 |
| `simulation_ui.export_cursor` | current | Server-only checkpoint; no re-export of the same fills or conversion to real performance. | SIM-002, SIM-003, UI-001 |

## Calendar navigation and selected day

Scope: **current**. Sources: `src/Calendar.tsx`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `calendar_ui.month` | current | Valid bounded calendar month; navigations handle leap years and year transitions. | UI-001 |
| `calendar_ui.selected_date` | current | Valid day in the displayed calendar; daily review stores that IST date, not the browser UTC day. | UI-001 |

## All administrative writes

Scope: **current**. Sources: `backend/admin.py`, `src/Admin.tsx`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `admin_common.reason` | current | Trimmed 3–1,000 chars, required; never include secrets. | ADM-001 |
| `admin_common.revision` | current | Positive integer equal to current catalog revision where applicable. | ADM-001 |
| `admin_common.idempotency_key` | current | 8–100 chars; same key + same actor + same payload = same result; changed payload conflicts. | ADM-001 |
| `admin_common.target_user_id` | current | Existing target ID; endpoint-specific roles and account state rechecked transactionally. | ADM-001 |

## Admin user edit

Scope: **current**. Sources: `src/Admin.tsx`, `backend/admin.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `admin_user.display_name` | current | Trimmed 1–100; reject all-whitespace after trim. | ADM-001 |
| `admin_user.suspended` | current | Strict boolean; no self-suspension and no active staff suspension without required owner workflow. | ADM-001, ADM-006 |

## Credit adjustments

Scope: **current**. Sources: `src/Admin.tsx`, `backend/admin.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `admin_credits.amount` | current | Nonzero integer between -1,000,000 and 1,000,000; cannot make current spendable credits negative; applies to current month with ledger/audit. | AI-002, ADM-002 |

## Manual plan access

Scope: **current**. Sources: `src/Admin.tsx`, `backend/admin.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `admin_grant.plan_code` | current | Existing active plan or null for explicit revoke. | ADM-002 |
| `admin_grant.expires_at` | current | Required future instant with zone for grant, within current 3,660-day server cap; null/ignored only for explicit revoke, not a malformed grant. | TIME-001, TIME-002, ADM-002 |

## Plan catalog editor

Scope: **current**. Sources: `src/Admin.tsx`, `backend/admin.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `admin_plan.code` | current | Stable lowercase code [a-z][a-z0-9_]{1,79}; immutable after creation. | ADM-003, UI-002 |
| `admin_plan.name` | current | Trimmed 1–100. | ADM-003, UI-002 |
| `admin_plan.monthly_credits` | current | Integer 0–1,000,000; zero explicitly supported. | ADM-003, UI-002 |
| `admin_plan.trade_limit` | current | Null = unlimited; integer 0–1,000,000 is a limit, including zero. | ADM-003, UI-002 |
| `admin_plan.model_tier` | current | standard/advanced with viable routes for offered AI tasks. | ADM-003, UI-002 |
| `admin_plan.features` | current | Unique subset of implemented backend feature codes. | ADM-003, UI-002 |
| `admin_plan.upcoming_features` | current | Unique subset of known upcoming codes; never grants usable access. | ADM-003, UI-002 |
| `admin_plan.active` | current | Strict boolean; Free fallback cannot be disabled; impact on existing customers previewed. | ADM-003, UI-002 |

## AI task editor

Scope: **current**. Sources: `src/Admin.tsx`, `backend/admin.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `admin_task.code` | current | Existing supported task code; no frontend-only arbitrary task. | ADM-003 |
| `admin_task.name` | current | Trimmed 1–100. | ADM-003 |
| `admin_task.credits` | current | Integer 0–100,000; zero = free AI usage, not subscription entitlement bypass. | ADM-003 |
| `admin_task.enabled` | current | Strict boolean; changes affect new work, not reserved historical job charges. | ADM-003 |

## AI model registry

Scope: **current**. Sources: `src/Admin.tsx`, `backend/admin.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `admin_model.id` | current | Provider/model format <=200; exact registry ID; do not assume an accepted string exists at provider. | ADM-004 |
| `admin_model.name` | current | Trimmed 1–100. | ADM-004 |
| `admin_model.enabled` | current | Strict boolean; disallow disabling a model referenced by an enabled route. | ADM-004 |

## Per-task AI routing

Scope: **current**. Sources: `src/Admin.tsx`, `backend/admin.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `admin_route.task` | current | Existing supported task path code. | ADM-004 |
| `admin_route.tier` | current | standard/advanced. | ADM-004 |
| `admin_route.model_id` | current | Enabled registered response model; check context/capabilities for task. | ADM-004 |
| `admin_route.planner_model_id` | current | Null means response model; otherwise enabled registry model capable of structured planning. | ADM-004 |
| `admin_route.max_output_tokens` | current | Integer 128–16,000, within provider/model context and cost policy. | ADM-004 |
| `admin_route.timeout_seconds` | current | Integer 10–90 per call; combined graph calls must fit worker deadline. | ADM-004 |
| `admin_route.temperature` | current | Finite decimal 0–2 and supported by selected model; no unsupported parameter sent silently. | ADM-004 |
| `admin_route.reasoning_effort` | current | none/minimal/low/medium/high supported or explicitly omitted by adapter. | ADM-004 |
| `admin_route.instructions` | current | Optional <=4,000 chars; additional guidance cannot override data/permissions/core safety. | ADM-004 |
| `admin_route.enabled` | current | Strict boolean; route availability must match advertised AI access. | ADM-004 |

## Subscription prices

Scope: **current**. Sources: `src/Admin.tsx`, `backend/admin.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `admin_price.code` | current | Stable lowercase unique price code; preserve existing history. | BILL-001, UI-002 |
| `admin_price.plan_code` | current | Existing paid plan. | BILL-001, BILL-002, UI-002 |
| `admin_price.interval` | current | month/year. | BILL-001, BILL-002, UI-002 |
| `admin_price.amount_paise` | current | Integer 100–100,000,000 INR paise; not rupees; two-decimal currency conversion only at UI boundary. | FEE-005, BILL-001, UI-002 |
| `admin_price.provider_plan_id` | current | Null or plan_ + alphanumeric <=100; verify exact provider amount, INR currency and interval before activation. | BILL-001, UI-002 |
| `admin_price.active` | current | Strict boolean; at most one offered price per plan/interval per current environment/currency. | BILL-001, BILL-002, UI-002 |
| `admin_price.currency` | current | Server-fixed INR. | BILL-001, UI-002 |
| `admin_price.tax_inclusive` | current | Currently server-fixed true; any future policy must match actual provider/invoice disclosure. | BILL-001, UI-002 |

## Product configuration

Scope: **current**. Sources: `src/Admin.tsx`, `backend/runtime_settings.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `admin_settings.brand_name` | current | Trimmed 1–60. | ADM-005 |
| `admin_settings.support_email` | current | Empty or robust email <=200. | ADM-005 |
| `admin_settings.legal_business_name` | current | Trimmed <=200; nonempty if checkout enabled. | ADM-005 |
| `admin_settings.legal_business_address` | current | Trimmed <=1,000; nonempty if checkout enabled. | ADM-005 |
| `admin_settings.terms_url` | current | Empty or full HTTPS URL <=500, with host and no embedded credentials/control characters. | ADM-005 |
| `admin_settings.privacy_url` | current | Same HTTPS rule. | ADM-005 |
| `admin_settings.refund_url` | current | Same HTTPS rule. | ADM-005 |
| `admin_settings.ai_enabled` | current | Strict boolean; enabled system needs backend key/routes, with readiness shown. | ADM-005 |
| `admin_settings.checkout_enabled` | current | Strict boolean; requires configured secrets, merchant details, policies and usable linked offers. | ADM-005 |
| `admin_settings.maintenance_enabled` | current | Strict boolean; preview public/customer/staff effect before activation. | ADM-005 |
| `admin_settings.maintenance_message` | current | Trimmed <=500, nonempty when maintenance enabled. | ADM-005 |
| `admin_settings.announcement` | current | Optional safe plain text <=500. | ADM-005 |
| `admin_settings.api_requests_per_minute` | current | Integer 30–1,200. | ADM-005 |
| `admin_settings.ai_requests_per_minute` | current | Integer 1–60; cannot exceed overall effective rate or worker budget without warning. | ADM-005 |
| `admin_settings.report_trade_limit` | current | Integer 100–50,000; coordinate with pagination, export and provider token limits. | ADM-005 |

## Staff permissions

Scope: **current**. Sources: `src/Admin.tsx`, `backend/admin.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `admin_staff.user_id` | current | Existing verified unsuspended user. | ADM-001, ADM-006 |
| `admin_staff.role` | current | owner/admin/support only; only owner may change staff. | ADM-001, ADM-006 |
| `admin_staff.active` | current | Strict boolean; cannot remove/demote last active owner. | ADM-001, ADM-006 |

## User, audit, job and model searches

Scope: **current**. Sources: `src/Admin.tsx`, `backend/admin.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `admin_search.q` | current | Trimmed <=100 for users/audit; provider search requires 2–100; escape SQL wildcard meaning. | ADM-007 |
| `admin_search.page` | current | Integer 1–10,000 currently; prefer cursor pagination for large directories. | ADM-007 |
| `admin_search.status` | current | Empty/queued/running/succeeded/failed only. | ADM-007 |
| `admin_search.user_id` | current | Explicit valid target identity; never resolve ambiguous display names to a staff grant. | ADM-006, ADM-007 |

## Subscription selection and checkout

Scope: **current**. Sources: `src/Billing.tsx`, `src/Pricing.tsx`, `backend/billing.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `checkout.price_code` | current | Existing active offer for an active paid plan; readiness, eligibility and current subscription checked. | BILL-001, UI-002 |
| `checkout.expected_amount_paise` | current | Positive integer equal to current backend price; missing/stale quoted price must not open a differently priced checkout. | BILL-001, UI-002 |
| `checkout.interval` | current | month/year presentation preference only; no purchase until explicit offer selection. | BILL-001, BILL-002, UI-002 |
| `checkout.plan` | current | Known plan code from public URL; untrusted navigation hint, never an entitlement or automatic purchase. | BILL-001, UI-002 |
| `checkout.checkout_id` | current | Owned pending checkout; cancel/continue/reconcile only in valid states. | BILL-001, BILL-003, UI-002 |

## Shared paths, headers and body boundaries

Scope: **mixed**. Sources: `backend/auth.py`, `backend/security.py`, `backend/billing.py`, `backend/admin.py`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `request.authorization` | current | Verified bearer identity with current suspension/staff checks; no user/role claims supplied by editable profile. | Schema + base rules |
| `request.resource_id` | current | Valid bounded ID and ownership for trade/account/record/thread/job/session/checkout; use 404 for inaccessible private objects. | Schema + base rules |
| `request.body` | current | Correct content type, syntactically valid JSON, allowed field names, bounded encoded bytes and nesting. | IMP-001, IMP-007 |
| `request.idempotency_key` | current | 8–100 length and operation/actor binding; required for paid, quota-consuming and retryable writes. | AI-002 |
| `request.webhook_signature` | current | Verify signature over raw bytes before parsing or side effects. | BILL-003 |
| `request.webhook_event_id` | current | Bounded provider ID; atomic dedup, owner/subscription binding and out-of-order handling. | BILL-003 |
| `request.webhook_body` | current | Bounded typed event shape; amounts, currency, provider IDs and paid periods verified against provider records. | BILL-003 |
| `request.record_version` | proposed | Proposed conflict check for ordinary edits; avoid overwriting newer trade notes or record values. | SIM-003 |

## Public non-persistent interactions

Scope: **current**. Sources: `src/Landing.tsx`, `src/Pricing.tsx`.

| Input path | Scope | Required behavior | Domain rule IDs |
|---|---|---|---|
| `landing_ui.market` | current | nifty/equity/crypto sample IDs only; clearly illustrative. | UI-001 |
| `landing_ui.candle_index` | current | Integer 0–29, clamped to actual sample length. | UI-001 |
| `landing_ui.chapter` | current | Integer 0–2. | UI-001 |
| `landing_ui.billing_interval` | current | month/year only; pricing derived from loaded catalog, no invented fallback price. | BILL-002, UI-001 |
| `landing_ui.faq_state` | current | Local boolean; no server write. | UI-001 |
| `landing_ui.navigation_hash` | current | Known section IDs or safely ignored unknown hashes; invalid URL encoding must not crash the page. | UI-001 |
| `landing_ui.mobile_navigation` | current | Local boolean; focus/escape/resize behavior cannot trap keyboard users. | UI-001 |
