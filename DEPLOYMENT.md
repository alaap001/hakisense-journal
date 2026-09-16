# Deployment and operations

## Current state

- Supabase project `gdyhnquqflgnjqlnhqog`: connected; migrations through `0008_pay_as_you_go` applied.
- All active application tables live in private schema `journal`, with RLS enabled and forced. Browser roles have no schema access.
- `backend/.env`: contains the supplied backend secrets and a generated, restricted `DATABASE_URL`; file permissions are `0600`. Secrets were not copied into frontend configuration or build assets.
- Real Supabase password sign-in, tenant isolation, one INR trade and one Qwen AI task were checked using disposable data, which was removed.
- Razorpay checkout remains disabled. No real payment was created. Public hosting, production email delivery, domain and merchant policies are not configured by this repository.

## 1. Credentials and configuration

Use `backend/.env.example` as the reference. Existing environment values take precedence over `backend/.env`, which takes precedence over the legacy root `.env`. On a hosting service, use its secret store. Do not mount the operator's entire `.env` into a public web container.

| Variable | Where it belongs |
| --- | --- |
| `DATABASE_URL` | Restricted `hakisense_app` login, API and worker only |
| `MIGRATION_DATABASE_URL` or `DIRECT_URL` | Admin connection, one-off migration/operator process only |
| `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` | Public Auth configuration; returned by `/api/config` |
| `SUPABASE_SECRET_KEY` | Optional operator verification script only; not needed by API or worker |
| `OPENROUTER_API_KEY` | API and worker secrets; never browser-side |
| `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` | Web/API secrets |
| `APP_ENV=production` | Hosted API and worker |
| `APP_ORIGIN` | Exact HTTPS origin of your application |
| `ALLOWED_HOSTS` | Comma-separated hostnames, without scheme/path; include `127.0.0.1` for container health probes |
| `CHECKOUT_ENABLED` | Keep `false` until payment setup and merchant policies are complete |

Both processes use task routing from PostgreSQL. Select models and limits in **Administration → AI configuration**; new jobs use the saved values without redeploying. `backend/ai_models.json` supplies initial seed values only. Product settings, policies and checkout switches also come from the admin-managed database; environment values seed initial configuration. See [ADMIN_GUIDE.md](ADMIN_GUIDE.md).

On another empty HakiSense database, apply migrations with the admin connection, then run `scripts/configure_runtime_db.py` to generate the runtime credential. That script intentionally refuses to overwrite an existing `DATABASE_URL` and is restricted to the configured project. Do not rotate the current credential merely to rerun setup. Use a planned operator rotation and update every API/worker instance together when rotation is needed.

PostgreSQL connections require TLS. Use a Supabase direct connection from an IPv6-capable host, or its supported session/transaction pooler connection when the host requires it. Configure the restricted database role in the pooler username; do not switch the application back to the admin account. Prepared statements are disabled for transaction-pooler compatibility. Verify the pooler's actual connection string in the project's Connect panel.

## 2. Auth and email

In the Supabase dashboard, set the Site URL to the real HTTPS origin and allow these exact application URLs:

```text
https://YOUR-DOMAIN/auth/callback
https://YOUR-DOMAIN/auth/reset
```

