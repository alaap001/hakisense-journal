import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ArrowDown, ArrowRight, ArrowUpRight, BarChart3, BookOpen, Check, ChevronDown, ChevronRight, CircleHelp, Clock3, FileUp, ListChecks, Menu, MessageSquare, Pause, Play, RotateCcw, SkipForward, X } from 'lucide-react';
import { Pricing } from './Pricing';
import type { Catalog } from './types';
import { HeroExperience } from './LandingExperience';
import { useLandingMotion } from './useLandingMotion';
import './landing.css';
import './landingMotion.css';

const breakdowns = [
  { name: 'Setup', title: 'Which setups deserve your attention?', rows: [{name:'Range retest',value:8400},{name:'Opening breakout',value:5100},{name:'Momentum chase',value:-2400}], note: 'The same market. Three very different results. Review each setup before treating them as one strategy.' },
  { name: 'Emotion', title: 'What changes when you chase?', rows: [{name:'Patient',value:9600},{name:'Neutral',value:3900},{name:'Rushed',value:-2400}], note: 'Add your mindset to each trade. Then compare the results behind “I trade better when I wait.”' },
  { name: 'Entry time', title: 'When does your process hold up?', rows: [{name:'09:15–10:00',value:6900},{name:'10:00–12:00',value:6600},{name:'After 12:00',value:-2400}], note: 'Review results by entry hour in IST. Find the sessions that deserve a closer look.' },
];
const questions = [
  { label:'Review my execution', question:'What should I review in these trades?', answer:'The RELIANCE note records an entry before confirmation. The NIFTY note records waiting for a retest. Compare those decisions against your entry rules; one win and one loss are not enough to establish a pattern.', evidence:['NIFTY · Waited for the retest','RELIANCE · Entered before confirmation'], takeaway:'Review the decision, not just the outcome.' },
  { label:'Look at my risk', question:'Did I respect my risk plan?', answer:'The RELIANCE note says the position exited at the planned stop. That is useful evidence of risk discipline, even on a losing trade. Review the recorded stop, quantity and fees alongside the note before drawing a wider conclusion.', evidence:['RELIANCE · Planned stop respected','RELIANCE · Net result −₹1,500'], takeaway:'A losing trade can still follow a sound process.' },
  { label:'Plan my next review', question:'What is one thing to focus on next?', answer:'Compare your planned entry conditions with what you actually did. The notes mention a patient retest, an early entry and a planned scale-out. Use these as starting points for your next journal review.', evidence:['NIFTY · Patient entry','BTC · Planned scale-out'], takeaway:'Choose one behaviour you can document next session.' },
];
const candleValues = [44,49,46,55,51,60,67,62,70,65,73,79,74,82,87,81,91,96,89,99,103,98,110,106];
const formatRupees = (value:number) => `${value < 0 ? '−' : '+'}₹${Math.abs(value).toLocaleString('en-IN')}`;

