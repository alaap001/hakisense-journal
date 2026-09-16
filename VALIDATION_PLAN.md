# HakiSenseJournal input validation plan

Planning snapshot: **13 September 2026**. This document specifies what to validate, which problems should block saving, and how to implement the checks consistently. It does **not** mean the proposed checks have been implemented. No application code, live configuration, credits, or database records were changed for this planning task.

The inventory covers **43 input groups and 279 field contracts**: 240 current input, parameter, or displayed-field contracts and 39 proposed fields needed for reliable validation. The catalog contains **78 domain rules, 43 schema rules, and 69 acceptance scenarios**. These counts include API-only parameters and proposed metadata; they are not counts of unique visible form controls.

## 1. Documents and source of truth

| Artifact | Purpose |
| --- | --- |
| [Input matrix](docs/validation/INPUT_MATRIX.md) | Every inventoried field, required behavior, current/proposed scope, and applicable rule IDs. Start here for individual inputs. |
| [Rule list](docs/validation/RULES.md) | Readable domain rules, severity, priority, messages, and evidence of existing checks. |
| [JSON catalog](docs/validation/validation-catalog.json) | Structured field bindings, proposed thresholds, compatibility matrix, rules, examples, and response contract. |
| [UI source inventory](docs/validation/source-inputs.json) | Source locations for 120 JSX control sites, 53 dynamic admin field definitions, and 16 prompt/helper call sites. These categories can overlap. |

The JSON is a **design specification**, not executable validation configuration. Its `implementation_key` values name future allowlisted validators. Never execute rule descriptions as Python, SQL, JavaScript, or model prompts. `current_declaration` preserves source evidence separately from the proposed requirement.

`present_in_code` means a relevant check was located in source. It does not mean every path was tested or that all aspects of the proposed rule are already covered. `partial`, `missing`, and `planned` identify remaining work.

## 2. Correct trading rules before adding restrictions

Entry and exit prices must allow both profits and losses. The suggested rule “long entry should not be less than exit” would reject profitable long trades. Reversing it would reject losing ones. Neither is a valid restriction.

Ignoring charges, for 10 units and multiplier 1:

| Side | Entry | Exit | Gross P&L | Validation |
| --- | ---: | ---: | ---: | --- |
| Long | ₹100 | ₹110 | +₹100 | Valid profit |
| Long | ₹100 | ₹90 | −₹100 | Valid loss |
| Short | ₹100 | ₹90 | +₹100 | Valid profit |
| Short | ₹100 | ₹110 | −₹100 | Valid loss |
| Either | ₹100 | ₹100 | ₹0 | Valid; charges can make the net result negative |

Use these distinct decisions:

- **Quantity must be positive for an executed trade.** Direction belongs in `side`, not a negative quantity. Ordinary shares use integral quantities; crypto uses the instrument's supported precision.
- **Bought puts are long positions in the option premium.** CE/PE does not determine Long/Short. Underlying exposure and premium P&L are separate concepts.
- **Initial stop/target geometry depends on side.** An unexpected stop in a historical journal is a warning: the journal must allow the user to document an actual mistake. A new simulator bracket is validated against its current executable price.
- **Trailing stops can cross the entry price.** A long entered at ₹100, now trading at ₹120, can legitimately have a ₹105 stop. Do not reject this or recalculate original risk from the trailed stop.
- **Zero exit prices need context.** Worthless option expiry or a documented write-off can be valid; a normal stock sale entered as zero needs correction or an explicit adjustment context. A missing value is not zero.
- **Canceled orders and filled trades need separate semantics.** A canceled unfilled order is not a zero-quantity execution. Canceling the remaining quantity of a partly filled order must preserve its actual fills.

## 3. Error, warning, information, or normalization

| Result | Example | Required behavior |
| --- | --- | --- |
| Error | Negative quantity, impossible date, foreign account ID, NIFTY classified as an ordinary stock | Block the operation; explain the correction beside the field. No acknowledgement can bypass integrity or access checks. |
| Warning | Charges exceed recorded trade value; a historical stop is on an unexpected side | Explain the unusual value. Allow legitimate history after explicit review where the rule requires it. |
| Information | Charges turn a gross profit into a net loss | Show the calculation without an unnecessary confirmation dialog. |
| Normalization | ` nifty ` becomes `NIFTY`; a label loses surrounding whitespace | Preserve an understandable change record. Never silently change economic meaning, clear fills, invent an expiry, or reinterpret currency. |

