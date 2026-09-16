# Validation rule list

Design requirements, not a statement that these checks all exist today. Severity and current implementation evidence are explicit below. Complete input bindings, thresholds and scenarios are in [validation-catalog.json](validation-catalog.json).

## BASE-001 · Strict type and finite numeric validation

**ERROR · P0 · current: partial**

Apply the declared type before business rules. Reject NaN/Infinity, booleans as numbers, malformed numeric strings and fractional integers. UI numeric text becomes a decimal only on valid parsing; API scalar coercion is explicitly specified.

User message: Enter a valid value of the required type.

Applies to: `*`.

Current evidence: `backend/schemas.py`, `backend/journal_routes.py`, `backend/admin.py`.

## BASE-002 · Required, blank, zero and null are distinct

**ERROR · P0 · current: partial**

Trim only fields declared trimmable. Required text cannot be whitespace. Optional absent numeric value is null; 0 is not missing. Never convert an empty input to zero or silently default a malformed value.

User message: Complete this field; a blank value is different from zero.

Applies to: `*`.

Current evidence: `src/Journal.tsx`, `src/Analytics.tsx`, `src/Simulator.tsx`.

## BASE-003 · Enums, IDs and unknown fields

**ERROR · P0 · current: partial**

Use backend-supported enums and typed allowlists. Reject unknown input keys on write DTOs after callers stop resending response-only fields. Snapshot migration adapters can explicitly accept documented legacy fields.

User message: Choose a supported value.

Applies to: `*`.

Current evidence: `backend/schemas.py:TradeInput uses extra='ignore'`, `backend/admin.py:Change uses extra='forbid'`.

## BASE-004 · Size, nesting and safe display

**ERROR · P1 · current: partial**

Enforce per-field limits plus UTF-8 encoded byte budgets and depth caps. Render user text as text/allowed Markdown, never executable HTML; forbid unsafe URL schemes. New proposed limits are in proposed_limits.

User message: This value is too large or uses an unsupported format.

Applies to: `*`.

Current evidence: `backend/schemas.py:RecordInput`, `backend/security.py`, `src/Notes.tsx`.

## BASE-005 · Resource ownership and authorization

**ERROR · P0 · current: present_in_code**

Check authentication, resource ownership, entitlement and role at the server for every operation. Current roles are trusted database membership, not user metadata. Validation previews must obey the same boundaries.

User message: This item is unavailable or you do not have access.

Applies to: `request.*`, `account.*`, `trade.account_id`, `filters.account_id`, `ai.thread_id`, `ai.trade_id`, `admin_common.*`, `checkout.*`.

Current evidence: `backend/auth.py`, `backend/db.py`, `backend/journal_routes.py`, `backend/admin.py`.

## BASE-006 · Non-destructive normalization

**NORMALIZATION · P0 · current: partial**

Return proposed changes separately from issues. Trim/case-normalize exact symbols and trim/deduplicate tags; preserve raw imported values. Never infer side, contract, currency, unit, date format or settlement from an ambiguous label.

User message: Review the suggested correction before saving.

Applies to: `trade.symbol`, `trade.tags`, `template.*`, `import_payload.*`, `auth.email`.

Current evidence: `backend/schemas.py:symbol_upper`, `backend/importer.py:preview_rows`.

## BASE-007 · Versions, deduplication and atomic writes

**ERROR · P0 · current: partial**

Reject stale record/catalog versions; same idempotency key and body replays the result, different body conflicts. Write record, quota, ledger and accepted warnings atomically; recheck ownership and balances inside the transaction.

User message: This information changed. Refresh and review it before saving.

Applies to: `request.*`, `admin_common.*`, `trade.*`, `import_payload.*`, `simulation_action.*`, `checkout.*`.

Current evidence: `backend/jobs.py`, `backend/admin.py`, `backend/billing.py`, `backend/journal_routes.py`.

## BASE-008 · Warnings cannot be forged or reused

**ERROR · P0 · current: planned**

Bind acknowledgements to user, operation, normalized payload hash, relevant record version, policy version, instrument revision and short expiry. A changed field invalidates affected warnings. Errors are never acknowledgeable.

User message: Review the current warnings before continuing.

Applies to: `trade_extension.warning_acknowledgements`, `import_payload.warning_acknowledgements`.

## BASE-009 · Reject writes to server-derived values

**ERROR · P0 · current: partial**

user_id, role, plan status, credits, P&L, fees-derived totals, payment state, is_demo and replay cursor are server-owned. Map editable fields explicitly; preserve system provenance across ordinary trade edits.

User message: This value is calculated or managed by the server.

Applies to: `request.body`, `profile.*`, `simulation_ui.export_cursor`, `admin_price.currency`, `admin_price.tax_inclusive`.

Current evidence: `backend/journal_routes.py:update_trade currently clears is_demo`, `backend/analytics.py`, `backend/billing.py`.

## AUTH-001 · Password and account fields by mode

**ERROR · P0 · current: partial**

Sign-up/reset uses 8–128 characters and matching provider policy; login does not force an existing password through new-password length rules. Validate email without revealing account existence; name required only when creating account.

User message: Use at least 8 characters for your new password.

Applies to: `auth.*`.

Current evidence: `src/Auth.tsx`, `backend/main.py:/api/config`.

## AUTH-002 · Recovery and callback integrity

