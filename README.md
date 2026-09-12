# HakiSenseJournal

A trading journal for Indian traders, with React/TypeScript, FastAPI, Supabase Auth/PostgreSQL, subscription entitlements and credit-metered AI through OpenRouter and LangGraph.

The application is connected to the **HakiSenseJournal Supabase project** (`gdyhnquqflgnjqlnhqog`). The private database schema, restricted application role and migrations are applied. Public hosting and live payment activation are still release steps; see [DEPLOYMENT.md](DEPLOYMENT.md). The previous SQLite journal is preserved in `data/` and is not assigned to any cloud account.

## Plans and credits

| Plan | Price | New trades / month | AI credits / month | Features |
| --- | --- | --- | --- | --- |
| Free | ₹0 | 100 | 50 | Journal, analytics, calendar, notes, accounts and file import/export |
| Pro | ₹400/month or ₹2,499/year | Unlimited | 1,000 | Free features, market replay, playbooks and saved journal views |
| Advanced | ₹8,999/year | Unlimited | 8,000 | Pro features and the advanced AI model |

`journal.plans`, `journal.prices` and `journal.ai_tasks` are the live source of truth. `backend/catalog.py` defines the initial seed, not an override of existing database values. The browser reads the catalog and cannot grant features, select its own model, or set its credit cost. The API checks the displayed price against the current catalog before charging credits or starting checkout.

Trade entries consume no AI credits. On Free, imports and manual entries share the 100-entry allowance; deleting a trade does not restore that allowance. Credits refresh at midnight IST on the first of each calendar month, including on annual plans. Unused credits expire. Upgrades adjust the allowance by the difference after usage; cancellation retains paid access through the verified paid period.

| AI task | Initial credit cost |
| --- | --- |
| Trade note | 3 |
| Chat or summary | 5 |
| Daily preparation | 8 |
| Query and chart | 10 |
| Coaching review | 15 |

AI requests reserve credits in the same database transaction that creates a durable job. Duplicate request keys return the same job. Results and conversation messages settle together; failed or abandoned jobs refund once. Provider calls are never automatically retried by the worker. Activity remains accessible after a page reload.

## Backend model configuration

Edit **`backend/ai_models.json`**, then restart/redeploy both API and worker:

```json
{
  "standard": "qwen/qwen3.7-flash",
  "advanced": "z-ai/glm-5.3-flash"
}
```

The actual file also lists `deepseek/deepseek-v4.1-flash`, `z-ai/glm-flash-latest` and `nvidia/nemotron-3.5-lightning`, plus output/timeout limits. Both selected defaults were found in OpenRouter's catalog. `z-ai/glm-flash-latest` was not listed when checked; verify availability before selecting that optional alias. `AI_STANDARD_MODEL` and `AI_ADVANCED_MODEL` are optional deployment overrides and must be in the configured allowlist. The old `OPENROUTER_MODEL` setting is unused.

`OPENROUTER_API_KEY` belongs in backend deployment secrets. There is no customer API-key setting. The browser receives only the Supabase publishable key. The server chooses a model from the user's verified plan and snapshots it when the job is submitted.

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
| `src/Billing.tsx`, `src/Settings.tsx` | Backend-driven plans, usage, billing history and account settings |
| `backend/auth.py`, `backend/security.py` | Token validation, bounded requests and shared database rate limits |
| `backend/db.py`, `migrations/` | Private tenant schema, forced RLS, indexes and versioned migrations |
| `backend/entitlements.py` | Monthly allowances and subscription feature checks |
| `backend/jobs.py`, `backend/worker.py` | Durable AI queue, reservations, settlement and refunds |
| `backend/ai.py`, `backend/ai_models.json` | LangChain/LangGraph and OpenRouter routing |
| `backend/billing.py`, `backend/payments.py` | Verified payment periods, hosted checkout and signed webhooks |
| `backend/journal_routes.py`, `backend/repository.py` | Authenticated journal/import/export and bounded queries |
| `backend/markets.py`, `backend/analytics.py`, `backend/simulator.py` | India conventions, journal calculations and replay |
| `Dockerfile`, `compose.yaml` | Separate API/web, worker and migration processes |

The production API uses PostgreSQL only. SQLite is confined to isolated automated checks. Transactions run as `hakisense_api` with a verified, transaction-local user ID; the connecting `hakisense_app` login cannot bypass RLS. Browser roles cannot access the private `journal` schema. Financial catalog changes require an operator/migration credential; runtime credit history is append-only.

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

Drawdown uses recorded realized exits. The active-day Sharpe proxy is explicitly a proxy, not a conventional calendar-return Sharpe ratio. Coach checks are heuristics; overlapping findings are not additive profit opportunities. Analytics and AI scopes are capped at 20,000 matching trades per request; larger accounts must narrow their date/account filters. Unlimited paid trade storage does not mean unbounded report payloads.

Replay reveals candles progressively, uses stop-first handling for ambiguous bars and opening prices for gaps. It does not model exchange liquidity, slippage, partial fills or buying-power enforcement. Saving practice trades is explicit. There is no order placement, live broker synchronization, market/news feed or licensed historical-data feed in this build.
