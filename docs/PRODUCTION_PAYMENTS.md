# HakiSense production payment setup

Prepared for `https://www.hakisense.in` on Render. The code is ready to push; the dashboard changes below are yours to complete. No Render deployment, Razorpay webhook edit, real-money payment, or public dummy-policy publication was performed by this change.

## What is already prepared

- Standard Checkout order creation, checkout modal, HMAC verification, capture validation and idempotent wallet settlement.
- The PostgreSQL checkout permission fix, plus the production security policy that allows Razorpay's script and iframe. Both must be in the commit you deploy.
- Administration → Overview now shows live/test mode, whether a webhook secret is present, the expected webhook URL, and each missing checkout setting. It never displays secret values.
- An explicit hosted test option allows owner/admin accounts to test before merchant details are finished. It works only with `rzp_test_` keys; it cannot bypass live-payment prerequisites.
- `backend/.env.production` contains a private payment-only environment overlay generated from your live keys. It has mode 0600 and is ignored by Git and Docker. It does not copy or replace database, Supabase Auth, AI or operator credentials.
- A separate webhook secret was generated in `backend/.env` and copied into that overlay. This does **not** configure Razorpay; you must set the same value in the dashboard.
- `docs/production-product-settings.example.json` contains intentionally obvious dummy values to replace. They have not been written into your public product settings.

## 1. Push and deploy the updated code

Commit the implementation, tests, scripts and documentation, then push to the branch your existing Render Docker web service deploys. Do not commit any real `.env` file. Deploy the latest commit, not only the previous build with new environment values: the previous public build blocked Razorpay in its Content Security Policy.

Keep the current Render service, custom domain, database and Supabase settings. The backend already serves the built frontend from the same origin. Leave Docker Command empty to use the Dockerfile command and use `/api/ready` for health checks.

After deployment:

- `https://www.hakisense.in/api/ready` should return `{"status":"ready"}`.
- Sign in as the existing owner and open Administration → Overview. The new payment-mode, webhook and missing-settings fields confirm you have the new build.
- Changing your laptop's `backend/.env` does not update Render. Set variables in Render → existing web service → Environment. Render supports **Add from .env** and **Save, rebuild, and deploy**. [Render environment variables](https://render.com/docs/configure-environment-variables).

## 2. Test the deployed integration without real money

Keep `APP_ENV=production` on Render so HTTPS, host validation, CSP and database protections stay enabled. Set:

```dotenv
APP_ENV=production
APP_ORIGIN=https://www.hakisense.in
RAZORPAY_KEY_ID=<your Razorpay TEST key ID, beginning rzp_test_>
RAZORPAY_KEY_SECRET=<the matching TEST API secret>
RAZORPAY_WEBHOOK_SECRET=<the secret configured on your TEST webhook>
RAZORPAY_ALLOW_TEST_CHECKOUT=true
CHECKOUT_ENABLED=true
```

Retain your current `ALLOWED_HOSTS`; it must include `www.hakisense.in`, your existing Render hostname, and `127.0.0.1`. Include `hakisense.in` if that hostname reaches the app directly. Use hostnames only, no scheme/path/port.

The saved database `checkout_enabled` switch is already true in the database inspected during this task. The environment variable is only a bootstrap default; on another database, enable the saved switch in Administration → Product settings.

For hosted testing, merchant placeholders can remain unfinished. Only an active owner/admin can create a test checkout; ordinary users and read-only support staff cannot. The wallet displays a test-mode banner. Use a dedicated test account with the appropriate admin membership.

**Test payments still grant application credits in the database being used.** Prefer a separate staging deployment/database for repeated tests. If you test on the existing shared database, keep track of the test account, balances and purchases. Do not delete or rewrite ledger entries. Use audited admin credit adjustments to remove test-granted credits if needed. Test orders belong to the test key account and cannot be reconciled with live keys after a switch; finish testing/reconciliation before switching and keep a test environment for their later verification. This change does not migrate or erase historical test purchases.