**ERROR · P0 · current: partial**

Use verified provider recovery/callback state; handle expired/reused codes. Never accept a user-supplied external next URL or reveal tokens in analytics/errors/logs. Do not charge or grant plans from signup query parameters.

User message: This sign-in link is invalid or expired. Request a new link.

Applies to: `auth.code`, `auth.redirect`, `auth.mode`.

Current evidence: `src/authClient.ts`, `src/Auth.tsx`, `src/ProtectedApp.tsx`.

## ACC-001 · Account integrity and duplicate names

**ERROR · P1 · current: partial**

Apply strict AccountInput bounds; trim before min/max checks. An identical normalized account name warns, rather than merging accounts. Reject changing reporting currency or deleting an account referenced by trades, income, practice sessions or saved scope.

User message: Check the account details and linked records.

Applies to: `account.*`, `profile.display_name`.

Current evidence: `backend/schemas.py:AccountInput`, `backend/journal_routes.py:delete_account`.

## ACC-002 · Zero balance and notional mismatch

**INFO · P1 · current: partial**

Zero starting balance is valid but percent return is undefined. Gross derivative exposure can exceed cash balance; no hard rejection on notional-to-balance alone. Negative cash due to a real correction belongs in a separate ledger type.

User message: Starting balance is zero, so return on capital is unavailable.

Applies to: `account.initial_balance`, `risk_calculator.balance`, `trade.quantity`, `trade.multiplier`.

Current evidence: `backend/analytics.py:ratio`.

## INS-001 · Exact instrument resolution

**ERROR · P0 · current: missing**

Resolve exact alias + venue + date + contract metadata. Bare NIFTY/BANKNIFTY/FINNIFTY/SENSEX cannot be equity shares. Do not use prefix matching; NIFTYBEES-like ETF names are distinct securities. Ambiguous derivatives require explicit contract selection.

User message: This is an index. Choose its contract, or record a reference/practice entry.

Applies to: `trade.symbol`, `trade.asset_type`, `trade.exchange`, `trade.segment`, `instrument.*`.

Current evidence: `backend/markets.py:SYMBOLS is suggestions only`, `src/Journal.tsx:asset defaults to Stocks`.

## INS-002 · Asset, venue and segment compatibility

**ERROR · P0 · current: partial**

Use compatibility_matrix; known conflicts block. Changing type displays the now-incompatible fields and asks for correction rather than clearing them silently. Compatibility does not prove a contract exists.

User message: This market segment does not match the selected instrument.

Applies to: `trade.asset_type`, `trade.exchange`, `trade.segment`, `trade.expiry`, `trade.strike`, `trade.option_type`, `simulation_create.*`.

Current evidence: `backend/schemas.py:check_position`.

## INS-003 · Reference index is not a cash execution

**ERROR · P0 · current: missing**

Cash indices are reference instruments. Keep reference/synthetic practice separate from real executed trades and real P&L. A bare index cannot become a real filled stock by acknowledgement.

User message: Select a tradable contract, or save this as reference/practice data.

Applies to: `trade.asset_type`, `trade_extension.record_context`, `simulation_create.asset_type`, `simulation_ui.export_account`.

Current evidence: `backend/schemas.py:Indices currently accepted`, `backend/journal_routes.py:export_simulation`.

## INS-004 · Unknown and historical contracts

**WARNING · P0 · current: planned**

When metadata is absent/stale, keep unresolved row in draft/review. Allow an explicit manually verified historical instrument with required economics and source, audit and unverified label; do not guess or reject delisted securities just because absent from current catalog.

User message: We could not verify this instrument for the trade date. Supply its contract details and source.

Applies to: `trade.symbol`, `trade.expiry`, `trade.lot_size`, `instrument.source`, `instrument.valid_from`, `instrument.valid_until`.

## INS-005 · Option and future identity

**ERROR · P0 · current: partial**

Listed expiring F&O needs expiry and lot metadata; options additionally need strike and CE/PE. Futures cannot carry strike/option type. Spot/equity cannot carry derivative fields. Crypto perpetuals do not need an invented expiry.

User message: Complete the contract details for this instrument.

Applies to: `trade.expiry`, `trade.strike`, `trade.option_type`, `trade.lot_size`, `trade.asset_type`.

Current evidence: `backend/schemas.py:check_position`.

## INS-006 · Effective dates and contract economics

**ERROR · P0 · current: missing**

Use metadata effective for that contract and execution/settlement date. No universal lot, multiplier, tick or expiry weekday; settlement chronology is distinct from trade execution chronology. Block known contradictions; unknown metadata follows INS-004.

User message: These contract details do not match the trade date.

Applies to: `instrument.*`, `trade.lot_size`, `trade.multiplier`, `trade.expiry`, `trade.entry_time`, `trade.exit_time`.

Current evidence: `backend/markets.py:contract_note`.

## INS-007 · Price tick versus average fill

**WARNING · P1 · current: planned**

Exchange tick validation applies to individual execution/order prices with reliable metadata; average prices may legitimately be between ticks. Never round a broker average silently. Strike must resolve to a listed strike, not a generic tick multiple.

User message: This execution price does not match the instrument tick. Verify whether it is an average fill.

Applies to: `trade.entry_price`, `trade.exit_price`, `trade.strike`, `instrument.tick_size`, `trade_extension.fills`.

