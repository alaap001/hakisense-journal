# Pay-as-you-go design and implementation

## Product decisions

Replace new subscriptions with one-time INR credit purchases. Everyone can use the journal, unlimited trade entries, analytics, notebooks, saved views, broker accounts, replay and existing playbooks. Creating a playbook costs 1 credit; reading, editing, deleting and linking one to a trade are free. Other credit charges are for AI. Deep Researched Stock Analysis remains explicitly coming soon.

| Pack | Credits | One-time price | Comparison with ₹1/credit |
| --- | ---: | ---: | --- |
| First recharge | 50 | ₹21 | 58% discount; once per account, before any successful payment |
| Starter | 50 | ₹50 | Standard reference rate |
| Review | 600 | ₹199 | 66.8% discount; 3.02× credits per rupee |
| Deep dive | 4,000 | ₹500 | 87.5% discount; 8× credits per rupee |

The later ₹21 figure takes precedence over the earlier ₹24 suggestion. Do not claim 600 credits is literally 3× 50 credits: the comparison is value per rupee. Compute comparisons from backend catalog amounts, not promotional strings.

Keep 50 free monthly credits, refreshed in IST; unused free credits expire. Purchased credits and administrative grants do not expire. Spend free credits first. Advanced AI is available to everyone, with a backend-configurable credit multiplier (initially 3), selectable in the AI coach. Other AI entry points use Standard. Model routes remain per-task/per-mode in the database and are snapshotted into LangGraph jobs.

## Implementation order

1. Add a persistent wallet, append-only sequenced ledger, credit-pack catalog, immutable purchase snapshots and first-purchase claim. Retain historical monthly wallets and subscription/payment records.
2. Move all spending, AI reservations/refunds and admin adjustments through one transactional wallet service. Lock each user's profile before wallet mutation; use unique event keys and unique request keys. Never call providers while holding a wallet lock.
3. Add hosted one-time Razorpay Payment Links. Verify captured payments server-side against link identity, amount, currency and stored checkout terms. Signed webhooks and authenticated reconciliation use the same settlement code. Never credit on a browser redirect or a client payment ID alone.
4. Restrict first-purchase promotion to one claim per user. Serialize pending purchases; preserve the same checkout/reference on retries and uncertain provider responses. Release an unused offer only after remote cancellation/expiry is verified. Refunds never restore introductory eligibility.
5. Handle partial refunds with proportional credits rounded up, capped at the original grant; disputes temporarily reverse the grant. Track previously applied entitlement so duplicate/out-of-order notifications cannot credit twice. If reversal exceeds remaining credits, record debt and prevent further spending; future top-ups settle it. Do not silently clamp and forgive debt.
6. Add admin pack editor, wallet and payment views, reconciliation checks, configurable monthly grant/playbook price/AI multiplier. Keep role checks, reasons, revisions and audit records.
7. Connect trade setups to stable playbook IDs and rule snapshots. Preserve legacy free-text setups. Validate ownership; archive deleted playbooks so existing links survive; rename without relabeling old trade history. Show selected rules during entry.
8. Replace pricing, billing, landing, account, help and feature-gate subscription copy. Show free/purchased balances, next free refresh, ledger and purchase status. Remove the old recurring-billing routes and controls after checking for active mandates.
9. Run a small targeted suite for money/idempotency/ownership boundaries, one frontend build and a basic visual check. No paid AI calls or real payment charges.

## Database and migration

Use the repository's existing Alembic migration chain (not a second Supabase migration history). New private `journal` tables use FORCE RLS, backend tenant policies and explicit admin grants; browser roles receive no access. Ledger update/delete privileges are revoked. Amounts are integer paise; credits are integers.

Migration `0008_pay_as_you_go` is applied. Preflight confirmed zero active mandates, pending recurring checkouts and active AI jobs. The migration also refuses cutover if any exist. Current-month balances transferred once into the persistent bucket with ledger opening entries; earlier expired balances remain historical. Runtime subscription models, plan/price editors, plan grants, provider methods, checkout/cancellation paths and customer controls have been removed. Historical commercial tables are retained, with access revoked from runtime/admin roles. Fresh monthly grants now use only the PAYG product settings.


Pack edits affect only new checkouts; each checkout snapshots price, credits, name and promotion eligibility. Existing live AI task prices and model routes stay unchanged. Future QA/prod separation remains a deployment concern.

## Verification gates

- Sum of ledger deltas equals wallet balance and both buckets; sequence is contiguous per wallet.
- Two spends cannot overspend; repeating one request cannot debit twice; failure refunds original bucket amounts once, including month rollover.
- Free refresh never resets purchased balance; refunds/chargebacks can create visible debt.
- Duplicate payment, webhook, refresh and admin request grant exactly once; mismatched amounts/currency/identity grant zero.
- Concurrent introductory checkouts cannot issue two discounted purchases; a refunded first purchase remains used.
- Playbook creation and debit commit together; retry returns the original record; invalid/foreign links cannot charge.
- Catalog edits do not rewrite existing purchase terms; support cannot change money/configuration.

## Operational activation

Checkout remains unavailable until backend Razorpay secrets, merchant identity, support and policy URLs are configured. Register `payment_link.paid`, payment refund and dispute events on the existing signed webhook endpoint. No email/SMS notifications are requested by the app when creating links. Reconcile from Wallet or Admin when notification delivery is delayed. Deployment should schedule `python -m backend.reconcile_payments --limit 50` every five minutes. It rotates through stored purchases and emits a nonzero status for unresolved checks; it never initiates a charge. The host scheduler itself has not been configured here.

References: [Razorpay Payment Links](https://razorpay.com/docs/api/payments/payment-links/create-standard/), [fetch a link](https://razorpay.com/docs/api/payments/payment-links/fetch-id/), [Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security).

## Completed verification

The frontend build passed. Bounded offline checks cover wallet buckets, idempotent spending/refunds, payment mismatch rejection, captured-payment webhooks, intro eligibility, administrative permissions and playbook linkage. Live Supabase verification confirmed the applied catalog, ledger sums, forced RLS, denied cross-user access, denied ledger rewrites and read-only support access. All database fixtures rolled back. Public pricing was visually checked using the real backend catalog. No real payment, email or AI generation was made for this change.

Checkout activation still requires backend payment credentials and merchant/support/policy settings. Test the configured provider in test mode before accepting real payments. Deep Researched Stock Analysis remains a future feature.
