# Razorpay Standard Checkout

The app uses React/Vite/TypeScript and FastAPI. New credit purchases use Razorpay Standard Checkout; existing Payment Links still work. Purchases, reconciliation, refunds and the append-only wallet ledger reuse the existing database tables. No migration is required.

## Configuration

- Install Python dependencies with `./setup.sh` or `uv pip install --python .venv/bin/python -r backend/requirements.lock`. Razorpay SDK 2.0.1 verifies payment signatures; the existing HTTPX provider adapter sends API requests.
- Set `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` in `backend/.env`. These are read by the backend only. Both `.env` and `backend/.env` are already ignored by Git.
- Root `.env` may contain `VITE_RAZORPAY_KEY_ID`, never a prefixed secret. Checkout uses the public `key_id` returned by the backend so the modal and order always use the same account.
- Product settings in PostgreSQL control `checkout_enabled`. `CHECKOUT_ENABLED=true` only seeds new installations; it does not override an existing saved setting. On an existing installation, enable **Administration → Product settings → Enable recharge checkout**.
- In `APP_ENV=development` or `test`, a saved enabled switch and `rzp_test_` credentials allow checkout without a public webhook or merchant policies. Hosted tests can explicitly opt in with `RAZORPAY_ALLOW_TEST_CHECKOUT=true`; hosted test checkout is restricted to owner/admin accounts. Live keys retain webhook, merchant identity/address, support email and HTTPS policy requirements regardless of that flag. See [Render production setup](PRODUCTION_PAYMENTS.md).

The supplied test credentials were placed in the ignored environment files, and the existing database checkout switch was enabled with an operator audit entry. Restart running backend/frontend processes after changing environment values.

## Endpoints

All purchase endpoints require the existing authenticated user session. Prices and credit quantities come from the stored pack; the client cannot select an arbitrary amount or credit grant.

`POST /api/billing/create-order` (`/api/billing/checkout` remains an alias):

```json
{
  "pack_code": "first_recharge",
  "expected_amount_paise": 2400,
  "expected_credits": 50
}
```

Send an `Idempotency-Key` header (8–100 characters). Read current terms from `/api/billing/catalog`; example prices may change. The backend validates the stored price is at least 100 paise, snapshots the terms, creates an INR Razorpay order with the purchase ID as receipt, and returns `order_id`, `amount`, `currency`, public `key_id` and display information. Stale prices return 409. Provider authentication errors return 401; other provider failures return 500. Uncertain requests recover by receipt and never automatically create a second order. Receipt lookup can lag briefly; refresh again later if confirmation is pending.

`POST /api/billing/verify-payment`:

```json
{
  "razorpay_order_id": "order_...",
  "razorpay_payment_id": "pay_...",
  "razorpay_signature": "64-character hexadecimal signature"
}
```

The backend locates the current user's stored order and checks HMAC-SHA256 of `stored_order_id + "|" + payment_id` with the backend secret, using a constant-time comparison. Missing fields or mismatched signatures return 400. It then fetches the order/payment from Razorpay and checks payment ownership, amount, INR currency and capture state. A valid signature alone does not grant credits. Captured payments settle once; an authorized payment still awaiting capture returns 202 with `success: false` and `verified: true`.

`POST /api/billing/reconcile` recovers confirmation after tab closure, callback failure or a delayed capture. The existing scheduled reconciler uses the same logic. Signed `payment.captured`, `order.paid`, refund and dispute webhooks also settle through this path. Old Payment Link events remain supported.

Closing the modal preserves a pending order for retry. Cancelling a recharge in the wallet closes the local purchase; Razorpay orders cannot be remotely cancelled. A late captured payment is still credited. An introductory claim stays reserved after local order cancellation to prevent two discounted orders from being paid; use Continue payment rather than Cancel recharge when pausing an introductory purchase.

## Try the checkout

1. Run `./start.sh` from the project root. Open `http://127.0.0.1:5173` and sign in.
2. Open **Your credit wallet** (`/billing`), select a credit pack, and confirm the Razorpay test modal opens with the correct amount.
3. Complete a payment using Razorpay's [test-mode payment methods](https://razorpay.com/docs/payments/payment-gateway/web-integration/standard/integration-steps/). Ensure automatic capture is enabled in the Razorpay test dashboard.
4. Confirm the success message and a single wallet credit entry. Click **Refresh payments**; it must not add the credits again.
5. Try dismissing the modal and a failed payment. The UI should show the outcome and allow retrying the pending order. If capture is delayed, use **Refresh payments** before starting another recharge.

For a hosted production deployment, configure `https://YOUR-DOMAIN/api/webhooks/razorpay`, set the matching `RAZORPAY_WEBHOOK_SECRET`, and subscribe to `payment.captured`, `order.paid`, `refund.processed`, applicable `payment.dispute.*` events, plus old `payment_link.*` events while old links exist. Configure merchant/support/policy settings, automatic capture, and the existing five-minute reconciliation schedule. Test capture, webhook delivery and refunds before switching to live keys.

## Verification performed

- `npm run build` passed, with the existing bundle-size warning.
- `python -m unittest tests.test_standard_checkout tests.test_wallet tests.test_admin -q`: 31 checks passed, using isolated SQLite and mocked payments.
- A real Razorpay test API order for 100 paise was created and fetched by ID and receipt. No payment was charged and no wallet credits were granted for this smoke order.
- Confirmed the backend secret is absent from frontend source and the production build; both real environment files remain ignored by Git.
- Frontend event smoke checks passed for script loading failure/retry, shared loading, modal dismissal, payment failure and successful callback handling.
- PostgreSQL regression: `.venv/bin/python scripts/verify_checkout_db.py` passed order creation/retry, signed verification, exactly-once credits and tenant isolation under `hakisense_api`, with read-only catalog privileges. Provider calls were mocked and all temporary database records rolled back.
- A complete browser payment/capture/refund cycle still needs a manual test with the test dashboard. No live-money purchase was performed.

Reference: [Razorpay Standard Checkout integration](https://razorpay.com/docs/payments/payment-gateway/web-integration/standard/integration-steps/).

## Files changed

Created: `src/razorpay.ts`, `tests/test_standard_checkout.py`, `docs/RAZORPAY_CHECKOUT.md`.

Follow-up regression helper: `scripts/verify_checkout_db.py`.

Modified: `backend/payments.py`, `backend/recharges.py`, `backend/billing.py`, `backend/runtime_settings.py`, `backend/admin.py`, `backend/main.py`, `backend/requirements.txt`, `backend/requirements.lock`, `src/Billing.tsx`, `tests/test_wallet.py`, `.env.example`, `backend/.env.example`, `README.md`, `DEPLOYMENT.md`, `docs/PAY_AS_YOU_GO.md`.

Local configuration updated: `.env`, `backend/.env` (ignored), plus the database product checkout switch and its audit entry. `.gitignore` already covered both environment files and needed no edit.

## Troubleshooting database errors

A 503 during order creation with PostgreSQL SQLSTATE `42501` can indicate a privilege mismatch. The initial checkout query used `SELECT ... FOR SHARE` on `credit_packs`; PostgreSQL requires UPDATE privileges for that lock, while `hakisense_api` intentionally has SELECT only. Checkout now reads and snapshots the pack without that lock; the existing user lock still serializes purchase creation. No catalog permissions were expanded. SQLite tests do not reproduce this PostgreSQL privilege check, so use the rollback-only database regression above when changing checkout persistence. The API logs the underlying database exception type and SQLSTATE without logging SQL parameters or secrets.
