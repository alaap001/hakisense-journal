import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Sparkles, ArrowUp, Plus, MessageSquare, BookmarkPlus, NotebookPen, Info, ChevronRight, History, ChevronDown, ArrowRight } from 'lucide-react';
import { Select } from './Select';
import { Markdown } from './Markdown';
import { useAIWorkflow, WorkflowProgress, AIReceipt } from './AIWorkflow';
import { api, post, useData, useStore, qs, money, date, explain, today, creditLabel } from './lib';
import type { Analysis } from './types';
import { Panel, Button, Badge, Empty, ErrorState } from './ui';
import { GroupChart } from './charts';
import './coach.css';

const tabs = ['Review checks', 'Ask HakiSense', 'Recent reviews'] as const;
type CoachTab = typeof tabs[number];
const suggestions = [
  { title: 'Review my latest trades', detail: 'A closer look at your last 3 trades', question: 'Tell me about my last 3 trades', mode: 'chat' },
  { title: 'Compare my setups', detail: 'See where your P&L comes from', question: 'Chart my P&L by setup', mode: 'query' },
  { title: 'Prepare for my next session', detail: 'Turn recent lessons into a plan', question: 'Help me prepare for my next session', mode: 'daily' },
  { title: 'Understand my performance', detail: 'Review the patterns in your journal', question: 'Summarize my recent performance', mode: 'summary' },
];
const statusLabels: Record<string, string> = { queued: 'Queued', running: 'In progress', awaiting_input: 'Waiting for you', succeeded: 'Completed', failed: 'Failed', cancelled: 'Stopped', partial: 'Stopped' };

