import { useEffect,useState } from 'react';
import { Link,useSearchParams } from 'react-router-dom';
import { Search,LifeBuoy,ArrowUpRight,Mail,Copy,BookOpen,CreditCard,ShieldCheck } from 'lucide-react';
import { useStore,num } from './lib';
import type { Catalog } from './types';
import { PageTitle,Panel,Field,Button,ErrorState } from './ui';
import { Select } from './Select';
import './account.css';

const topics=['Getting started','Trades & imports','Credits & payments','AI credits','Sign-in & security','Privacy & account','Report a problem'];

export function HelpPage({publicPage=false}:{publicPage?:boolean}){
  const workspace=useStore(s=>s.workspace),[params]=useSearchParams();
  const [catalog,setCatalog]=useState<Catalog|null>(workspace?.catalog||null),[loadError,setLoadError]=useState(''),[retry,setRetry]=useState(0);
  const [search,setSearch]=useState(''),[topic,setTopic]=useState(topics.includes(params.get('topic')||'')?params.get('topic')!:'Getting started');
  const [subject,setSubject]=useState(''),[message,setMessage]=useState(''),[reference,setReference]=useState(''),[draft,setDraft]=useState<{subject:string;body:string}|null>(null),[notice,setNotice]=useState('');
  useEffect(()=>{
    if(workspace?.catalog){setCatalog(workspace.catalog);return;}
    const controller=new AbortController();setLoadError('');
    fetch('/api/catalog',{signal:controller.signal}).then(async r=>{if(!r.ok)throw new Error('Support details could not be loaded. Please try again.');return r.json();}).then(setCatalog).catch(e=>{if(e.name!=='AbortError')setLoadError(e.message);});
    return()=>controller.abort();
  },[workspace?.catalog,retry]);

  const questions=[
    ['How do I add my first trade?','Open Trading accounts to add your broker account, then use Quick entry or Import trades. File imports show a mapping and preview before you commit your positions.','/trades','Open trade journal'],
    ['What can I use for free?',`All existing journal tools, unlimited trade entries, analytics and replay are unlocked. Each account receives ${catalog?.monthly_free_credits??50} free monthly credits. Creating a playbook costs ${catalog?.playbook_creation_credits??1} credits; edits and trade links are free.`,'/billing','View my wallet'],
    ['Where can I see credit usage and refunds?','Your wallet shows purchased and monthly free credits separately. Purchased credits never expire; free credits refresh monthly in IST. Failed AI tasks return their reserved credits.','/billing','View credit activity'],
    ['I paid, but my credits have not appeared.','Use Refresh payments in your wallet to retrieve server-verified confirmation. If it stays pending, include the payment reference in your support request. Do not make another payment for the same recharge.','/billing','Open wallet'],
    ['Will recharges renew automatically?','No. Every recharge is a one-time purchase. Add more credits only when you need them; nothing renews automatically.','/billing','Manage wallet'],
    ['Can I change my email or password?','Account & security lets you request an email change, send a password-reset link, and sign out this device or other devices. Follow the email confirmation instructions to finish a change.','/settings/security','Open account security'],
    ['How do I download my journal or request account closure?','Your data provides a JSON journal archive. For privacy or account-closure requests, use the customer-care section below and choose Privacy & account.','/settings/data','Open my data'],
    ['Does market replay place real orders?','Market replay is practice using uploaded or labelled sample candles. It does not connect to your broker or place orders. Replay is free for all accounts.','/simulator','Open market replay'],
  ];
  const visible=questions.filter(q=>q.slice(0,2).join(' ').toLowerCase().includes(search.toLowerCase().trim()));
  const support=catalog?.legal.support_email||'';
  function destination(path:string){return publicPage?(path==='/billing'?'/pricing':'/login'):path;}
  return <><PageTitle eyebrow="A LITTLE HELP, WHEN YOU NEED IT" title="Help & customer care" description="Find an answer, manage your account, or get in touch."/><div className="help-shortcuts">{[[BookOpen,'Journal & imports','Your trades, in one place.','/import'],[CreditCard,'Credits & payments','Recharges, usage and payment history.','/billing'],[ShieldCheck,'Account & security','Email, password and sessions.','/settings/security']].map(([Icon,title,text,path]:any)=><Link key={path} to={destination(path)}><Icon size={22}/><strong>{title}</strong><span>{text}</span><ArrowUpRight size={16}/></Link>)}</div>
    {loadError&&<><ErrorState message={loadError}/><Button onClick={()=>setRetry(v=>v+1)}>Retry support details</Button></>}
    <Panel title="Find an answer" className="section-gap"><div className="padded"><label className="help-search"><Search size={19}/><input type="search" aria-label="Search help articles" placeholder="Search payments, password, imports…" value={search} maxLength={120} onChange={e=>setSearch(e.target.value)}/></label><div className="help-questions">{visible.map(([q,a,path,label])=><details key={q}><summary>{q}</summary><p>{a}</p><Link to={destination(path)}>{label} →</Link></details>)}{!visible.length&&<p className="muted">No matching answers. Try a different term or prepare a message below.</p>}</div></div></Panel>
    <Panel title="Contact customer care" className="section-gap"><div className="help-contact"><div><span className="help-icon"><LifeBuoy size={28}/></span><h2>Let’s work it out.</h2><p>Describe what happened and what you expected. For payment questions, add the reference shown in your billing history.</p>{support?<a className="help-address" href={'mailto:'+support}><Mail size={16}/>{support}</a>:<p className="help-contact-unavailable">{catalog?'Email support is not available right now. You can prepare and copy your request below.':'Loading contact details…'}</p>}<p className="small muted">Please leave passwords, one-time codes and card details out of your message.</p></div>
      <form className="stack" onChange={()=>{setDraft(null);setNotice('');}} onSubmit={e=>{e.preventDefault();if(!subject.trim()||!message.trim()){setNotice('Add a subject and describe what you need help with.');return;}setDraft({subject:`[${topic}] ${subject.trim()}`,body:[message.trim(),'','Topic: '+topic,reference.trim()?'Payment / issue reference: '+reference.trim():'',workspace?'Account email: '+workspace.user.email:''].filter(Boolean).join('\n')});setNotice('Your message is ready to review. It has not been sent.');}}>
        <Field label="What can we help with?"><Select value={topic} onChange={e=>{setTopic(e.target.value);setDraft(null);}}>{topics.map(t=><option key={t}>{t}</option>)}</Select></Field><Field label="Subject"><input required value={subject} maxLength={120} onChange={e=>setSubject(e.target.value)} placeholder="A short description of your question"/></Field><Field label="Payment or issue reference (optional)"><input value={reference} maxLength={100} onChange={e=>setReference(e.target.value)}/></Field><Field label="Your message"><textarea required rows={5} value={message} minLength={10} maxLength={1500} onChange={e=>setMessage(e.target.value)} placeholder="Include the page, what happened, and any error message."/></Field><div><Button variant="primary">Prepare message <ArrowUpRight size={16}/></Button></div>{notice&&<p className="account-notice" role="status">{notice}</p>}{draft&&<div className="support-draft"><strong>{draft.subject}</strong><p>{draft.body}</p><div className="button-row">{support&&<a className="button primary" href={`mailto:${support}?subject=${encodeURIComponent(draft.subject)}&body=${encodeURIComponent(draft.body)}`}><Mail size={16}/>Open email app</a>}<Button type="button" onClick={async()=>{try{await navigator.clipboard.writeText(draft.subject+'\n\n'+draft.body);setNotice('Message copied.');}catch{setNotice('Copy is unavailable in this browser. Select and copy the message above.');}}}><Copy size={16}/>Copy message</Button></div></div>}
      </form></div></Panel>
    <div className="help-policies">{[['privacy','Privacy policy'],['terms','Terms of service'],['refunds','Refund policy']].map(([key,label])=>catalog?.legal[key]&&<a href={catalog.legal[key]} key={key} target="_blank" rel="noreferrer">{label} <ArrowUpRight size={13}/></a>)}</div>
  </>;
}

export default function PublicHelp(){
  useEffect(()=>{document.title='Help & customer care · HakiSense';},[]);
  return <div className="public-help"><header><Link to="/" className="public-help-brand"><span className="brand-logo">H</span>HakiSense</Link><nav aria-label="Help navigation"><Link to="/pricing">Pricing</Link><Link className="button primary" to="/login">Open my journal <ArrowUpRight size={16}/></Link></nav></header><main><HelpPage publicPage/></main><footer><Link to="/">← Back to HakiSense</Link><span>Made for Indian traders · INR / IST</span></footer></div>;
}
