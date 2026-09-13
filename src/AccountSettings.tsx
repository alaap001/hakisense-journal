import { useEffect,useState,type ReactNode } from 'react';
import { Link,NavLink,Outlet } from 'react-router-dom';
import { UserRound,ShieldCheck,SlidersHorizontal,Wallet,CreditCard,Download,LifeBuoy,Save,Mail,LogOut,ArrowUpRight,Globe2 } from 'lucide-react';
import { useStore,put,downloadApi,num } from './lib';
import { authClient } from './authClient';
import { defaultPreferences,landingPages,signOut,type Preferences } from './account';
import { PageTitle,Panel,Button,Field,Badge,ErrorState } from './ui';
import { Select } from './Select';
import './account.css';

const sections=[
  ['/settings/profile','Profile',UserRound],['/settings/security','Account & security',ShieldCheck],
  ['/settings/preferences','Preferences',SlidersHorizontal],['/settings/accounts','Trading accounts',Wallet],
  ['/billing','Wallet & recharges',CreditCard],['/settings/data','Your data',Download],['/settings/help','Help & customer care',LifeBuoy],
] as const;

export function SettingsLayout({children,wide=false}:{children?:ReactNode;wide?:boolean}){
  const workspace=useStore(s=>s.workspace);
  if(!workspace)return null;
  return <div className={`account-settings ${wide?'account-settings-wide':''}`}><div className="account-heading"><span className="eyebrow">MAKE YOURSELF AT HOME</span><h1>Your account</h1><p>One place for your profile, preferences and membership.</p></div>
    <div className="account-layout"><aside className="account-settings-nav"><div className="account-card-identity"><span className="account-avatar">{workspace.user.name.trim()[0]?.toUpperCase()||'H'}</span><strong>{workspace.user.name}</strong><small>{workspace.user.email}</small><Badge tone="green">{workspace.billing.label}</Badge></div><nav aria-label="Account settings">{sections.map(([path,label,Icon])=><NavLink key={path} to={path} className={({isActive})=>isActive?'active':''}><Icon size={17}/>{label}</NavLink>)}</nav><Link to="/overview" className="account-back">Back to journal <ArrowUpRight size={15}/></Link></aside><div className="account-settings-content">{children||<Outlet/>}</div></div></div>;
}

function Notice({text}:{text:string}){return text?<div className="account-notice" role="status">{text}</div>:null;}