function Brand({name = 'HakiSense'}:{name?:string}) {
  return <Link className="landing-brand" to="/" aria-label={`${name} home`}><span className="landing-monogram" aria-hidden="true">H<span/></span><span>{name}<small>THE TRADING JOURNAL</small></span></Link>;
}
function SignupLink({children = 'Start your free journal',light = false}:{children?:React.ReactNode;light?:boolean}) {
  return <Link to="/signup" className={`landing-cta${light?' cta-light':''}`}>{children}<ArrowUpRight size={18}/></Link>;
}
function ChapterLabel({number,children}:{number:string;children:React.ReactNode}) {
  return <div className="chapter-label"><span>{number}</span>{children}</div>;
}
function CaptureChapter() {
  return <section data-story-chapter className="landing-section landing-container story-split" id="the-process" aria-labelledby="capture-title">
    <div className="chapter-copy"><ChapterLabel number="01">REMEMBER WHAT REALLY HAPPENED</ChapterLabel><h2 id="capture-title">Your broker records<br/>the trade.<br/><span>You record the why.</span></h2><p>Price and quantity tell one part of the story. Your setup, risk, timing and state of mind tell the part you can learn from.</p><ul className="benefit-list"><li><Check/>Bring in your history with CSV, TSV or Excel imports.</li><li><Check/>Keep entries, exits, fees and notes together.</li><li><Check/>Tag your setups and emotions while they’re still fresh.</li></ul><a className="landing-text-link" href="#ai-review">Review it with your AI coach <ArrowRight size={17}/></a></div>
    <figure className="entry-example"><div className="example-header"><span><BookOpen size={17}/>THE TRADE, IN CONTEXT</span><span className="example-label">EXAMPLE</span></div><div className="entry-symbol"><div><span className="demo-eyebrow">NSE · INDEX OPTIONS</span><h3>NIFTY</h3></div><span className="entry-result">+2.4R</span></div><dl className="entry-facts"><div><dt>Setup</dt><dd>Opening range breakout</dd></div><div><dt>Risk plan</dt><dd>Defined before entry</dd></div><div><dt>State of mind</dt><dd><span className="journal-tag">Patient</span><span className="journal-tag">Focused</span></dd></div></dl><div className="entry-note"><span className="demo-eyebrow">WHAT I WANT TO REMEMBER</span><blockquote>“Skipped the first move. Waited for the retest. Kept my stop where the setup failed.”</blockquote></div><figcaption><Check size={15}/>More than a result. A decision you can revisit.</figcaption></figure>
  </section>;
}
function AnalyticsChapter() {
  const [active,setActive] = useState(0);
  const current = breakdowns[active];
  return <section data-story-chapter className="analytics-chapter" id="patterns" aria-labelledby="patterns-title"><div className="landing-container landing-section story-split">
    <div className="analysis-example"><div className="example-header"><span><BarChart3 size={17}/>PERFORMANCE BREAKDOWN</span><span className="example-label">SAMPLE DATA</span></div><div className="demo-switcher" role="group" aria-label="Group sample performance by">{breakdowns.map((item,i)=><button type="button" key={item.name} aria-pressed={active===i} onClick={()=>setActive(i)}>{item.name}</button>)}</div><div className="analysis-content" aria-live="polite" aria-atomic="true"><h3 key={`title-${active}`} className="demo-content-enter">{current.title}</h3><div className="breakdown-key"><span>Net P&L after fees</span><span>Illustrative results</span></div><div className="breakdown-bars">{current.rows.map((row,index)=><div key={index}><div><span>{row.name}</span><strong className={row.value<0?'demo-loss':'demo-gain'}>{formatRupees(row.value)}</strong></div><div className="breakdown-track"><span className={row.value<0?'loss-bar':''} style={{width:`${Math.abs(row.value)/100}%`}}/></div></div>)}</div><p key={`note-${active}`} className="analysis-observation demo-content-enter">{current.note}</p></div><div className="example-footer"><CircleHelp size={15}/>Try a different view. Notice what the total hides.</div></div>
    <div className="chapter-copy"><ChapterLabel number="03">SEE WHAT KEEPS REPEATING</ChapterLabel><h2 id="patterns-title">One P&L.<br/><span>Many possible stories.</span></h2><p>A green month can hide a weak setup. A red day can hide a well-executed plan. Break down your performance to see the difference.</p><ul className="benefit-list"><li><Check/>Compare setups, instruments, emotions and entry times.</li><li><Check/>Look beyond win rate to expectancy and profit factor.</li><li><Check/>See fees, drawdowns and risk in the same workspace.</li></ul><a className="landing-text-link" href="#practice">Put your insights into practice <ArrowRight size={17}/></a></div>
  </div></section>;
}
function AIChapter() {
  const [active,setActive] = useState(0);
  const current = questions[active];
  return <section data-story-chapter className="ai-chapter" id="ai-review" aria-labelledby="ai-title">
    <div className="landing-container landing-section">
      <ChapterLabel number="02">AI TRADE ANALYSIS</ChapterLabel>
      <div className="ai-layout">
        <div className="ai-copy">
          <div className="ai-heading">
            <h2 id="ai-title">Your trades.<br/><span>Your AI coach.</span></h2>
            <p>Understand the decisions behind your results. Review your execution, examine your risk and find a clear focus for your next session—with your own journal as the evidence.</p>
          </div>
          <div className="ai-prompts">
            <span className="demo-eyebrow">TAKE A CLOSER LOOK</span>
            {questions.map((item,i)=><button type="button" key={item.label} aria-pressed={active===i} onClick={()=>setActive(i)}><MessageSquare size={18}/><span>{item.label}</span><ArrowUpRight size={16}/></button>)}
            <Link className="landing-text-link" to="/signup">Start your first AI review <ArrowUpRight size={17}/></Link>
          </div>
        </div>
        <div className="ai-response">
          <div className="example-header"><span><MessageSquare size={17}/>HAKISENSE AI COACH</span><span className="example-label">ILLUSTRATIVE ANSWER</span></div>
          <div key={active} className="ai-answer-content demo-content-enter" aria-live="polite" aria-atomic="true">
            <div className="ai-question">{current.question}</div>
            <div className="ai-answer"><span className="mini-monogram">H</span><div><p>{current.answer}</p><span className="demo-eyebrow">SUPPORTING SAMPLE TRADES</span><div className="evidence-chips">{current.evidence.map(item=><span key={item}><BookOpen size={13}/>{item}</span>)}</div><strong>{current.takeaway}</strong></div></div>
          </div>
          <div className="ai-response-footer">Sample review · Grounded in journal entries, guided by your judgment.</div>
        </div>
      </div>
    </div>
  </section>;
}
function ReplayExample() {
  const [position,setPosition] = useState(12);
  return <div className="replay-example"><div className="replay-top"><span>NIFTY <small>· PRACTICE</small></span><span className="example-label">SAMPLE CANDLES</span></div><svg viewBox="0 0 480 165" role="img" aria-label={`Practice preview showing ${position} of 24 sample candles. Future candles remain hidden.`}>{[35,80,125].map(y=><line key={y} x1="0" y1={y} x2="480" y2={y} stroke="#dce3d5" strokeDasharray="3 5"/>)}{candleValues.slice(0,position).map((value,i)=>{const previous = i ? candleValues[i-1] : 40; const rising=value>=previous;return <g key={i}><line x1={i*19+14} x2={i*19+14} y1={160-Math.max(value,previous)*1.15-6} y2={160-Math.min(value,previous)*1.15+6} stroke={rising?'#547848':'#aa6b5f'}/><rect x={i*19+10} y={160-Math.max(value,previous)*1.15} width="8" height={Math.max(3,Math.abs(value-previous)*1.15)} rx="1" fill={rising?'#547848':'#aa6b5f'}/></g>})}{position<24&&<text x="327" y="37" fill="#667260" fontSize="12">The next move?</text>}</svg><div className="replay-controls"><button type="button" aria-label="Reset sample replay" onClick={()=>setPosition(4)}><RotateCcw size={16}/></button><span aria-live="polite">Candle {position} / 24</span><button type="button" disabled={position===24} onClick={()=>setPosition(value=>Math.min(24,value+1))}>{position===24?'Replay complete':'Reveal next candle'}<SkipForward size={15}/></button></div></div>;
}
function PlaybookExample() {
  const [checked, setChecked] = useState([true, false, false]);
  const complete = checked.filter(Boolean).length;
  return <div className="playbook-example"><div className="example-header"><span>MY OPENING RANGE PLAYBOOK</span><BookOpen size={17}/></div>{['Wait for the opening range to form','Enter only after confirmation','Define the stop before the entry'].map((text,index)=><button type="button" className="playbook-rule" key={text} aria-pressed={checked[index]} onClick={()=>setChecked(values=>values.map((value,i)=>i===index?!value:value))}><span>0{index+1}</span>{text}<span className="playbook-check"><Check size={14}/></span></button>)}<div className="playbook-footer" aria-live="polite"><span>{complete} / 3 conditions checked</span><strong>{complete===3?'A plan worth following.':'Try your pre-trade checklist.'}</strong></div></div>;
}
function PracticeChapter({catalog}:{catalog:Catalog|null}) {
  return <section data-story-chapter className="landing-container landing-section practice-chapter" id="practice" aria-labelledby="practice-title"><div className="section-heading"><ChapterLabel number="04">MAKE THE LESSON PART OF YOUR PROCESS</ChapterLabel><h2 id="practice-title">An insight is a start.<br/><span>A repeatable routine is the next step.</span></h2><p>Bring what you learned into a playbook. Then give yourself room to practise it.</p></div><div className="practice-grid"><article className="practice-card"><div className="practice-card-copy"><ListChecks size={23}/><h3>Write the rules you want to follow.</h3><p>Build a strategy playbook with entry conditions and a checklist. Link your trades to see how the setup performs.</p></div><PlaybookExample/><p className="practice-footnote">{catalog?`${catalog.playbook_creation_credits} credit${catalog.playbook_creation_credits===1?'':'s'} to create a playbook. `:'Playbook creation uses credits. '}Editing and linking trades are free.</p></article><article className="practice-card"><div className="practice-card-copy"><Clock3 size={23}/><h3>Practise without the hindsight.</h3><p>Reveal the market one candle at a time. Use uploaded price history or sample data to rehearse your decisions.</p></div><ReplayExample/><p className="practice-footnote">Simulated practice with uploaded OHLC or sample candles.</p></article></div><div className="routine-line"><span>Record</span><ArrowRight/><span>Understand</span><ArrowRight/><span>Refine</span><ArrowRight/><span>Repeat</span><RotateCcw/></div></section>;
}
function IndiaChapter() {
  return <section className="india-chapter" id="made-for-india" aria-labelledby="india-title"><div className="landing-container landing-section"><div className="india-heading"><div><span className="landing-eyebrow">YOUR MARKET. YOUR CONTEXT.</span><h2 id="india-title">At home in<br/><span>your trading day.</span></h2></div><p>From the opening bell on Dalal Street to your last review of the day. A workspace built around Indian traders.</p></div><div className="india-grid"><article><span className="india-icon">₹</span><h3>Your numbers, in rupees.</h3><p>Review performance and recorded fees in INR, with Indian number formatting and sessions in IST.</p></article><article><BarChart3 size={26}/><h3>Your markets, together.</h3><p>Journal NSE and BSE equities, index options, futures and crypto across your trading accounts.</p></article><article><FileUp size={26}/><h3>Your history, a head start.</h3><p>Import position-level CSV, TSV or Excel files. Map columns and check duplicates before adding trades.</p></article></div><div className="india-note"><span>NSE / BSE</span><span>INDEX DERIVATIVES</span><span>CRYPTO</span><span>INR / IST</span><p>File imports · No live broker connection required</p></div></div></section>;
}
function FreeStart({catalog}:{catalog:Catalog|null}) {
  return <section className="landing-container landing-section free-start" id="plans" aria-labelledby="free-title"><div className="chapter-copy"><span className="landing-eyebrow">TAKE YOUR PROCESS SERIOUSLY. START SIMPLY.</span><h2 id="free-title">Build the habit.<br/><span>Keep the commitment small.</span></h2><p>Your journal, analytics and replay are free to use. Credits cover AI reviews and playbook creation. Recharge when you need more.</p><Link className="landing-text-link" to="/pricing">Explore credit packs & pricing <ArrowRight size={17}/></Link></div><div className="free-card"><span className="landing-eyebrow">YOUR FREE WORKSPACE</span><div className="free-price">₹0<span>to start. No subscription.</span></div><ul className="benefit-list"><li><Check/>Unlimited trade entries</li><li><Check/>Analytics, imports, notes and replay</li><li><Check/>{catalog?`${catalog.monthly_free_credits.toLocaleString('en-IN')} free credits every month`:'Monthly free credits included'}</li><li><Check/>No card needed to get started</li></ul><SignupLink/><p>One-time recharges. Purchased credits never expire.</p></div></section>;
}

