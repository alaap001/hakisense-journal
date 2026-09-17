import { useEffect,useId,useLayoutEffect,useRef,useState } from 'react';
import { createPortal } from 'react-dom';
import { Link,useLocation } from 'react-router-dom';
import { ChevronDown,UserRound,SlidersHorizontal,ShieldCheck,Wallet,CreditCard,LifeBuoy,LogOut,LockKeyhole,ArrowUpRight } from 'lucide-react';
import { useStore,num } from './lib';
import { signOut } from './account';
import './account.css';
import { useDropdownPresence } from './dropdownMotion';

export function AccountMenu({variant='workspace'}:{variant?:'workspace'|'profile'|'avatar'}){
  const workspace=useStore(s=>s.workspace);
  const location=useLocation();
  const [open,setOpen]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const {present,phase}=useDropdownPresence(open);
  const [position,setPosition]=useState({top:0,left:0});
  const trigger=useRef<HTMLButtonElement>(null),menu=useRef<HTMLDivElement>(null);
  const id=useId();
  useEffect(()=>{setOpen(false);},[location.pathname]);
  useLayoutEffect(()=>{
    if(!open||!present||!trigger.current||!menu.current)return;
    const rect=trigger.current.getBoundingClientRect(),height=menu.current.offsetHeight;
    setPosition({left:Math.max(12,Math.min(rect.left,window.innerWidth-300)),top:Math.max(12,Math.min(rect.bottom+8,window.innerHeight-height-12))});
    menu.current.querySelector<HTMLElement>('[role="menuitem"]')?.focus({preventScroll:true});
  },[open,present]);
  useEffect(()=>{
    if(!open)return;
    const outside=(e:PointerEvent)=>{if(!menu.current?.contains(e.target as Node)&&!trigger.current?.contains(e.target as Node))setOpen(false);};
    const close=()=>setOpen(false);
    const scroll=(e:Event)=>{if(!menu.current?.contains(e.target as Node))setOpen(false);};
    document.addEventListener('pointerdown',outside);window.addEventListener('resize',close);window.addEventListener('scroll',scroll,true);
    return()=>{document.removeEventListener('pointerdown',outside);window.removeEventListener('resize',close);window.removeEventListener('scroll',scroll,true);};
  },[open]);
  if(!workspace)return null;
  const {user,billing}=workspace;
  const initial=user.name.trim()[0]?.toUpperCase()||'H';
  const links=[
    ['/settings/profile','My profile',UserRound],['/settings/security','Account & security',ShieldCheck],
    ['/settings/preferences','Preferences',SlidersHorizontal],['/settings/accounts','Trading accounts',Wallet],
    ['/billing','Wallet & recharges',CreditCard],['/settings/help','Help & customer care',LifeBuoy],
    ...(workspace.admin_role?[['/admin','Administration',LockKeyhole]]:[]),
  ] as const;
  return <><button ref={trigger} type="button" className={`account-trigger account-trigger-${variant}`} aria-label={variant==='avatar'?'Open user profile menu':`Account menu for ${user.name}`} aria-haspopup="menu" aria-expanded={open} aria-controls={open?id:undefined} onClick={()=>{setError('');setOpen(!open);}} onKeyDown={e=>{if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();setOpen(true);}}}>
    <span className="account-avatar">{initial}</span>{variant!=='avatar'&&<span className="account-trigger-label"><strong>{user.name}</strong><small>{variant==='workspace'?`${billing.label} · India`:user.email}</small></span>}<ChevronDown size={15} className={open?'menu-chevron open':'menu-chevron'}/>
  </button>{present&&createPortal(<div data-phase={phase} inert={!open} aria-hidden={!open} id={id} ref={menu} className="account-menu" role="menu" aria-label="Your account" style={position} onBlur={e=>{
    // Safari can report no next focus target when clicking another menu item.
    // Keep it mounted for the click; the outside pointer handler dismisses click-away.
    if(e.relatedTarget&&!e.currentTarget.contains(e.relatedTarget as Node)&&e.relatedTarget!==trigger.current)setOpen(false);
  }} onKeyDown={e=>{
    if(e.key==='Escape'){e.preventDefault();setOpen(false);trigger.current?.focus({preventScroll:true});return;}
    const items=Array.from(menu.current?.querySelectorAll<HTMLElement>('[role="menuitem"]:not(:disabled)')||[]);
    const current=items.indexOf(document.activeElement as HTMLElement);
    if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){e.preventDefault();const next=e.key==='Home'?0:e.key==='End'?items.length-1:(current+(e.key==='ArrowDown'?1:-1)+items.length)%items.length;items[next]?.focus({preventScroll:true});}
  }}>
    <div className="account-menu-identity" role="presentation"><span className="account-avatar">{initial}</span><div><strong>{user.name}</strong><small>{user.email}</small></div></div>
    <Link role="menuitem" className="account-menu-wallet" to="/billing" onClick={()=>setOpen(false)}><span><strong>{billing.label}</strong><small>{num(billing.credits.remaining,0)} credits remaining</small></span><ArrowUpRight size={17}/></Link>
    <div className="account-menu-links" role="presentation">{links.map(([path,label,Icon])=><Link role="menuitem" to={path as string} key={path as string} onClick={()=>setOpen(false)}><Icon size={17}/>{label as string}</Link>)}</div>
    {error&&<p className="account-menu-error" role="alert">{error}</p>}
    <button type="button" role="menuitem" className="account-menu-signout" disabled={busy} onClick={async()=>{setBusy(true);try{await signOut();}catch(e){setError((e as Error).message);setBusy(false);}}}><LogOut size={17}/>{busy?'Signing out…':'Sign out'}<small>This device</small></button>
  </div>,document.body)}</>;
}