Add separate preview URLs only if needed. The UI uses PKCE and the Supabase SDK handles callback code exchange. Redirects must be allowlisted; use exact production paths. See [Supabase redirect URLs](https://supabase.com/docs/guides/auth/redirect-urls).

Configure a verified sender and custom SMTP for public email confirmation and password recovery. Supabase's default email service has restrictions and is not suitable as public production mail delivery. See [Supabase custom SMTP](https://supabase.com/docs/guides/auth/auth-smtp). Keep email confirmation enabled and anonymous sign-in disabled. Set password policy in Supabase as well as the UI. Do not enable CAPTCHA until its frontend token integration is configured; this build does not include a CAPTCHA widget.

Complete one real confirmation/reset-email round trip on the eventual domain before opening registration publicly. The existing validation used an operator-confirmed disposable account and did not send an email. Access JWTs can remain valid until expiry after logout; choose a short supported expiry and a deliberate revocation policy. The backend performs live Auth verification for mutations, while asymmetric JWT reads use signature/issuer/audience/expiry validation.

## 3. Payment setup

The adapter uses hosted Razorpay **one-time Payment Links**. No recurring products or provider-plan binding is needed. Checkout URLs do not grant credits: signed webhooks or authenticated reconciliation fetch the link and captured payment, validate identity/amount/currency, and post the verified wallet delta. See [Razorpay Payment Links](https://razorpay.com/docs/api/payments/payment-links/create-standard/).

1. Configure merchant payment capabilities and backend Razorpay keys. Use a separate test-mode deployment before accepting real payments.
2. Configure the webhook `https://YOUR-DOMAIN/api/webhooks/razorpay` for `payment_link.paid`, `payment_link.cancelled`, `payment_link.expired`, `refund.processed`, and applicable `payment.dispute.*` events. Set the matching signing secret.
3. Set actual merchant identity/address, support email and HTTPS terms/privacy/refund policy URLs in **Admin → Product settings**. Displayed prices include applicable taxes; configure merchant invoicing consistently.
4. Review credit packs in Admin. Enable recharge checkout only after these prerequisites are configured. Checkout creates links with email/SMS notification and reminder flags disabled.
5. Complete a bounded provider test-mode purchase/refund/webhook round trip on the deployed domain. This has not been executed in this workspace; no money was charged.
6. Schedule a recovery pass every five minutes using the runtime credentials:

   ```bash
   .venv/bin/python -m backend.reconcile_payments --limit 50
   ```

The recovery pass rotates through stored purchases, including older refunds/disputes. It never creates payments. Monitor nonzero exit status and payment-provider rate limits; tune the batch/schedule for deployment volume. Wallet and Admin also offer explicit reconciliation.

Creation uses a unique saved reference. Network-uncertain creation is looked up by that reference; it is never blindly POSTed again. Only one pending recharge is allowed per account. A provider-confirmed cancellation or expiry releases an unused introductory claim. Captured purchases consume eligibility permanently, even if later refunded. If creation is uncertain and no provider link can be found, keep it pending for operator review rather than risking duplicate payment.

Migration `0008` refuses cutover while active mandates, old checkouts or AI jobs exist. Stop API/worker instances first. In this project preflight found zero of each. The migration preserved current balances, disabled old offers, and revoked runtime access to historical tables. Do not rewrite this applied migration; use a new forward migration for changes.

## 4. Build and deploy

Use a container host with HTTPS termination. The image serves the compiled SPA and API from one origin; it also provides a separate worker command. The API starts without seeding or running migrations.

### Render setup

Create a **Docker Web Service** from the repository root, using `./Dockerfile`. Leave **Docker Command** empty so the image's default web command runs. Set **Health Check Path** to `/api/ready`. The same service serves both the built React app and FastAPI; do not run `npm run dev`, `start.sh`, or a separate Vite process on Render.

Copy the actual public hostname from the Render dashboard. The following uses `YOUR-SERVICE.onrender.com` as a placeholder, not a value to paste unchanged:

```dotenv
APP_ENV=production
APP_ORIGIN=https://YOUR-SERVICE.onrender.com
ALLOWED_HOSTS=YOUR-SERVICE.onrender.com,127.0.0.1
WEB_CONCURRENCY=1
DATABASE_URL=<the restricted runtime connection from backend/.env>
SUPABASE_URL=<your Supabase project URL>
SUPABASE_PUBLISHABLE_KEY=<your Supabase publishable key>
OPENROUTER_API_KEY=<your OpenRouter key>
```

`APP_ORIGIN` needs `https://`; `ALLOWED_HOSTS` contains hostnames only, without a scheme, path or port. If you use a custom domain, set `APP_ORIGIN` to that domain's HTTPS origin and include both its hostname and the Render hostname in `ALLOWED_HOSTS`, along with `127.0.0.1` for the container probe.

Render supplies `PORT` (normally `10000`). The image now reads it for both Uvicorn and its container health check; outside Render, it defaults to `8000`. `WEB_CONCURRENCY` controls API processes and defaults to one. It does not start an AI worker. See [Render port binding](https://render.com/docs/web-services#port-binding), [Docker command settings](https://render.com/docs/docker), and [health checks](https://render.com/docs/health-checks).

The deployment log ending with `Production requires PostgreSQL, an HTTPS APP_ORIGIN and explicit ALLOWED_HOSTS` indicates a failed application configuration check, not a failed frontend build. Missing `APP_ORIGIN` falls back to the local HTTP development URL. Missing `ALLOWED_HOSTS` leaves only local hosts and would reject public requests. The updated validation identifies the offending setting. A later `No open ports detected` message can be a consequence of the application exiting; changing the port alone will not fix missing configuration.

Use the existing `hakisense_app` database login for `DATABASE_URL`, not the Supabase dashboard's `postgres` admin URL. For a shared pooler, the username includes the project suffix, e.g. `hakisense_app.<project-ref>`; use that login's password, not the admin password. If a subsequent deployment reports IPv6/network reachability errors, use the project's supported IPv4 session pooler connection from **Connect**. Do not guess the region/hostname. See [Supabase connection methods](https://supabase.com/docs/guides/database/connecting-to-postgres).

The application's Auth SDK gets its public configuration at runtime through `/api/config`; no `VITE_SUPABASE_*` build variables are needed. `SUPABASE_SECRET_KEY` is not read by the API/worker, and `DIRECT_URL`/`MIGRATION_DATABASE_URL` are only migration/operator credentials. Neither replaces a missing `DATABASE_URL`, `APP_ORIGIN`, or `ALLOWED_HOSTS`. Keep operator/admin credentials out of the web/worker services.

For AI jobs, also create a **Background Worker** from the same repository/Dockerfile, with **Docker Command**:

```text
python -m backend.worker
```

Give it `APP_ENV`, `APP_ORIGIN`, `ALLOWED_HOSTS`, `DATABASE_URL`, and `OPENROUTER_API_KEY` as above. Use the web application's origin/hosts, not a worker hostname. The worker has no HTTP endpoint. The app can serve pages without it, but queued AI jobs will not be processed. API and worker logs appear under their respective Render services. See [Render background workers](https://render.com/docs/background-workers).

Before using signup/reset emails, set the Supabase Auth **Site URL** to `APP_ORIGIN` and allow `https://YOUR-SERVICE.onrender.com/auth/callback` and `/auth/reset` under redirect URLs (use the custom domain instead if that is the application origin). See [Supabase redirect configuration](https://supabase.com/docs/guides/auth/redirect-urls).

Deploy the commit containing these changes after saving the variables; an old manually overridden Docker Command will not pick up the new port/process defaults. Confirm `/api/ready` returns `{"status":"ready"}`, `/api/config` returns the expected public Auth configuration, and the worker logs `ai_worker_started`. Check the first actual traceback if startup still fails. A database connection or schema error is a separate next failure; this log does not establish that the credentials or latest migrations have been verified.

Keep migrations as a separate controlled operation using the admin connection. Run `python -m alembic current` and compare with `python -m alembic heads` before deciding whether an upgrade is needed. Do not rerun runtime-role setup or rotate credentials merely to fix this deployment error.

### Docker Compose / other hosts

Configure the deployment environment, then:

```bash
docker compose --env-file backend/.env build web
docker compose --env-file backend/.env --profile tools run --rm migrate
docker compose --env-file backend/.env up -d web worker
```

The included Compose file exposes the web process on host loopback port `8000`; route your TLS reverse proxy to it and preserve the public Host header. If your container platform provides routing itself, use its `PORT` value (or the image's `8000` default when none is supplied) instead of exposing a public development server. Set an edge body limit of 20 MB and apply edge request controls to public endpoints. `/api/health` is liveness; `/api/ready` verifies database connectivity/catalog availability. Production disables interactive API docs and adds CSP/HSTS and other response headers.

The image runs without root, excludes environment files and old journal data, and supports a read-only filesystem with a temporary `/tmp`. API and worker receive only explicit runtime variables. The migration container alone receives the admin database connection. Do not copy `DIRECT_URL` or `SUPABASE_SECRET_KEY` into web/worker environments.

Allow at least 240 seconds for graceful worker shutdown. A worker can process one AI job at a time; increase the worker count separately from API replicas. Postgres `FOR UPDATE SKIP LOCKED` assigns work without an in-memory broker. Each user can have one AI task in flight. Request timeouts stop a task after 200 seconds; abandoned running jobs refund after five minutes and unclaimed jobs after fifteen. An uncertain paid provider request is not retried automatically.

Each process has a pool of five connections with up to five overflow connections. Budget total connections across all API processes and workers before scaling, and use a supported pooler when needed. Current analytics/AI scopes default to 20,000 matching trades, configurable in administration; broader reporting/export and very large replay histories need workload-specific capacity work before increasing those limits.

## 5. Operate and recover

- Monitor API error rates, readiness, oldest queue age, failed/refunded AI jobs, worker logs, OpenRouter spend and webhook failures. Logs use identifiers and error types instead of journal text or keys.
- Configure database backup retention/PITR suitable for the deployment and verify a restore into a separate project before relying on it. Those Supabase project settings have not been changed here. JSON export is a customer data export, not a database disaster-recovery backup.
- Keep the private schema unexposed to browser roles. Maintain forced RLS and ownership constraints for every new tenant table. Do not use user-editable Auth metadata for wallet/role decisions.
- Deploy schema changes as new reviewed Alembic migrations. Migrations through `0008_pay_as_you_go` are already applied and must not be rewritten. Prefer additive changes and forward fixes; take a backup before destructive operator work. Never run isolated-test initialization against the cloud database.
- Preserve raw payment identifiers and immutable credit history during incident resolution. Fix a billing issue through verified provider reconciliation or an auditable operator adjustment, not by deleting history.
- Stop API and workers before an account-removal incident if necessary; user deletion is an operator action through Supabase Auth, with application rows cascading from the Auth user. This build does not include a customer self-service deletion workflow. Define retention/deletion procedures before public launch.
- The old `data/journal.db` remains untouched. Any migration of those positions must identify the owning Supabase user, explicitly map India/currency assumptions and pass the same import validation rules. There is no automatic cross-user restore endpoint.

## Verification commands

```bash
npm run build
.venv/bin/python scripts/smoke.py
```

For operator validation only:

```bash
.venv/bin/python scripts/verify_payg.py
.venv/bin/python scripts/verify_services.py
.venv/bin/python scripts/verify_auth_ai.py
```

The first checks rollback-only RLS fixtures in the configured project. The second reads Auth/model metadata. The third creates and removes a disposable confirmed Auth user; it does not send email. Adding `--ai` makes a paid generation request: one such call already passed, and routine checks should not repeat it. See [VALIDATION.md](VALIDATION.md) for the exact completed scope.
