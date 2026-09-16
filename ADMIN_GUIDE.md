# Administration guide

The admin workspace is available at **`/admin`** after signing in as assigned staff. Its link appears in the sidebar. No existing account was promoted automatically.

## Assign your first owner

Register and verify the HakiSense account you want to use. From the repository, run this operator-only command with your own email:

```bash
.venv/bin/python scripts/bootstrap_admin.py --email your-email@example.com
```

It uses the migration credential already configured in `backend/.env`. It refuses unverified/suspended accounts and refuses to bootstrap again once an active owner exists. It records the assignment in the audit log. There is no public endpoint that can promote the first visitor.

Refresh the app, open Administration, find a user under **Users → Manage → Staff access**, and choose their role. You can also manage assignments under **Staff access**.

| Role | Capabilities |
| --- | --- |
| Support | Read account, wallet, purchase, configuration, job metadata and audit summaries |
| Admin | Support access plus account changes, wallet adjustments, packs, payment reconciliation, workflow availability, models and product settings |
| Owner | Admin access plus staff assignment/removal |

The last owner cannot be removed. Verified, unsuspended accounts can receive staff access; credit purchases never confer administration privileges.

## Admin screens

- **Overview:** users, paid recharges, final credit charges this IST month, currently reserved AI credits, recorded agent usage, queue and readiness. Charges are attributed to the month a workflow finishes; open reservations can span months.
- **Users:** search accounts; inspect wallet balances, ledger consistency, credit activity and recharges. Adjust credits with a reason; positive amounts are non-expiring, negative amounts cannot create debt. Suspend accounts or edit names. Owners manage staff.
- **Recharge packs:** create/edit names, credits, INR amounts in paise, first-purchase-only eligibility, display order and availability. Existing purchases retain their saved terms.
- **Payments:** inspect recharge states, refunds and credits retained. Reconcile fetches current payment-provider data; it cannot initiate a new payment or issue a cash refund.
- **AI configuration:** the exact versioned credit buckets, task names/availability, Standard/Advanced answer and planning models, per-call output limits, stream read timeouts, reasoning and writer style instructions. Model lookup reads metadata without generation.
- **Product settings:** free monthly credit grant, playbook creation charge, standard comparison rate, merchant/support policies, AI/checkout switches, maintenance and request limits.
- **Staff access / Audit trail:** role assignment and immutable administrative change history.
- **AI operations:** filter by status, task, workflow ID or user ID. Inspect accepted maximum, current reservation, actual charge, released credits, total/cache/reasoning token usage, receipt count, saved model roles, pricing version and lifecycle timestamps. Paused and stopping states are explained. Historical fixed-price jobs are identified, including refunded legacy failures. Private prompts, answers, evidence, clarification text and specialist responses are excluded.

## Wallet rules

AI uses `workflow-buckets-v1`. Choose the smallest bucket containing both total input and total output across all agent calls:

| Input at most | Output at most | Credits |
| ---: | ---: | ---: |
| 8,000 | 2,000 | 1 |
| 16,000 | 4,000 | 2 |
| 32,000 | 6,000 | 3 |
| 64,000 | 8,000 | 4 |
| 128,000 | 16,000 | 7 |

The operational limit is **100,000 input and 16,000 output per workflow**. The 128k pricing row does not increase that limit. 5,000 input plus 3,000 output costs 2 credits. Cached input and reasoning output are already included in the totals. Standard and Advanced share this policy; their model routes differ.

The buckets are displayed as backend-defined policy, with no per-task price or Advanced multiplier editor. Retired `credits` writes to the task-edit API are rejected. Existing legacy database values remain historical and do not price new jobs. Creating a playbook retains its separately configurable charge.

Wallet operations lock the account and append a unique, sequenced ledger entry. The highest affordable bucket, up to 7 credits, is reserved automatically when the job is created. Older clients may still specify a smaller maximum. Success settles the actual bucket once and releases the unused portion. Stopping charges already performed work; failure refunds the reservation. Free credits are consumed first. Unused free reservations released after their month expires do not become purchased credits; platform-failure compensation retains the existing non-expiring rollover refund policy.

The overview separates final charges from open reservations. Failed legacy jobs may retain their old quoted price in storage; operations correctly display a zero final charge and a refunded reservation. Receipt totals for finished workflows include recorded usage from failures and stops. Unknown usage and older jobs without receipts cannot provide a complete provider-cost accounting ledger.

Purchase refunds remove proportional credits rounded up; disputes hold the purchase's credits until won. If credits have already been used, the wallet records debt instead of silently forgetting it. New credits repay the balance. Cash refunds are issued through the payment provider, then reconciled here.

Monthly free-credit changes apply to the next grant and new accounts, not retroactively to existing months. Added administrative credits do not expire. First-purchase eligibility is claimed under the account lock and stays used after a paid purchase, including a refund. An unpaid claim is released only after provider-confirmed cancellation/expiry.

## Database configuration and LangGraph

Runtime model selection now comes from `journal.ai_routes` and `journal.ai_models`, not the environment or a browser-supplied model ID. `backend/ai_models.json` is only the initial bootstrap catalog and is not a runtime override.

1. The backend validates the user, selected task, Standard/Advanced mode and available credits.
2. It loads that task's Standard/Advanced route from PostgreSQL and validates its model registry entries.
3. It saves the route, limits, instructions, model IDs and credit reservation atomically with the job.
4. The worker passes the saved route into LangGraph. The planning agent chooses evidence; deterministic tools select the requested cohort and calculate facts; the answer agent responds directly. Concepts skip trade retrieval. There is no mandatory investigation/review loop.
5. Successful results settle once. Failures refund the original reservation. Administrative edits affect subsequent jobs without restarting workers.