## INS-008 · Quote currency and crypto contract types

**ERROR · P0 · current: missing**

Require source currency and explicit conversion into INR; USDT/USD amounts cannot be relabelled INR. Linear/inverse crypto contracts need their correct valuation formula; unsupported economics must remain draft, not pass through the stock formula.

User message: Confirm the quote currency, conversion and contract type before calculating INR performance.

Applies to: `trade.symbol`, `trade.entry_price`, `trade.exit_price`, `trade.fees`, `trade_extension.price_currency`, `trade_extension.fx_rate`, `trade_extension.fx_as_of`, `instrument.settlement_type`.

Current evidence: `backend/importer.py:preview_rows strips dollar sign`, `backend/analytics.py:enrich uses linear price delta`.

## QTY-001 · Filled quantity must be positive

**ERROR · P0 · current: present_in_code**

Require positive finite value. Never store negative shares to indicate a short; canonical side is separate. Explicit broker debit/credit sign conversion is permitted only by a reviewed source profile.

User message: Quantity must be greater than zero.

Applies to: `trade.quantity`, `simulation_action.quantity`.

Current evidence: `backend/schemas.py:quantity`, `backend/journal_routes.py:SimAction`.

## QTY-002 · Valid quantity precision and whole lots

**ERROR · P0 · current: partial**

Ordinary equity executions use whole shares. Indian F&O entered in units must be exact multiples of effective lot size, multiplier 1. Crypto uses its configured step. Corporate-action fractional entitlements use explicit adjustment context. Use Decimal, not float modulo.

User message: Enter a quantity in this instrument’s valid share or lot increment.

Applies to: `trade.quantity`, `trade.closed_quantity`, `trade.lot_size`, `trade.multiplier`, `simulation_action.quantity`, `simulation_action.multiplier`.

Current evidence: `backend/schemas.py:check_position currently uses float modulo`.

## QTY-003 · Prevent lots multiplied twice

**ERROR · P0 · current: partial**

If user enters lots, convert once to units using effective lot size and persist original units. For unit-quantity NSE/BSE F&O require multiplier 1; reject contradictory quantity unit and multiplier. MCX/crypto use their own instrument formula.

User message: Confirm whether this quantity is units or lots; it must not be multiplied twice.

Applies to: `trade.quantity`, `trade.multiplier`, `trade_extension.quantity_unit`, `import_file.quantity_unit`.

Current evidence: `backend/schemas.py:multiplier validation`, `backend/importer.py:contracts header alias`.

## POS-001 · Position lifecycle consistency

**ERROR · P0 · current: partial**

Open: closed quantity 0 and no exit. Closed: full quantity, exit price/time required. Partial: 0 < closed < total with realized exit price/time. Contradictions return errors and a proposed normalization, not silent data loss.

User message: The quantities and exit fields do not match this trade status.

Applies to: `trade.status`, `trade.quantity`, `trade.closed_quantity`, `trade.exit_price`, `trade.exit_time`.

Current evidence: `backend/schemas.py:check_position overwrites contradictory exit fields`.

## POS-002 · Canceled is unfilled, not a zero-share execution

**ERROR · P1 · current: partial**

Separate order intent from executed position: canceled unfilled orders may have requested quantity but no executed quantity/P&L; original execution price may be absent. Keep compatibility adapter for existing Canceled records and exclude them from execution counts, P&L and fee-turnover denominators.

User message: Record this as an unfilled order, not a completed execution.

Applies to: `trade.status`, `trade.quantity`, `trade.entry_price`, `trade.entry_time`, `trade.commission`, `trade.fees`.

Current evidence: `backend/schemas.py:Canceled still requires positive entry price/quantity`.

## POS-003 · Profit and loss are both legitimate

**INFO · P0 · current: present_in_code**

Never require exit to be above entry for Long or below entry for Short. Long gross=(exit-entry)*realized_units*multiplier; Short reverses the sign. Same-price exits can lose money after fees. Long PE is long the option premium, not a Short position.

User message: This is a valid trade outcome; review the calculated net P&L.

Applies to: `trade.side`, `trade.entry_price`, `trade.exit_price`, `trade.commission`, `trade.fees`.

Current evidence: `backend/analytics.py:enrich`.

## POS-004 · Scales, averages and open remainder

**ERROR · P0 · current: partial**

Maintain fill-level conservation; closes cannot exceed open quantity. Scale-in averages and partial close averages must be weighted correctly. Until fills exist, label one-entry/average-exit limitations and do not claim per-fill execution validity.

User message: The realized quantity exceeds the available position or its fills do not reconcile.

Applies to: `trade.quantity`, `trade.closed_quantity`, `trade.entry_price`, `trade.exit_price`, `trade_extension.fills`.

Current evidence: `backend/schemas.py:aggregated trade model`, `backend/analytics.py:enrich`.

## PRICE-001 · Price domains and exceptional zero prices

**ERROR · P0 · current: partial**

Execution entry >0; exit/mark >=0 only with reason/source for zero. Planned entry >0 when supplied. Stop/target 0 normally needs correction; allow explicit valid zero-price exceptional contexts. No blanket fixed upper price cap; use precision/storage caps and typo warnings.

User message: Enter a valid price, or explain the zero-price settlement.