export default function Landing() {
  const {pathname,hash,key:locationKey} = useLocation();
  const pricingOnly = pathname === '/pricing';
  const [catalog,setCatalog] = useState<Catalog|null>(null);
  const [error,setError] = useState(false);
  const [retry,setRetry] = useState(0);
  const [mobile,setMobile] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const nav = useRef<HTMLElement>(null);
  const root = useRef<HTMLDivElement>(null);
  const motion = useLandingMotion(root, pathname);
  useEffect(()=>{
    const controller = new AbortController();
    setError(false);
    fetch('/api/catalog',{signal:controller.signal}).then(response=>{if(!response.ok)throw new Error('Catalog unavailable');return response.json();}).then(setCatalog).catch(cause=>{if(cause.name!=='AbortError')setError(true);});
    return ()=>controller.abort();
  },[retry]);
  useEffect(()=>{
    setMobile(false);
    document.title = pricingOnly?'Credit packs & pricing · HakiSense':'HakiSense — Turn your trading history into your next advantage';
    if(!hash) window.scrollTo({top:0, behavior:'instant'});
  },[pathname,hash,pricingOnly,locationKey]);
  useEffect(()=>{
    if(!mobile)return;
    const onKey = (event:KeyboardEvent)=>{if(event.key==='Escape'){setMobile(false);menuButton.current?.focus();}};
    const outside = (event:PointerEvent)=>{if(event.target instanceof Node&&!nav.current?.contains(event.target)&&!menuButton.current?.contains(event.target))setMobile(false);};
    document.addEventListener('keydown',onKey);document.addEventListener('pointerdown',outside);
    return ()=>{document.removeEventListener('keydown',onKey);document.removeEventListener('pointerdown',outside);};
  },[mobile]);
  const faqs = [
    ['What can I do for free?',`Log unlimited trades, import your history, explore analytics, keep notes and use market replay. ${catalog?`You also receive ${catalog.monthly_free_credits.toLocaleString('en-IN')} free credits each month.`:'Monthly free credits are also included.'} No subscription or card is required to start.`],
    ['Can I bring in my existing trades?','Yes. Import position-level CSV, TSV or Excel files, map your columns and review duplicates. You can also enter trades manually. Imports use files you provide; they are not a live broker sync.'],
    ['How does the AI use my journal?','Ask questions about your trading history and review the supporting evidence. Standard and Advanced modes are available. AI helps you investigate your records; it does not place trades or provide a live market feed.'],
    ['What uses credits?',`AI reviews use credits based on the work needed, with the final charge shown alongside the result. ${catalog?`Creating a playbook costs ${catalog.playbook_creation_credits} credit${catalog.playbook_creation_credits===1?'':'s'}.`:'Creating a playbook also uses credits.'} Editing playbooks and linking trades are free. See pricing for current allowances and charges.`],
    ['Do I need a subscription?','No. Credit recharges are one-time purchases without automatic renewal. Purchased credits never expire; monthly free credits refresh each month. Failed AI tasks are refunded.'],
    ['Does replay include live market data?','Replay uses OHLC candle history you upload or clearly labelled sample data. It reveals candles progressively so you can practise decisions without seeing the next bar. It is a simulation, not a live trading or execution service.'],
  ];
  return <div ref={root} data-motion={motion.paused?'off':'on'} className={`landing${pricingOnly?' pricing-page':''}`}><a href="#landing-main" className="landing-skip">Skip to content</a>
    <header className="landing-header"><div className="landing-reading-progress" aria-hidden="true"/><div className="landing-container landing-nav"><Brand name={catalog?.brand_name}/><nav ref={nav} id="landing-navigation" onClick={event=>{if(event.target instanceof Element&&event.target.closest('a'))setMobile(false);}} className={mobile?'is-open':''} aria-label="Main navigation"><div className="landing-nav-links"><Link to="/#the-process">The process</Link><Link to="/#ai-review">AI coach</Link><Link to="/#made-for-india">Built for India</Link><Link to="/pricing" aria-current={pricingOnly?'page':undefined}>Pricing</Link><Link className="mobile-sign-in" to="/login">Sign in</Link></div></nav><div className="landing-nav-actions"><button type="button" className="landing-motion-toggle" disabled={motion.systemReduced} aria-label={motion.systemReduced?'Motion reduced by system preference':motion.paused?'Enable page motion':'Pause page motion'} title={motion.systemReduced?'Reduced motion follows your device settings':motion.paused?'Enable page motion':'Pause page motion'} aria-pressed={motion.paused} onClick={motion.toggleMotion}>{motion.paused?<Play size={15}/>:<Pause size={15}/>}<span>Motion</span></button><Link className="landing-login" to="/login">Sign in</Link><Link className="nav-cta" to="/signup">Start free <ArrowUpRight size={16}/></Link><button ref={menuButton} type="button" className="landing-mobile-toggle" aria-label={mobile?'Close navigation':'Open navigation'} aria-expanded={mobile} aria-controls="landing-navigation" onClick={()=>setMobile(value=>!value)}>{mobile?<X/>:<Menu/>}</button></div></div></header>
    <main className="landing-main" id="landing-main" tabIndex={-1}>
      {!pricingOnly?<>
        <section className="landing-container landing-hero" aria-labelledby="hero-title"><div className="hero-copy"><span className="landing-eyebrow"><span className="status-dot"/>FOR TRADERS WHO WANT TO UNDERSTAND THEIR EDGE</span><h1 id="hero-title">Your next edge<br/>is in your<br/><span>last trade.</span></h1><p>A trading journal, analytics desk and AI review partner in one place. Understand the setups you repeat, the risks you take and what to work on next.</p><div className="hero-actions"><SignupLink/><a href="#the-process" className="hero-secondary">See how it works <ArrowDown size={16}/></a></div><div className="hero-assurance"><span><Check size={14}/>Free journal & analytics</span><span><Check size={14}/>No card needed</span></div></div><HeroExperience motionPaused={motion.paused}/></section>
        <div className="capability-bar"><nav className="landing-container capability-strip" aria-label="Explore the review routine"><span>EXPLORE YOUR NEXT EDGE</span><a data-story-link="the-process" href="#the-process"><span>01</span><BookOpen size={17}/>Journal</a><a data-story-link="ai-review" href="#ai-review"><span>02</span><MessageSquare size={17}/>AI coach</a><a data-story-link="patterns" href="#patterns"><span>03</span><BarChart3 size={17}/>Analytics</a><a data-story-link="practice" href="#practice"><span>04</span><ListChecks size={17}/>Playbooks & replay</a></nav></div>
        <CaptureChapter/><AIChapter/><AnalyticsChapter/><PracticeChapter catalog={catalog}/><IndiaChapter/><FreeStart catalog={catalog}/>
      </>:<section className="landing-container landing-pricing-wrap"><div className="pricing-page-intro"><Link to="/">HakiSense <ChevronRight size={14}/></Link><span>Credit packs & pricing</span></div>{catalog?<Pricing catalog={catalog} headingLevel={1}/>:<div className="catalog-state" role="status"><span className="landing-eyebrow">SIMPLE, ONE-TIME RECHARGES</span><h1>{error?'Pricing is temporarily unavailable.':'Your next review starts here.'}</h1><p>{error?'We couldn’t load current credit packs. Please try again.':'Loading current prices and monthly allowances…'}</p>{error&&<button type="button" className="landing-cta" onClick={()=>setRetry(value=>value+1)}>Try again <RotateCcw size={17}/></button>}</div>}</section>}
      <section className="landing-container landing-section faq-section" aria-labelledby="faq-title"><div><span className="landing-eyebrow">A FEW THINGS, MADE CLEAR.</span><h2 id="faq-title">Before your<br/><span>first entry.</span></h2><p>Need a hand getting started?</p><Link to="/help" className="landing-text-link">Visit the help centre <ArrowUpRight size={16}/></Link></div><div className="faq-list">{faqs.map(([question,answer])=><details key={question}><summary>{question}<ChevronDown size={18}/></summary><p>{answer}</p></details>)}</div></section>
      <section className="closing-section"><div className="landing-container"><span className="landing-eyebrow">THE NEXT SESSION WILL COME. BRING SOMETHING FORWARD.</span><h2>Don’t leave the lesson<br/><span>in yesterday’s trade.</span></h2><p>Start with one trade. Find one thing worth repeating.<br/>Build your process from there.</p><SignupLink light/><div className="closing-assurance">Free to start <span>·</span> Made for Indian traders <span>·</span> Built around your process</div></div></section>
    </main>
    <footer className="landing-footer"><div className="landing-container"><div className="footer-top"><div><Brand name={catalog?.brand_name}/><p>For the work that makes<br/>the next session more deliberate.</p></div><div className="footer-links"><div><strong>Explore</strong><Link to="/#the-process">The process</Link><Link to="/#ai-review">AI coach</Link><Link to="/#practice">Playbooks & replay</Link></div><div><strong>Get started</strong><Link to="/signup">Create an account</Link><Link to="/pricing">Pricing</Link><Link to="/login">Sign in</Link></div><div><strong>We’re here to help</strong><Link to="/help">Help & customer care</Link>{catalog?.legal.support_email&&<a href={`mailto:${catalog.legal.support_email}`}>Contact support <ArrowUpRight size={12}/></a>}<span>INR / IST</span></div></div></div><div className="footer-bottom"><span>© {new Date().getFullYear()} {catalog?.brand_name||'HakiSense'}</span><p>A journal for reflection and analysis. Trading outcomes are never guaranteed.</p><div><Link to="/terms">Terms</Link><Link to="/privacy">Privacy</Link><Link to="/refunds">Refunds</Link></div></div></div></footer>
  </div>;
}
