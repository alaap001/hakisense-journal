# Build plan

The original local prototype has been migrated to the production architecture described in [PRODUCTION_PLAN.md](PRODUCTION_PLAN.md).

Implemented build sequence:

1. Supabase identity, private PostgreSQL schema, forced RLS and a restricted runtime login.
2. Backend catalog, monthly trade allowances, transactional AI credit ledger and paid feature enforcement.
3. Durable AI queue, LangGraph execution, configurable standard/advanced OpenRouter models, refunds and request idempotency.
4. Razorpay adapter, backend-verified subscription periods, signed webhooks, cancellation and billing UI.
5. Indian markets, INR/IST reporting, explicit derivatives metadata and Indian broker file-import workflows.
6. Removal of customer key configuration, local password lock, folder scanning, demo seeding and cross-workspace restore routes.
7. Auth/account/usage screens, deployment image, separate worker, migrations and focused CI checks.

The live Supabase schema and one real Auth/AI flow are verified. The remaining release work depends on a hosting domain, production email configuration and a configured merchant account. Follow [DEPLOYMENT.md](DEPLOYMENT.md); do not treat those external steps as already deployed. The bounded verification record is in [VALIDATION.md](VALIDATION.md).