Applies to: `trade.entry_price`, `trade.exit_price`, `trade.mark_price`, `trade.planned_entry`, `trade.stop_loss`, `trade.target_price`, `candle.*`, `trade_extension.settlement_reason`.

Current evidence: `backend/schemas.py`.

## PRICE-002 · Unit and scale typo warning

**WARNING · P1 · current: missing**

Flag unusually large price ratios using configurable 10x price-change threshold and instrument context. Suppress expected near-zero expiry outcomes; missing price data is unknown, not proof of invalidity. Do not auto-shift decimal points.

User message: The price change is unusually large. Check the decimal point, unit and contract.

Applies to: `trade.entry_price`, `trade.exit_price`, `trade.mark_price`, `trade.strike`.

## TIME-001 · Dates and timestamp ordering

**ERROR · P0 · current: partial**

Reject invalid dates and malformed/ambiguous timestamps. Compare parsed UTC instants, not arbitrary original strings. Exit >= entry; equality is valid at source precision. Date-only expiry is not forced to midnight before same-day execution.

User message: Enter a valid date; an exit cannot occur before its entry.

Applies to: `trade.entry_time`, `trade.exit_time`, `trade.expiry`, `candle.time`, `filters.start`, `filters.end`, `note.date`, `dividend.date`, `admin_grant.expires_at`.

Current evidence: `backend/schemas.py:valid_date and check_position`, `backend/markets.py`.

## TIME-002 · Future execution versus future plans

**ERROR · P0 · current: planned**

Reject actual execution timestamps beyond configurable five-minute clock-skew allowance; near-future within skew warns. Future note/goal planning dates, expected income and option expiry are allowed. Reference/practice clocks are explicitly separate.

User message: This execution time is in the future. Check the date and time zone.

Applies to: `trade.entry_time`, `trade.exit_time`, `dividend.date`, `note.date`, `admin_grant.expires_at`.

## TIME-003 · Market session checks are contextual

**WARNING · P1 · current: planned**

Out-of-session/holiday entries warn using dated venue calendar and event type. Do not hard-reject all weekends, special sessions, settlements, corporate actions or crypto trading. No calendar data means no claim of verified session validity.

User message: This time is outside the recorded session. Confirm the time zone and event type.

Applies to: `trade.entry_time`, `trade.exit_time`, `instrument.source`.

## TIME-004 · Expiry and lifecycle boundaries

**ERROR · P0 · current: missing**

Known contract execution after expiry blocks; same-day expiry trades and later documented settlement events are distinct valid contexts. Metadata unknown -> review instead of fabricated cut-off. Expired contracts remain valid historical journal entries.

User message: This execution is outside the contract’s valid trading period.

Applies to: `trade.expiry`, `trade.entry_time`, `trade.exit_time`, `trade_extension.settlement_reason`.

## RISK-001 · Original bracket direction

**WARNING · P1 · current: missing**

For an executable new Long bracket: stop < entry < target where supplied; Short reverses. For an already-executed journal record, unexpected planned direction/equality warns because it may document a real mistake. Do not erase the historical plan.

User message: The recorded stop or target is on an unexpected side of entry. Confirm the original plan.

Applies to: `trade.side`, `trade.stop_loss`, `trade.target_price`, `trade.entry_price`, `trade_extension.stop_kind`.

## RISK-002 · Trailing stops and replay brackets

**ERROR · P0 · current: partial**

Replay open order compares with current execution price; bracket update compares with current market price, not original entry. Long trail above entry but below current price is valid; inverse logic for Short. Closing/step actions must not fail on hidden stale order-form values.

User message: The bracket must be on the correct side of the current executable price.

Applies to: `simulation_action.stop_loss`, `simulation_action.target_price`, `trade_extension.stop_kind`.

Current evidence: `backend/journal_routes.py:simulation_action`.

## RISK-003 · Risk amount and excursion consistency

**WARNING · P1 · current: planned**

Compare declared original risk with abs(entry-original_stop)*risk_quantity*multiplier, with defined fee inclusion. Warn only on mismatches over configured 10%; current trailing stop cannot replace original risk. MFE/MAE in INR share the same gross/full-position time window; otherwise mark incomparable.

User message: Check whether risk and excursion values use the same units and observation window.

Applies to: `trade.risk_amount`, `trade.mfe`, `trade.mae`, `trade.stop_loss`, `trade.entry_price`, `trade.quantity`, `trade.closed_quantity`.

## RISK-004 · Risk calculator cannot emit invalid size

**ERROR · P1 · current: partial**

Reject invalid numerics and risk outside 0–100%; entry==stop makes size undefined, not zero/infinity. Zero balance/risk ->0 units with explanation. Round down to valid lot/quantity step once metadata exists; if below one lot show no valid size. Current generic calculator cannot imply brokerage margin or execution eligibility.

User message: A valid position size needs different entry and stop prices and valid instrument units.

Applies to: `risk_calculator.*`.

Current evidence: `src/Analytics.tsx`.

## RISK-005 · High selected risk is advisory

**WARNING · P1 · current: planned**

Warn when chosen risk exceeds proposed configurable 5% of relevant capital. Historical trade entries are not rejected and no investment recommendation is implied by the threshold.

User message: This risk percentage is high relative to the entered balance. Confirm it is intentional.

Applies to: `risk_calculator.risk_percent`, `trade.risk_amount`.

## FEE-001 · Fee fields and scope

