# Landing page redesign

## Diagnosis and decision

The previous page paired a very large expressive headline with tiny supporting copy, miniature labels, a tilted chart and only three short content sections before a full pricing catalog. It communicated a mood before explaining the product. Strong existing features were difficult to discover.

Three directions were considered before implementation:

- A dense trading terminal: credible product detail, but too much visual competition and jargon for a first visit.
- An editorial journal: distinctive and calm, but insufficient on its own to show concrete value (the existing page's weakness).
- An editorial narrative supported by product demonstrations: selected. Consistent typography and generous spacing establish the brand; focused examples substantiate the story.

## Narrative and conversion

1. **Promise:** your trading history contains lessons; show a realistic, labelled product overview beside an explicit journal/analytics/AI proposition.
2. **Tension:** P&L alone cannot explain execution. Give three recognisable questions rather than generic feature claims.
3. **Capture:** gather trades, risk, notes and mindset in one record. Establish the input before promising insights.
4. **Understand:** interactive analytics examples grouped by setup, emotion and entry time. Show both gains and losses.
5. **Investigate:** AI questions, grounded sample answers and supporting trade references. No provider calls or invented endorsements.
6. **Apply:** playbook rules plus candle-by-candle practice. The lesson becomes a repeatable routine.
7. **Fit:** Indian market conventions, INR, IST and imports. Clearly distinguish file imports from connected broker sync.
8. **Start:** free journal tools, dynamic monthly allowance and a link to current credit packs. Full shared pricing remains on /pricing.
9. **Resolve:** concise FAQs, then a final invitation tied to the opening promise.

Urgency comes from the opportunity to learn from trades already taken. No fabricated scarcity, customer counts, returns, testimonials or guarantees.

## Visual contract

- Warm paper, forest ink, muted green secondary text and a single lime action accent.
- DM Sans for prose; Space Grotesk for headings/numbers. No decorative serif. The subsequent motion revision restores restrained perspective and a layered takeaway to the interactive hero.
- Desktop hero approximately 64px; section headings 38–44px; card headings 20–24px; body 16–18px; supporting copy 14px; short labels 12px.
- Mobile hero approximately 40px; section headings approximately 32px. Product previews reflow rather than shrinking into illegible screenshots.
- 1184px content maximum; shared section spacing and borders; alternating light and dark chapters to distinguish narrative transitions.
- All landing rules scoped to .landing, preserving authenticated application and shared billing styles.
- Native links/buttons, visible keyboard focus, reduced-motion support, accessible navigation and demo controls. Content never depends on scroll-triggered animation.

## Evidence and scope

Verified against src/Analytics.tsx, src/Notes.tsx, src/Import.tsx, src/Simulator.tsx, src/Pricing.tsx and the current README. Sample visuals are simplified demonstrations, not screenshots or live account data. Replay uses uploaded OHLC or sample candles. Playbook creation uses credits; editing and linking trades are free. Catalog prices and allowances must remain backend-controlled. No database, auth, billing or payment behavior changes are required.

## Acceptance checks

Production TypeScript/Vite build; desktop and narrow-mobile rendering; no horizontal page overflow; analytics and AI examples switch correctly; replay controls update visible bars; mobile navigation and Escape behavior; FAQ, signup and pricing navigation; catalog failure/retry; live pricing when API is available; keyboard and reduced-motion checks. Keep any unavailable backend verification explicit.

## Verification completed — 17 September 2026

- `npm run build`: passed after final source changes (TypeScript and Vite). Vite still reports the existing >500 kB authenticated-workspace chunk warning; the landing bundle is separate.
- `git diff --check`: passed.
- Browser layout reviewed at 1280, 1440, 768, 390 and 320px widths. Document width matched viewport width at all measured breakpoints; explicit element overflow checks passed at 768, 390 and 320px.
- Desktop and mobile screenshots inspected for the hero and feature chapters. Simplified the initial hero preview after inspection to keep its action visible on desktop. Fixed the narrowest header so the primary action stays on one line.
- Analytics: selecting Emotion updated the heading and grouped results.
- AI example: selecting Look at my risk updated the question, answer and supporting sample references.
- Replay: stepping changed candle 12 to 13; reset returned to candle 4.
- Mobile menu: opens, Escape closes it and returns focus, and choosing AI review closes it and navigates to the section.
- FAQ: opening the free-tools question exposes its answer.
- Primary signup action reaches `/signup` and the registration page.
- Pricing link reaches `/pricing`; the live catalog rendered 50 monthly free credits and current recharge packs. No payment was attempted.
- Exactly one h1 on the landing page; all in-page fragment links resolve. Desktop section typography measured 44px headings and 17px body copy.
- Browser console check returned no errors or warnings during the inspected session.
- Reduced-motion rules and catalog failure/retry handling are present and source-reviewed. Network failure injection, OS reduced-motion emulation and a full assistive-technology audit were not performed.

No database, authentication, AI-provider or payment changes were needed. Existing unrelated modifications to `backend/runtime_settings.py` and `scripts/prepare_production_env.py` were left intact.

## Motion and interaction revision — 17 September 2026

The user found the first revision too static, especially the hero, and asked for a clean, modern presentation with purposeful motion rather than interaction everywhere. This revision supersedes the initial static hero decision.

- Restored a dark, interactive hero with NIFTY, RELIANCE and BTC sample trades; a keyboard-accessible candle slider; hover inspection; user-started, one-shot replay; notes that follow the trade phase; and a layered takeaway.
- Added restrained desktop pointer perspective and scroll parallax. The scroll listener updates CSS properties through requestAnimationFrame; it does not drive React renders or alter layout dimensions. Coarse/small-screen layouts omit parallax.
- Added one-time section reveals, short content transitions, interpolated analytics bars, gentle button feedback, a chapter navigator and a reading-progress line. Content stays available when motion is paused or reduced.
- Made the example playbook checklist interactive. This is local demonstration state only.
- Added a visible motion toggle and device reduced-motion support. Playback stops when the hero leaves view or the document is hidden.
- Added shared native smooth anchor navigation in `src/AnchorScrolling.tsx`. Same-page clicks have one scroll owner; repeated anchors work; cross-route lazy content is observed until its target mounts; sticky-header offsets are defined in CSS. Route resets and history navigation remain immediate. No global smooth-scroll CSS or custom easing loop.
- Added shared dropdown presence and transitions for Select, SuggestInput and AccountMenu. Closing portals become inert and hidden from assistive technology immediately, then unmount after 140ms. Opening lasts 180ms. Search/suggestion content is retained during closing to avoid a visual flash.
- Dropdown keyboard navigation now scrolls only the option list; focus uses preventScroll. This prevents document movement and accidental popup dismissal. Account menus close on external scrolling.
- Mobile navigation expands without changing page layout. Native details disclosures receive progressive CSS transitions where supported, including other app pages.

### Verification

- Production TypeScript/Vite build and `git diff --check` passed. Existing authenticated-workspace bundle-size warning remains.
- Hero market switching, keyboard Home scrubbing, replay completion, pause/enable controls, manual stepping while motion is paused, playbook completion, analytics switching and AI switching were checked in the browser.
- The current browser supports native disclosure size interpolation; FAQ opening and mobile menu navigation were checked.
- Desktop section anchors settled at 175px below the header/chapter navigator; mobile anchors settled at 90px. Cross-route navigation from pricing to a homepage section passed.
- The local fixture at `/tests/ui/motion-preview.html` verifies shared Select/SuggestInput, list scrolling, portals inside a modal dialog and anchor scrolling without customer data or backend calls.
- Long dropdown list Home/End navigation changed list scrollTop from 0 to 1213 while document scrollY remained exactly 456.5. Escape restored trigger focus with the closing portal inert. Selection, suggestions and modal dropdowns passed.
- Instrumented native scrolling produced 60 nondecreasing positions going down and 87 nonincreasing positions returning to the top; no reversal or second jump was recorded.
- Responsive checks covered 320, 390, 768, 1280 and 1440px. Fixed narrow-header clipping; final 320px header controls fit the available client width. No horizontal document overflow at checked widths.
- The final clean browser run returned no console errors or warnings after fixing duplicate animation keys. In-view sections were revealed and parallax/progress values updated as expected.
- Device reduced-motion CSS/JS handling is implemented and source-reviewed; OS preference emulation and a full screen-reader audit were not performed. The visible motion toggle was tested directly. AccountMenu shares the tested presence helper; authenticated account actions were not exercised.

## Navigation surface and AI emphasis — 17 September 2026

- Moved the sticky positioning and background from the constrained chapter navigator to a full-width wrapper. The primary header and chapter bar now share an opaque neutral surface, so underlying section colours cannot create a floating rectangle. Reduced the chapter bar to 65px on desktop and updated anchor offsets to 164px; mobile retains the non-sticky chapter list.
- Gave AI coaching a dedicated warm amber section, dark readable text, contrasting selected prompts and a framed example response. The headline explicitly names the AI trading coach, explains its review benefits, and includes a signup CTA. Navigation now says “AI coach”. The illustrative responses and their evidence remain unchanged.
- Removed the browser outline on programmatically focused section containers while retaining visible focus indicators on interactive controls.
- Verified the desktop chapter bar spans the full viewport (1280px), ends at 148px, and the analytics anchor lands at approximately 164px. Checked 390px and 320px layouts without horizontal overflow, AI prompt selection, and a clean browser console. Production build passed; the existing workspace bundle-size warning remains.

### Correction after visual feedback

The amber treatment was rejected. Replaced it with a deep blue-charcoal section and restrained mint accents, and rebuilt the section as a compact two-column introduction/demo layout. On small screens it stacks. The chapter navigator now remains in normal page flow; only the primary header is sticky. Desktop anchor offsets return to 98px. AI wording remains explicit and the sample answers are unchanged.

Verified the corrected desktop and 390px layouts, no horizontal overflow, prompt switching, static chapter positioning, production build and diff whitespace checks. No additional motion was introduced.

### Theme and story order requested by the user

AI coaching now uses the exact hero dark green (`#1c3328`) through a shared `--lp-dark` variable, with the existing green/lime accents. Removed the tension/question section entirely. The first feature after the hero/navigation is now 01 AI coaching, followed by 02 Journal, 03 Analytics, and 04 Playbooks & replay. Header/footer links and the chapter navigator follow that order; the hero demo link goes to AI coaching and analytics continues forward to practice. Removed the deleted section's styling and reveal selectors.

Production build and diff checks passed. Browser inspection confirmed identical hero/AI background colours, matching chapter/navigation order, the deleted section's absence, and no desktop horizontal overflow.

### Final section order clarification

The user specified the exact order: 01 Remember what really happened (Journal), 02 AI trade analysis, 03 See what keeps repeating (Analytics), 04 Make the lesson part of your process (Playbooks & replay). Updated rendered section order, chapter numbers, navigation and forward links accordingly. The hero secondary link starts at Journal. Theme colours and removal of the tension section remain as requested.