export function Coach() {
  const { workspace, filters, notify, refresh } = useStore();
  const { data: analysis, error } = useData<Analysis>('/analytics' + qs(filters));
  const { data: jobs } = useData<any[]>('/ai/jobs');
  const { data: threads } = useData<any[]>('/ai/threads');
  const [tab, setTab] = useState<CoachTab>('Review checks');
  const [thread, setThread] = useState<string>();
  const [messages, setMessages] = useState<any[]>([]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState('chat');
  const [tier, setTier] = useState('standard');
  const [expanded, setExpanded] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const flow = useAIWorkflow(result => {
    setThread(result.thread_id);
    setMessages(previous => [...previous, { role: 'assistant', content: result.answer, metadata_json: result }]);
    setBusy(false);
    refresh();
  });
  const scroller = useRef<HTMLDivElement>(null);
  const followReply = useRef(true);
  const composer = useRef<HTMLTextAreaElement>(null);
  const pending = busy || flow.active;
  const checks = analysis?.checks || [], hits = checks.filter(c => c.sample > 0);
  const runningJobs = jobs?.filter(j => ['queued', 'running', 'awaiting_input'].includes(j.status)).length || 0;

  useEffect(() => {
    const element = scroller.current;
    if (element && messages.length && followReply.current) element.scrollTop = element.scrollHeight;
  }, [messages, busy, flow.text, flow.job?.status, tab]);
  useEffect(() => {
    const element = composer.current;
    if (element) { element.style.height = 'auto'; element.style.height = `${Math.min(element.scrollHeight, 150)}px`; }
  }, [text, tab]);

  async function send(message = text, selectedMode = mode, checkId?: string) {
    if (!message.trim() || pending) return;
    followReply.current = true;
    setBusy(true); setTab('Ask HakiSense'); setHistoryOpen(false);
    setMessages(previous => [...previous, { role: 'user', content: message }]); setText('');
    try { await flow.start({ message, mode: selectedMode, model_tier: tier, thread_id: thread, filters, check_id: checkId }); }
    finally { setBusy(false); }
  }
  function newConversation() {
    flow.reset(); setThread(undefined); setMessages([]); setText(''); setHistoryOpen(false);
    followReply.current = true;
    composer.current?.focus();
  }
  async function openConversation(id: string) {
    setBusy(true);
    try {
      const rows = await api('/ai/threads/' + id);
      flow.reset(); followReply.current = true;
      setThread(id); setMessages(rows); setTab('Ask HakiSense'); setHistoryOpen(false);
    } catch (e) { explain(e); }
    finally { setBusy(false); }
  }
  async function openProgress(job: any) {
    setBusy(true); setTab('Ask HakiSense'); followReply.current = true;
    try {
      const current = await api('/ai/jobs/' + job.id);
      setThread(current.thread_id || undefined);
      const previous = current.thread_id ? await api('/ai/threads/' + current.thread_id) : [];
      setMessages([...previous, { role: 'user', content: current.message }]);
      await flow.watch(job.id);
    } catch (e) { explain(e); }
    finally { setBusy(false); }
  }
  async function save(message: any, kind: 'pin' | 'note') {
    try {
      await post('/records/' + kind, { data: kind === 'pin'
        ? { title: 'HakiSense insight', body: message.content, chart: message.metadata_json?.chart, filters }
        : { title: 'HakiSense review · ' + date(today()), body: message.content, date: today(), mood: 'Neutral' } });
      refresh(); notify(kind === 'pin' ? 'Insight pinned to your overview' : 'Review saved to your notebook');
    } catch (e) { explain(e); }
  }

  return <div className="coach-page">
    <header className="coach-page-header">
      <div><p className="eyebrow">YOUR TRADING REVIEW PARTNER</p><h1>AI coach</h1><p>Understand your trades. Build better habits.</p></div>
      <div className="coach-preferences">
        <div className="coach-tier"><label htmlFor="ai-tier">Review model</label><Select id="ai-tier" aria-label="Review model" value={tier} disabled={pending} onChange={e => setTier(e.target.value)}>
          <option value="standard">Standard · everyday reviews</option><option value="advanced">Advanced · in-depth reviews</option>
        </Select></div>
        <div className="coach-credit-note"><span>1–7 credits per review</span><Link to="/billing">Add credits <ArrowRight size={12} /></Link></div>
      </div>
    </header>
    {!workspace?.billing.ai_available && <div className="info-bar"><Info size={16} />AI is temporarily unavailable. Your credits remain in your account.</div>}
    <div className="coach-tabs" role="tablist" aria-label="AI coach views">
      {tabs.map((item, index) => <button key={item} id={`coach-tab-${index}`} role="tab" type="button" aria-selected={tab === item} aria-controls="coach-view" tabIndex={tab === item ? 0 : -1} className={tab === item ? 'active' : ''} onClick={() => setTab(item)} onKeyDown={e => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
        e.preventDefault(); const next = e.key === 'Home' ? 0 : e.key === 'End' ? tabs.length - 1 : (index + (e.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
        setTab(tabs[next]); document.getElementById(`coach-tab-${next}`)?.focus();
      }}>{item === 'Recent reviews' && <History size={15} />}{item}{item === 'Recent reviews' && runningJobs > 0 && <span className="coach-tab-count">{runningJobs}</span>}</button>)}
    </div>
    <div id="coach-view" role="tabpanel" aria-labelledby={`coach-tab-${tabs.indexOf(tab)}`}>
      {tab === 'Review checks' && <>
        <div className="coach-hero">
          <div className="coach-orb"><Sparkles size={26} /></div>
          <div><p className="eyebrow">A FRESH PERSPECTIVE</p><h2>Find the habits behind your results.</h2><p>{hits.length} of 16 checks have observations in your current scope. Explore a finding or ask for a guided review.</p></div>
          <Button variant="primary" disabled={pending || !workspace?.billing.ai_available} onClick={() => void send('Review my performance. Rank the findings by observed INR impact and evidence strength, and give me three specific actions to review next session.', 'coach')}><Sparkles size={16} />Review my performance</Button>
        </div>
        <div className="coach-check-intro"><div><h2>Your review checks</h2><p>16 checks, included at no credit cost.</p></div><span>Based on your current filters</span></div>
        <p className="coach-check-note"><Info size={15} />Figures show observed losses or costs, not recoverable savings. Checks may overlap.</p>
        {error && <ErrorState message={error} />}
        <div className="check-grid">{(showAll ? checks : checks.slice(0, 6)).map((c, i) => <Panel key={c.id}>
          <div className="check-card">
            <div className="check-card-top"><span className="check-index">{String(i + 1).padStart(2, '0')}</span><Badge tone={c.impact > 0 ? 'amber' : c.sample ? 'green' : 'neutral'}>{c.impact > 0 ? 'Worth a review' : c.sample ? 'Observed' : 'No observations'}</Badge></div>
            <h3>{c.title}</h3><div className="check-impact">{c.impact > 0 ? money(c.impact) : '—'}<small>{c.id === 'slippage' || c.id === 'fees' ? 'observed costs' : 'observed net loss'}</small></div>
            <p>{c.action}</p><div className="check-evidence"><span>{c.sample} trades</span><span>{c.confidence} sample confidence</span></div>
            <button className="check-expand" aria-expanded={expanded === c.id} onClick={() => setExpanded(expanded === c.id ? null : c.id)}>{expanded === c.id ? 'Hide evidence' : 'Review evidence'}<ChevronRight size={15} /></button>
            {expanded === c.id && <div className="check-detail"><p>Observed group net P&L: <strong>{money(c.net_pnl)}</strong>. {c.sample < 10 ? 'This is a small sample; treat patterns as questions to investigate.' : 'Compare these trades with similar setups before attributing the outcome to one factor.'}</p><Button disabled={!c.sample || pending || !workspace?.billing.ai_available} onClick={() => void send(`Explain the "${c.title}" finding. What can I reasonably infer, what are the limits, and what should I review next?`, 'coach', c.id)}>Discuss · {creditLabel('coach', tier)}</Button></div>}
          </div>
        </Panel>)}</div>
        <div className="center-action"><Button onClick={() => setShowAll(!showAll)}>{showAll ? 'Show top six checks' : 'View all 16 checks'}</Button></div>
      </>}
      {tab === 'Recent reviews' && <Panel className="coach-activity">
        <div className="coach-activity-heading"><h2>Recent reviews</h2><p>Revisit an answer or pick up a review in progress.</p></div>
        {!jobs?.length && <Empty title="Your reviews will appear here" text="Start a conversation or explore a review check." action={<Button onClick={() => setTab('Ask HakiSense')}>Ask HakiSense</Button>} />}
        {jobs?.map(job => <div className="coach-activity-row" key={job.id}>
          <div className="coach-activity-icon"><Sparkles size={17} /></div><div className="coach-activity-detail"><strong>{({ chat: 'Conversation', query: 'Query & chart', coach: 'Coaching review', daily: 'Next-session plan', summary: 'Performance summary', trade_note: 'Trade review' } as Record<string, string>)[job.task] || 'AI review'}</strong><span>{job.created_at && date(job.created_at, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}{job.status === 'failed' ? ' · Credits refunded' : ['cancelled', 'partial'].includes(job.status) ? ' · Unused credits released' : job.status === 'succeeded' ? ` · ${job.credits} credit${job.credits === 1 ? '' : 's'} used` : ''}</span></div>
          <Badge tone={job.status === 'failed' ? 'red' : job.status === 'succeeded' ? 'green' : 'neutral'}>{statusLabels[job.status] || job.status}</Badge>
          {job.status === 'succeeded' && job.result?.thread_id ? <Button disabled={pending} onClick={() => void openConversation(job.result.thread_id)}>Open review <ArrowRight size={14} /></Button> : ['queued', 'running', 'awaiting_input'].includes(job.status) ? <Button disabled={pending} onClick={() => void openProgress(job)}>View progress</Button> : null}
        </div>)}
      </Panel>}
      {tab === 'Ask HakiSense' && <div className="chat-layout">
        <aside className={`chat-sidebar ${historyOpen ? 'history-open' : ''}`} aria-label="Conversations">
          <div className="chat-sidebar-controls"><Button onClick={newConversation} disabled={pending}><Plus size={16} />New conversation</Button><Button className="chat-history-toggle" aria-expanded={historyOpen} aria-controls="coach-conversations" onClick={() => setHistoryOpen(!historyOpen)}><History size={16} /><span>History</span><ChevronDown size={14} /></Button></div>
          <div id="coach-conversations" className="chat-conversations"><p className="eyebrow">CONVERSATIONS</p><div className="chat-thread-list">
            {threads?.map(t => <button key={t.id} title={t.title} disabled={pending} aria-current={thread === t.id ? 'true' : undefined} className={thread === t.id ? 'thread active' : 'thread'} onClick={() => void openConversation(t.id)}><MessageSquare size={15} /><span>{t.title}</span></button>)}
            {!threads?.length && <p className="chat-history-empty">Your conversations are saved here so you can return to them.</p>}
          </div></div>
          <div className="chat-model"><Sparkles size={16} /><span>A little reflection.<small>A better next session.</small></span></div>
        </aside>
        <Panel className="chat-panel">
          <div className="chat-heading"><div className="chat-heading-identity"><span className="chat-brand-icon"><Sparkles size={18} /></span><div><strong>HakiSense</strong><span>Your journal analyst</span></div></div><span className="chat-scope-note">Uses your current filters</span></div>
          <div className="chat-messages" ref={scroller} onScroll={e => { const el = e.currentTarget; followReply.current = el.scrollHeight - el.scrollTop - el.clientHeight < 100; }}>
            <div className="chat-reading-column">
              {!messages.length && <div className="chat-welcome"><div className="coach-orb"><Sparkles size={28} /></div><p className="eyebrow">MAKE SENSE OF YOUR TRADES</p><h2>What would you like to understand?</h2><p>Start with a question, or choose a place to begin.</p><div className="suggestion-grid">{suggestions.map(suggestion => <button key={suggestion.title} onClick={() => void send(suggestion.question, suggestion.mode)} disabled={pending || !workspace?.billing.ai_available}><span><strong>{suggestion.title}</strong><small>{suggestion.detail}</small></span><ArrowRight size={16} /></button>)}</div></div>}
              {messages.map((message, i) => <div key={message.id || i} className={`chat-message ${message.role}`}>
                <div className="message-avatar" aria-hidden="true">{message.role === 'user' ? 'Y' : <Sparkles size={16} />}</div>
                <div className="message-content"><span className="message-name">{message.role === 'user' ? 'You' : 'HakiSense'}</span>
                  {message.role === 'user' ? <div className="chat-question">{message.content}</div> : <Markdown>{message.content}</Markdown>}
                  {message.metadata_json?.chart && <div className="chat-chart"><GroupChart data={message.metadata_json.chart.rows} metric={message.metadata_json.chart.metric} /></div>}
                  {message.role === 'assistant' && <div className="message-bottom"><div className="message-actions"><Button variant="ghost" onClick={() => void save(message, 'pin')}><BookmarkPlus size={14} />Pin insight</Button><Button variant="ghost" onClick={() => void save(message, 'note')}><NotebookPen size={14} />Save to notebook</Button></div><AIReceipt result={message} /></div>}
                </div>
              </div>)}
              <WorkflowProgress flow={flow} />
            </div>
          </div>
          <div className="chat-composer-area"><form className="chat-composer" onSubmit={e => { e.preventDefault(); void send(); }}>
            <textarea ref={composer} aria-label="Question for HakiSense" disabled={pending} value={text} onChange={e => setText(e.target.value)} placeholder="Ask about your trades, habits, or performance…" rows={1} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send(); } }} />
            <div className="chat-composer-tools"><Select aria-label="Review type" value={mode} disabled={pending} onChange={e => setMode(e.target.value)}>{[['chat', 'Conversation'], ['query', 'Query & chart'], ['coach', 'Coaching review'], ['daily', 'Next-session plan'], ['summary', 'Performance summary']].map(([value, label]) => <option value={value} key={value}>{label}</option>)}</Select><span className="chat-keyboard-hint">Shift + Enter for a new line</span><Button type="submit" variant="primary" disabled={pending || !text.trim() || !workspace?.billing.ai_available} aria-label="Send message"><ArrowUp size={18} /></Button></div>
          </form><p className="chat-footer">Based on your journal. No live market data.</p></div>
        </Panel>
      </div>}
    </div>
  </div>;
}