All paths use the same backend rules: manual entry, edit, import, simulator export, AI note append, and future integrations. Frontend validation gives immediate feedback; backend validation remains authoritative. Invalid input must not consume trade quota, reserve AI credits, create payments, or partially mutate records.

For an input with several related issues, show the actionable cause first. For example, resolving the instrument may resolve several derived field errors. If charges trigger both fee warnings, show one explanation with the amounts rather than two confirmation dialogs.

## 4. Important gaps found in the current source

| Area | Existing behavior/evidence | Planned change |
| --- | --- | --- |
| Instrument identity | [markets.py](backend/markets.py) provides suggestions; [TradeInput](backend/schemas.py) accepts a symbol and asset class independently. | Resolve exact identity; reject a known symbol/class conflict. Do not classify by substring. |
| Cross-field consistency | Contract fields and some lot checks exist, but venue, segment, class, currency, and optional derivative fields are not validated as a complete combination. | Apply the compatibility matrix before saving. |
| Position lifecycle | `TradeInput.check_position` overwrites some supplied values and clears exit fields for Open/Canceled records. | Report conflicting input and offer an explicit correction; preserve fills and user intent. |
| Quantity arithmetic | Request financial fields use floats, including lot remainder checks. | Parse exact decimals at the boundary; define units and reject double multiplication. |
| Fees | Positive/nonnegative bounds exist; turnover warnings and explicit fee scope do not. | Add comparable-value warnings and a declared allocation basis, especially for partial trades. |
| Dates | Entry/exit parsing and ordering exist. | Add strict calendar parsing, execution-clock checks, source timezone rules, and historical contract context. |
| Imports | [importer.py](backend/importer.py) maps buy price to entry, sell price to exit, and contracts to quantity by aliases. | Require broker/profile semantics for shorts, execution ordering, and lots versus units. |
| Import ambiguity | Mapping, locale, repeated headers, and source currency can be ambiguous. | Review these before insertion; preserve original values and row provenance. |
| Notes and other records | [validate_record](backend/journal_routes.py) accepts loosely structured `data` objects with a few kind-specific checks. | Define separate schemas for notes, playbooks, goals, dividends, pins, templates, and saved filters. |
| Simulator input | Empty candle arrays fall back to synthetic candles; volume lacks validation. | Distinguish intentional sample mode from uploads; validate shape and OHLCV before creating a session. |
| Simulator actions | One action schema includes unrelated order fields on every request. | Separate step/open/close/bracket contracts and protect repeated actions with versioning/idempotency. |
| Practice provenance | Trade updates currently set `is_demo=False`. | Preserve practice provenance through edits and exports; exclude it from actual-trade reports unless the user explicitly selects practice data. |
| AI input | Cost/ownership checks exist, but whitespace-only prompts and missing task-specific context need stronger checks. | Validate context and exact current cost before any reservation; validate generated results before saving them. |
| Admin and billing | Role, revision, audit, and balance checks exist. Active price uniqueness and some configuration compatibility checks are incomplete. | One active offer per explicit offer key; validate model capabilities, coherent limits, readiness, and nonblank configuration. |

These are source findings, not results from a new application or production test run.

## 5. Instrument selection for Indian markets and crypto

The backend should own a versioned instrument catalog. Search text proposes matches; selecting an exact instrument supplies its class, venue, segment, currency, and contract metadata.

| Input | Resolution behavior |
| --- | --- |
| `NIFTY` | Resolve the known index alias. Ask for the actual listed option/futures contract when recording an execution, or an explicit reference/practice context. Do not save it as an ordinary stock. |
| An exact ETF symbol containing `NIFTY` | Resolve the security's exact catalog entry. A name containing an index name does not make it an index. |
| An option | Identify underlying, venue, expiry, strike, and CE/PE. Never pick the nearest expiry or current lot size automatically. |
| An equity listed on multiple venues | Require the relevant listing/venue when the text match is ambiguous. |
| Unknown, renamed, or delisted historical symbol | Keep a draft or use a reviewed manual historical identity with provenance. Do not pretend a missing catalog match proves a trade impossible. |
| Crypto pair | Preserve venue, base/quote currency, spot/derivative type, quantity step, contract formula, and reporting conversion. `Crypto` alone is not a venue identity. |

