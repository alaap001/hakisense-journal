# User accounts, preferences and help

The workspace account button, bottom profile button and top-right avatar share the same accessible account menu. It supports keyboard navigation, Escape, outside-click dismissal, and viewport-aware positioning. Sign-out is available directly in the menu.

## Pages

| Route | Functionality |
| --- | --- |
| `/settings/profile` | Edit the database-backed display name; view sign-in email and current membership. |
| `/settings/security` | Request an email change, send a password-reset email, sign out this browser, other devices, or all devices. |
| `/settings/preferences` | Save the starting page, account/date scope, compact tables and reduced motion. INR/IST remain the reporting conventions. |
| `/settings/accounts` | Existing broker-account creation and editing, integrated into account settings. |
| `/billing` | Backend credit packs, persistent balances, one-time checkout and purchase history in the settings navigation. |
| `/settings/data` | Journal archive download and links to trade import/export and privacy assistance. |
| `/settings/help` | Searchable help, account and billing shortcuts, support-message preparation and policy links. |
| `/help` | Public help, available without signing in and linked from the landing and authentication pages. |

`/settings`, `/profile`, `/preferences`, `/accounts`, and `/settings/wallet` resolve to the relevant pages. `/home` opens the saved starting page after sign-in. Starting account/date filters apply when the workspace opens; display preferences apply after saving.

## Backend and authentication

`backend/preferences.py` defines a strict preference schema and profile-name contract. `PUT /api/settings/preferences` validates owned account references and stores settings in the existing user-scoped `journal.settings` record. `/api/workspace` supplies complete defaults for older records and falls back to all accounts if a default account has been removed. This change needs no database migration.

`PUT /api/profile` changes only the signed-in user's display name. Email/password changes use Supabase Auth, with confirmation/recovery callbacks on the existing `/auth/callback` and `/auth/reset` routes. Provider email delivery and redirect allowlists must be configured for the deployed origin. Email change completion follows provider verification; the interface does not relabel an email before confirmation. See [Supabase updateUser](https://supabase.com/docs/reference/javascript/auth-updateuser).

Sign-out uses explicit local/global/other-session scopes. The normal menu signs out this device, clears in-memory journal state and navigates to sign-in. Other-session sign-out preserves the current browser session. Previously issued access tokens remain subject to their expiry; session revocation does not promise instantaneous invalidation of every issued token. See [Supabase sign-out scopes](https://supabase.com/docs/guides/auth/signout).

## Customer-care configuration

Set **Administration → Product settings → Support email** and the policy URLs. These values come from the backend catalog; the frontend does not contain a fixed support address. The current catalog has no support email configured.

The contact form prepares a message for review, then opens the user's email application or copies the draft. It does not claim that a message was sent and does not create help-desk tickets. Without a configured email, FAQs and copying a prepared request remain available. No support message is sent automatically.

## Focused verification

- Frontend build/type checking.
- Two offline backend checks: persistence/user isolation, and invalid/privileged input rejection including safe legacy defaults. These use the existing temporary test database and make no provider calls.
- Browser check of public help while signed out.
- Isolated UI preview of profile/settings layout, opening the top and sidebar menus, navigation to Preferences, and Escape returning focus to the trigger. The preview blocks account API requests and is not shipped with the application.

Live email delivery, changing the user's credentials, signing the user out, and real billing transactions were not exercised.
