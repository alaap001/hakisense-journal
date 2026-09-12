import { useEffect, useState } from 'react';
import { create } from 'zustand';
import { authClient } from './authClient';
import type { Filters, Trade, Workspace } from './types';

export const emptyFilters: Filters = {account_id:'',start:'',end:'',symbol:'',asset_type:'',side:'',status:'',setup:'',emotion:'',tag:'',outcome:''};
type Store = {
  workspace: Workspace | null; filters: Filters; revision: number; toast: string; tradeEditor: Trade | 'new' | null; detail: Trade | null;
  reset: () => void;
  setWorkspace: (value: Workspace) => void; setFilter: (value: Partial<Filters>) => void; refresh: () => void; notify: (message: string) => void;
  edit: (trade: Trade | 'new' | null) => void; inspect: (trade: Trade | null) => void;
};
let toastTimer: ReturnType<typeof setTimeout>;
export const useStore = create<Store>((set) => ({
  reset:()=>set({workspace:null,filters:emptyFilters,tradeEditor:null,detail:null,toast:'',revision:0}),
  workspace:null, filters:emptyFilters, revision:0, toast:'', tradeEditor:null, detail:null,
  setWorkspace:workspace=>set({workspace}), setFilter:value=>set(s=>({filters:{...s.filters,...value}})), refresh:()=>set(s=>({revision:s.revision+1})),
  notify:toast=>{clearTimeout(toastTimer);set({toast});toastTimer=setTimeout(()=>set({toast:''}),5500);},
  edit:tradeEditor=>set({tradeEditor}),inspect:detail=>set({detail}),
}));

export class ApiError extends Error {
  constructor(message:string,public status:number,public code?:string){super(message);}
}
export async function authorizedFetch(path:string,init:RequestInit={}){
  const {client}=await authClient();
  const {data}=await client.auth.getSession();
  const headers=new Headers(init.headers);
  if(data.session)headers.set('Authorization','Bearer '+data.session.access_token);
  if(init.body&&!(init.body instanceof FormData))headers.set('Content-Type','application/json');
  return fetch('/api'+path,{...init,headers});
}
async function checkResponse(response:Response){
  if(!response.ok){
    let detail:any;
    try{detail=(await response.json()).detail;}catch{detail='HakiSense is temporarily unavailable. Please try again.';}
    if(Array.isArray(detail))detail=detail.map(e=>`${e.loc?.slice(1).join('.')}: ${e.msg}`).join('; ');
    if(['price_changed','config_changed','subscription_required'].includes(detail?.code))useStore.getState().refresh();
    throw new ApiError(typeof detail==='string'?detail:detail?.message||`Request failed (${response.status})`,response.status,detail?.code);
  }
  return response;
}
export async function api<T=any>(path:string,init:RequestInit={}):Promise<T>{
  return (await checkResponse(await authorizedFetch(path,init))).json();
}
export async function waitForJob(id:string){
  for(let i=0;i<120;i++){
    const job=await api('/ai/jobs/'+id);
    if(job.status==='succeeded'){useStore.getState().refresh();return job.result;}
    if(job.status==='failed'){useStore.getState().refresh();throw new Error(job.error||'The review failed. Your credits were refunded.');}
    await new Promise(resolve=>setTimeout(resolve,2000));
  }
  useStore.getState().refresh();throw new Error('Your review is still processing. View its progress in AI activity.');
}
export async function post(path:string,data:unknown):Promise<any>{
  const body=path==='/ai/query'?{...(data as Record<string,unknown>),expected_credits:creditsFor((data as any).mode||'chat')}:data;
  const init={method:'POST',body:JSON.stringify(body),headers:{'Idempotency-Key':crypto.randomUUID()}};
  if(path==='/ai/query'){
    let job;
    try{job=await api(path,init);}catch(error){if(!(error instanceof TypeError))throw error;job=await api(path,init);}
    useStore.getState().refresh();return waitForJob(job.id);
  }
  return api(path,init);
}
export const put=(path:string,data:unknown)=>api(path,{method:'PUT',body:JSON.stringify(data)});
export const del=(path:string)=>api(path,{method:'DELETE'});
export async function downloadApi(path:string,name:string){
  const response=await checkResponse(await authorizedFetch(path));const blob=await response.blob();
  const url=URL.createObjectURL(blob);const anchor=document.createElement('a');anchor.href=url;anchor.download=name;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
export const creditsFor=(mode:string)=>useStore.getState().workspace?.catalog.tasks.find(t=>t.code===mode)?.credits;
export const creditLabel=(mode:string)=>`${creditsFor(mode)??'—'} credits`;
export const hasFeature=(feature:string)=>!!useStore.getState().workspace?.billing.features.includes(feature);
export const qs=(filters:Partial<Filters>)=>'?'+new URLSearchParams(Object.entries(filters).filter(([,v])=>v)).toString();
export function useData<T=any>(path:string,enabled=true){
  const revision=useStore(s=>s.revision);
  const [data,setData]=useState<T|null>(null);
  const [error,setError]=useState('');
  const [loading,setLoading]=useState(true);
  useEffect(()=>{if(!enabled){setData(null);setLoading(false);return;}let active=true;setLoading(true);setError('');api<T>(path).then(value=>{if(active)setData(value);}).catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};},[path,revision,enabled]);
  return {data,error,loading,setData};
}
export function money(value:number|null|undefined,compact=false){
  if(value==null || !Number.isFinite(value))return '—';
  const currency='INR';
  return new Intl.NumberFormat('en-IN',{style:'currency',currency,maximumFractionDigits:compact?0:2,notation:compact?'compact':'standard'}).format(value);
}
export function num(value:number|null|undefined,digits=2){return value==null || !Number.isFinite(value)?'—':new Intl.NumberFormat('en-IN',{maximumFractionDigits:digits}).format(value);}
export const signed=(value:number|null|undefined)=>value==null?'—':(value>0?'+':'')+money(value);
export const date=(value:string,options:Intl.DateTimeFormatOptions={month:'short',day:'numeric'})=>new Date(value).toLocaleDateString('en-IN',{...options,timeZone:'Asia/Kolkata'});
export const today=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
export const istInput=(value?:string|null)=>new Date(new Date(value||Date.now()).getTime()+19800000).toISOString().slice(0,16);
export function download(name:string,content:string,type='text/plain'){
  const url=URL.createObjectURL(new Blob([content],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();URL.revokeObjectURL(url);
}
export function explain(e:unknown){useStore.getState().notify(e instanceof Error?e.message:String(e));}
