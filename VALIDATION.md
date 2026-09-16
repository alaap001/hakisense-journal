# Current verification · pay as you go

- `0008_pay_as_you_go` applied to HakiSenseJournal Supabase. Preflight: zero recurring mandates, pending recurring checkouts and active AI jobs.
- Frontend production build passed (existing bundle-size advisory remains).
- Bounded offline coverage: persistent credit buckets, month rollover, refunds, debt, idempotency, server-verified recharge settlement, signed duplicate webhooks, first-purchase protection, admin audit/permissions, configurable model routing, playbook charges and owned stable trade links. All calls use local fixtures/mocked providers.
- Live PostgreSQL checks confirmed current pack prices, exact wallet/ledger sums, forced RLS, denied cross-user wallet access, denied ledger rewrites and read-only support access. Test fixtures rolled back.
- Real-backend public pricing rendered correctly. No real purchase, email or paid generation was used in this change.
- Runtime recurring billing and plan gates were removed; old tables remain restricted historical records. Earlier checks below describe prior versions, not current commercial behavior.

## Still external

Payment-provider test-mode/live activation, registered webhooks, host scheduler for reconciliation, public domain/TLS and production email delivery remain deployment steps. No load test or comprehensive browser regression was performed.

<details><summary>Historical verification record (superseded where commercial behavior changed)</summary>

# Verification record

Production migration checks completed on 12 September 2026. Verification was deliberately bounded; no load-testing campaign, repeated model evaluation or exhaustive browser regression suite was run.

## Completed

| Check | Result and boundary |
| --- | --- |
| `npm run build` | Passed TypeScript and Vite production compilation after the final UI changes. Auth loads separately from the workspace; Vite still reports a nonblocking chunk-size advisory. |
| `scripts/smoke.py` | All 10 focused checks passed in an isolated temporary SQLite database, with no provider calls. |
| Supabase migrations | `0001_production` and `0002_queue_integrity` applied to project `gdyhnquqflgnjqlnhqog`, PostgreSQL 17.6. |
| Real PostgreSQL isolation | `scripts/verify_supabase.py` passed: all 19 app tables have RLS enabled/forced; cross-user reads, updates and inserts are denied; missing tenant context sees no tenant rows. Fixtures rolled back. |
| Runtime permissions | Real restricted role could not update the plan catalog or existing credit history. `anon` and `authenticated` could not access the private schema. Runtime is neither superuser nor RLS-bypass. |
| Auth service and models | Read-only metadata check passed. Email confirmation is enabled. Both default model IDs were listed by OpenRouter; optional `z-ai/glm-flash-latest` was not listed. |
| Real sign-in and persistence | Disposable confirmed Supabase Auth account signed in, received its 50-credit Free allowance, created an INR fixture trade, downloaded its export and was denied paid replay. Account and all associated app fixtures were deleted afterward. |
| Real AI flow | One paid Qwen summary through LangChain/LangGraph/OpenRouter returned nonempty content. The job result and conversation persisted, and the 5-credit reservation settled to a 45-credit balance. No additional paid calls were made for regression checks. |
| Running preview | `/api/ready` returned `ready` against Supabase. The browser rendered the new Indian-market sign-in screen. A separate AI worker process was started; no worker errors appeared during the startup observation. |

The 10 core checks cover missing/forged authentication, removed local endpoints, cross-user CRUD/export, atomic trade quota and batch rollback, deletion without quota refund, stale credit-price rejection without deduction, idempotent AI requests/results/refunds, private conversations, IST month/day boundaries, backend subscription gates, browser plan-tampering rejection, paid invoice/cancellation/refund reconciliation, Indian contract validation and forged webhook rejection before provider calls.

The live AI check enqueued and settled a real job but invoked its graph directly under a controlled disposable fixture. Worker startup was observed separately; a production process crash/recovery exercise was not performed. The automated payment checks use provider fixtures, not real Razorpay transactions.

## Not yet verified or activated

- Advanced-model generation: model availability checked, no paid advanced-model request made.
- Public signup confirmation and password-reset email round trips: require production SMTP and redirect settings. No email was sent by the validation scripts.
- Razorpay test/live checkout, renewal, webhook delivery and refunds with the merchant account: keys, provider plans, webhook configuration and merchant policies remain required. Checkout is disabled.
- Public-domain deployment, TLS reverse proxy, actual Docker image build/run, backup restoration/PITR, production monitoring and sustained concurrency. Packaging is implemented; these are environment-dependent release steps.
- Full authenticated UI/browser regression, mobile/device matrix and independent security audit.
- Live broker connections, order execution and licensed market data: not implemented capabilities, rather than untested integrations.

See [DEPLOYMENT.md](DEPLOYMENT.md) for the operator steps. The old `data/journal.db` was not modified, reset or assigned to a Supabase user. Routine `scripts/smoke.py` checks do not touch Supabase or the user's journal.

## Advanced administration update

- Migrations through `0006_user_directory` applied. The real database contains 26 application tables with RLS enabled and forced, an Auth directory synchronization trigger, protected admin membership/audit tables and twelve task/tier model routes.
- Initial task prices verified after the one-time reduction: trade note 1, chat 2, summary 2, daily 3, query 4 and coaching 5. Password forms read the backend's eight-character minimum.
- **19 offline checks passed**, including nine administration checks: unauthorized/self-promotion denial, support read-only behavior, catalog revisions and audit idempotency, safe credit adjustments and plan grants, model snapshots, separate planning/response routing through LangGraph, last-owner protection, price-history protection, feature/settings enforcement and downgrade/bonus refund accounting. These make no provider calls.
- Real database verification passed after adapting to Supabase's protected Auth schema: admin access reads a narrow synchronized directory, not Auth tables. Ordinary/support writes were denied, owner edits allowed, revocation immediately effective, and passwords, prompts and history rewrites denied. All role fixtures rolled back.
- One disposable Auth account was created, signed in and deleted after the directory trigger was installed. Onboarding, INR journal persistence, free allowance, paywall and export passed. **No email, AI generation or payment was sent during this administration update.**
- No real user received administrator access. `scripts/bootstrap_admin.py` is provided for the owner to run. Authenticated admin browser interaction with a real staff account remains unverified until that account is assigned; TypeScript/Vite compilation and API/database behavior were checked.
- Final admin frontend build passed after adding direct user-to-staff assignment and backend-driven feature labels. Vite retains its existing nonblocking bundle-size advisory.
- Updated API, frontend preview and separate AI worker were started. `/api/ready` confirmed the configured database is reachable after restart.

## Landing and pricing update — 13 September 2026

- Frontend TypeScript + Vite build passed. The existing large workspace bundle advisory remains. Public landing and pricing are separate lazy-loaded pages.
- 21 offline checks passed in 1.611 seconds, including the public catalog response, absence of provider IDs, and admin-editable upcoming features remaining separate from entitlements. No AI provider calls or payments.
- Applied `0007_landing_pricing` to Supabase. A read-only verification confirmed the four active offer amounts, retained old annual prices, Advanced-only upcoming research metadata, and unchanged plan RLS.
- Browser checked: public landing, mouse and keyboard market selection, monthly/annual price switching, signup routing, desktop and 390px mobile layout with no horizontal overflow.
- A temporary isolated dialog confirmed controlled and default-value selections, searching a 12-option list, free-text symbol suggestions, and the resulting FormData values. Fixture removed after verification. No account or administrator was created.
- Coming-soon stock research is not implemented. New offers do not become purchasable until their payment-provider plan IDs and checkout requirements are configured. No load test or broad authenticated UI regression was performed.

</details>
