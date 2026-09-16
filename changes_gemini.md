# Summary of Changes: Legal Policies & URLs Integration

This document details all changes implemented to support **Terms of Service**, **Privacy Policy**, and **Cancellation & Refund Policy** for **HakiSense** (frontend, routing, and backend configuration), tailored for Indian regulatory compliance (IT Act, DPDP Act 2023, SEBI disclaimers) and Razorpay live merchant activation.

---

## 1. Files Added & Modified

| File | Status | Description |
| --- | --- | --- |
| `src/Legal.tsx` | **NEW** | Standalone public legal page with tabbed navigation (`/terms`, `/privacy`, `/refunds`), business metadata card, and responsive markdown rendering. |
| `src/App.tsx` | **MODIFIED** | Added lazy import for `Legal` and registered public routes for `/terms`, `/privacy`, and `/refunds` (bypassing authentication redirect). |
| `src/Landing.tsx` | **MODIFIED** | Updated footer links to route directly to internal `/terms`, `/privacy`, and `/refunds` pages. |
| `src/Help.tsx` | **MODIFIED** | Updated policy links in customer care and footer to route to internal policy pages. |
| `src/Billing.tsx` | **MODIFIED** | Updated "Refund policy" link in the wallet panel to route directly to `/refunds`. |
| `backend/runtime_settings.py` | **MODIFIED** | Updated `https_url` validator to permit `localhost` and `127.0.0.1` HTTP URLs during development and test mode, while enforcing strict HTTPS in production. |
| `backend/.env` | **MODIFIED** | Configured live production URLs for `TERMS_URL`, `PRIVACY_POLICY_URL`, and `REFUND_POLICY_URL`. |

---

## 2. Detailed Breakdown of Changes

### A. New Public Legal Component (`src/Legal.tsx`)
- **Path:** `src/Legal.tsx`
- **Features:**
  - Tabbed switcher allowing users and auditors to flip between **Terms of Service**, **Privacy Policy**, and **Cancellation & Refunds**.
  - Dynamic operator metadata banner displaying:
    - **Legal Operator:** `HakiSense` (or verified legal name from catalog)
    - **Customer Support:** `contact@hakisense.in`
    - **Jurisdiction & Address:** `Sector 14, Sonepat, Haryana, India`
  - Utilizes existing `Markdown` component (`src/Markdown.tsx`) to render headings, callouts, lists, and tables with responsive styling.
  - Updates `document.title` dynamically (`Terms of Service · HakiSense`, etc.) and scrolls to top on navigation.

### B. Public Router Registration (`src/App.tsx`)
- Registered routes so that visitors and Razorpay compliance reviewers can access them without having to sign in:
```tsx
const Legal = lazy(() => import('./Legal'));

// Inside Routes:
<Route path="/terms" element={<Legal page="terms"/>}/>
<Route path="/privacy" element={<Legal page="privacy"/>}/>
<Route path="/refunds" element={<Legal page="refunds"/>}/>
```

### C. Footer & In-App Links Updated
- **`src/Landing.tsx`**: Replaced conditional catalog anchors in the footer with direct `<Link>` elements:
```tsx
<div>
  <Link to="/terms">Terms</Link>
  <Link to="/privacy">Privacy</Link>
  <Link to="/refunds">Refunds</Link>
  <span>INR / IST</span>
</div>
```
- **`src/Help.tsx`**: Updated `help-policies` and footer links to route internally using `<Link>`.
- **`src/Billing.tsx`**: Updated "Refund policy" link in the wallet info card to route to `/refunds`.

### D. Backend Settings Validator (`backend/runtime_settings.py`)
- Updated the Pydantic validator `https_url` to allow local HTTP testing while maintaining strict HTTPS enforcement in production:
```python
@field_validator('terms_url', 'privacy_url', 'refund_url')
@classmethod
def https_url(cls, value):
    if value:
        u = urlsplit(value)
        if config.environment in ('development', 'test') and u.scheme in ('http', 'https') and u.hostname in ('localhost', '127.0.0.1'):
            return value
        if u.scheme != 'https' or not u.hostname or u.username:
            raise ValueError('Use a complete HTTPS URL.')
    return value
```

