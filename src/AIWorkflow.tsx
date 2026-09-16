import {useEffect,useRef,useState} from 'react';
import {Markdown} from './Markdown';
import {Sparkles,Square,ArrowRight} from 'lucide-react';
import {api,authorizedFetch,useStore} from './lib';
import {Button,ErrorState} from './ui';
import {createSSEParser} from './aiStream.mjs';
import type {AIJob,AIResult} from './types';
import './aiWorkflow.css';

const terminal=(job:AIJob)=>['succeeded','failed','cancelled','partial'].includes(job.status);
export function useAIWorkflow(onComplete:(result:AIResult)=>void){
  const [job,setJob]=useState<AIJob|null>(null),[text,setText]=useState(''),[stages,setStages]=useState<string[]>([]),[error,setError]=useState(''),[connecting,setConnecting]=useState(false);
  const callback=useRef(onComplete),controller=useRef<AbortController|null>(null),cursor=useRef(0),mounted=useRef(true),delivered=useRef<string|null>(null);
  callback.current=onComplete;
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;controller.current?.abort();};},[]);
  function update(value:AIJob){
    if(!mounted.current)return;
    setJob(value);
    if(value.status==='succeeded'&&value.result&&delivered.current!==value.id){delivered.current=value.id;callback.current(value.result);}
    if(terminal(value)||value.status==='awaiting_input')useStore.getState().refresh();
    if(value.status==='failed'){setText('');setError(value.error||'This review failed. Its credits were refunded.');}
    if(value.status==='cancelled')setText('');
  }
  async function watch(id:string,reset=true){
    controller.current?.abort();const abort=new AbortController();controller.current=abort;
    if(reset){cursor.current=0;setText('');setStages([]);setError('');}
    setConnecting(true);
    try{
      let finalSnapshot:AIJob|null=null;
      for(let attempt=0;attempt<4;attempt++){
        if(abort.signal.aborted)return;
        const initial=await api<AIJob>('/ai/jobs/'+id,{signal:abort.signal});if(abort.signal.aborted)return;update(initial);
        if(terminal(initial)||initial.status==='awaiting_input'){
          if(initial.status==='awaiting_input'&&reset){/* Replay stages below before showing its saved pause. */}
          else return initial;
        }
        const response=await authorizedFetch('/ai/jobs/'+id+'/events?after='+cursor.current,{signal:abort.signal});
        if(!response.ok)throw new Error(response.status===401?'Your session expired. Sign in again; your review is saved.':'Could not connect to your review.');
        if(!response.body)throw new Error('This browser could not connect to your review.');
        const reader=response.body.getReader(),decoder=new TextDecoder();
        const parser=createSSEParser(event=>{
          if(abort.signal.aborted)return;
          if(event.id!=null){if(event.id<=cursor.current)return;cursor.current=event.id;}
          if(event.kind==='text')setText(previous=>previous+event.data.delta);
          if(event.kind==='status')setStages(previous=>[...previous.filter(x=>x!==event.data.message),event.data.message].slice(-6));
          if(event.kind==='snapshot'){finalSnapshot=event.data;update(event.data);}
        });
        try{
          while(true){const chunk=await reader.read();if(chunk.done){parser.feed(decoder.decode());break;}parser.feed(decoder.decode(chunk.value,{stream:true}));}
        }finally{reader.releaseLock();}
        if(finalSnapshot)return finalSnapshot;
        await new Promise(resolve=>setTimeout(resolve,Math.min(1000*2**attempt,4000)));
      }
      throw new Error('The connection was interrupted. Your review is saved. Reconnect to continue viewing it.');
    }catch(e){if(!abort.signal.aborted&&mounted.current)setError((e as Error).message);}
    finally{if(controller.current===abort&&mounted.current)setConnecting(false);}
  }
  async function start(payload:Record<string,unknown>){
    controller.current?.abort();setJob(null);setError('');setText('');setStages([]);setConnecting(true);
    try{
      const init={method:'POST',body:JSON.stringify(payload),headers:{'Idempotency-Key':crypto.randomUUID()}};
      let created:AIJob;
      try{created=await api<AIJob>('/ai/query',init);}catch(e){if(!(e instanceof TypeError))throw e;created=await api<AIJob>('/ai/query',init);}
      update(created);useStore.getState().refresh();return await watch(created.id);
    }catch(e){if(mounted.current){setError((e as Error).message);setConnecting(false);}return null;}
  }
  async function resume(answer:string){
    if(!job)return;
    setError('');
    try{const value=await api<AIJob>('/ai/jobs/'+job.id+'/continue',{method:'POST',body:JSON.stringify({revision:job.revision,answer})});update(value);await watch(value.id,false);}catch(e){setError((e as Error).message);}
  }
  async function stop(){
    if(!job)return;
    try{const value=await api<AIJob>('/ai/jobs/'+job.id+'/cancel',{method:'POST'});update(value);if(terminal(value)){controller.current?.abort();setConnecting(false);}else if(!connecting){void watch(value.id,false);}}catch(e){setError((e as Error).message);}
  }
  return {job,text,stages,error,connecting,start,resume,stop,watch,active:connecting||!!job&&!terminal(job),reset:()=>{controller.current?.abort();setJob(null);setText('');setStages([]);setError('');setConnecting(false);}};
}
export type Workflow = ReturnType<typeof useAIWorkflow>;
export function WorkflowProgress({flow}:{flow:Workflow}){
  const [answer,setAnswer]=useState(''),[submitting,setSubmitting]=useState(false);
  useEffect(()=>{setAnswer('');},[flow.job?.id,flow.job?.revision,flow.job?.pause?.question]);
  const paused=flow.job?.status==='awaiting_input',failed=flow.job?.status==='failed',active=flow.active;
  const clarify=paused&&flow.job?.pause?.kind==='clarification';
  return <>{(active||flow.error)&&<section className="ai-workflow" aria-label="Review progress">
    <div className="ai-workflow-heading"><strong><Sparkles size={16}/> {failed?'Review could not be completed':flow.job?.cancel_requested?'Stopping your review':clarify?'A quick clarification':paused?'Review interrupted':flow.error?'Review interrupted':'Review in progress'}</strong>{flow.job&&active&&!failed&&<Button variant="ghost" disabled={flow.job?.cancel_requested} onClick={()=>void flow.stop()}><Square size={13}/>Stop</Button>}</div>
    {active&&!paused&&!flow.error&&<div role="status" aria-live="polite"><p className="current">{flow.stages.at(-1)||'Starting your review…'}</p></div>}
    {flow.text&&<Markdown className="ai-provisional">{flow.text}</Markdown>}
    {paused&&<form className="ai-clarification" onSubmit={async e=>{e.preventDefault();setSubmitting(true);try{await flow.resume(answer);}finally{setSubmitting(false);}}}>
      <label htmlFor={'clarify-'+flow.job!.id}>{flow.job?.pause?.question}</label>
      {clarify&&<textarea id={'clarify-'+flow.job!.id} value={answer} onChange={e=>setAnswer(e.target.value)} rows={3} required maxLength={12000}/>}
      <Button variant="primary" disabled={submitting}>Continue review <ArrowRight size={15}/></Button>
    </form>}
    {flow.error&&<><ErrorState message={flow.error}/>{flow.job&&!terminal(flow.job)&&<Button onClick={()=>void flow.watch(flow.job!.id,false)}>Reconnect</Button>}</>}
    <small className="muted">{failed?'You can send another message or try this question again.':'You can return to this review from Recent reviews in AI coach.'}</small>
  </section>}</>;
}
export function AIReceipt({result}:{result:any}){
  const value=result.metadata_json||result;
  return typeof value.credits==='number'?<p className="small muted ai-receipt">{value.credits} credit{value.credits===1?'':'s'} used</p>:null;
}
