import { Select } from './Select';
import { useEffect,useRef,useState,lazy,Suspense } from 'react';
import { Routes,Route,NavLink,Link,useLocation,Navigate } from 'react-router-dom';
import { LayoutDashboard,BookOpen,CalendarDays,ChartNoAxesCombined,Sparkles,NotebookPen,Layers,Play,Upload,Wallet,Settings,ChevronDown,Plus,Menu,ArrowUpRight,Check,Target,Command,LockKeyhole } from 'lucide-react';
import { api,post,useStore,useData,explain,date,emptyFilters } from './lib';
import { Button,IconButton,Loading,ErrorState,Field,Badge } from './ui';
import { Dashboard } from './Dashboard';
import { Journal,TradeEditor,TradeDetail } from './Journal';
import type { Workspace } from './types';
import { Analytics } from './Analytics';
import { Calendar } from './Calendar';
import { Coach } from './Coach';
import { Notebook,Playbooks,Goals } from './Notes';
import { ImportTrades } from './Import';
import { Accounts } from './Settings';
import { AccountMenu } from './AccountMenu';
import { SettingsLayout,ProfilePage,SecurityPage,PreferencesPage,DataPage } from './AccountSettings';
import { HelpPage } from './Help';
import { defaultPreferences,dateScope,signOut } from './account';
import { Simulator } from './Simulator';
import { BillingPage,FeatureGate } from './Billing';
import { CreditCard } from 'lucide-react';
import { today,num } from './lib';

const Admin=lazy(()=>import('./Admin'));
const navigation=[
  {title:'WORKSPACE',items:[['/overview','Overview',LayoutDashboard],['/trades','Trade journal',BookOpen],['/calendar','Calendar',CalendarDays],['/analytics','Analytics',ChartNoAxesCombined],['/coach','AI coach',Sparkles]]},
  {title:'GROW YOUR EDGE',items:[['/notebook','Notebook',NotebookPen],['/playbooks','Playbook',Layers],['/simulator','Market replay',Play],['/goals','Goals & income',Target]]},
  {title:'MANAGE',items:[['/import','Import trades',Upload],['/accounts','Accounts',Wallet],['/billing','Credit wallet',CreditCard],['/settings','My account',Settings]]},
];