### E. Backend Environment File (`backend/.env`)
- Set the three production URLs:
```env
TERMS_URL="https://www.hakisense.in/terms"
PRIVACY_POLICY_URL="https://www.hakisense.in/privacy"
REFUND_POLICY_URL="https://www.hakisense.in/refunds"
```

---

## 3. Policy Content Summary

### 1. Terms of Service (`/terms`)
- **SEBI Non-Advisory Disclaimer:** Explicitly states that HakiSense is **not** a SEBI-registered Investment Adviser (RIA), Research Analyst (RA), or broker. It does not provide trade signals, tips, or investment advice.
- **Market Risk Warning:** Users acknowledge trading in equities, futures, and options involves significant risk of capital loss, and trading decisions are made solely at the user's discretion.
- **Digital Credit Terms:** Recharges are one-time payments for computation utility; in-app credits have no fiat cash value, cannot be redeemed for cash, and cannot be transferred or withdrawn.
- **Governing Law & Jurisdiction:** Republic of India, with exclusive jurisdiction in Sonepat, Haryana.

### 2. Privacy Policy (`/privacy`)
- **Governing Laws:** Information Technology Act, 2000 and Digital Personal Data Protection Act, 2023 (DPDP Act).
- **Data Collected:** Account credentials, trading logs, notes, tags, broker CSV imports, and transaction identifiers.
- **Payment Privacy:** Explicit statement that sensitive payment credentials (cards, UPI PINs, net banking passwords) are processed exclusively by Razorpay (PCI-DSS Level 1) and never stored on HakiSense servers.
- **Third-Party Processing:** Discloses use of Supabase (auth/database), Razorpay (payments), OpenRouter / AI partners (LLM reviews), and Render (hosting). Explicitly guarantees no selling of user trading data to brokers or advertisers.
- **User Rights & Grievance:** Data export (JSON), correction, account deletion, and Grievance Officer contact (`contact@hakisense.in`).

### 3. Cancellation & Refund Policy (`/refunds`)
- **No Recurring Subscriptions:** Clearly identifies that recharges are one-time payments with no automated renewals.
- **Automatic In-App Refunds:** Failed or timed-out AI tasks automatically release/refund reserved credits back to the wallet immediately.
- **Monetary Refund Eligibility:**
  - 7-day request window for unused credit packs.
  - Proportional refund option for partially consumed packs.
  - Full refund for duplicate or accidental technical charges.
- **Turnaround Timeline:** Review within 24–48 hours; approved funds credited via original payment method through Razorpay within 5–7 business days.

---

## 4. Local Testing & Verification

1. **Verify Frontend Compilation:**
   ```bash
   npm run build
   ```
   *(Confirmed: built cleanly with zero TypeScript errors; `Legal` is code-split into a separate chunk).*

2. **Run Locally:**
   ```bash
   npm run dev
   ```
   Open in your browser without logging in:
   - `http://localhost:5173/terms`
   - `http://localhost:5173/privacy`
   - `http://localhost:5173/refunds`

3. **Check Routing:**
   - Verify tab clicks switch between documents and update the URL.
   - Verify footer links on `/` and `/help` navigate directly to these pages.

---

## 5. Next Steps for Production & Razorpay Live Review

When you are ready to deploy to production:
1. **Push & Deploy:** Deploy the changes to your Render web service.
2. **Update Admin Settings:** In your live HakiSense app, log in as admin and open **Admin → Product settings**. Save the URLs:
   - Terms URL: `https://www.hakisense.in/terms`
   - Privacy URL: `https://www.hakisense.in/privacy`
   - Refund policy URL: `https://www.hakisense.in/refunds`
3. **Submit to Razorpay:** In the Razorpay Dashboard under **Settings → Business Website Details**, submit these 3 URLs for merchant compliance review.
