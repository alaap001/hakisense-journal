# HakiSenseJournal

A trading journal for Indian traders, with React/TypeScript, FastAPI, Supabase Auth/PostgreSQL, a persistent pay-as-you-go credit wallet and AI through OpenRouter and LangGraph.

The application is connected to the **HakiSenseJournal Supabase project** (`gdyhnquqflgnjqlnhqog`). The private database schema, restricted application role and migrations are applied. Public hosting and live payment activation are still release steps; see [DEPLOYMENT.md](DEPLOYMENT.md). The previous SQLite journal is preserved in `data/` and is not assigned to any cloud account.

## Credit wallet

All existing tools and unlimited trade entries are available to everyone. AI tasks spend credits; creating a playbook costs 1 credit by default, and its edits and trade links are free.

| Recharge | Credits | One-time price |
| --- | ---: | ---: |
| First purchase only | 50 | ₹21 (58% off) |
| Starter | 50 | ₹50 |
| Review | 600 | ₹199 (66.8% off; 3.02× value) |
| Deep dive | 4,000 | ₹500 (87.5% off; 8× value) |

The default reference rate is ₹1 per credit. Prices, pack sizes, eligibility, task costs and models come from the backend and can be edited in Administration. Checkout snapshots its terms, so later catalog changes cannot rewrite a pending purchase.

Each account receives 50 monthly free credits by default. Free credits refresh at midnight IST on the first and are spent first; purchased and admin-granted credits never expire. Refunds restore failed AI reservations once. Payment reversals can create an outstanding credit balance, which future recharges repay. See the [design and implementation guide](docs/PAY_AS_YOU_GO.md).

| AI task | Initial credit cost |
| --- | --- |
| Trade note | 1 |
| Chat or summary | 2 |
| Daily preparation | 3 |
| Query and chart | 4 |
| Coaching review | 5 |

AI requests reserve credits in the same database transaction that creates a durable job. Duplicate request keys return the same job. Results and conversation messages settle together; failed or abandoned jobs refund once. Provider calls are never automatically retried by the worker. Activity remains accessible after a page reload.

## Administration

User-facing profile, security, preferences, trading accounts, wallet and Help pages are connected through the account menus and `/settings`. See [Account settings and support](docs/ACCOUNT_SETTINGS.md) for routes, backend behavior and support-email configuration.

Use **Administration** in the sidebar, or `/admin`, after assigning an owner. [ADMIN_GUIDE.md](ADMIN_GUIDE.md) explains first-owner setup, user management, recharge-pack editing, credits, model routing, product settings and audit history. No account is promoted automatically.

The proposed input-validation work is documented in [VALIDATION_PLAN.md](VALIDATION_PLAN.md), with a complete field matrix, rule catalog, and acceptance examples. It separates existing checks from changes still to implement.

## Backend model configuration

Models are now managed in **Administration → AI configuration**. PostgreSQL stores a route for every task and tier, including an optional query-planning model, token/time limits, reasoning effort and supplemental instructions. The defaults remain `qwen/qwen3.7-flash` for Standard and `z-ai/glm-5.3-flash` for Advanced. Jobs snapshot that configuration before entering the queue; LangGraph consumes the snapshot.

`backend/ai_models.json` and model environment variables are bootstrap inputs, not runtime overrides of the database. Add or select model IDs in the panel. Its provider-catalog search does not make a generation call.

`OPENROUTER_API_KEY` belongs in backend deployment secrets. There is no customer API-key setting. The browser receives only the Supabase publishable key. The server validates the requested Standard/Advanced mode and chooses its configured model and snapshots it when the job is submitted.

LangGraph collects the user's scoped journal/history, optionally plans allowlisted query filters, calculates metrics, then asks the selected model to explain the evidence. Normal tasks use one generation call; query/chart can use two. There are no model calls on page load. Models cannot execute code, change trades, place orders or claim live market knowledge.

## Indian market conventions

- INR amounts and Indian number formatting throughout; reports, imports and credit periods use `Asia/Kolkata`.
- NSE/BSE shares and index derivatives, MCX and cryptocurrency records; Indian broker account labels include Zerodha, Groww, Upstox, Angel One, Dhan, ICICI Direct, FYERS, CoinDCX, CoinSwitch and Delta Exchange.
- NSE/BSE futures/options require expiry and the lot size applicable to the recorded contract. Options also require strike and CE/PE. Quantity is in **units**, and the multiplier is **1** for these contracts; lot size is recorded separately to prevent double-counting P&L.
- Prices/fees for crypto must already be in INR. There is no implicit USD/USDT conversion. Enter actual brokerage and charges; the app does not fabricate statutory tax amounts or maintain a current exchange contract master.
- CSV/TSV/XLSX imports accept position-level rows with mapping and duplicate detection. Broker labels do not imply a live API connection or automatic matching of raw executions.
- `public/sample-trades.csv` and `public/sample-candles.csv` contain synthetic examples. Replay uses uploaded OHLC data or a clearly labelled synthetic NIFTY-scale series.

