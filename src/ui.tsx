import { useEffect, useRef } from 'react';
import type { ReactNode, ButtonHTMLAttributes } from 'react';
import { X, LoaderCircle, ArrowUpRight, Inbox, AlertCircle, ChevronDown } from 'lucide-react';
import { num, money } from './lib';

export function Button({children,variant='default',className='',...props}:ButtonHTMLAttributes<HTMLButtonElement>&{variant?:'default'|'primary'|'ghost'|'danger'}){
  return <button className={`button ${variant} ${className}`} {...props}>{children}</button>;
}
export function IconButton({children,label,...props}:ButtonHTMLAttributes<HTMLButtonElement>&{label:string}){return <button className="icon-button" aria-label={label} title={label} {...props}>{children}</button>;}
export function Panel({children,className='',title,aside}: {children:ReactNode;className?:string;title?:string;aside?:ReactNode}){return <section className={`panel ${className}`}>{title&&<div className="panel-heading"><h3>{title}</h3>{aside}</div>}{children}</section>;}
export function PageTitle({eyebrow,title,description,actions}:{eyebrow?:string;title:string;description?:string;actions?:ReactNode}){return <div className="page-title"><div>{eyebrow&&<p className="eyebrow">{eyebrow}</p>}<h1>{title}</h1>{description&&<p className="muted">{description}</p>}</div><div className="page-actions">{actions}</div></div>;}
export function Empty({title='Nothing here yet',text,action}:{title?:string;text?:string;action?:ReactNode}){return <div className="empty"><Inbox size={32}/><h3>{title}</h3>{text&&<p>{text}</p>}{action}</div>;}
export function Loading(){return <div className="loading"><LoaderCircle className="spin" size={22}/> Loading your workspace…</div>;}
export function ErrorState({message}:{message:string}){return <div className="error-state"><AlertCircle size={20}/><div><strong>Something needs attention</strong><p>{message}</p></div></div>;}
export function Modal({title,children,onClose,wide=false}:{title:string;children:ReactNode;onClose:()=>void;wide?:boolean}){
  const ref=useRef<HTMLDialogElement>(null);
  useEffect(()=>{ref.current?.showModal();const el=ref.current;return()=>el?.close();},[]);
  return <dialog ref={ref} className={`modal ${wide?'wide':''}`} onCancel={onClose} onClick={e=>{if(e.target===e.currentTarget)onClose();}}><div className="modal-heading"><h2>{title}</h2><IconButton label="Close dialog" onClick={onClose}><X size={20}/></IconButton></div>{children}</dialog>;
}
export function Field({label,children,hint}:{label:string;children:ReactNode;hint?:string}){return <label className="field"><span>{label}</span>{children}{hint&&<small>{hint}</small>}</label>;}
export function Badge({children,tone='neutral'}:{children:ReactNode;tone?:string}){return <span className={`badge ${tone}`}>{children}</span>;}
export function Metric({label,value,hint,positive,children}:{label:string;value:ReactNode;hint?:ReactNode;positive?:boolean;children?:ReactNode}){return <div className="metric-card"><div className="metric-label">{label}<ArrowUpRight size={15}/></div><div className={`metric-value ${positive===true?'positive':positive===false?'negative':''}`}>{value}</div><div className="metric-bottom"><span>{hint}</span>{children}</div></div>;}
export function Progress({value,color}:{value:number;color?:string}){return <div className="progress"><div style={{width:`${Math.max(0,Math.min(100,value))}%`,background:color}}/></div>;}
export function Sparkline({values,color='#729b46'}:{values:number[];color?:string}){
  if(!values.length)return null;
  const min=Math.min(...values),range=Math.max(...values)-min||1;
  const pts=values.map((v,i)=>`${i/(values.length-1||1)*92},${29-(v-min)/range*26}`).join(' ');
  return <svg width="94" height="32" viewBox="0 0 94 32" aria-hidden="true"><polyline points={pts} fill="none" stroke={color} strokeWidth="1.7"/></svg>;
}
export const Pnl=({value}:{value:number|null|undefined})=><span className={`pnl ${(value||0)>0?'positive':(value||0)<0?'negative':''}`}>{money(value)}</span>;
