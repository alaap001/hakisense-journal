import { useEffect, useRef, useState } from 'react';
import { BrowserRouter } from 'react-router-dom';
import { AnchorScrolling } from '../../src/AnchorScrolling';
import { createRoot } from 'react-dom/client';
import { Select } from '../../src/Select';
import { SuggestInput } from '../../src/SuggestInput';
import '../../src/styles.css';
import '../../src/motion.css';

// Synthetic, local controls only. No authentication, backend or customer data.
function Preview() {
  const [value,setValue]=useState('35');
  const [samples,setSamples]=useState<number[]>([]);
  useEffect(()=>{const record=()=>setSamples(values=>[...values.slice(-119),Math.round(window.scrollY)]);window.addEventListener('scroll',record,{passive:true});return()=>window.removeEventListener('scroll',record);},[]);
  const dialog=useRef<HTMLDialogElement>(null);
  const options=Array.from({length:40},(_,i)=>`Example ${String(i+1).padStart(2,'0')}`);
  return <><AnchorScrolling/><aside style={{position:'fixed',bottom:10,left:10,right:10,zIndex:4000,background:'#eff3e8',border:'1px solid #cad6bc',padding:8,height:80,overflow:'auto'}}><button type="button" onClick={()=>setSamples([])}>Reset scroll measurements</button> <a href="#fixture-top">Scroll to top</a> · <a href="#fixture-bottom">Scroll to bottom</a><output aria-label="Scroll samples" style={{display:'block',whiteSpace:'nowrap'}}>{JSON.stringify(samples)}</output></aside><main id="fixture-top" style={{maxWidth:680,margin:'0 auto',padding:'36px 24px'}}><h1>Shared dropdown motion</h1><p>Local verification fixture. Scroll to the controls, use the keyboard, and confirm the page stays still.</p><div style={{height:650}}/><section style={{padding:24,border:'1px solid #dce3d5',borderRadius:12,background:'white'}}><label className="field"><span>Long option list</span><Select aria-label="Long option list" value={value} onChange={event=>setValue(event.target.value)}>{options.map((label,index)=><option key={label} value={String(index+1)}>{label}</option>)}</Select></label><p role="status">Selected: {value}</p><label className="field" style={{marginTop:24}}><span>Known setups</span><SuggestInput aria-label="Known setups" options={options}/></label><button type="button" style={{marginTop:24}} onClick={()=>dialog.current?.showModal()}>Open dialog</button></section><div style={{height:650}}/><h2 id="fixture-bottom">Bottom anchor</h2><dialog ref={dialog} style={{padding:32,border:'1px solid #dce3d5',borderRadius:12}}><h2>Dialog dropdown</h2><Select aria-label="Dialog options" value={value} onChange={event=>setValue(event.target.value)}>{options.map((label,index)=><option key={label} value={String(index+1)}>{label}</option>)}</Select><button type="button" onClick={()=>dialog.current?.close()} style={{marginLeft:16}}>Close dialog</button></dialog></main></>;
}
createRoot(document.getElementById('root')!).render(<BrowserRouter><Preview/></BrowserRouter>);