**ERROR · P0 · current: partial**

Nonnegative finite costs for these fields; negative rebates belong in a signed adjustment component. Define whether costs are total record or realized portion. Detect brokerage/charges already combined by broker instead of summing duplicate columns.

User message: Enter nonnegative charges and confirm what is included.

Applies to: `trade.commission`, `trade.fees`, `simulation_action.fees`, `trade_extension.fee_scope`, `trade_extension.fee_components`.

Current evidence: `backend/schemas.py`, `backend/analytics.py`, `backend/importer.py`.

## FEE-002 · Charges exceed recorded trade value

**WARNING · P0 · current: missing**

For a supported linear record in one currency, cost_basis_turnover=abs(entry*quantity*multiplier)+abs(exit*closed_quantity*multiplier) when realized. Options use premium, not underlying index notional. When total charges exceed this value and turnover>0, require explicit review; never reject solely due to this ratio.

User message: Charges exceed the recorded entry and exit value. Check INR units, quantity and duplicate charges.

Applies to: `trade.commission`, `trade.fees`, `trade.entry_price`, `trade.exit_price`, `trade.quantity`, `trade.closed_quantity`, `trade.multiplier`.

## FEE-003 · High fee ratio and zero-turnover exception

**WARNING · P1 · current: planned**

Warn above proposed 1% fee/recorded-turnover ratio; per-segment thresholds are admin-editable and not tax assumptions. When turnover is zero (unfilled order/standalone fee) ratio is undefined: review charge source instead of dividing by zero. Suppress duplicate low-severity alert if FEE-002 already applies.

User message: Charges are high for the recorded trade value. Please review them.

Applies to: `trade.commission`, `trade.fees`, `trade.status`, `trade_extension.fee_scope`.

## FEE-004 · Charges consume gross profit

**INFO · P1 · current: partial**

If gross profit >0 and realized allocated costs >= gross profit, show informational net outcome. A profitable price move can produce zero or negative net P&L; do not reject it.

User message: The price move was profitable, but charges consumed the gross profit.

Applies to: `trade.commission`, `trade.fees`, `trade.entry_price`, `trade.exit_price`, `trade.side`, `trade.closed_quantity`.

Current evidence: `backend/analytics.py:net_pnl is net of charges`.

## FEE-005 · Fee totals and monetary precision

**ERROR · P0 · current: partial**

Use decimal monetary math; exact configured scope and currency. Component sums reconcile within defined paise rounding; do not compare repeated binary float calculations. Taxes/levies need dated rules before automated estimates, not hardcoded generic rates.

User message: The charge breakdown does not match the total.

Applies to: `trade_extension.fee_components`, `trade.commission`, `trade.fees`, `admin_price.amount_paise`, `dividend.amount`.

Current evidence: `backend/analytics.py:Decimal math after float DTO conversion`.

## META-001 · Trade text, tags and JSON attributes

**ERROR · P1 · current: partial**

Apply field-specific limits, known moods, integer rating, unique tags and bounded JSON. Typed reserved attributes for delta/gamma/theta/vega/iv need documented units. A response-only privileged key cannot be promoted from attributes to account state. Appending AI text must respect final combined note length.

User message: Check the labels, notes and custom data for this trade.

Applies to: `trade.setup`, `trade.emotion`, `trade.rating`, `trade.notes`, `trade.tags`, `trade.attributes`, `journal_ui.ai_draft`.

Current evidence: `backend/schemas.py`, `src/Journal.tsx`.

## META-002 · Option metadata cannot contradict core fields

**ERROR · P1 · current: missing**

Canonical contract expiry/strike/type live at top level. Reject or explicitly migrate conflicting duplicate values in custom attributes. Analytics must read the canonical fields. IV is a nonnegative fraction and can exceed 1; option-unit delta bounds require stated convention.

User message: The custom option details conflict with the selected contract.

Applies to: `trade.attributes`, `trade.expiry`, `trade.strike`, `trade.option_type`, `query_plan.*`.

Current evidence: `src/Analytics.tsx:Options view currently reads expiry/strike/type from attributes`.

## FILTER-001 · Filter types, ranges and ownership

**ERROR · P0 · current: partial**

All filter entry paths use the same typed validator. start<=end and inclusive IST-day bounds; empty sentinel distinct from invalid date. Limit search lengths; owned IDs only; unknown enums rejected. Invalid persisted filters require repair, not a crashing page.

User message: Choose a valid date range and supported filters.

Applies to: `filters.*`, `journal_ui.date_mode`, `journal_ui.page`, `query_plan.filters`, `saved_filter.filters`, `pin.filters`.

Current evidence: `backend/schemas.py:FilterInput`, `src/WorkspaceApp.tsx`.

## FILTER-002 · Charts and undefined statistics

**INFO · P1 · current: partial**

Allowlisted dimensions/metrics; divisions by zero, missing MFE/marks and no-loss profit factors shown as defined null/infinity labels, never serialized NaN/Infinity. Count actual rows and report truncation; capped results must not look like the complete journal.

User message: There is not enough valid data for this metric.

Applies to: `query_plan.*`, `risk_calculator.metric_search`, `pin.chart`, `dashboard.*`.

Current evidence: `backend/analytics.py`, `src/Analytics.tsx`, `backend/repository.py`.

## REC-001 · Replace arbitrary record objects with typed kinds

