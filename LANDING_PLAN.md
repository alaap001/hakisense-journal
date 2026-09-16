> Historical design: commercial behavior is superseded by [the implemented pay-as-you-go design](docs/PAY_AS_YOU_GO.md).

# Landing, pricing and menus

1. Add a public `/` landing page and `/pricing`, with the signed-in overview at `/overview`. Keep sign-in, sign-up and recovery working through the existing Supabase boundary.
2. Build an editorial, India-focused page with an interactive illustrative journal, restrained scroll/pointer parallax, a clear review workflow, and responsive/reduced-motion layouts. No invented customer counts, returns or live market data.
3. Share one pricing component between the public page and signed-in billing. Fetch prices, allowances and upcoming plan features from the backend. Calculate discounts from active monthly and annual prices: Pro ₹400 / ₹1,899; Advanced ₹1,500 / ₹7,600. Show annual totals and renewal terms clearly. Deep Researched Stock Analysis is an Advanced-only **coming soon** item, not a working entitlement.
4. Ship a forward Alembic migration with new price records, preserving previous payment/subscription terms. Add admin-editable upcoming plan features. Keep checkout readiness enforced by the existing backend.
5. Replace native dropdown menus throughout the app with one themed component with keyboard navigation, typeahead/search, form submission, focus handling and dialog support.
6. Verify with one frontend build, a focused backend/catalog check and a small desktop/mobile browser pass. No paid AI, payment or broad regression runs.

Completed: public routes, interactive landing, shared live pricing, new catalog migration, admin upcoming-feature controls and themed dropdown/suggestion menus. Focused validation is recorded in `VALIDATION.md`.