export function ProfilePage(){
  const {workspace,refresh}=useStore();
  const [name,setName]=useState(workspace?.user.name||''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  if(!workspace)return null;
  return <><PageTitle title="Your profile" description="A familiar face, and the details that make this journal yours."/><Panel><div className="profile-cover"><div className="profile-monogram">{name.trim()[0]?.toUpperCase()||'H'}</div><div><span className="eyebrow">THE TRADER BEHIND THE TRADES</span><h2>{workspace.user.name}</h2><p>{workspace.user.email}</p></div></div><form className="padded stack" onSubmit={async e=>{e.preventDefault();setError('');setNotice('');if(!name.trim()){setError('Enter your name.');return;}setBusy(true);try{await put('/profile',{data:{display_name:name.trim()}});setName(name.trim());refresh();setNotice('Your profile has been saved.');}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>
      <Field label="Display name" hint="Used in your journal and account menu."><input value={name} onChange={e=>setName(e.target.value)} required maxLength={100} autoComplete="name"/></Field><Field label="Sign-in email"><input value={workspace.user.email} type="email" readOnly/></Field><Link className="text-link" to="/settings/security">Change email or manage account security →</Link>{error&&<ErrorState message={error}/>}<Notice text={notice}/><div><Button variant="primary" disabled={busy||name.trim()===workspace.user.name}><Save size={16}/>{busy?'Saving…':'Save profile'}</Button></div></form></Panel>
      <div className="profile-wallet"><div><span className="eyebrow">YOUR WALLET</span><h3>{workspace.billing.label}</h3><p>{num(workspace.billing.credits.remaining,0)} credits available</p></div><Link to="/billing" className="button">Recharge wallet <ArrowUpRight size={16}/></Link></div></>;
}

export function SecurityPage(){
  const {workspace,refresh}=useStore();
  const [email,setEmail]=useState(''),[pendingEmail,setPendingEmail]=useState(''),[busy,setBusy]=useState(''),[error,setError]=useState(''),[notice,setNotice]=useState('');
  useEffect(()=>{let alive=true;authClient().then(({client})=>client.auth.getUser()).then(({data,error})=>{if(alive&&!error)setPendingEmail(data.user?.new_email||'');}).catch(()=>{});return()=>{alive=false;};},[]);
  if(!workspace)return null;
  async function run(key:string,action:()=>Promise<void>){setBusy(key);setError('');setNotice('');try{await action();}catch(e){setError((e as Error).message);}finally{setBusy('');}}
  return <><PageTitle title="Account & security" description="Manage how you sign in and where you stay signed in."/>{error&&<ErrorState message={error}/>}<Notice text={notice}/><div className="stack">
    <Panel title="Email address"><form className="padded stack" onSubmit={e=>{e.preventDefault();void run('email',async()=>{
      const next=email.trim();if(next.toLowerCase()===workspace.user.email.toLowerCase())throw new Error('Enter a different email address.');
      const {client}=await authClient();const result=await client.auth.updateUser({email:next},{emailRedirectTo:location.origin+'/auth/callback'});if(result.error)throw result.error;
      setPendingEmail(result.data.user?.new_email||'');await client.auth.refreshSession();refresh();setEmail('');
      setNotice(result.data.user?.new_email?'Check your inboxes for confirmation instructions. Your sign-in email changes only after verification.':'Your email has been updated.');
    });}}><div className="account-detail-row"><span>Current sign-in email</span><strong>{workspace.user.email}</strong></div>{pendingEmail&&<div className="account-notice">Awaiting verification: {pendingEmail}</div>}<Field label="New email address"><input type="email" autoComplete="email" required maxLength={254} value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@example.com"/></Field><p className="small muted">Follow the confirmation links sent to your email addresses to complete the change.</p><div><Button disabled={!!busy||!email.trim()}><Mail size={16}/>{busy==='email'?'Requesting change…':'Change email'}</Button></div></form></Panel>
    <Panel title="Password"><div className="padded stack"><p>Send a secure password-reset link to <strong>{workspace.user.email}</strong>. Your new password must have at least 8 characters.</p><div><Button disabled={!!busy} onClick={()=>void run('password',async()=>{const {client}=await authClient();const {error}=await client.auth.resetPasswordForEmail(workspace.user.email,{redirectTo:location.origin+'/auth/reset'});if(error)throw error;setNotice('Password-reset email requested. Check your inbox and spam folder.');})}>{busy==='password'?'Sending…':'Send password-reset link'}</Button></div></div></Panel>
    <Panel title="Sign-in sessions"><div className="padded stack"><div className="account-session"><span className="session-dot"/><div><h3>This browser</h3><p>You are signed in as {workspace.user.email}.</p></div><Badge tone="green">Current</Badge></div><div className="button-row"><Button disabled={!!busy} onClick={()=>void run('local',()=>signOut())}><LogOut size={16}/>Sign out this device</Button><Button disabled={!!busy} onClick={()=>void run('others',async()=>{await signOut('others');setNotice('Other sessions have been signed out. Their current access expires shortly; this browser stays signed in.');})}>Sign out other devices</Button><Button variant="danger" disabled={!!busy} onClick={()=>void run('global',()=>signOut('global'))}>Sign out all devices</Button></div><p className="small muted">Signing out does not delete your journal or cancel your subscription.</p></div></Panel>
  </div></>;
}

export function PreferencesPage(){
  const {workspace,refresh}=useStore();
  const [value,setValue]=useState<Preferences>({...defaultPreferences,...workspace?.settings.preferences});
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  if(!workspace)return null;
  function change<K extends keyof Preferences>(key:K,next:Preferences[K]){setValue(v=>({...v,[key]:next}));setNotice('');}
  return <><PageTitle title="Your preferences" description="Set the starting point and reading experience that suit your routine."/><form className="stack" onSubmit={async e=>{e.preventDefault();setBusy(true);setError('');setNotice('');try{const result=await put('/settings/preferences',{data:value});setValue(result.preferences);refresh();setNotice('Preferences saved. Display changes apply now; starting filters apply when you next open your workspace.');}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>
    <Panel title="Start your session"><div className="padded stack"><Field label="Page after sign-in"><Select value={value.landing_page} onChange={e=>change('landing_page',e.target.value)}>{landingPages.map(([path,label])=><option key={path} value={path}>{label}</option>)}</Select></Field><Field label="Default trading account"><Select value={value.default_account_id||''} onChange={e=>change('default_account_id',e.target.value||null)}><option value="">All trading accounts</option>{workspace.accounts.map(a=><option value={a.id} key={a.id}>{a.name}</option>)}</Select></Field><Field label="Starting date range"><Select value={value.date_range} onChange={e=>change('date_range',e.target.value as Preferences['date_range'])}><option value="all">All time</option><option value="7">Last 7 days</option><option value="30">Last 30 days</option><option value="90">Last 90 days</option><option value="365">Last year</option></Select></Field></div></Panel>
    <Panel title="Reading & accessibility"><div className="padded stack"><label className="preference-toggle"><span><strong>Compact tables</strong><small>Fit more journal and activity rows on screen.</small></span><input type="checkbox" role="switch" checked={value.compact_tables} onChange={e=>change('compact_tables',e.target.checked)}/></label><label className="preference-toggle"><span><strong>Reduce motion</strong><small>Minimise transitions and animation in your workspace. Your device’s reduced-motion setting is also respected.</small></span><input type="checkbox" role="switch" checked={value.reduce_motion} onChange={e=>change('reduce_motion',e.target.checked)}/></label></div></Panel>
    <Panel title="Market & region"><div className="padded stack"><div className="settings-item"><Globe2 size={22}/><p>Indian markets, Indian time. These reporting conventions keep your journal consistent.</p></div><div className="account-detail-row"><span>Reporting currency</span><strong>Indian rupee · INR (₹)</strong></div><div className="account-detail-row"><span>Time zone</span><strong>Asia/Kolkata · IST</strong></div><div className="account-detail-row"><span>Interface language</span><strong>English</strong></div></div></Panel>
    {error&&<ErrorState message={error}/>}<Notice text={notice}/><div className="button-row"><Button variant="primary" disabled={busy}><Save size={16}/>{busy?'Saving…':'Save preferences'}</Button><Button type="button" disabled={busy} onClick={()=>{setValue({...defaultPreferences});setNotice('Defaults selected. Save to apply them.');}}>Restore defaults</Button></div>
  </form></>;
}

export function DataPage(){
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  return <><PageTitle title="Your data" description="Keep a copy of your work, and bring your trading history with you."/><div className="stack"><Panel title="Export your journal"><div className="padded stack"><p>Download a JSON archive of your accounts, trades, notes, conversations and practice sessions.</p>{error&&<ErrorState message={error}/>}<div><Button disabled={busy} onClick={async()=>{setBusy(true);setError('');try{await downloadApi('/backup','hakisense-journal.json');}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}><Download size={16}/>{busy?'Preparing archive…':'Download my data'}</Button></div><p className="small muted">The archive contains your personal journal information. Store it somewhere you trust.</p></div></Panel><Panel title="Import & export trades"><div className="padded stack"><p>Preview and map broker position files before importing. Export filtered trades from your journal.</p><div className="button-row"><Link className="button" to="/import">Import trades</Link><Link className="button" to="/trades">Open trade journal</Link></div></div></Panel><Panel title="Privacy & account requests"><div className="padded stack"><p>For privacy, account closure, or help with your data, contact customer care. Subscription renewal is managed separately in your billing settings.</p><div className="button-row"><Link className="text-link" to="/settings/help?topic=Privacy%20%26%20account">Contact customer care →</Link><Link className="text-link" to="/billing">Manage renewal →</Link></div></div></Panel></div></>;
}