Default Standard routes use `qwen/qwen3.7-flash`; Advanced routes use `z-ai/glm-5.3-flash`. All six tasks have both routes. The registry includes the other requested alternatives. Provider availability and model-specific parameter support still matter; catalog search reads current metadata but does not run or benchmark a model.

The workflow-wide limits apply across all agents. The route output setting is an additional **per-call ceiling**, now defaulting to 16,000 instead of 2,400. Planning disables optional reasoning and keeps most output capacity for the answer agent. If an endpoint explicitly requires reasoning, planning uses low effort instead. The saved reasoning setting applies to the answer. The per-call output ceiling includes reasoning: a small ceiling can truncate an otherwise valid answer. Keep 16,000 to allow the answer to use the remaining shared capacity. Each provider stream has a configurable read timeout up to 90 seconds; the complete workflow has a 30-minute execution timeout. Human-input pauses release the worker and do not expire automatically.

Input size is estimated before dispatch for the current provider and checked against actual native usage afterward. This is not exact native-token enforcement before a provider call. Overruns fail and refund, rather than producing an over-budget successful charge. Model quality and provider availability need separate evaluation when routes change.

## Configuration boundaries

Product settings are stored in `journal.platform_config`. Catalog edits require the revision that was opened in the editor; stale saves are rejected instead of overwriting someone else's change. Close and reopen the editor to load the current revision after a conflict. Writes require a reason and idempotency key, and their audit entry commits with the database change.

OpenRouter/payment secrets, database connections, Supabase project selection, TLS/domain and email delivery stay in deployment secrets/configuration. The panel does not display or accept those secret values. Environment model, policy and checkout values are bootstrap defaults once the database is initialized; edit their runtime equivalents in the panel.

The app's signup and password-recovery forms now require **8 characters**. Supabase Auth also has a project-level password policy: it must allow that length, and should be configured to enforce an eight-character minimum directly. That external project setting is not changed by the product admin panel.

Maintenance mode blocks customer API access while active staff retain administration access. Suspending a user blocks application requests; it does not delete their Auth identity or purchase history. Self-service account deletion, emailing users from the panel, provider refund issuance and arbitrary SQL execution are not admin capabilities in this build.

## Database security

Application administration uses the restricted `hakisense_admin` role with a transaction-local actor ID. Policies check active membership and the required role. Regular customer transactions still use `hakisense_api` and their own tenant ID. There is no superuser or RLS-bypass credential in runtime processes.

A safe directory mirrors only Auth user ID, email, creation, confirmation and last-sign-in timestamps into `journal.user_directory`. An invoker-rights Auth trigger keeps it synchronized; deleting an Auth user cascades its directory row. The sync role can modify only the directory. The admin role has no direct access to Auth tables, passwords, session tokens, customer prompts or journal messages.

Migration `9dd7527249ac` extends the existing staff-membership RLS policy with column-level access only to workflow usage, accepted maximum, pricing version, saved route, cancellation flag and heartbeat. It grants no access to job request/result/checkpoint/pause payloads, events or private agent receipts. New wallet, ledger, pack, purchase and routing tables use forced RLS. The old commercial tables are retained only as restricted historical records; their runtime models and routes have been removed. Future QA/prod environments should use separate Supabase projects and secret sets.

Public `/pricing` and the account wallet expose only the customer credit range. Token buckets, usage, saved routes and limits are Admin-only. Deep Researched Stock Analysis is explicitly coming soon, with no active task or claimed availability.


## Guided tour

The first-login tour is account-specific, uses saved progress and can be replayed by the customer from Help. It is described in Product settings but is not exposed as a global switch or a credit-priced task.

## Verification

```bash
.venv/bin/python -m unittest discover -s tests -q
npm run build
.venv/bin/python scripts/verify_admin_db.py
```

The PostgreSQL script tests the actual catalog, overview and operations functions with temporary staff and job fixtures under restricted roles. It verifies support read-only access, owner edits, membership revocation and denial of private payloads. All fixture changes roll back. Pass `--test-migration` to also exercise the metadata permission migration in that rolled-back transaction before applying it.

The isolated browser check covers task editing without fixed prices, route saves, workflow receipts, zero-valued settings, support read-only controls and desktop/mobile layout. No paid AI calls or real account edits are required for these checks.

The initial Admin update was verified on 15 September 2026 with 61 Python tests, production frontend build, PostgreSQL verification before and after applying migration `9dd7527249ac`, and the isolated browser checks all passed. Browser checks reported no page errors or horizontal overflow at 390px. No paid model calls were made for the Admin update.

Synthetic previews: [credit policy](docs/admin/screenshots/admin-policy.png), [workflow details](docs/admin/screenshots/admin-workflow-detail.png), [mobile](docs/admin/screenshots/admin-mobile.png).


## Latest AI simplification

The updated [AI handoff](../ai-workflow-redesign/README.md) replaces the four-agent review loop with two model roles and database-level latest-N selection. Internal capacity problems no longer ask customers to choose token limits; human input is only for genuine question ambiguity. Customer progress and receipts omit token counts, buckets and operational metadata. Historical capacity pauses can resume under the corrected graph. No additional database migration is required for this correction.


AI failures can be traced locally in `logs/worker.log` by the workflow ID shown in AI operations. `logs/api.log` contains HTTP request logs. The 15 September chat output-ceiling repair appears in audit history as `routing.repair_output_ceiling` under the maintenance actor, with exact before/after values. Provider rate limits are shown to customers as temporary service unavailability with refunded credits.
