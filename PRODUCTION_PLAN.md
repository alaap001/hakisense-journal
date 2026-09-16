> Historical design: commercial behavior is superseded by [the implemented pay-as-you-go design](docs/PAY_AS_YOU_GO.md).

# HakiSenseJournal production migration

## Product decisions

- India is the default: INR, Indian number formatting, Asia/Kolkata sessions and reporting, NSE/BSE stocks and index derivatives, and crypto recorded in INR.
- Free: 100 new trades per calendar month, 50 monthly AI credits, journal, basic analytics, calendar, notebook, CSV import/export and account management.
- Pro: ₹400/month or ₹2,499/year, 1,000 monthly credits, unlimited trade entries, replay, playbooks and saved journal views.
- Advanced: ₹8,999/year, 8,000 monthly credits, every Pro feature and a separately configured advanced AI model. No unrequested monthly Advanced price is invented.
- Backend tables own plan prices, allowances, feature grants and task credit costs. UI renders these values. Trades never consume AI credits. Deleting trades does not refund the monthly entry allowance.
- Credit periods are calendar months in India, including annual subscriptions. Unused credits expire; upgrades increase the current month's allowance by the difference. Subscription access is valid only through a verified paid period.
- Razorpay is the implemented INR recurring billing adapter; checkout stays disabled until merchant configuration is supplied. An adapter boundary permits a later provider change. Payment secrets and OpenRouter keys are deployment secrets, with no user-facing key entry.

## Build order

1. Introduce environment configuration, Supabase Auth, private Postgres schema and versioned migrations. No automatic SQLite migration, production demo seed or anonymous workspace.
2. Add tenant-scoped database access, forced row-level security, exact numeric storage, ownership constraints, bounded requests and shared rate limits.
3. Implement backend plan catalog, transactional monthly allowances, immutable credit ledger, feature enforcement and subscription records.
4. Add idempotent Razorpay checkout, signature verification, paid-invoice reconciliation, cancellation and webhook handling. Never grant subscriptions from a browser success callback.
5. Move LangGraph AI calls to durable Postgres jobs. Reserve credits atomically; use idempotency keys; settle once on success; refund on failure. Workers never retry provider calls automatically after an uncertain result.
6. Replace local settings with account/preferences, billing and usage pages. Add Supabase sign-in, registration, verification and password recovery. Authenticate downloads too.
7. Convert journal, import, replay and AI prompts to Indian markets. Record exchange, segment, contract expiry/strike/option type and explicit lot size. Do not hard-code changing contract lots or estimate statutory charges.
8. Package an API/web container, worker, migrations, CI and operator runbook. Perform a bounded set of checks for auth/isolation, credits, paywalls, payment replay safety, IST boundaries and a frontend build.

## Data and security design

`journal` is a private Postgres schema, separate from the earlier SQLite workspace and any existing Supabase public tables. Tenant rows have `user_id`. Runtime transactions assume a non-bypass role and set the verified user's ID transaction-locally. Application filters and database RLS both enforce ownership. Supabase's public browser key only handles Auth; it cannot write balances, prices or subscriptions.

Separate modules own authentication, billing, entitlements, credits, AI jobs, journal analytics and market conventions. Postgres holds the durable job queue and rate counters, allowing multiple API/worker processes without in-memory credit or payment authority. Locks and uniqueness constraints protect grants, reservations, imports and webhooks.

AI requests send only the requesting user's bounded journal context to the backend-selected OpenRouter model. The browser never chooses model IDs or credit charges. Task prices are displayed before requesting AI. Provider errors are sanitized; failed tasks refund the reservation. Logs contain request/job identifiers rather than journal text or secrets.

## Connection and release gates

Target: HakiSenseJournal, `https://gdyhnquqflgnjqlnhqog.supabase.co`. Credentials in `backend/.env` were used to connect directly because a Supabase MCP tool was not exposed. Migrations `0001_production` and `0002_queue_integrity` are applied. The generated restricted runtime login is configured separately from the admin connection. RLS was verified against the real project with rollback-only fixtures.

Default model routing is configured in `backend/ai_models.json`: Free/Pro use `qwen/qwen3.7-flash`, Advanced uses `z-ai/glm-5.3-flash`. The backend file allowlists the other requested alternatives. Both defaults were found in the provider catalog; one real Qwen task passed with credit settlement and disposable Auth-user cleanup.

Remaining external release prerequisites are a production origin/domain and host, Supabase email/redirect configuration, and Razorpay account credentials/plan IDs/webhook secret plus merchant policies. Checkout remains disabled. No real payment or public deployment has been made. [DEPLOYMENT.md](DEPLOYMENT.md) is the operator runbook, and [VALIDATION.md](VALIDATION.md) records completed checks.

## Explicit boundaries

Broker selection and import support do not claim live broker connectivity. No order placement, live quotes, licensed historical feed, fabricated tax calculation or current contract master is included. Supplied exports must be position-level; raw execution matching is a separate broker-adapter capability. The previous local database is preserved rather than assigned to an arbitrary new user.

## Administration extension

The advanced admin panel now owns user access, catalog, credits, per-task AI routing and product settings. Model-file/environment values are bootstrap defaults; runtime decisions come from PostgreSQL and are snapshotted into jobs. Migrations through `0006_user_directory` are applied. See [ADMIN_GUIDE.md](ADMIN_GUIDE.md) for capabilities and owner setup. Task costs are now 1 / 2 / 2 / 3 / 4 / 5 for trade note / chat / summary / daily / query / coaching. No account was promoted automatically.
