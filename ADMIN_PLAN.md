> Historical design: commercial behavior is superseded by [the implemented pay-as-you-go design](docs/PAY_AS_YOU_GO.md).

# Administration implementation plan

## Outcome

An authenticated `/admin` workspace manages the product without routine Supabase-console edits: searchable users, suspension, time-limited plan grants, monthly credit adjustments, plans/features/allowances, versioned prices, AI task costs, model registry, task/tier routing, product settings, AI operations and an immutable audit trail.

## Security and data boundaries

- Roles: owner, admin, support. Support is read-only; admins operate the product; owners additionally manage staff. Initial owner is assigned by an operator script to an explicitly identified, verified Auth user. There is no public bootstrap endpoint.
- Normal tenant access remains unchanged. A separate restricted database role serves admin requests, after fresh application membership checks. Admin access does not expose journal notes/conversations or credential-bearing Auth columns.
- Every write requires a reason and idempotency key and records actor, target, before/after and timestamp. Catalog edits use a revision check to reject stale changes.
- Payment history and credit entries stay immutable. Manual plan grants are separate from provider subscriptions; they do not invent payments or alter recurring mandates. Credit adjustments expire with their monthly wallet.
- Existing price rows referenced by checkout/subscriptions cannot change financial terms. Create a new price and deactivate the old offer instead.

## Configuration

- PostgreSQL owns models and per-task/per-tier routing, including an optional separate query-planning model, token cap, timeout, temperature, reasoning level and supplemental instructions.
- `ai_models.json` becomes bootstrap defaults. Jobs snapshot database routing at submission; LangGraph uses that snapshot throughout execution.
- Product settings include branding, support/policy links, maintenance, AI/checkout switches and bounded operating limits. Provider secrets and database credentials remain deployment secrets.
- Password minimum becomes eight characters. Task costs migrate once using ceiling(old / 3): chat 2, trade note 1, summary 2, query/chart 4, daily 3, coaching 5.

## Build order

1. Add versioned schema migration and protected admin access/roles/audit/configuration tables.
2. Implement scoped admin endpoints and backend configuration reads; update credits and model routing.
3. Build admin navigation, overview, user detail/actions, catalog editors, settings and activity/audit screens.
4. Apply the migration to the supplied Supabase project; bootstrap the requested owner after their account is identified.
5. Run a frontend build and focused tests for admin denial, roles, audit/idempotency, credits and routing. Verify real Postgres permissions with rollback-only fixtures. No repeated paid AI calls.

## Completion

Implemented all eight administration screens and applied migrations through `0006_user_directory`. Prices were reduced once, models/routes are database-backed, and no owner was assigned. The admin guide documents bootstrap and operation. Offline checks and real Postgres role checks are recorded in `VALIDATION.md`.
