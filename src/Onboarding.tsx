import { createContext, useContext, useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { KeyboardEvent, ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { useLocation, useNavigate } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Check, Compass, Sparkles } from 'lucide-react';
import { api, ApiError, useStore } from './lib';
import { Button } from './ui';
import type { OnboardingState } from './types';
import './onboarding.css';

const steps = [
  {id:'quick-entry', route:'/overview', target:'quick-entry', label:'Quick entry', title:'Your first trade starts here', text:'Welcome to your journal. Use Quick entry from any page to record an entry, exit, fees and the thinking behind your trade.', tip:'This short tour will show you where everything lives.'},
  {id:'journal', route:'/trades', target:'add-trade', label:'Trade journal', title:'Keep every trade in one place', text:'You can also use Add trade here. Your journal lets you find, filter and review recorded positions, then open any trade to add detail.', tip:'An empty journal is ready for your first real trade.'},
  {id:'import', route:'/import', target:'nav-import', label:'Import trades', title:'Already have a trading history?', text:'Bring it in with a CSV, TSV or Excel file. Match your columns and review the preview before saving the trades.', tip:'Importing a file does not connect to your broker.'},
  {id:'analytics', route:'/analytics', target:'nav-analytics', label:'Analytics', title:'See what is working for you', text:'Explore your P&L, win rate, drawdown and performance by setup. Use the account and date filters to focus your review.', tip:'Your charts will fill in as you record trades.'},
  {id:'calendar', route:'/calendar', target:'nav-calendar', label:'Calendar', title:'Review your trading days', text:'See your realized results day by day and spot patterns across weeks and months.', tip:'Calendar results follow trade exit dates, in IST.'},
  {id:'coach', route:'/coach', target:'nav-coach', label:'AI coach', title:'Turn your records into questions', text:'Ask the AI coach about your journal or request a review. Reviews cost 1–7 credits, with the final charge shown alongside your answer.', tip:'Opening this page or taking the tour spends no AI credits.'},
  {id:'accounts', route:'/settings/accounts', target:'nav-accounts', label:'Trading accounts', title:'Make this workspace yours', text:'We have created “My trading account” to get you started. Rename it for your broker, or add accounts to keep your records organized.', tip:'Manage your profile and preferences in My account.'},
  {id:'wallet', route:'/billing', target:'nav-billing', label:'Credit wallet', title:'You are ready to start journaling', text:'Your wallet shows your free and purchased credits, usage and recharge options. Trade entry and the journal tools are free to use.', tip:'Want another look? Restart this tour in My account → Help & customer care.'},
] as const;
type Action = 'next'|'back'|'skip'|'complete'|'restart';
type TourContext = {restart:()=>void; busy:boolean; error:string};
const Context = createContext<TourContext|null>(null);
const activeState = (state:OnboardingState) => state.version===1 && steps.some(s=>s.id===state.step) && ['pending','in_progress'].includes(state.status);
const automaticRoutes = new Set(['/overview','/trades','/import','/analytics','/calendar','/coach','/notebook','/playbooks','/goals','/simulator']);

export function OnboardingProvider({initial,userId,setNavigationOpen,blocked,children}:{initial:OnboardingState;userId:string;setNavigationOpen:(value:boolean)=>void;blocked:boolean;children:ReactNode}){
  const [state,setState] = useState(initial);
  const [open,setOpen] = useState(false), [busy,setBusy] = useState(false), [error,setError] = useState('');
  const handled = useRef(false), saving = useRef(false), alive = useRef(true);
  const location = useLocation(), navigate = useNavigate();
  const channel = useRef<BroadcastChannel|null>(null);
  const supported = !!state && state.version===1 && steps.some(s=>s.id===state.step);
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
  useEffect(()=>{if(initial)setState(current=>!current||initial.revision>current.revision?initial:current);},[initial]);
  useEffect(()=>{
    // A refresh can land on the previous page after a save committed but before navigation.
    const resumeHere=state?.status==='in_progress'&&['/settings/accounts','/billing'].includes(location.pathname)&&!location.search;
    if(!supported||handled.current||blocked||(!automaticRoutes.has(location.pathname)&&!resumeHere)||document.querySelector('dialog[open]'))return;
    handled.current=true;
    if(activeState(state))setOpen(true);
  },[supported,state,blocked,location.pathname,location.search]);
  useEffect(()=>{if(state&&!activeState(state))setOpen(false);},[state]);
  useEffect(()=>{
    let active=true;
    const sync=async()=>{
      try{
        const latest=await api<OnboardingState>('/onboarding',{signal:AbortSignal.timeout(10000)});
        if(active)setState(current=>!current||latest.revision>current.revision?latest:current);
      }catch{/* An optional background sync must not interrupt the journal. */}
    };
    const onVisible=()=>{if(document.visibilityState==='visible')void sync();};
    window.addEventListener('focus',sync);
    document.addEventListener('visibilitychange',onVisible);
    if(typeof BroadcastChannel!=='undefined'){
      channel.current=new BroadcastChannel('hakisense-tour-'+userId);
      channel.current.onmessage=()=>void sync();
    }
    return()=>{active=false;window.removeEventListener('focus',sync);document.removeEventListener('visibilitychange',onVisible);channel.current?.close();channel.current=null;};
  },[userId]);

  async function act(action:Action){
    if(saving.current||!supported)return;
    saving.current=true;setBusy(true);setError('');
    try{
      const latest=await api<OnboardingState>('/onboarding',{method:'PUT',body:JSON.stringify({version:state.version,revision:state.revision,action}),signal:AbortSignal.timeout(10000)});
      if(!alive.current)return;
      setState(current=>latest.revision>=current.revision?latest:current);
      channel.current?.postMessage('changed');
      if(action==='restart'){handled.current=true;setOpen(true);}
      if(action==='complete'){
        navigate('/trades');
        useStore.getState().notify('You’re ready. Add a trade whenever you like.');
      }
    }catch(e){
      if(!alive.current)return;
      if(e instanceof ApiError&&e.status===409){
        try{const latest=await api<OnboardingState>('/onboarding',{signal:AbortSignal.timeout(10000)});if(alive.current){setState(current=>latest.revision>=current.revision?latest:current);setError('Your tour changed in another tab. The latest progress is now loaded.');}}
        catch{if(alive.current)setError('We could not load your tour progress. Please try again.');}
      }else setError('We could not save your tour progress. Check your connection and try again.');
    }finally{saving.current=false;if(alive.current)setBusy(false);}
  }
  return <Context.Provider value={{restart:()=>void act('restart'),busy:busy||!supported,error:open?'':error}}>{children}
    {open&&supported&&activeState(state)&&!blocked&&<GuidedTour stepIndex={steps.findIndex(s=>s.id===state.step)} busy={busy} error={error} act={act} setNavigationOpen={setNavigationOpen} closeForNow={()=>{setOpen(false);setError('');}}/>}
  </Context.Provider>;
}

export function TourLauncher(){
  const tour=useContext(Context);
  if(!tour)return null;
  return <div className="tour-launcher"><span className="tour-launcher-icon"><Compass size={24}/></span><div><strong>A quick look around your journal</strong><p>Find trade entry, imports, analytics and your account tools.</p>{tour.error&&<p role="alert">{tour.error}</p>}</div><Button disabled={tour.busy} onClick={tour.restart}><Compass size={16}/>{tour.busy?'Opening tour…':'Restart guided tour'}</Button></div>;
}

type Box={x:number;y:number;width:number;height:number};
type Layout={target:Box|null;card:Box;cardMaxHeight:number;width:number;height:number};
const clamp=(n:number,min:number,max:number)=>Math.max(min,Math.min(n,max));

function GuidedTour({stepIndex,busy,error,act,setNavigationOpen,closeForNow}:{stepIndex:number;busy:boolean;error:string;act:(action:Action)=>Promise<void>;setNavigationOpen:(open:boolean)=>void;closeForNow:()=>void}){
  const step=steps[stepIndex], navigate=useNavigate(), location=useLocation();
  const dialog=useRef<HTMLDialogElement>(null), card=useRef<HTMLDivElement>(null), heading=useRef<HTMLHeadingElement>(null);
  const [layout,setLayout]=useState<Layout|null>(null);
  const layoutReady=!!layout;
  useEffect(()=>{
    const element=dialog.current!, previous=document.activeElement as HTMLElement|null;
    const overflow=document.body.style.overflow;
    element.showModal();document.body.style.overflow='hidden';
    return()=>{element.close();document.body.style.overflow=overflow;if(previous?.isConnected)previous.focus({preventScroll:true});};
  },[]);
  useEffect(()=>{
    if(location.pathname!==step.route)navigate(step.route);
  },[step.route,location.pathname,navigate]);
  useEffect(()=>{
    const query=window.matchMedia('(max-width: 760px)');
    const update=()=>setNavigationOpen(query.matches&&step.target.startsWith('nav-'));
    update();query.addEventListener('change',update);
    return()=>{query.removeEventListener('change',update);setNavigationOpen(false);};
  },[step.target,location.pathname,setNavigationOpen]);
  useEffect(()=>{if(layoutReady)heading.current?.focus({preventScroll:true});},[stepIndex,layoutReady]);

  function trapFocus(event:KeyboardEvent<HTMLDialogElement>){
    if(event.key!=='Tab')return;
    const buttons=Array.from(dialog.current!.querySelectorAll<HTMLButtonElement>('button:not(:disabled)'));
    const index=buttons.indexOf(document.activeElement as HTMLButtonElement);
    if(!buttons.length){event.preventDefault();heading.current?.focus();}
    else if(event.shiftKey&&index<=0){event.preventDefault();buttons.at(-1)!.focus();}
    else if(!event.shiftKey&&(index===-1||index===buttons.length-1)){event.preventDefault();buttons[0].focus();}
  }

  useLayoutEffect(()=>{
    let frame=0, target:HTMLElement|null=null;
    const measure=()=>{
      cancelAnimationFrame(frame);
      frame=requestAnimationFrame(()=>{
        const width=window.innerWidth,height=window.innerHeight;
        const found=document.querySelector<HTMLElement>(`[data-tour="${step.target}"]`);
        if(found&&found!==target){target=found;target.scrollIntoView({block:'center',inline:'nearest',behavior:'instant'});observer.observe(target);}
        const bounds=found?.getBoundingClientRect();
        const visible=bounds&&bounds.width>0&&bounds.height>0&&bounds.right>0&&bounds.left<width&&bounds.bottom>0&&bounds.top<height;
        const bx=Math.max(6,(bounds?.left||0)-6),by=Math.max(6,(bounds?.top||0)-6);
        const box=visible?{x:bx,y:by,width:Math.min(width-6,bounds.right+6)-bx,height:Math.min(height-6,bounds.bottom+6)-by}:null;
        const cw=Math.min(380,width-24);
        const fitsBeside=box&&width>760&&(box.x+box.width+cw+32<width||box.x>cw+32);
        // On a small screen, scroll the card within the space above/below the highlight.
        const cardMaxHeight=box&&!fitsBeside?Math.max(120,Math.max(box.y-38,height-box.y-box.height-38)):height-24;
        const ch=Math.min(card.current?.offsetHeight||300,cardMaxHeight);
        let x=(width-cw)/2,y=(height-ch)/2;
        if(box){
          if(width>760&&box.x+box.width+cw+32<width){x=box.x+box.width+26;y=box.y+box.height/2-ch/2;}
          else if(width>760&&box.x>cw+32){x=box.x-cw-26;y=box.y+box.height/2-ch/2;}
          else{x=box.x+box.width/2-cw/2;y=box.y+box.height+ch+32<height?box.y+box.height+26:box.y-ch-26;}
        }
        const next={target:box,card:{x:clamp(x,12,width-cw-12),y:clamp(y,12,height-ch-12),width:cw,height:ch},cardMaxHeight,width,height};
        setLayout(old=>JSON.stringify(old)===JSON.stringify(next)?old:next);
      });
    };
    const observer=new ResizeObserver(measure);
    observer.observe(document.body);if(card.current)observer.observe(card.current);
    const mutations=new MutationObserver(measure);mutations.observe(document.querySelector('.app-shell')!,{childList:true,subtree:true});
    measure();const settled=window.setTimeout(measure,260);
    window.addEventListener('resize',measure);window.addEventListener('scroll',measure,true);document.addEventListener('transitionend',measure);
    return()=>{cancelAnimationFrame(frame);clearTimeout(settled);observer.disconnect();mutations.disconnect();window.removeEventListener('resize',measure);window.removeEventListener('scroll',measure,true);document.removeEventListener('transitionend',measure);};
  },[step.target,location.pathname,error]);

  const t=layout?.target,c=layout?.card;
  let connector='';
  if(t&&c){
    const tx=t.x+t.width/2,ty=t.y+t.height/2,cx=c.x+c.width/2,cy=c.y+c.height/2;
    if(c.x>t.x+t.width){const ex=t.x+t.width+5;connector=`M ${c.x-3} ${cy} Q ${ex+10} ${cy} ${ex} ${ty}`;}
    else if(c.x+c.width<t.x){const ex=t.x-5;connector=`M ${c.x+c.width+3} ${cy} Q ${ex-10} ${cy} ${ex} ${ty}`;}
    else if(c.y>t.y+t.height){const ey=t.y+t.height+5;connector=`M ${cx} ${c.y-3} Q ${tx} ${c.y-10} ${tx} ${ey}`;}
    else if(c.y+c.height<t.y){const ey=t.y-5;connector=`M ${cx} ${c.y+c.height+3} Q ${tx} ${c.y+c.height+10} ${tx} ${ey}`;}
  }
  return createPortal(<dialog ref={dialog} className="guided-tour" aria-labelledby="tour-title" aria-describedby="tour-description" onKeyDown={trapFocus} onCancel={e=>{e.preventDefault();if(!busy)void act('skip');}}>
    <svg className="tour-spotlight" width="100%" height="100%" aria-hidden="true">
      <defs><mask id="tour-cutout"><rect width="100%" height="100%" fill="white"/>{t&&<rect x={t.x} y={t.y} width={t.width} height={t.height} rx="10" fill="black"/>}</mask><marker id="tour-arrow" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M 1 1 L 6 4 L 1 7" fill="none" stroke="#d8f5a7" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></marker></defs>
      <rect width="100%" height="100%" fill="#112115" fillOpacity=".64" mask="url(#tour-cutout)"/>
      {t&&<><rect className="tour-ring" x={t.x} y={t.y} width={t.width} height={t.height} rx="10"/>{connector&&<path d={connector} fill="none" stroke="#d8f5a7" strokeWidth="2" strokeLinecap="round" markerEnd="url(#tour-arrow)"/>}<circle cx={t.x+8} cy={Math.max(14,t.y)} r="12" fill="#daf2b8" stroke="#31562c" strokeWidth="2"/><text x={t.x+8} y={Math.max(14,t.y)+4} textAnchor="middle" fill="#223b20" fontSize="11" fontWeight="700">{stepIndex+1}</text></>}
    </svg>
    <div ref={card} className="tour-card" style={{left:c?.x??12,top:c?.y??80,width:c?.width??'min(380px, calc(100vw - 24px))',maxHeight:layout?.cardMaxHeight,visibility:layout?'visible':'hidden'}}>
      <div className="tour-card-top"><span className="tour-brand"><Sparkles size={15}/> A LITTLE GUIDANCE</span><span className="tour-count">{stepIndex+1} / {steps.length}</span></div>
      <div className="tour-progress" aria-hidden="true">{steps.map((s,i)=><span key={s.id} className={i<=stepIndex?'filled':''}/>)}</div>
      <span className="tour-destination">{step.label}</span><h2 id="tour-title" ref={heading} tabIndex={-1}>{step.title}</h2>
      <p id="tour-description">{step.text}</p><div className="tour-tip"><Compass size={17}/><span>{step.tip}</span></div>
      {error&&<div className="tour-error" role="alert">{error}<button onClick={closeForNow} disabled={busy}>Close for now</button><small>Unfinished progress resumes next time you sign in.</small></div>}
      <div className="tour-controls"><Button variant="ghost" disabled={busy} onClick={()=>void act('skip')}>Skip tour</Button><div>{stepIndex>0&&<Button aria-label="Previous tour step" variant="ghost" disabled={busy} onClick={()=>void act('back')}><ArrowLeft size={16}/><span>Back</span></Button>}<Button variant="primary" disabled={busy} onClick={()=>void act(stepIndex===steps.length-1?'complete':'next')}>{busy?'Saving…':stepIndex===steps.length-1?'Finish':'Next'}{stepIndex===steps.length-1?<Check size={16}/>:<ArrowRight size={16}/>}</Button></div></div>
      <span className="tour-save-note">{busy?'Saving to your account…':'Your progress is saved as you go.'}</span>
    </div>
  </dialog>,document.body);
}
