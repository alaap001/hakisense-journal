// Development-only fixture: all requests are intercepted; no real trades, AI calls or credits.
import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { Sparkles, LayoutDashboard, BookOpen, ChartNoAxesCombined, Wallet, CalendarDays, Plus } from 'lucide-react';
import '@fontsource/dm-sans/400.css';
import '@fontsource/dm-sans/500.css';
import '@fontsource/dm-sans/600.css';
import '@fontsource/dm-sans/700.css';
import '@fontsource/space-grotesk/500.css';
import '@fontsource/space-grotesk/600.css';
import { Coach } from '../../src/Coach';
import { useStore } from '../../src/lib';
import '../../src/styles.css';
import '../../src/pages.css';

const answer = `## Performance at a glance

Your closed trades show a positive result overall. **Opening Range Breakout** contributed the most profit, while Flag & Pole Breakout deserves a closer review.

| Metric | Result |
| --- | --- |
| Net P&L | **₹6,10,607.63** |
| Closed positions | 465 |
| Win rate | 58.49% |
| Profit factor | 2.29 |
| Average win | ₹3,982.78 |
| Average loss | −₹2,449.26 |

## How your setups compare

Compare both the return and the size of the sample before changing your approach.

| Setup | Net P&L | Win rate | Profit factor | Avg. hold (min) |
| --- | --- | --- | --- | --- |
| Opening Range Breakout | ₹1,20,119.99 | 60.29% | 2.88 | 667 |
| Trend Continuation | ₹1,06,215.76 | 62.50% | 2.52 | 824 |
| VWAP Pullback | ₹1,04,872.52 | 67.74% | 3.20 | 700 |
| Mean Reversion | ₹1,01,843.34 | 53.85% | 3.51 | 623 |
| Liquidity Sweep | ₹82,783.68 | 60.42% | 3.35 | 454 |
| Support Bounce | ₹66,461.11 | 59.26% | 2.12 | 898 |
| Resistance Rejection | ₹35,452.38 | 51.06% | 1.59 | 307 |
| **Flag & Pole Breakout** | **−₹7,151.15** | 50.00% | 0.93 | 640 |

### What to review next

1. **Review the losing breakout trades.** Check whether entries followed the rules you recorded.
2. Compare position size across winners and losers.
3. Keep a note of execution changes before the next session.

> These are observations from your journal. A pattern is a starting point for review, not a prediction.
`;
const threads = [
  { id: 'preview-performance', title: 'Review my recent performance' },
  { id: 'preview-latest', title: 'Tell me about my last 3 trades' },
  { id: 'preview-setups', title: 'Compare my profitable and losing setups' },
];
const checks = ['Trading after a loss', 'Position sizing', 'Holding losing trades', 'Execution costs', 'Setup consistency', 'Late entries'].map((title, i) => ({ id: `check-${i}`, title, impact: 12850 - i * 1400, sample: 12 + i * 3, confidence: 'Moderate', net_pnl: -12850 + i * 1400, action: 'Compare these trades with your usual process to understand what changed.' }));
let currentJob: any;
let sentMessage = '';
const saved: any[] = [];
const jobs = [{ id: 'preview-job', task: 'summary', status: 'succeeded', credits: 2, created_at: '2026-09-15T08:00:00Z', result: { thread_id: threads[0].id } }, { id: 'preview-failed', task: 'chat', status: 'failed', credits: 0, created_at: '2026-09-15T07:00:00Z' }];
const json = (data: unknown) => new Response(JSON.stringify(data), { headers: { 'Content-Type': 'application/json' } });
window.fetch = async (input, init) => {
  const url = String(input);
  if (url === '/api/config') return json({ supabase_url: 'http://ui-preview.invalid', supabase_publishable_key: 'preview-only' });
  if (url.startsWith('/api/analytics')) return json({ checks });
  if (url === '/api/ai/threads') return json(threads);
  if (url.startsWith('/api/ai/threads/')) return json([{ role: 'user', content: 'Review my recent performance and compare my setups.' }, { role: 'assistant', content: answer, metadata_json: { credits: 2 } }]);
  if (url === '/api/ai/jobs') return json(jobs);
  if (url === '/api/ai/query') {
    sentMessage = JSON.parse(String(init?.body)).message;
    currentJob = { id: 'preview-stream', status: 'running', revision: 1, thread_id: 'preview-performance' };
    return json(currentJob);
  }
  if (url.includes('/events?')) {
    const encoder = new TextEncoder();
    const stream = new ReadableStream({ async start(controller) {
      let id = 1;
      const emit = (kind: string, data: unknown) => controller.enqueue(encoder.encode(`id: ${id++}\nevent: ${kind}\ndata: ${JSON.stringify(data)}\n\n`));
      emit('status', { message: 'Reviewing your trades…' });
      for (let i = 0; i < answer.length; i += 45) { emit('text', { delta: answer.slice(i, i + 45) }); await new Promise(resolve => setTimeout(resolve, 90)); }
      currentJob = { ...currentJob, status: 'succeeded', result: { answer, thread_id: threads[0].id, credits: 2 } };
      emit('snapshot', currentJob); controller.close();
    }});
    return new Response(stream, { headers: { 'Content-Type': 'text/event-stream' } });
  }
  if (url === '/api/ai/jobs/preview-stream') return json(currentJob);
  if (url.startsWith('/api/records/')) { saved.push(JSON.parse(String(init?.body))); return json({ id: 'preview-saved' }); }
  throw new Error('Unmocked preview request: ' + url);
};
useStore.setState({ workspace: { billing: { ai_available: true, credits: { remaining: 31 } }, catalog: { tasks: [] } } as any });
function Preview() {
  const toast = useStore(s => s.toast);
  return <BrowserRouter><div className="app-shell"><aside className="sidebar"><div className="brand"><div className="brand-logo">H</div><div>HakiSense<span>TRADING JOURNAL</span></div></div><div className="workspace-pill">Personal workspace</div><nav><span className="nav-caption">WORKSPACE</span>{[[LayoutDashboard, 'Overview'], [BookOpen, 'Trade journal'], [CalendarDays, 'Calendar'], [ChartNoAxesCombined, 'Analytics'], [Sparkles, 'AI coach']].map(([Icon, label]: any) => <div key={label} className={`nav-item ${label === 'AI coach' ? 'active' : ''}`}><Icon size={18} />{label}</div>)}</nav></aside><div className="main-shell"><header className="topbar"><div className="breadcrumb"><span>Workspace</span><span>/</span><strong>Coach</strong></div><div className="topbar-actions"><span className="credit-pill"><Sparkles size={14} />31 credits</span><span className="topbar-divider" /><span className="button ghost"><Plus size={16} />Quick entry</span></div></header><main><div className="global-filters"><div className="scope-control"><Wallet size={15} />All accounts</div><div className="scope-control"><CalendarDays size={15} />All time</div><span className="filters-note">All recorded entry dates · INR · IST</span></div><Coach /></main></div></div>{toast && <div className="toast">{toast}</div>}<details style={{ margin: '20px', fontSize: 11 }}><summary>Synthetic preview checks</summary><button onClick={() => {
    const tables = [...document.querySelectorAll('.markdown table')];
    const result = { tables: tables.length, rows: tables.map(table => table.querySelectorAll('tbody tr').length), headers: tables.every(table => [...table.querySelectorAll('th')].every(cell => cell.scope === 'col')), pageOverflow: document.documentElement.scrollWidth > window.innerWidth, sentMessage, saved: saved.length };
    document.getElementById('preview-result')!.textContent = JSON.stringify(result);
  }}>Inspect rendered result</button><pre id="preview-result" /></details></BrowserRouter>;
}
const previewWindow = window as Window & { coachPreviewRoot?: ReturnType<typeof createRoot> };
(previewWindow.coachPreviewRoot ||= createRoot(document.getElementById('root')!)).render(<Preview />);
