import { useEffect,useRef,useState,type ReactNode } from 'react';
import type { Session,SupabaseClient } from '@supabase/supabase-js';
import { ArrowRight,ShieldCheck,TrendingUp,Mail,KeyRound,CheckCircle2 } from 'lucide-react';
import { authClient,type PublicConfig } from './authClient';
import { useStore } from './lib';
import { Button,Field,ErrorState,Loading } from './ui';
import { useLocation, useNavigate } from 'react-router-dom';

export function AuthBoundary({children}:{children:(session:Session)=>ReactNode}){
  const navigate=useNavigate();
  const currentUser=useRef<string|null>(null);
  const [client,setClient]=useState<SupabaseClient|null>(null),[session,setSession]=useState<Session|null>(null),[config,setConfig]=useState<PublicConfig|null>(null),[loading,setLoading]=useState(true),[error,setError]=useState(''),[recovering,setRecovering]=useState(false);
  useEffect(()=>{let alive=true;let unsubscribe:undefined|(()=>void);
    authClient().then(async value=>{
      if(!alive)return;setClient(value.client);setConfig(value.config);
      const {data}=value.client.auth.onAuthStateChange((event,next)=>{
        if(!alive)return;
        if(currentUser.current!==(next?.user.id||null)){useStore.getState().reset();currentUser.current=next?.user.id||null;}
        setSession(next);setLoading(false);
        if(event==='USER_UPDATED')useStore.getState().refresh();
        if(event==='PASSWORD_RECOVERY')setRecovering(true);
        if(event==='SIGNED_OUT'){setRecovering(false);useStore.getState().reset();}
      });unsubscribe=()=>data.subscription.unsubscribe();
      const initial=await value.client.auth.getSession();
      if(alive){if(initial.error)setError(initial.error.message);setSession(initial.data.session);setLoading(false);}
    }).catch(e=>{if(alive){setError(e.message);setLoading(false);}});
    return()=>{alive=false;unsubscribe?.();};
  },[]);
  if(loading)return <div className="initial-loading"><div className="brand-logo">H</div><Loading/></div>;
  if(!client||!config)return <div className="initial-loading"><h1>HakiSense</h1><ErrorState message={error}/><Button onClick={()=>location.reload()}>Try again</Button></div>;
  if(!session||recovering)return <AuthScreen client={client} config={config} recovering={recovering} onRecovered={()=>{setRecovering(false);navigate('/home',{replace:true});}}/>;
  return <>{children(session)}</>;
}

function AuthScreen({client,config,recovering,onRecovered}:{client:SupabaseClient;config:PublicConfig;recovering:boolean;onRecovered:()=>void}){
  const {pathname}=useLocation();
  const [mode,setMode]=useState<'login'|'signup'|'forgot'>(pathname==='/signup'?'signup':'login'),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  useEffect(()=>{document.title=(recovering?'Reset password':mode==='signup'?'Create an account':mode==='forgot'?'Reset password':'Sign in')+' · '+config.brand_name;},[mode,recovering,config.brand_name]);
  const title=recovering?'Choose a new password':mode==='signup'?'Build your trading journal.':mode==='forgot'?'Reset your password.':'Welcome back.';
  return <div className="auth-layout"><section className="auth-story"><a href="/" className="brand"><div className="brand-logo">H</div><div>{config.brand_name}<span>TRADING JOURNAL</span></div></a><div className="auth-story-content"><span className="auth-kicker">FOR THE INDIAN TRADER</span><h1>Your trades.<br/>Your process.<br/><em>A clearer edge.</em></h1><p>Review your NIFTY setups, equity trades and crypto positions in one journal built around the way you trade.</p><div className="market-chips"><span>NSE & BSE</span><span>Index F&O</span><span>Crypto</span></div><div className="auth-preview"><TrendingUp size={24}/><div><strong>Make every session a lesson.</strong><span>Journal → Review → Refine</span></div></div></div><div className="auth-story-footer"><span>₹ INR reporting</span><span>Asia/Kolkata · IST</span></div></section><section className="auth-form-side"><div className="auth-form-card"><div className="auth-form-icon">{mode==='forgot'?<Mail size={25}/>:<ShieldCheck size={25}/>}</div><h2>{title}</h2><p>{recovering?'Secure your account with a strong password.':mode==='signup'?'Start with a free account. Upgrade when you need more.':mode==='forgot'?'We’ll send a secure reset link to your email.':'Sign in to your workspace and pick up where you left off.'}</p><form onSubmit={async e=>{e.preventDefault();setError('');setNotice('');setBusy(true);const data=new FormData(e.currentTarget),email=String(data.get('email')||''),password=String(data.get('password')||'');try{
    if(recovering){const result=await client.auth.updateUser({password});if(result.error)throw result.error;onRecovered();}
    else if(mode==='login'){const result=await client.auth.signInWithPassword({email,password});if(result.error)throw result.error;}
    else if(mode==='signup'){const result=await client.auth.signUp({email,password,options:{data:{display_name:String(data.get('name')||'Trader')},emailRedirectTo:location.origin+'/auth/callback'}});if(result.error)throw result.error;setNotice('Check your email to verify your account, then sign in.');}
    else{const result=await client.auth.resetPasswordForEmail(email,{redirectTo:location.origin+'/auth/reset'});if(result.error)throw result.error;setNotice('If an account exists for this email, a reset link is on its way.');}
  }catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>
    {mode==='signup'&&!recovering&&<Field label="Your name"><input name="name" autoComplete="name" required maxLength={100} placeholder="How should we address you?"/></Field>}
    {!recovering&&<Field label="Email address"><input name="email" type="email" autoComplete="email" required placeholder="you@example.com"/></Field>}
    {(mode!=='forgot'||recovering)&&<Field label="Password" hint={mode==='signup'||recovering?'Use at least 8 characters.':undefined}><input name="password" type="password" required minLength={mode==='signup'||recovering?config.password_min_length:1} maxLength={128} autoComplete={mode==='signup'||recovering?'new-password':'current-password'}/></Field>}
    {error&&<ErrorState message={error}/>} {notice&&<div className="auth-notice" role="status"><CheckCircle2 size={19}/>{notice}</div>}
    <Button variant="primary" disabled={busy}>{busy?'Please wait…':recovering?'Update password':mode==='login'?'Sign in':mode==='signup'?'Create free account':'Send reset link'}<ArrowRight size={17}/></Button>
  </form>{!recovering&&<div className="auth-switch">{mode==='login'?<><button onClick={()=>{setMode('forgot');setError('');setNotice('');}}>Forgot password?</button><span>New to HakiSense? <button onClick={()=>{setMode('signup');setError('');setNotice('');}}>Create an account</button></span></>:<button onClick={()=>{setMode('login');setError('');setNotice('');}}>Back to sign in</button>}</div>}<div className="auth-policies"><a href="/help">Help & customer care</a>{config.policies.terms&&<a href={config.policies.terms} target="_blank" rel="noreferrer">Terms</a>}{config.policies.privacy&&<a href={config.policies.privacy} target="_blank" rel="noreferrer">Privacy</a>}{config.support_email&&<a href={'mailto:'+config.support_email}>Contact support</a>}</div></div></section></div>;
}
