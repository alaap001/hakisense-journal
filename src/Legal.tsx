import { useEffect, useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { ArrowUpRight, Shield, FileText, RotateCcw, Mail, MapPin, Building2, ExternalLink } from 'lucide-react';
import { Markdown } from './Markdown';
import type { Catalog } from './types';
import './account.css';

export type LegalPageType = 'terms' | 'privacy' | 'refunds';

function getLegalContent(type: LegalPageType, brand: string, businessName: string, supportEmail: string, address: string) {
  if (type === 'terms') {
    return `# Terms of Service

**Last Updated:** September 16, 2026  
**Product / Platform:** ${brand} (https://www.hakisense.in)  
**Operator / Entity:** ${businessName}  
**Registered Address:** ${address}  
**Contact Email:** [${supportEmail}](mailto:${supportEmail})  

---

### 1. Acceptance of Terms
By accessing or using the ${brand} web platform, tools, APIs, or related services (collectively, the "Service"), you agree to be bound by these Terms of Service ("Terms"). If you do not agree to these Terms, you must not access or use the Service.

---

### 2. IMPORTANT DISCLAIMERS — NO INVESTMENT ADVICE & TRADING RISK

> **SEBI Non-Registration Notice:**  
> **${brand} is NOT a SEBI-registered Investment Adviser (RIA), Research Analyst (RA), Portfolio Manager, or Stock Broker under the regulations of the Securities and Exchange Board of India (SEBI).**

- **Educational & Analytical Tool Only:** The Service provides self-directed trading journaling, analytical calculations, trade tag aggregation, and AI-assisted performance reviews. Nothing contained on ${brand} constitutes financial, investment, legal, tax, or accounting advice.
- **No Buy/Sell Recommendations:** ${brand} does not provide trade signals, recommendations, or tips to buy, sell, or hold any stock, futures, options, currency, or cryptocurrency.
- **Substantial Market Risk:** Trading in financial markets—especially equities, index futures, and options—involves significant risk of capital loss. You acknowledge and agree that **all trading decisions are made solely by you at your own discretion and risk**, and ${brand} accepts zero liability for any trading losses, missed opportunities, or financial consequences.

---

### 3. User Accounts & Verification
- You must provide accurate, current, and complete information during registration.
- You are solely responsible for maintaining the confidentiality of your credentials and account sessions.
- You must notify us immediately at [${supportEmail}](mailto:${supportEmail}) if you discover or suspect any unauthorized access to your account.

---

### 4. Digital Usage Credits & Billing
- **One-Time Recharges:** ${brand} provides digital computation credits used to run AI-assisted trade reviews and coach workflows. Recharges are **one-time purchases**. There is **no recurring subscription, monthly auto-debit, or hidden charge**.
- **Utility Tokens Only:** Credits are in-app usage units for computational processing. Credits hold **no fiat currency value**, cannot be exchanged for cash, cannot be transferred to another user, and cannot be withdrawn to a bank account.
- **Credit Expiry:** Purchased credits do not expire. Promotional or monthly free credit grants refresh monthly in Indian Standard Time (IST).
- **Payment Processing:** Payments are processed securely in Indian Rupees (INR) via our payment gateway partner, **Razorpay**. We do not store sensitive payment credentials (card numbers, CVV, UPI PINs, or net banking passwords).

---

### 5. Intellectual Property & User Data
- **Your Data:** You retain full ownership of the trade logs, trade notes, tags, screenshots, and strategies you enter into ${brand}. You grant us a limited license to process and display this information solely to deliver the Service to you.
- **Platform IP:** All software, interfaces, designs, visual assets, trademarks, and source code of ${brand} are the exclusive intellectual property of ${businessName}.

---

### 6. Prohibited Activities
You agree not to:
- Use the platform for any unlawful purpose or in violation of applicable SEBI regulations or Indian law.
- Attempt to reverse engineer, decompile, scrape, or systematically extract data or models from the Service.
- Share, sublicense, or resell account access or computational credits to third parties.
- Interfere with or disrupt the security or availability of ${brand}'s servers and APIs.

---

### 7. Limitation of Liability
To the maximum extent permitted by applicable Indian law, ${businessName}, its operators, contributors, and service partners shall not be liable for any indirect, incidental, special, consequential, or punitive damages, including loss of profits, trading capital, data, or business opportunities, arising from your use of or inability to use the Service.

---

### 8. Governing Law & Jurisdiction
These Terms are governed by and construed in accordance with the laws of the **Republic of India**. Any dispute, claim, or controversy arising under these Terms shall be subject to the exclusive jurisdiction of the competent courts in **Sonepat, Haryana, India**.

---

### 9. Modifications to Terms
We may update these Terms from time to time. Any material changes will be announced on the platform or sent to your registered email. Continued use of the Service following such updates constitutes your acceptance of the revised Terms.

If you have questions regarding these Terms, please email [${supportEmail}](mailto:${supportEmail}).`;
  }

  if (type === 'privacy') {
    return `# Privacy Policy

**Last Updated:** September 16, 2026  
**Product / Platform:** ${brand} (https://www.hakisense.in)  
**Operator / Entity:** ${businessName}  
**Registered Address:** ${address}  
**Grievance Officer / Contact:** [${supportEmail}](mailto:${supportEmail})  

---

### 1. Introduction
${businessName} ("we", "us", or "our") respects your privacy. This Privacy Policy outlines how we collect, store, protect, and process your personal and trading information when you use ${brand} ("Service") in accordance with the **Information Technology Act, 2000**, the **IT (Reasonable Security Practices and Procedures and Sensitive Personal Data or Information) Rules, 2011**, and the **Digital Personal Data Protection Act, 2023 (DPDP Act)**.

---

### 2. Information We Collect
We collect only the data necessary to provide and support your trading journal:
- **Account & Authentication Information:** Email address and login credentials handled securely through our authentication provider (Supabase Auth).
- **Trading Journal Data:** Trade execution timestamps, buy/sell prices, instruments, contracts, quantities, tags, trade screenshots, playbook setups, and broker CSV import files that you upload.
- **Payment & Transaction Identifiers:** Razorpay payment ID, order ID, amount paid (in INR), date of transaction, and credit pack selected. **We never store credit/debit card numbers, UPI PINs, CVVs, or net banking passwords.**
- **Technical & Diagnostics Data:** IP address, browser type, operating system, and system performance metrics for security, rate-limiting, and error diagnosis.

---

### 3. How We Use Your Information
Your data is used strictly for the following purposes:
- To calculate trade metrics, win rates, risk-reward ratios, and journal analytics.
- To execute AI-assisted coaching, trade review, and query workflows requested by you.
- To maintain your credit wallet, verify payments, and process eligible refunds.
- To protect against security threats, abuse, and platform instability.
- To send transactional notifications, password-reset emails, and support replies.

---

### 4. AI Review Processing & Confidentiality
When you request an AI review:
- Relevant journal context (e.g., trade entries, notes, and metrics) is sent via secure API to our LLM inference providers (e.g., OpenRouter / AI model partners).
- Your trade data is transmitted over encrypted channels solely to generate your requested review response.
- **We do NOT sell, rent, or trade your personal or trading data to brokers, advertising networks, or proprietary trading firms.**

---

### 5. Third-Party Service Providers
We work with reputable infrastructure providers who process data on our behalf under strict confidentiality agreements:
- **Supabase:** Cloud database and authentication infrastructure.
- **Razorpay:** Payment gateway and transaction processing (PCI-DSS Level 1 certified).
- **OpenRouter / AI Partners:** LLM inference infrastructure for trade reviews.
- **Render:** Cloud hosting for web services and APIs.

---

### 6. Data Security
We implement technical and organizational security measures to protect your data:
- TLS/HTTPS encryption for all data in transit.
- PostgreSQL Row-Level Security (RLS) ensuring strict isolation between user accounts.
- Encrypted password hashing and restricted system access.

---

### 7. Your Rights Under Indian Data Protection Law
You have complete control over your data:
- **Export Data:** Download your complete journal archive in JSON format anytime from Account Settings.
- **Rectification:** Edit or update inaccurate trade logs, profile settings, or account details.
- **Account & Data Deletion:** Request permanent deletion of your account and all associated trading data by contacting [${supportEmail}](mailto:${supportEmail}).

---

### 8. Grievance Redressal
If you have any questions, concerns, or grievances regarding our privacy practices or wish to exercise your statutory rights, please contact our Grievance Officer:

- **Attn:** Grievance Officer — ${brand}
- **Email:** [${supportEmail}](mailto:${supportEmail})  
- **Address:** ${address}  
- **Response Timeline:** Within 24–48 business hours.`;
  }

  return `# Cancellation & Refund Policy

**Last Updated:** September 16, 2026  
**Product / Platform:** ${brand} (https://www.hakisense.in)  
**Operator / Entity:** ${businessName}  
**Registered Address:** ${address}  
**Support Email:** [${supportEmail}](mailto:${supportEmail})  

---

### 1. Nature of Product & Billing
- ${brand} is a web-based Software-as-a-Service (SaaS) and personal trading journal.
- All credit pack purchases are **one-time payments**. We **do not** charge recurring subscriptions, automated monthly renewals, or hidden membership fees.
- Essential trade logging, analytics, and market replay features are available with monthly free allowances.

---

### 2. Credit Rules & In-App Auto-Refunds
- **Purchased Credits:** Credits purchased in packs do not expire and carry forward indefinitely.
- **Automatic In-App Refund for Failed AI Tasks:** If an AI review, coaching task, or workflow fails to generate or times out due to a system error, the reserved credits are **automatically returned to your in-app credit wallet immediately**.

---

### 3. Payment Refund Eligibility
We evaluate monetary refund requests on purchase transactions under the following terms:
- **7-Day Window for Unused Packs:** You may request a full refund within **7 calendar days** of the purchase date, provided the purchased credit pack remains **completely unused**.
- **Partially Used Packs:** If you have utilized a portion of the purchased credits, we may, at our discretion, issue a proportional refund for the unconsumed credits, calculated by deducting the consumed credits at our standard reference rate.
- **Duplicate or Erroneous Transactions:** If your account or card was charged more than once for the same recharge due to a network glitch or timeout, we will promptly refund the duplicate transaction in full upon verification.

---

### 4. Non-Refundable Scenarios
- Refund requests submitted after 7 calendar days from the purchase date.
- Packs where all purchased credits have been fully consumed.
- Free promotional grants, welcome credits, or monthly free credits (these hold zero cash value).
- Accounts suspended or terminated due to violations of our Terms of Service.

---

### 5. How to Request a Refund
To request a refund, please send an email to [${supportEmail}](mailto:${supportEmail}) from your registered account email with the following details:
1. **Email Subject:** \`Refund Request — [Your Registered Email]\`
2. **Razorpay Payment ID:** (e.g., \`pay_...\` available in your billing history and email receipt)
3. **Date of Payment & Amount (INR)**
4. **Reason for the refund request**

---

### 6. Processing & Payout Timeline
- **Review & Approval:** Our team reviews and responds to all refund requests within **24 to 48 business hours**.
- **Payout:** Once approved, the refund is initiated directly via Razorpay back to your original payment method (Bank Account, UPI, or Debit/Credit Card).
- **Settlement Timeline:** Funds typically reflect in your account within **5 to 7 business days**, depending on your bank's clearance cycles.
- Any unconsumed credits associated with the refunded transaction will be reversed from your wallet balance.`;
}

interface LegalProps {
  page?: LegalPageType;
}

export default function Legal({ page: initialPage }: LegalProps) {
  const location = useLocation();
  const navigate = useNavigate();

  // Infer tab from URL if prop is omitted: /terms -> 'terms', /privacy -> 'privacy', /refunds -> 'refunds'
  const inferTab = (): LegalPageType => {
    if (initialPage) return initialPage;
    const path = location.pathname.toLowerCase();
    if (path.includes('privacy')) return 'privacy';
    if (path.includes('refund')) return 'refunds';
    return 'terms';
  };

  const [activeTab, setActiveTab] = useState<LegalPageType>(inferTab);
  const [catalog, setCatalog] = useState<Catalog | null>(null);

  useEffect(() => {
    setActiveTab(inferTab());
  }, [location.pathname, initialPage]);

  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/catalog', { signal: controller.signal })
      .then(r => (r.ok ? r.json() : null))
      .then(setCatalog)
      .catch(() => {});
    return () => controller.abort();
  }, []);

  const brand = catalog?.brand_name || 'HakiSense';
  const businessName = catalog?.legal?.business_name || 'HakiSense';
  const supportEmail = catalog?.legal?.support_email || 'contact@hakisense.in';
  const address = 'Sector 14, Sonepat, Haryana, India';

  useEffect(() => {
    const titles: Record<LegalPageType, string> = {
      terms: `Terms of Service · ${brand}`,
      privacy: `Privacy Policy · ${brand}`,
      refunds: `Cancellation & Refund Policy · ${brand}`,
    };
    document.title = titles[activeTab];
    window.scrollTo(0, 0);
  }, [activeTab, brand]);

  const content = getLegalContent(activeTab, brand, businessName, supportEmail, address);

  const tabs: { key: LegalPageType; label: string; icon: typeof FileText; path: string }[] = [
    { key: 'terms', label: 'Terms of Service', icon: FileText, path: '/terms' },
    { key: 'privacy', label: 'Privacy Policy', icon: Shield, path: '/privacy' },
    { key: 'refunds', label: 'Cancellation & Refunds', icon: RotateCcw, path: '/refunds' },
  ];

  return (
    <div className="public-help">
      <header>
        <Link to="/" className="public-help-brand">
          <span className="brand-logo">H</span>
          {brand}
        </Link>
        <nav aria-label="Help and legal navigation">
          <Link to="/pricing">Pricing</Link>
          <Link to="/help">Help & customer care</Link>
          <Link className="button primary" to="/login">
            Open my journal <ArrowUpRight size={16} />
          </Link>
        </nav>
      </header>

      <main style={{ maxWidth: 960, margin: '0 auto', padding: '40px 24px' }}>
        {/* Policy Selector Tabs */}
        <div
          role="tablist"
          aria-label="Legal documents"
          style={{
            display: 'flex',
            gap: 12,
            marginBottom: 30,
            borderBottom: '1px solid #dfe7d7',
            paddingBottom: 16,
            flexWrap: 'wrap',
          }}
        >
          {tabs.map(tab => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                type="button"
                role="tab"
                aria-selected={isActive}
                onClick={() => {
                  setActiveTab(tab.key);
                  navigate(tab.path);
                }}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '10px 18px',
                  borderRadius: 8,
                  border: isActive ? '1px solid #8ba966' : '1px solid #e0e8d7',
                  background: isActive ? '#f0f6e7' : '#ffffff',
                  color: isActive ? '#395325' : '#69785e',
                  fontSize: 13,
                  fontWeight: isActive ? 600 : 500,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <Icon size={16} />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Business Summary Card for Razorpay Reviewers & Users */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: 14,
            background: '#ffffff',
            border: '1px solid #dfe7d7',
            borderRadius: 12,
            padding: '20px 24px',
            marginBottom: 36,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
            <Building2 size={18} style={{ color: '#739150', marginTop: 2, flexShrink: 0 }} />
            <div>
              <small style={{ color: '#88987d', fontSize: 11, display: 'block' }}>Legal Operator</small>
              <strong style={{ fontSize: 13, color: '#273827' }}>{businessName}</strong>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
            <Mail size={18} style={{ color: '#739150', marginTop: 2, flexShrink: 0 }} />
            <div>
              <small style={{ color: '#88987d', fontSize: 11, display: 'block' }}>Customer Support</small>
              <a href={`mailto:${supportEmail}`} style={{ fontSize: 13, color: '#567c3b', textDecoration: 'none' }}>
                {supportEmail}
              </a>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
            <MapPin size={18} style={{ color: '#739150', marginTop: 2, flexShrink: 0 }} />
            <div>
              <small style={{ color: '#88987d', fontSize: 11, display: 'block' }}>Jurisdiction & Address</small>
              <span style={{ fontSize: 12, color: '#273827' }}>Sector 14, Sonepat, Haryana</span>
            </div>
          </div>
        </div>

        {/* Legal Markdown Document Container */}
        <div
          style={{
            background: '#ffffff',
            border: '1px solid #dfe7d7',
            borderRadius: 14,
            padding: '36px 42px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.02)',
          }}
        >
          <Markdown>{content}</Markdown>
        </div>
      </main>

      <footer>
        <Link to="/">← Back to {brand}</Link>
        <div style={{ display: 'flex', gap: 20 }}>
          <Link to="/terms">Terms</Link>
          <Link to="/privacy">Privacy</Link>
          <Link to="/refunds">Refunds</Link>
          <Link to="/help">Help</Link>
        </div>
        <span>Made for Indian traders · INR / IST</span>
      </footer>
    </div>
  );
}