**ERROR · P0 · current: partial**

Each supported kind has an explicit schema and limits from the input matrix; reject unknown fields after an explicit legacy migration. Enforce on create AND update AND AI-generated saves, including required bodies, dates, checklist arrays and statuses.

User message: Complete the required fields for this record type.

Applies to: `record_envelope.*`, `note.*`, `playbook.*`, `goal.*`, `dividend.*`, `pin.*`, `template.*`, `saved_filter.*`.

Current evidence: `backend/journal_routes.py:validate_record`, `backend/schemas.py:RecordInput`.

## REC-002 · Names and historical references

**WARNING · P1 · current: partial**

Warn on normalized duplicate names. Prefer stable IDs for new links; renaming a playbook must not silently relabel historical trade setups. Offer a separately reviewed migration when desired.

User message: An item with this name already exists. Keep both or choose a clearer name.

Applies to: `playbook.title`, `template.title`, `saved_filter.title`, `account.name`.

Current evidence: `src/Notes.tsx:rename notice`.

## REC-003 · Goal metric-specific targets

**ERROR · P1 · current: partial**

Counts must be positive integers; percentage targets >0 through100; INR profit target positive finite decimal. Do not apply one generic positive float check to every metric.

User message: This target must use the units and range of the selected metric.

Applies to: `goal.metric`, `goal.target`.

Current evidence: `backend/journal_routes.py:validate_record`.

## REC-004 · Income semantics and dates

**WARNING · P1 · current: partial**

Require account, typed symbol/source, status and valid date; positive received income. Zero placeholder warns; negative correction is separate type. Expected future date valid; future Received warns. Duplicate same-account/source/date/amount warns, not unconditional rejection.

User message: Check the income amount, payment date and whether it is expected or received.

Applies to: `dividend.*`.

Current evidence: `backend/journal_routes.py:validate_record`.

## REC-005 · Dashboard settings and chart snapshots

**ERROR · P1 · current: missing**

Only known widget IDs, valid order/permutation and hidden subset. Pins accept typed chart data or body and known saved scope. No arbitrary scripts/HTML/SQL. Preference keys and language are bounded enums.

User message: This layout or saved chart contains an unsupported value.

Applies to: `dashboard.*`, `pin.chart`, `pin.body`, `preferences.*`.

Current evidence: `backend/journal_routes.py:save_setting and generic pin data`.

## IMP-001 · File boundaries and supported content

**ERROR · P0 · current: partial**

Enforce compressed/expanded/row/column/cell budgets before expensive parsing. Inspect allowed format; reject macros/external link loading/encrypted unsupported workbooks, formula cells without explicit value provenance and duplicate normalized headers. No formula evaluation.

User message: This file is unsupported, ambiguous or exceeds the import limits.

Applies to: `import_file.*`, `request.body`.

Current evidence: `backend/importer.py:read_table`, `backend/security.py`.

## IMP-002 · Mapping and defaults must be explicit

**ERROR · P0 · current: partial**

Each mapping destination is allowlisted and column exists. Required fields supplied. Multiple conflicting source columns do not silently pick first. Shared column use needs a defined transform; defaults must not hide malformed nonempty row data. Inspect source schema whenever loading template.

User message: Review the required columns and conflicting mappings.

Applies to: `import_payload.mapping`, `import_payload.defaults`, `template.*`, `import_file.headers`.

Current evidence: `backend/importer.py:read_table and preview_rows`.

## IMP-003 · Buy/sell is not universal entry/exit

**ERROR · P0 · current: missing**

For Short positions, selling may open and buying may close. Broker execution files need pairing/open-close semantics; buy price/sell price cannot always map to entry/exit. Reject unsupported fills-as-positions import or require an explicit reviewed adapter.

User message: This file needs entry/exit mapping for its position direction. Confirm the broker format.

Applies to: `import_payload.rows`, `import_payload.mapping`, `import_file.date_format`.

Current evidence: `backend/importer.py:ALIASES maps buy price to entry_price and sell price to exit_price`.

## IMP-004 · Date, locale, currency and unit ambiguity

**ERROR · P0 · current: partial**

Preserve raw cell. Reject ambiguous date formats and malformed separators; parse declared day-first/ISO profile, source zone and Excel serial type. Date-only data needs coarse-precision provenance. Do not strip currency symbols and guess INR, or guess contracts versus units.

User message: Confirm this file’s date format, currency and quantity units.

Applies to: `import_file.date_format`, `import_file.quantity_unit`, `import_file.currency`, `import_payload.rows`.

Current evidence: `backend/importer.py:normalize_date`, `backend/importer.py:NUMBERS`.

## IMP-005 · One validator for preview and commit

**ERROR · P0 · current: partial**

Run the exact same rules for manual create/update/import preview/import commit/replay export. Preview reports original row, normalized values, errors and warnings. Commit rechecks current account, policy, dedup and quota; preview is never write authority.

User message: The import changed since preview. Review the affected rows again.

Applies to: `import_payload.*`, `trade.*`.

Current evidence: `backend/journal_routes.py:preview_import and commit_import`.

## IMP-006 · Duplicates and atomic row accounting

**ERROR · P0 · current: partial**

Prefer broker execution IDs. Fingerprint fallback warns about identical-looking legitimate trades; exact known duplicate skips. Catch in-file, existing and concurrent duplicates before counting usage. Credit/trade allowances reflect inserted rows only. No silent partial success; row results enumerate saved/skipped/failed.

