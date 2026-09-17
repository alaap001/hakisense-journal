import { useId, useLayoutEffect, useRef, useState } from 'react';
import type { InputHTMLAttributes } from 'react';
import { createPortal } from 'react-dom';
import './select.css';
import { useDropdownPresence, revealDropdownOption } from './dropdownMotion';

/** Free text remains valid; the list only helps fill known symbols and setups. */
export function SuggestInput({options,defaultValue,id,...props}:Omit<InputHTMLAttributes<HTMLInputElement>,'value'|'onChange'|'list'> & {options:string[]}) {
  const uid=useId(), listId=`suggest-${uid}`, input=useRef<HTMLInputElement>(null), menu=useRef<HTMLDivElement>(null);
  const [value,setValue]=useState(String(defaultValue||'')), [open,setOpen]=useState(false), [active,setActive]=useState(-1);
  const [position,setPosition]=useState({left:0,top:0,width:240,maxHeight:260,transformOrigin:'top'});
  const matches=[...new Set(options)].filter(o=>o.toLowerCase().includes(value.toLowerCase())).slice(0,100);
  const visible=open&&matches.length>0;
  const lastMatches=useRef(matches);
  if(visible)lastMatches.current=matches;
  const displayedMatches=visible?matches:lastMatches.current;
  const {present,phase}=useDropdownPresence(visible);
  useLayoutEffect(()=>{
    if(!visible||!present||!input.current)return;
    const rect=input.current.getBoundingClientRect(),below=window.innerHeight-rect.bottom-12;
    const above=below<170&&rect.top>below,height=Math.min(260,matches.length*39+40);
    const maxHeight=Math.max(80,Math.min(260,above?rect.top-12:below)),width=Math.min(Math.max(240,rect.width),window.innerWidth-24);
    setPosition({left:Math.max(12,Math.min(rect.left,window.innerWidth-width-12)),top:above?Math.max(12,rect.top-Math.min(height,maxHeight)-6):rect.bottom+6,width,maxHeight,transformOrigin:above?'bottom':'top'});
    const el=menu.current;if(el?.showPopover&&!el.matches(':popover-open'))el.showPopover();
    const close=(e:Event)=>{if(!menu.current?.contains(e.target as Node))setOpen(false);};
    window.addEventListener('scroll',close,true);window.addEventListener('resize',close);
    return()=>{window.removeEventListener('scroll',close,true);window.removeEventListener('resize',close);};
  },[visible,present]);
  useLayoutEffect(()=>{if(active>=0)revealDropdownOption(menu.current,active);},[active]);
  const choose=(v:string)=>{setValue(v);setOpen(false);setActive(-1);input.current?.focus({preventScroll:true});};
  return <span className="suggest-input"><input {...props} id={id} ref={input} role="combobox" aria-autocomplete="list" aria-expanded={visible} aria-controls={visible?listId:undefined} aria-activedescendant={visible&&active>=0?`${listId}-${active}`:undefined} autoComplete="off" value={value} onChange={e=>{setValue(e.target.value);setActive(-1);setOpen(true);}} onFocus={()=>setOpen(true)} onBlur={()=>setOpen(false)} onKeyDown={e=>{
    if(e.key==='Escape'&&visible){e.preventDefault();e.stopPropagation();setOpen(false);}
    if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();setOpen(true);setActive(i=>Math.max(0,Math.min(matches.length-1,i+(e.key==='ArrowDown'?1:-1))));}
    if(e.key==='Enter'&&visible&&matches[active]){e.preventDefault();choose(matches[active]);}
    if(e.key==='Tab')setOpen(false);
  }}/>{present&&createPortal(<div ref={menu} data-phase={phase} inert={!visible} aria-hidden={!visible} popover="manual" className="select-menu suggest-menu" style={position}><div className="suggest-hint">Choose a suggestion or keep typing</div><div className="select-options" role="listbox" id={listId} aria-label="Suggestions">{displayedMatches.map((v,i)=><div key={v} id={`${listId}-${i}`} role="option" aria-selected={i===active} data-index={i} className={`select-option ${i===active?'focused':''}`} onPointerDown={e=>e.preventDefault()} onPointerMove={()=>setActive(i)} onClick={()=>choose(v)}>{v}</div>)}</div></div>,input.current?.closest('dialog')||document.body)}</span>;
}