NSE describes NIFTY as the underlying for distinct futures/options contracts and points to dated contract files for applicable lot sizes. This plan therefore requires contract metadata effective for the recorded trade, rather than hardcoded current lot sizes or expiry weekdays. Sources: [NSE NIFTY contract details](https://www.nseindia.com/static/products-services/equity-derivatives-nifty50), [NSE contract information](https://www.nseindia.com/static/products-services/equity-derivatives-contract-information).

Keep historical revisions of identity, aliases, lot size, quantity step, tick size, and settlement rules. Store which revision validated each trade. Where an authoritative historical source is unavailable, record the uncertainty and source instead of silently applying today's specifications.

The catalog's compatibility matrix separates equities, ETFs, index references, equity/index derivatives, commodity derivatives, and crypto instruments. A classification is not a claim that its accounting is implemented. Keep instruments requiring unsupported valuation—such as inverse contracts—out of ordinary P&L until their calculation and settlement rules are implemented.

Quantity checks must use explicit units. For the app's NSE/BSE F&O convention, quantity is already in underlying units and multiplier is 1. A fictional lot size of 50 makes quantity 100 valid and 51 invalid; 50 here is a test fixture, **not a statement of any actual contract's lot size**. Average prices from multiple valid fills need not themselves fall on an individual execution tick.

## 6. Trade value, charges, and P&L

For supported linear instruments, when prices and charges share a declared currency and basis:

```text
entry_value         = abs(entry_price × quantity × multiplier)
realized_exit_value = abs(exit_price × closed_quantity × multiplier)
recorded_turnover   = entry_value + realized_exit_value
recorded_costs      = commission + fees
fee_ratio           = recorded_costs / recorded_turnover
```

For an open position, there is no realized exit value yet. For an option, this comparison uses premium value, not underlying notional. A mark is not an execution. Missing exit prices, unknown conversions, unsupported payoff formulas, or unclear fee scope must produce an explanation rather than a fabricated ratio.

Proposed rules:

1. Negative ordinary brokerage/fees are errors. Record rebates or corrections as explicit signed adjustments, preserving their identity.
2. Costs above the combined recorded value produce a strong **warning**, not a universal prohibition. Additional funding, interest, settlement costs, or historical adjustments can exceed execution value.
3. A lower advisory threshold starts at **1%** of comparable recorded turnover, configurable by instrument segment in the backend. This is a typo/review heuristic, not a claim about applicable broker charges or taxes.
4. Costs exceeding gross profit are information: gross ₹100 minus charges ₹150 legitimately produces a net loss of ₹50.
5. Components must not double count brokerage already included in fees. Define whether entered costs cover the whole record, realized fills only, or individual fills.
6. Round only at declared accounting/display boundaries; keep exact internal quantities and financial values. Subscription prices remain integer paise.

Example: 10 units entered at ₹100 and exited at ₹110 have recorded turnover ₹2,100. Charges ₹2,200 trigger the “exceeds value” warning. Charges ₹30 trigger the proposed 1% advisory because ₹30/₹2,100 is approximately 1.43%.

The current [analytics calculation](backend/analytics.py) allocates costs proportionally between realized and remaining quantity. For 4 of 10 units closed, it assigns 40% of recorded costs to realized P&L. That is only appropriate if the entered cost covers the whole record. Preserve existing behavior during migration, label its assumption, and require an explicit basis before changing imported partial-trade calculations.

## 7. Coverage outside the trade form

The input matrix gives individual limits; these are the main cross-field requirements:

| Surface | Required checks |
| --- | --- |
| Authentication/profile | Eight-character minimum for new/reset passwords, provider-compatible maximum, no password trimming; meaningful names, email syntax, allowed redirects, mode-specific fields, valid recovery callbacks. |
| Accounts | Owned IDs, meaningful labels, valid colors, explicit broker identity, balance zero versus missing, deletion dependencies across all record kinds. Editing currency cannot relabel historic money. |
| Filters/search | Allowed enums, bounded strings/pages, start ≤ end, inclusive IST date ranges, ownership, valid saved selections. Zero-denominator analytics show unavailable values. |
| Risk sizing | Valid balance/risk percentage, positive entry, distinct stop, side-aware geometry, correct instrument step and multiplier. Never show Infinity or silently turn empty fields into zero. |
| Notes/playbooks/goals | Typed data, bounded text/checklists, allowed moods/metrics, whole-number count goals, percentage targets within 0–100, duplicate labels reviewed. |
| Dividends | Owned account, exact symbol, valid date/status, declared currency, valid amount; reversals need adjustment semantics. |
| Pins/templates/views/dashboard | Known chart types and fields, bounded snapshots, safe nested JSON, valid unique IDs/order, and revalidated saved filters/mappings. |
| Imports | File type/signature and limits, unambiguous headers, explicit mapping/date/currency/quantity units, per-row issues, duplicate handling, and repeat validation at commit. |
| Replay | Correct candle shape, finite positive OHLC, consistent high/low, increasing timestamps, nonnegative optional volume, valid action state, no future-candle leakage, and durable practice identity. |
| AI | Meaningful input, required task context, owned references, available route/model, current credit quote, entitlement, idempotency, and normal validation of model-generated output. |
| Pricing/checkout | Backend offer identity, paise/currency, current expected price, provider readiness, permitted subscription transition, idempotency, and verified webhook events. |
| Admin users/roles/credits | Authorized operation, exact user ID, revision/reason, immutable audit, no negative balance, explicit grant expiry/revocation, and protection of the last active owner. |
| Admin plans/models/settings | Null versus zero allowance, supported features, truthful upcoming labels, unique active offers, enabled compatible model routes, coherent context/time limits, bounded valid URLs/email, and conditional readiness fields. |
| Landing and themed controls | Allowed billing interval/market/view state; keyboard selection, disabled options, no-results handling, accessible errors, preserved drafts, and protection against repeat submissions. |
| Request boundary | Body/file/JSON-depth limits, strict types, allowlisted fields, owned path IDs, version/idempotency contracts, trusted payment signatures, and safe rendering/export. |

Discounts must come from comparable backend prices: `1 − annual / (12 × monthly)`. Show no savings badge when prices are missing, the baseline is zero, or annual is more expensive. Usage multiples must likewise come from actual current allowances. Do not replace live catalog values with old seed defaults.

## 8. Shared architecture

The following paths are proposed implementation locations; this planning task has not created them:

| Location | Responsibility |
| --- | --- |
| `backend/validation/issues.py` | Stable issue IDs, field paths, severity, safe messages, and normalization records. |
| `backend/validation/policies.py` | Load and validate a versioned backend policy; expose only safe public limits. |
| `backend/validation/instruments.py` | Resolve exact identity and effective contract metadata. |
| `backend/validation/trades.py` | Lifecycle, quantities, prices, dates, fees, and risk checks. |
| `backend/validation/records.py` | Typed records and reusable filter validation. |
| `backend/validation/imports.py` | Broker/source adapters and per-row issues using the same trade rules. |
| `backend/validation/simulations.py` | Candle and action-specific validation with session state. |
| `src/validation/` | Typed response handling, immediate form checks, and shared issue rendering. |

Keep request schemas in the API layer and domain rules reusable beneath it. Build explicit request objects in the frontend before enabling rejection of unknown fields: some current edits spread response objects back into requests. Otherwise, adding `extra='forbid'` would break legitimate workflows containing response-only properties.

Proposed processing sequence:

1. Authenticate, check request limits, parse the declared content type, and enforce strict object/field types.
2. Apply only safe normalizations, preserving supplied values for review where needed.
3. Resolve owned references and instrument metadata; distinguish unresolved from invalid.
4. Validate individual fields and their cross-field relationships using a policy snapshot.
5. Return errors, warnings, and computed context without charging or writing.
6. If review is required, issue a short-lived warning-review token bound to the canonical input, user, resource/version, relevant instrument revision, policy revision, and warning IDs.
7. On save, revalidate. Recheck authorization, quota, price/credit conditions, and versions within the appropriate transaction. Consume the operation idempotently.

Proposed endpoints are `GET /api/validation/policy` for safe public form limits and authenticated `POST /api/trades/validate` for preflight feedback. Existing mutations remain authoritative and must also validate when preflight was skipped. Imports reuse their preview path; a preview is never permission to bypass current write-time checks.

Warning acknowledgement cannot be a plain client-controlled `ignore_errors: true`. Reject stale tokens when relevant inputs or policy change. Bulk import review must be bound to the selected rows and mapping; acknowledging one row cannot authorize a changed row or the whole account.

The JSON catalog includes an example response for an invalid NIFTY/Stocks combination. The normalized symbol remains visible, the class error points to the instrument picker, `can_commit` is false, and no review token is issued for bypassing the error.

## 9. Backend configuration and admin management

Add a **Validation policies** area to the existing admin panel during implementation:

- Show rules, fixed versus configurable status, effective thresholds, scope, revision, reason, and change history.
- Allow authorized admins to edit bounded advisory thresholds, messages, and segment-specific overrides. Owner permissions govern publication according to the existing role model.
- Preview policy changes against saved acceptance fixtures without paid AI calls. Show which outcomes would change before applying a version.
- Publish a coherent revision atomically. Existing form previews become stale when affected rules change.
- Provide a data-quality view for unresolved instruments, ambiguous imports, and reviewed warnings. Corrections use ordinary record authorization and audit rules.

Never make positive executed quantity, access control, finite-number checks, quota/credit integrity, payment verification, or protection of the last owner optional admin settings. Financial accounting formulas are versioned application logic, not arbitrary editable expressions.

Starting configurable defaults are in `proposed_limits`: fee advisory 1%, costs/value warning 100%, price-change review factor 10, risk-percentage advisory 5%, risk-amount comparison tolerance 10%, and execution-clock tolerance 300 seconds. These are proposed review settings, not advice or live configuration. Validate relationships too: the lower fee warning must not exceed the stronger warning threshold; disabled advisory states must be explicit.

Only publish browser-safe policy data. Provider secrets, privileged model instructions, internal security thresholds, staff access, and validation internals remain behind authorized backend APIs. Model selections still come from the existing backend registry and task/tier routes consumed by LangGraph; validators do not choose or call an AI model to decide deterministic correctness.

## 10. Data changes and historical records

Implementation will need versioned instrument metadata and per-trade provenance, explicit units/currency/fee scope, optional fills and settlement context, record revisions, and warning-review history. JSON record kinds need typed schemas and schema versions. Exact-decimal storage changes require inspection of existing database precision and a migration that checks for overflow or changed values; the catalog's proposed precision is not an applied schema change.

Roll out without rewriting legitimate history:

- Run a read-only quality scan first and classify records by rule. Do not assume existing records will satisfy new schemas.
- Preserve raw import values, old instrument revisions, and existing accounting assumptions. Never silently relabel currency, replace lot sizes, change asset classes, or delete fills.
- New writes use the new contract after compatible clients are deployed. Preserve legacy reads; allow corrections through an explicit migration/edit flow. Do not make an unrelated note edit silently normalize an entire old trade.
- Integrity and access restrictions still apply to every write. A record that cannot meet essential integrity rules stays a draft or explicit reference record, outside realized-trade analytics, until corrected.
- Store practice/reference provenance independently of whether a record was edited. Keep paid entitlements and monthly usage separate from validation-warning state.
- Rollback of a policy restores a prior approved policy revision; it does not remove audit history or undo valid trades/payments.

## 11. Implementation order and small verification gates

| Phase | Work | Completion gate |
| --- | --- | --- |
| 1 — Shared foundation | Typed issue response, exact input parsing, blank/null/zero distinction, unknown-field handling with frontend request projection, normalization, state consistency, source provenance. | Invalid basic data produces the same issue through manual entry and import; valid winning and losing positions save without silent field loss. |
| 2 — Instrument and trade correctness | Exact catalog identity, dated metadata, quantity units, compatibility, fees, lifecycle, dates, risk context, currency basis, and historical review flow. | NIFTY cannot become an ordinary stock; legitimate historical, partial, option-expiry, and fractional-crypto cases have explicit outcomes. |
| 3 — Import and replay | Declared broker/date/unit mappings, bounded file parsing, preview-to-commit integrity, duplicate/quota handling, candle/action contracts, practice identity. | One small mixed fixture returns correct row issues; invalid rows cannot slip through commit; repeated replay actions cannot duplicate fills. |
| 4 — Remaining forms and configuration | Typed records, filters, risk calculator, AI context, admin policy editor, model/offer coherence, consistent themed error UI. | Invalid forms do not write, charge, or erase drafts; fixed integrity rules remain non-disableable. |
| 5 — Existing-data rollout | Read-only quality report, explicit corrections, policy revisions, compatible deployment, and migration receipts. | No automatic reinterpretation of old trades; unresolved records remain identifiable and scoped correctly. |

Do not wait until later phases to preserve existing auth, ownership, credit, and payment checks. They remain active throughout. Dependent rules should be enabled only when the required metadata and compatible request contracts exist.

Verification should stay small and relevant: use the catalog's scenarios to build compact deterministic checks for decimal/type boundaries, long/short losses, lot units, status/date conflicts, fee warnings, symbol resolution, import mapping/deduplication, OHLC/actions, warning-token freshness, ownership/credits, admin invariants, and pricing math. A few parameterized tests can cover related scenarios; each of the 69 examples does not need a separate browser test. No paid model calls or repeated end-to-end loops are needed to validate deterministic input rules.

For **this planning task**, verification is limited to parsing the JSON, checking unique IDs and rule references, matching inventoried backend model fields, and checking document consistency. No new application tests, payment attempts, AI generations, migrations, or live-data edits are part of this work.