Use the Test Mode Razorpay dashboard to configure a test webhook and automatic capture. Complete a test payment, dismiss a modal, try a failure, refresh payments, and confirm a successful recharge is credited only once. Also test webhook recovery after closing the browser and a test refund. [Razorpay Standard Checkout testing](https://razorpay.com/docs/payments/payment-gateway/web-integration/standard/integration-steps/).

## 3. Correct the webhook from your screenshot

Your screenshot shows the homepage as the webhook URL. Edit it to the exact backend endpoint:

```text
https://www.hakisense.in/api/webhooks/razorpay
```

Configure it in **Test Mode** for test keys, then separately in **Live Mode** when switching to live keys. The webhook secret is a separate value you choose; it is not automatically the API key secret. Copy the `RAZORPAY_WEBHOOK_SECRET` value from the appropriate local environment file into Razorpay's webhook Secret field and into Render's environment.

Select these relevant events instead of all 51:

- `payment.captured`
- `order.paid`
- `refund.processed`
- The `payment.dispute.*` events available in the dashboard, for dispute/reversal updates.
- `payment_link.paid`, `payment_link.cancelled`, `payment_link.expired` only if you still have older Payment Links to support.

The endpoint expects POST requests with a valid raw-body signature and `x-razorpay-event-id`. Opening the URL in a browser sends GET and can return 405; that does not mean the webhook is broken. Check actual delivery results in Razorpay after a test payment. Do not test with an invented live payment event. [Razorpay webhook setup](https://razorpay.com/docs/webhooks/setup-edit-payments/).

## 4. Replace the dummy merchant information

You do not need to invent a company name because you operate alone. Use the legal person/business identity already verified for your Razorpay account. HakiSense can remain the app's display brand; the legal business name should identify the actual operator consistently with your account. This setup guide does not determine your business registration or tax status.

Open Administration → Product settings and replace the fields from `production-product-settings.example.json`:

| Field | Dummy example | What you should enter |
| --- | --- | --- |
| Product/brand name | HakiSense | The name users see in the app |
| Legal business name | REPLACE_WITH_YOUR_RAZORPAY_VERIFIED_LEGAL_NAME | The actual name verified by Razorpay; use your own legal name if that is the approved operator |
| Legal business address | REPLACE_WITH_YOUR_ACTUAL_BUSINESS_CONTACT_ADDRESS | Your actual business contact address consistent with your merchant records |
| Support email | replace-me@example.invalid | A working email inbox you monitor; a branded inbox is optional |
| Terms URL | https://example.invalid/terms | A published HTTPS page describing the actual service and conditions |
| Privacy URL | https://example.invalid/privacy | A published HTTPS policy reflecting the data you collect and services you use |
| Refund policy URL | https://example.invalid/refunds | A published HTTPS policy explaining eligibility, how to request a refund and applicable timelines |
| Enable recharge checkout | true | The saved switch; live checkout also requires complete configuration |

These URLs are examples, not existing pages. Merely entering `/terms`, `/privacy` or `/refunds` will not create policies. Publish the pages on your website or use a supported external policy-page location, then enter their real URLs. Razorpay also documents policy-page setup through its dashboard. [Razorpay website details](https://razorpay.com/docs/payments/dashboard/account-settings/business-website-details/).

Choose the actual refund rules and support commitments before publishing them; do not copy arbitrary timelines or claim a refund policy you cannot honour. The app already uses one-time credit packs, no recurring renewal, no cash withdrawal/transfer, server-confirmed grants and proportional credit reversals for refunds. Your published policy should accurately explain your offering. Environment `LEGAL_BUSINESS_NAME`, `TERMS_URL`, etc. only seed new databases; update **Product settings** for this existing installation.

## 5. Switch to live payments

Once your published details are correct and testing is complete:

1. In Render's web-service Environment, import **only the payment overlay** from the ignored `backend/.env.production` file. It contains the live pair you saved locally, the generated webhook secret, `APP_ENV=production`, `APP_ORIGIN`, `CHECKOUT_ENABLED`, and `RAZORPAY_ALLOW_TEST_CHECKOUT=false`. Preserve all existing database/Auth/AI/host settings.
2. In Razorpay **Live Mode**, correct the webhook URL and use the same webhook secret as Render. Enable automatic capture in the live dashboard.
3. Save/redeploy Render. Administration should show **live**, **Webhook configured**, and no checkout blockers. The wallet must no longer show a test-mode banner.
4. Perform a controlled real payment yourself and confirm the order/payment IDs, wallet credit and webhook delivery. Verify a refund through the dashboard if needed; only the backend's verified refund state should reverse credits.

There is no `VITE_RAZORPAY_KEY_SECRET` or public secret. The modal receives the public key ID from the same backend that created the order. You do not need a frontend key variable on Render.

To regenerate the overlay after updating local keys or the webhook secret:

```bash
.venv/bin/python scripts/prepare_production_env.py
```

An existing webhook secret is preserved. Optionally pass `--render-host YOUR-SERVICE.onrender.com` to include a complete host list; omit it to leave Render's existing list untouched. The script never deploys or prints secrets.

## 6. Payment recovery schedule

The app supports manual **Refresh payments**, signed webhooks and the existing reconciliation command. Create a Render Cron Job from the same repository/Dockerfile if you want automatic recovery:

```text
Schedule: */5 * * * *
Docker command: python -m backend.reconcile_payments --limit 50
```

Give it the restricted runtime `DATABASE_URL` and the same Razorpay key pair/mode as the web service, plus `APP_ENV=production`, `APP_ORIGIN` and `ALLOWED_HOSTS`. Do not give it migration/admin credentials. It reads provider state and settles verified payments; it cannot start a charge. Cron jobs are separate Render resources; review Render's current plan/cost before creating one. [Render Cron Jobs](https://render.com/docs/cronjobs).

## Validation and boundaries

The preceding integration passed frontend build, payment/wallet/admin tests, a real Razorpay test-order API check, and a rollback-only PostgreSQL checkout test. This change passed `npm run build` and 42 focused payment, wallet, admin, deployment and catalog tests, including hosted-test authorization and live-mode readiness checks. Deployment, webhook delivery against Render, actual policy publication and live payment/refund verification remain your dashboard steps. Existing database merchant fields were left unchanged; the dummy template is local documentation only.
