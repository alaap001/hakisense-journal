import {useState} from 'react';
import {Sparkles} from 'lucide-react';
import {useAIWorkflow,WorkflowProgress,AIReceipt} from './AIWorkflow';
import {Button} from './ui';
import {api,useStore,explain} from './lib';
import type {Trade,AIResult} from './types';

export function TradeAIReview({trade}:{trade:Trade}){
  const [draft,setDraft]=useState(''),[result,setResult]=useState<AIResult|null>(null),[saving,setSaving]=useState(false);
  const {workspace,inspect,refresh,notify}=useStore();
  const flow=useAIWorkflow(value=>{setDraft(value.answer);setResult(value);});
  return <div className="ai-note-box"><div className="panel-heading"><h3><Sparkles size={17}/> A second perspective</h3><Button disabled={flow.active||!workspace?.billing.ai_available} onClick={()=>void flow.start({message:'Review this trade and draft a concise journal note.',mode:'trade_note',trade_id:trade.id})}>Draft review · 1–7 credits</Button></div><WorkflowProgress flow={flow}/>{draft&&result&&<><textarea aria-label="Editable AI trade review" rows={7} value={draft} onChange={e=>setDraft(e.target.value)}/><AIReceipt result={result}/><Button disabled={saving||!draft.trim()} onClick={async()=>{setSaving(true);try{const updated=await api<Trade>('/trades/'+trade.id+'/ai-note',{method:'POST',body:JSON.stringify({job_id:result.job_id,expected_notes:trade.notes,draft})});inspect(updated);refresh();setDraft('');notify('AI draft added to your notes');}catch(e){explain(e);}finally{setSaving(false);}}}>Append to trade notes</Button></>}{!draft&&!flow.active&&<p className="muted">Generate a review from this trade’s recorded data.</p>}</div>;
}