User message: These rows already exist or changed since preview. Review the import summary.

Applies to: `import_payload.rows`, `import_payload.preview_id`, `trade_extension.source_trade_id`.

Current evidence: `backend/importer.py:fingerprint`, `backend/journal_routes.py:commit_import`.

## IMP-007 · Safe export round trip

**INFO · P1 · current: partial**

CSV escape formula prefixes as text without destroying genuine signed numeric values. JSON remains parseable and bounded. Export preserves currency, unit, timestamp precision and provenance so re-import cannot silently change identity.

User message: Some values need safe text encoding in the exported file.

Applies to: `trade.tags`, `trade.attributes`, `request.body`, `import_file.cells`.

Current evidence: `backend/journal_routes.py:export_trades`.

## SIM-001 · Validate OHLCV and series type

**ERROR · P0 · current: partial**

Require list/object shape before len/index, valid strictly increasing unique instants, finite positive OHLC with high>=max(open,close,low), low<=min(open,close,high), volume absent/null or finite >=0. Empty uploaded series is an error, not synthetic fallback.

User message: Supply a valid, ordered OHLCV series.

Applies to: `simulation_create.candles`, `candle.*`.

Current evidence: `backend/journal_routes.py:create_simulation ignores volume and uses candles or sample`.

## SIM-002 · Replay action schema and state

**ERROR · P0 · current: partial**

Discriminate by action: step only needs count; close needs position; open requires no position and unfinished session; bracket needs position. Ignore no hidden financial value silently: wrong action fields rejected or excluded by request builder. Validate relevant fields only.

User message: This action is not valid for the current replay state.

Applies to: `simulation_action.*`, `simulation_ui.*`.

Current evidence: `backend/journal_routes.py:SimAction and simulation_action`.

## SIM-003 · Practice provenance, progress and no lookahead

**ERROR · P0 · current: partial**

Server owns cursor, balance, fills and export checkpoint; do not accept future candle fills or replay client P&L. Practice remains practice after export AND edit. Repeated action/export requests do not duplicate fills. Historical candle replay needs disclosed gap/stop-target execution assumptions.

User message: This replay has changed. Refresh its current position and progress.

Applies to: `simulation_create.*`, `simulation_ui.export_cursor`, `simulation_action.count`, `request.record_version`.

Current evidence: `backend/simulator.py:visible and step`, `backend/journal_routes.py:update_trade and export_simulation`.

## AI-001 · Validate before charging or calling a model

**ERROR · P0 · current: partial**

Require nonblank message, allowed enabled mode, owned conversation/trade and typed filters. A trade_note requires trade_id. Missing/stale expected cost returns conflict before reserving. User-supplied model or subscription info never chooses routing.

User message: Review the task, context and current credit cost before sending.

Applies to: `ai.*`.

Current evidence: `backend/jobs.py:enqueue`, `backend/schemas.py:AIRequest`.

## AI-002 · Credit eligibility and exactly-once settlement

**ERROR · P0 · current: present_in_code**

Atomic current balance/entitlement/rate/active-job checks, zero-cost task allowed, one reservation per job, fail/refund once, no automatic paid retry. Model/catalog config snapshot attached to job and used by graph. Invalid inputs consume neither credits nor monthly trade quota.

User message: This task is unavailable or your balance has changed.

Applies to: `ai.expected_credits`, `request.idempotency_key`, `admin_credits.amount`.

Current evidence: `backend/jobs.py`, `backend/entitlements.py`, `backend/worker.py`.

## AI-003 · Generated data uses ordinary validators

**ERROR · P0 · current: partial**

Model-generated plans/charts/notes are untrusted. Validate enums, scoped filters, finite chart rows, output length and safe rendering; save only via normal authorized endpoints. Explanatory AI can suggest a correction but cannot override validation or invent contract metadata.

User message: The generated result needs review before it can be saved.

Applies to: `query_plan.*`, `journal_ui.ai_draft`, `pin.*`, `note.*`.

Current evidence: `backend/ai.py`, `src/Coach.tsx`, `src/Journal.tsx`.

## BILL-001 · Server quote and offer readiness

**ERROR · P0 · current: partial**

Require current expected price, active plan/price, linked matching provider plan, enabled checkout and valid subscription transition. Same key cannot create duplicate external checkout; cancellation only affects authorized eligible subscription. Browser pricing hints do not grant access.

User message: The offer has changed or checkout is not ready. Review the current plan.

Applies to: `checkout.*`, `admin_price.*`.

Current evidence: `backend/billing.py`, `backend/admin.py:save_price`.

## BILL-002 · No ambiguous active offers or invented discounts

**ERROR · P0 · current: partial**

At most one active offer per plan/interval/currency/environment unless an explicit offer-selection model exists. Discount compares same-plan same-currency annual vs 12 monthly total; suppress savings if annual>=monthly*12 or either missing. Credits/8x badge derived from real nonzero baseline.

User message: Resolve duplicate active offers before publishing pricing.

Applies to: `admin_price.active`, `admin_price.plan_code`, `admin_price.interval`, `checkout.interval`, `landing_ui.billing_interval`.

Current evidence: `src/Pricing.tsx:priceDetails finds first active price`, `backend/admin.py:save_price`.