## Application modules

| Location | Responsibility |
| --- | --- |
| `src/Auth.tsx`, `src/authClient.ts` | Supabase sign-in, registration, email confirmation and password recovery |
| `src/Billing.tsx`, `src/Settings.tsx` | Backend-driven credit packs, usage, purchase history and account settings |
| `backend/auth.py`, `backend/security.py` | Token validation, bounded requests and shared database rate limits |
| `backend/db.py`, `migrations/` | Private tenant schema, forced RLS, indexes and versioned migrations |
| `backend/entitlements.py` | Public catalog, monthly free grants and feature availability |
| `backend/wallet.py`, `backend/recharges.py` | Persistent buckets, append-only ledger, purchase snapshots and verified settlement |
| `backend/jobs.py`, `backend/worker.py` | Durable AI queue, reservations, settlement and refunds |
| `backend/ai.py`, `backend/ai_models.json` | LangChain/LangGraph and OpenRouter routing |
| `backend/billing.py`, `backend/payments.py` | Wallet API, hosted one-time checkout and signed webhooks |
| `backend/journal_routes.py`, `backend/repository.py` | Authenticated journal/import/export and bounded queries |
| `backend/markets.py`, `backend/analytics.py`, `backend/simulator.py` | India conventions, journal calculations and replay |
| `Dockerfile`, `compose.yaml` | Separate API/web, worker and migration processes |

The production API uses PostgreSQL only. SQLite is confined to isolated automated checks. Transactions run as `hakisense_api` with a verified, transaction-local user ID; the connecting `hakisense_app` login cannot bypass RLS. Browser roles cannot access the private `journal` schema. Financial catalog changes require an authorized admin; runtime credit history is append-only.

## Preview and basic checks

Dependencies are already installed here. On a new checkout, run `./setup.sh`, configure `backend/.env`, and apply migrations as described in the deployment guide. Start the authenticated Supabase-backed preview with:

```bash
./start.sh
```

This launches the API, Vite and the AI worker. Open `http://127.0.0.1:5173/`. Customer data still lives in Supabase; this command only runs the application processes on your machine. Email verification requires working Supabase email settings. No demonstration account is seeded.

```bash
npm run build
.venv/bin/python scripts/smoke.py
```

These checks make no paid model calls. [VALIDATION.md](VALIDATION.md) distinguishes completed checks from remaining external release checks. [DEPLOYMENT.md](DEPLOYMENT.md) covers credentials, payments, hosting and operations.

## Accounting and scope

Gross realized P&L is `(exit − entry) × closed quantity × multiplier × direction`; net subtracts the allocated fees. Partial positions record one weighted-average exit, not an execution ledger. Manual marks are required for unrealized P&L. Missing risk does not produce a fabricated R multiple. Entry dates define journal scope; exit dates determine realized calendar results, in IST. Equity excludes deposits, withdrawals, dividends and FX conversion.

Drawdown uses recorded realized exits. The active-day Sharpe proxy is explicitly a proxy, not a conventional calendar-return Sharpe ratio. Coach checks are heuristics; overlapping findings are not additive profit opportunities. Analytics and AI scopes default to 20,000 matching trades per request, configurable by an admin; larger accounts must narrow their date/account filters. Unlimited trade storage does not mean unbounded report payloads.

Replay reveals candles progressively, uses stop-first handling for ambiguous bars and opening prices for gaps. It does not model exchange liquidity, slippage, partial fills or buying-power enforcement. Saving practice trades is explicit. There is no order placement, live broker synchronization, market/news feed or licensed historical-data feed in this build.

## Public website and pricing

The public landing page is `/`, public pricing is `/pricing`, and the authenticated dashboard is `/overview`. Sign-in and sign-up are at `/login` and `/signup`. The landing preview uses illustrative trades and makes no AI calls.

Public pricing and the signed-in wallet share `src/Pricing.tsx`. Migration `0008_pay_as_you_go` is applied to Supabase. Runtime subscription models, routes, provider methods, feature gates and plan editors have been removed; historical tables are retained but access is revoked from application roles. Existing current-month balances were carried into the persistent wallet once. No owner was assigned and no real payment was made.

`src/Select.tsx` and `src/SuggestInput.tsx` supply themed, keyboard-accessible selection and free-text suggestion menus throughout the app.
