import {num,date} from './lib';
import {Panel,Modal,Badge} from './ui';
import type {AIPricing} from './types';

export function AIWorkflowPolicy({pricing}:{pricing:AIPricing}){
  return <Panel title="Workflow credit policy" className="section-gap">
    <div className="padded stack">
      <p>Charge the smallest bucket that covers <strong>both</strong> input and output, summed across every agent call. Standard and Advanced use the same buckets.</p>
      <div className="table-wrap"><table><thead><tr><th>Total input at most</th><th>Total output at most</th><th>Credits</th></tr></thead><tbody>
        {pricing.buckets.map(bucket=><tr key={bucket.credits}><td>{num(bucket.input_tokens,0)}</td><td>{num(bucket.output_tokens,0)}</td><td>{bucket.credits}</td></tr>)}
      </tbody></table></div>
      <p><strong>Workflow limits:</strong> {num(pricing.input_limit,0)} input and {num(pricing.output_limit,0)} output tokens. The 128k pricing bucket covers permitted input above 64k; it does not raise the 100k input limit.</p>
      <p className="small muted">5,000 input + 3,000 output = 2 credits. Cached input and reasoning output are included in their respective totals, never added twice. Input is estimated before dispatch and verified against provider usage afterward.</p>
      <p className="small muted">An affordable maximum of up to 7 credits is reserved automatically. Completion releases unused credits; stopping charges recorded work; provider failures refund the reservation. These versioned buckets are defined by the backend, independently of route settings.</p>
      <small className="muted">Policy version: {pricing.version}</small>
    </div>
  </Panel>;
}

export function AIJobDetails({job,onClose}:{job:Record<string,any>;onClose:()=>void}){
  const bill=job.billing,usage=job.usage||{},route=job.routing||{};
  return <Modal title="AI workflow details" onClose={onClose} wide><div className="modal-body stack">
    <div className="admin-user-head"><div><h3>{job.task_code} · {route.tier||'Legacy route'}</h3><code>{job.id}</code></div><Badge>{job.cancel_requested&&job.status==='running'?'Stopping':job.status.replaceAll('_',' ')}</Badge></div>
    <p className="small muted">User ID: {job.user_id}</p>
    <div className="admin-detail-grid">
      {[['Accepted maximum',bill.maximum],['Currently reserved',bill.reserved],['Final charge',bill.charged??'Pending'],['Unused released',bill.released??'Pending']].map(([label,value])=><div key={label}><small>{label}</small><strong>{value}</strong></div>)}
    </div>
    <p className="small muted">{bill.legacy?'Historical fixed-price job. Failed legacy reservations were refunded; no native token usage was retained.':`Pricing version: ${job.pricing_version}. The final charge uses combined workflow usage, including work recorded before a user stop.`}</p>
    {!bill.legacy&&<><h3>Recorded provider usage</h3><dl className="admin-settings-list">
      {[['Input tokens',usage.input_tokens],['Output tokens',usage.output_tokens],['Cached input (included above)',usage.cached_tokens],['Reasoning output (included above)',usage.reasoning_tokens],['Agent calls with usage receipts',usage.calls]].map(([label,value])=><div key={label}><dt>{label}</dt><dd>{num(value||0,0)}</dd></div>)}
    </dl><h3>Saved model route</h3><dl className="admin-settings-list">
      <div><dt>Planning agent</dt><dd>{route.planner_model_id||route.model_id||job.model}</dd></div>
      <div><dt>Answer agent</dt><dd>{route.model_id||job.model}</dd></div>
      <div><dt>Output ceiling per call</dt><dd>{num(route.max_output_tokens,0)} tokens, also limited by remaining workflow capacity</dd></div>
      <div><dt>Answer reasoning / stream timeout</dt><dd>{route.reasoning_effort} · {route.timeout_seconds}s</dd></div>
    </dl><p className="small muted">This is the route accepted at submission. Later configuration edits affect new workflows.</p></>}
    <dl className="admin-settings-list">{[['Created',job.created_at],['Last heartbeat',job.heartbeat_at],['Finished',job.finished_at]].map(([label,value])=><div key={label}><dt>{label} · IST</dt><dd>{value?date(value,{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}):'—'}</dd></div>)}</dl>
    {job.status==='awaiting_input'&&<div className="info-bar">Waiting for the customer to clarify an ambiguous question. Legacy interrupted reviews can also be resumed. They can continue or stop from Recent reviews in AI coach; a paused job does not occupy a worker.</div>}
    {job.cancel_requested&&job.status==='running'&&<div className="info-bar">The current provider call is finishing so its usage can be recorded. No further agent will start.</div>}
    {job.error&&<p>{job.error}</p>}
    <p className="small muted">Customer questions, trade evidence, clarification text and private agent responses are excluded from administration.</p>
  </div></Modal>;
}