## BILL-003 · Payment and webhook integrity

**ERROR · P0 · current: present_in_code**

Verify raw signature, event ID dedup, retrieved provider objects, subscription ownership, amount in paise, currency, paid status, periods and refund/dispute events. Invalid/stale/out-of-order messages cannot grant access or reset credits twice.

User message: Payment could not be verified yet. Refresh billing after confirmation.

Applies to: `request.webhook_signature`, `request.webhook_event_id`, `request.webhook_body`, `checkout.checkout_id`.

Current evidence: `backend/billing.py:verify_invoice, apply_verified and process_event`.

## ADM-001 · Role, revision, reason and immutable history

**ERROR · P0 · current: present_in_code**

Support is read-only; admin handles authorized catalog/user operations; owner manages staff. Recheck active role in transaction. Require meaningful reason and optimistic revision, audit atomically, preserve immutable price/credit/payment/audit history.

User message: This change is not permitted or the configuration has changed.

Applies to: `admin_common.*`, `admin_staff.*`, `admin_user.*`.

Current evidence: `backend/admin.py:mutate`, `migrations/versions/0003_admin_control.py`.

## ADM-002 · Credit and grant math

**ERROR · P0 · current: present_in_code**

Integer nonzero adjustments cannot make spendable monthly balance negative; current-month only and audit before/after. Grant needs active plan and finite future zoned expiry <=3,660 days. Grant revocation must be explicit and cannot create or cancel a provider payment.

User message: Check the credit adjustment or access expiry.

Applies to: `admin_credits.*`, `admin_grant.*`.

Current evidence: `backend/admin.py:adjust_credits and grant_plan`.

## ADM-003 · Plan and feature catalog consistency

**ERROR · P0 · current: partial**

Trim names; keep immutable supported codes; strict integer limits; null versus zero trade limit distinct; Free remains active. Enabled paid features must have implementations; upcoming metadata never unlocks anything. Preview allowance/feature impact on existing users without resetting spent credits.

User message: This plan has inconsistent limits, features or AI availability.

Applies to: `admin_plan.*`, `admin_task.*`.

Current evidence: `backend/admin.py:PlanChange and save_plan`.

## ADM-004 · Model existence, compatibility and budgets

**ERROR · P0 · current: partial**

Validate ID format and registry identity, enabled references, capability-compatible parameters and response/planner requirements. Check output+input context budget and graph aggregate timeout. Warn on stale/unverified provider catalog; do not make a paid model call merely to validate a dropdown.

User message: This model or parameter combination is not available for the selected task.

Applies to: `admin_model.*`, `admin_route.*`.

Current evidence: `backend/admin.py:save_model and save_route`, `backend/runtime_settings.py:routing`.

## ADM-005 · Product settings and readiness

**ERROR · P0 · current: partial**

Use strict bounds, robust email/HTTPS validation and nonblank conditional fields. No embedded credentials or control characters in URLs; do not fetch arbitrary admin URLs during validation. Checkout activation requires matching offer/payment readiness; AI/rate/report limits stay coherent.

User message: Complete the required settings before enabling this service.

Applies to: `admin_settings.*`.

Current evidence: `backend/runtime_settings.py:ProductSettings`, `backend/admin.py:save_settings`.

## ADM-006 · Last owner and staff identity

**ERROR · P0 · current: present_in_code**

Use unique verified user ID, not ambiguous email/name search match. Only owner assigns staff; never remove final active owner, self-suspend or suspend active staff via ordinary user-edit bypass.

User message: Keep an active owner and use the staff-access workflow for this change.

Applies to: `admin_staff.*`, `admin_user.suspended`, `admin_search.user_id`.

Current evidence: `backend/admin.py:save_staff and update_user`.

## ADM-007 · Search and pagination inputs

**ERROR · P1 · current: partial**

Validate query bounds and job status enum before querying; escape LIKE wildcard input and use parameterized queries. Page sizes bounded; stale user selection cannot carry into another record after a search update.

User message: Enter a supported status, page or search term.

Applies to: `admin_search.*`.

Current evidence: `backend/admin.py:users, jobs, audit, provider_models`.

## UI-001 · Control behavior and error access

**ERROR · P1 · current: partial**

Invalid numbers stay editable strings; do not replace partial input with 0. Associate messages with fields, show first invalid field on submit, preserve form content, prevent double-submit and reset stale selection/error state when dependent fields change. Search/select supports keyboard, disabled options and no-results without selecting hidden values.

User message: Review the highlighted fields.

Applies to: `journal_ui.*`, `landing_ui.*`, `calendar_ui.*`, `simulation_ui.*`.

Current evidence: `src/Select.tsx`, `src/SuggestInput.tsx`, `src/Analytics.tsx`.

## UI-002 · No silent change of destructive or financial intent

**ERROR · P0 · current: partial**

Changing dependent fields previews affected values; do not clear exit fields, money, contract details or saved source context silently. A confirmation handles user intent; backend validation/ownership remains mandatory after confirmation.

User message: This change affects existing values. Review them before saving.

Applies to: `trade.status`, `trade.asset_type`, `account.currency`, `checkout.*`, `admin_plan.*`, `admin_price.*`, `dashboard.*`.

Current evidence: `src/Journal.tsx`, `src/Billing.tsx`, `src/Admin.tsx`.
