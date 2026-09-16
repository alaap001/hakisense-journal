import { Pricing } from './Pricing';
import type { ReactNode } from 'react';
import { useEffect,useState } from 'react';
import { Link,useSearchParams } from 'react-router-dom';
import { ArrowRight,RefreshCw,Coins,ReceiptText,Check } from 'lucide-react';
import { useStore,useData,post,api,ApiError,explain,num,date,money } from './lib';
import { PageTitle,Panel,Button,Badge,ErrorState,Empty } from './ui';

export function FeatureGate({feature,children}:{feature:string;children:ReactNode}){
  const workspace=useStore(s=>s.workspace);
  if(workspace?.billing.features.includes(feature))return <>{children}</>;
  return <Empty title="This tool is currently unavailable" text="Refresh your workspace or contact support." action={<Link to="/settings/help">Get help</Link>}/>;
}
export function BillingPage(){
  const {workspace,refresh,notify}=useStore();
  const [params]=useSearchParams();
  const {data:pending}=useData<any[]>('/billing/pending');
  const [cursor,setCursor]=useState<number|undefined>();
  const {data:history,error}=useData<any>('/billing/history'+(cursor?'?before='+cursor:''));
  const [busy,setBusy]=useState(''),[notice,setNotice]=useState('');
  async function reconcile(){setBusy('refresh');try{const result=await post('/billing/reconcile',{});setNotice(result.pending_checks?.length?'Some payments are still awaiting confirmation. Your existing credits are safe. Try Refresh again shortly.':'Wallet is up to date.');refresh();}catch(e){explain(e);}finally{setBusy('');}}
  useEffect(()=>{if(params.get('payment')==='return')void reconcile();},[]);
  if(!workspace)return null;
  const {billing,catalog}=workspace;
  async function recharge(code:string){
    const pack=catalog.packs.find(p=>p.code===code);const existing=pending?.find(p=>p.pack_code===code);
    if(!pack&&!existing)return;
    const terms=existing||pack;
    const storageKey='recharge:'+workspace!.user.id+':'+code;
    setBusy(code);try{
      let key=sessionStorage.getItem(storageKey);if(!key){key=crypto.randomUUID();sessionStorage.setItem(storageKey,key);}
      const result=await api('/billing/checkout',{method:'POST',body:JSON.stringify({pack_code:code,expected_amount_paise:terms.amount_paise,expected_credits:terms.credits}),headers:{'Idempotency-Key':key}});
      window.location.assign(result.url);
    }catch(e){if(e instanceof ApiError&&['checkout_closed','price_changed','offer_unavailable'].includes(e.code||'')){sessionStorage.removeItem(storageKey);refresh();}explain(e);}finally{setBusy('');}
  }
  return <><PageTitle eyebrow="PAY AS YOU GO" title="Your credit wallet" description="Your tools stay unlocked. Recharge when you want to explore further." actions={<Button disabled={!!busy} onClick={()=>void reconcile()}><RefreshCw size={16} className={busy==='refresh'?'spin':''}/>Refresh payments</Button>}/>
    <Panel className="wallet-hero"><div className="wallet-total"><span className="eyebrow">AVAILABLE TO USE</span><strong>{num(billing.credits.remaining,0)}<small> credits</small></strong><span><Check size={15}/> All existing features unlocked</span></div><div className="wallet-buckets"><div><span>Purchased & carried forward</span><strong>{num(billing.credits.purchased_remaining,0)}</strong><small>Never expire</small></div><div><span>Monthly free credits</span><strong>{num(billing.credits.free_remaining,0)}</strong><small>Refresh {date(billing.credits.resets_at,{day:'numeric',month:'short'})} · IST</small></div></div></Panel>
    {billing.credits.purchased_debt>0&&<div className="info-bar section-gap">A payment reversal left {num(billing.credits.purchased_debt,0)} credits to recover. Your available balance accounts for this; recharges first clear the outstanding amount. <Link to="/settings/help">Contact billing support</Link></div>}
    {notice&&<div className="info-bar section-gap" role="status">{notice}</div>}
    {!!pending?.length&&<Panel title="Your pending recharge" className="section-gap"><div className="padded stack">{pending.map(p=><div className="button-row" key={p.id}><span><strong>{p.pack_name}</strong> · {money(p.amount_paise/100)} · {num(p.credits,0)} credits <Badge>{p.status}</Badge></span><Button disabled={!!busy} onClick={()=>void recharge(p.pack_code)}>Continue payment</Button><Button disabled={!!busy} onClick={async()=>{setBusy('cancel');try{await post('/billing/checkout/'+p.id+'/cancel',{});sessionStorage.removeItem('recharge:'+workspace.user.id+':'+p.pack_code);refresh();notify('Recharge cancelled.');}catch(e){explain(e);}finally{setBusy('');}}}>Cancel recharge</Button></div>)}</div></Panel>}
    <Pricing catalog={catalog} introEligible={billing.intro_eligible} busy={busy} onRecharge={code=>void recharge(code)}/>
    <div className="two-columns section-gap"><Panel title="What costs credits?"><div className="padded"><div className="task-prices"><div><span>Create a playbook</span><strong>{catalog.playbook_creation_credits} credits</strong></div>{catalog.tasks.map(t=><div key={t.code}><span>{t.name}{!t.enabled?' · unavailable':''}</span><strong>1–7 credits</strong></div>)}</div><p className="small muted">AI reviews cost 1–7 credits depending on the work needed. Standard and Advanced follow the same pricing. Your final charge appears with the answer; unused credits are returned. Failed reviews are refunded, and stopping charges work already completed.</p><p className="small muted">Trade entries, playbook edits, analytics and replay are free. {catalog.credit_policy}</p></div></Panel><Panel title="Clear pricing. No renewal."><div className="padded stack"><Coins size={25}/><h3>A wallet that works at your pace.</h3><p>Buy a pack when you need it. Credits are added only after the payment is verified. Your purchased balance carries forward, and free monthly credits are spent first.</p><Link className="text-link" to="/settings/help?topic=Credits%20%26%20payments">Payment help & customer care <ArrowRight size={15}/></Link>{catalog.legal.refunds&&<a className="text-link" href={catalog.legal.refunds} target="_blank" rel="noreferrer">Refund policy</a>}<p className="small muted">These are in-app usage credits, with no cash withdrawal or transfer facility.</p></div></Panel></div>
    {error&&<ErrorState message={error}/>}<Panel title="Credit activity" className="section-gap" aside={cursor?<Button onClick={()=>setCursor(undefined)}>Latest activity</Button>:<Badge>COMPLETE WALLET HISTORY</Badge>}>{history?.credits.length?<><div className="table-wrap"><table><thead><tr><th>Activity</th><th>Date · IST</th><th>Credits</th><th>Balance after</th></tr></thead><tbody>{history.credits.map((c:any)=><tr key={c.id}><td>{c.reason}<small className="admin-subtext">Entry #{c.sequence}</small></td><td>{date(c.created_at,{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'})}</td><td className={c.amount>0?'positive':''}>{c.amount>0?'+':''}{num(c.amount,0)}</td><td>{num(c.balance_after,0)}</td></tr>)}</tbody></table></div>{history.next_cursor&&<div className="padded"><Button onClick={()=>setCursor(history.next_cursor)}>Older activity</Button></div>}</>:<Empty title="Your credit history starts here" text="Recharges, free grants and usage will appear here."/>}</Panel>
    <Panel title="Recent recharges" className="section-gap">{history?.purchases.length?<div className="table-wrap"><table><thead><tr><th>Pack / reference</th><th>Paid</th><th>Credits retained</th><th>Status</th><th>Date · IST</th></tr></thead><tbody>{history.purchases.map((p:any)=><tr key={p.id}><td>{p.pack_name}<small className="admin-subtext">{p.payment_id||p.id}</small></td><td>{money(p.amount_paise/100)}</td><td>{num(p.credited,0)} / {num(p.credits,0)}</td><td><Badge>{p.status.replaceAll('_',' ')}</Badge></td><td>{date(p.created_at)}</td></tr>)}</tbody></table></div>:<Empty title="No recharges yet" text="Your verified credit purchases will be listed here."/>}</Panel>
  </>;
}