export default function WorkspaceApp(){
  const location=useLocation();
  const {workspace,setWorkspace,filters,setFilter,revision,toast,edit,tradeEditor,detail}=useStore();
  const [error,setError]=useState(''),[mobile,setMobile]=useState(false);
  const [dateMode,setDateMode]=useState('all');
  const initialized=useRef(false);
  const preferences={...defaultPreferences,...workspace?.settings.preferences};
  const accountPage=location.pathname.startsWith('/settings')||['/billing','/accounts','/profile','/preferences','/admin'].includes(location.pathname);
  const pageLabel=location.pathname.startsWith('/settings')?'My account':location.pathname==='/billing'?'Subscription':location.pathname.slice(1).replaceAll('-',' ');
  useEffect(()=>{
    if(!workspace||initialized.current)return;initialized.current=true;
    const p={...defaultPreferences,...workspace.settings.preferences};
    setDateMode(p.date_range);setFilter({account_id:p.default_account_id||'',...dateScope(p.date_range)});
  },[workspace,setFilter]);
  useEffect(()=>{
    document.documentElement.classList.toggle('reduce-motion',preferences.reduce_motion);
    return()=>document.documentElement.classList.remove('reduce-motion');
  },[preferences.reduce_motion]);
  useEffect(()=>{document.title=(pageLabel||'Journal')+' · '+(workspace?.product.brand_name||'HakiSense');},[pageLabel,workspace?.product.brand_name]);
  useEffect(()=>{let active=true;api<Workspace>('/workspace').then(value=>{if(active){setWorkspace(value);setError('');}}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[revision,setWorkspace]);
  useEffect(()=>{setMobile(false);window.scrollTo(0,0);},[location.pathname]);
  useEffect(()=>{const listener=(e:KeyboardEvent)=>{if((e.metaKey||e.ctrlKey)&&e.key==='j'){e.preventDefault();edit('new');}};window.addEventListener('keydown',listener);return()=>window.removeEventListener('keydown',listener);},[edit]);
  useEffect(()=>{
    const context=(document as any).modelContext;if(!context?.registerTool)return;
    const lifecycle=new AbortController();
    Promise.resolve(context.registerTool({name:'read_filtered_trades',title:'Read journal trades',description:'Read trades in the currently selected journal scope without changing data.',inputSchema:{type:'object',properties:{},additionalProperties:false},annotations:{readOnlyHint:true,untrustedContentHint:true},execute:async()=>{const f=useStore.getState().filters;const rows=await api('/trades?'+new URLSearchParams(Object.entries(f).filter(([,v])=>v)));return {count:rows.length,trades:rows};}},{signal:lifecycle.signal})).catch(()=>{});
    return()=>lifecycle.abort();
  },[]);
  if(!workspace)return <div className="initial-loading"><div className="brand-logo">H</div><h2>HakiSense</h2>{error?<><ErrorState message={error}/><Button onClick={()=>window.location.reload()}>Try again</Button><Link className="text-link" to="/help">Help & customer care</Link><Button onClick={()=>void signOut().catch(explain)}>Sign out</Button></>:<Loading/>}</div>;
  return <div className={`app-shell ${preferences.compact_tables?'compact-tables':''}`}><aside className={`sidebar ${mobile?'mobile-open':''}`}><Link to="/overview" className="brand"><div className="brand-logo">H</div><div>{workspace.product.brand_name}<span>TRADING JOURNAL</span></div></Link><AccountMenu/><nav>{navigation.map(section=><div className="nav-section" key={section.title}><span className="nav-caption">{section.title}</span>{section.items.map(([path,label,Icon]:any)=><NavLink key={path} to={path} end={path==='/overview'} className={({isActive})=>isActive?'nav-item active':'nav-item'}><Icon size={18}/><span>{label}</span>{label==='AI coach'&&<span className="nav-new">AI</span>}</NavLink>)}</div>)}</nav>{workspace.admin_role&&<NavLink className="admin-launch-link" to="/admin"><LockKeyhole size={16}/>Administration</NavLink>}<div className="sidebar-bottom"><div className="sidebar-note"><div><Sparkles size={17}/><strong>A better review habit.</strong></div><p>Turn your trading history into your next lesson.</p><Link to="/coach">Meet your AI coach <ArrowUpRight size={15}/></Link></div><AccountMenu variant="profile"/></div></aside>{mobile&&<div className="sidebar-scrim" onClick={()=>setMobile(false)}/>}<div className="main-shell"><header className="topbar"><div className="breadcrumb"><IconButton label="Toggle navigation" className="mobile-menu" onClick={()=>setMobile(!mobile)}><Menu size={20}/></IconButton><span>Workspace</span><span>/</span><strong>{pageLabel}</strong></div><div className="topbar-actions"><Link className="credit-pill" to="/billing"><Sparkles size={14}/>{num(workspace.billing.credits.remaining,0)} credits</Link><span className="topbar-divider"/><Button variant="ghost" onClick={()=>edit('new')}><Plus size={16}/>Quick entry <kbd>⌘ J</kbd></Button><AccountMenu variant="avatar"/></div></header><main>{workspace.product.announcement&&<div className="admin-announcement">{workspace.product.announcement}</div>}{!accountPage&&<div className="global-filters"><div className="scope-control"><Wallet size={15}/><Select aria-label="Select trading account" value={filters.account_id} onChange={e=>setFilter({account_id:e.target.value})}><option value="">All accounts</option>{workspace.accounts.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</Select></div><div className="scope-control"><CalendarDays size={15}/><Select aria-label="Date range" value={dateMode} onChange={e=>{const value=e.target.value;setDateMode(value);if(value==='custom')return;if(value==='all'){setFilter({start:'',end:''});return;}const start=new Date();start.setUTCDate(start.getUTCDate()-Number(value));setFilter({start:new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit',day:'2-digit'}).format(start),end:today()});}}><option value="all">All time</option><option value="7">Last 7 days</option><option value="30">Last 30 days</option><option value="90">Last 90 days</option><option value="365">Last year</option><option value="custom">Custom dates</option></Select></div>{dateMode==='custom'&&<><input type="date" aria-label="Start entry date" value={filters.start} onChange={e=>setFilter({start:e.target.value})}/><span className="muted">to</span><input type="date" aria-label="End entry date" value={filters.end} onChange={e=>setFilter({end:e.target.value})}/></>}<span className="filters-note">{filters.start?`${date(filters.start)} – ${filters.end?date(filters.end):'present'}`:'All recorded entry dates'} · INR · IST</span>{Object.entries(filters).some(([k,v])=>v&&!['account_id','start','end'].includes(k))&&<Button variant="ghost" onClick={()=>setFilter({...emptyFilters,account_id:filters.account_id,start:filters.start,end:filters.end})}>Clear journal filters</Button>}</div>}<Routes><Route path="/admin" element={<Suspense fallback={<Loading/>}><Admin/></Suspense>}/><Route path="/home" element={<Navigate to={preferences.landing_page} replace/>}/><Route path="/overview" element={<Dashboard/>}/><Route path="/trades" element={<FeatureGate feature="journal"><Journal/></FeatureGate>}/><Route path="/calendar" element={<FeatureGate feature="calendar"><Calendar/></FeatureGate>}/><Route path="/analytics" element={<FeatureGate feature="analytics"><Analytics/></FeatureGate>}/><Route path="/coach" element={<Coach/>}/><Route path="/notebook" element={<FeatureGate feature="notebook"><Notebook/></FeatureGate>}/><Route path="/playbooks" element={<FeatureGate feature="playbooks"><Playbooks/></FeatureGate>}/><Route path="/simulator" element={<FeatureGate feature="replay"><Simulator/></FeatureGate>}/><Route path="/goals" element={<Goals/>}/><Route path="/import" element={<FeatureGate feature="import_export"><ImportTrades/></FeatureGate>}/><Route path="/accounts" element={<Navigate to="/settings/accounts" replace/>}/><Route path="/profile" element={<Navigate to="/settings/profile" replace/>}/><Route path="/preferences" element={<Navigate to="/settings/preferences" replace/>}/><Route path="/billing" element={<SettingsLayout wide><BillingPage/></SettingsLayout>}/><Route path="/settings" element={<SettingsLayout/>}><Route index element={<Navigate to="profile" replace/>}/><Route path="profile" element={<ProfilePage/>}/><Route path="security" element={<SecurityPage/>}/><Route path="preferences" element={<PreferencesPage/>}/><Route path="accounts" element={<FeatureGate feature="accounts"><Accounts/></FeatureGate>}/><Route path="wallet" element={<Navigate to="/billing" replace/>}/><Route path="data" element={<DataPage/>}/><Route path="help" element={<HelpPage/>}/><Route path="*" element={<Navigate to="/settings/profile" replace/>}/></Route><Route path="*" element={<Navigate to="/overview" replace/>}/></Routes><footer className="page-footer"><span>HakiSense Journal</span><Link to="/settings/help">Help & customer care</Link></footer></main></div>{toast&&<div className="toast" role="status"><Check size={18}/>{toast}</div>}{tradeEditor&&<TradeEditor key={typeof tradeEditor==='string'?'new':tradeEditor.id}/>} {detail&&<TradeDetail key={detail.id}/>}</div>;
}
