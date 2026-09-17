import { Children, Fragment, isValidElement, useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import type { ReactNode, SelectHTMLAttributes, KeyboardEvent } from 'react';
import { createPortal } from 'react-dom';
import { Check, ChevronDown, Search } from 'lucide-react';
import './select.css';
import { useDropdownPresence, revealDropdownOption } from './dropdownMotion';

type Option = { value: string; label: string; disabled: boolean };
function plain(node: ReactNode): string {
  return Children.toArray(node).map(child => isValidElement<{children?:ReactNode}>(child) ? plain(child.props.children) : String(child)).join('');
}
function optionsFrom(children: ReactNode): Option[] {
  return Children.toArray(children).flatMap(child => {
    if (!isValidElement<{children?:ReactNode;value?:string|number;disabled?:boolean;label?:string}>(child)) return [];
    if (child.type === Fragment) return optionsFrom(child.props.children);
    if (child.type === 'optgroup') return optionsFrom(child.props.children).map(o => ({...o, disabled: o.disabled || !!child.props.disabled}));
    if (child.type !== 'option') return [];
    const label = child.props.label || plain(child.props.children);
    return [{value: String(child.props.value ?? label), label, disabled: !!child.props.disabled}];
  });
}

/** A themed listbox with a real select underneath for FormData, validation and change events. */
export function Select({children, value, defaultValue, onChange, className = '', id, disabled, ...props}: SelectHTMLAttributes<HTMLSelectElement>) {
  const uid = useId(), triggerId = id || `select-${uid}`, listId = `${triggerId}-list`;
  const native = useRef<HTMLSelectElement>(null), trigger = useRef<HTMLButtonElement>(null), menu = useRef<HTMLDivElement>(null), search = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false), [query, setQuery] = useState(''), [active, setActive] = useState(0);
  const {present, phase} = useDropdownPresence(open);
  const [internal, setInternal] = useState(String(defaultValue ?? '')), [labelledBy, setLabelledBy] = useState(props['aria-labelledby']);
  const [position, setPosition] = useState({left: 0, top: 0, width: 240, maxHeight: 320, transformOrigin: 'top'});
  const options = optionsFrom(children), selectedValue = String(value ?? internal);
  const selected = options.find(o => o.value === selectedValue) || options.find(o => !o.disabled);
  const filtered = options.filter(o => o.label.toLocaleLowerCase().includes(query.toLocaleLowerCase()));
  const searchable = options.length > 8;
  const close = (focus = false) => {setOpen(false); if (focus) trigger.current?.focus({preventScroll:true});};
  useEffect(() => {
    const label = trigger.current?.closest('label')?.querySelector('span');
    if (!props['aria-label'] && !props['aria-labelledby'] && label) {if (!label.id) label.id = `${triggerId}-label`; setLabelledBy(label.id);}
    const form = native.current?.form;
    const reset = () => {setInternal(String(defaultValue ?? '')); close();};
    form?.addEventListener('reset', reset);
    return () => form?.removeEventListener('reset', reset);
  }, [defaultValue, triggerId, props['aria-label'], props['aria-labelledby']]);
  useLayoutEffect(() => {
    if (!open || !present || !trigger.current) return;
    const rect = trigger.current.getBoundingClientRect(), below = window.innerHeight - rect.bottom - 12;
    const height = Math.min(340, (filtered.length || 1) * 39 + (searchable ? 56 : 16));
    const above = below < Math.min(height, 190) && rect.top > below;
    const maxHeight = Math.max(80, Math.min(340, above ? rect.top - 12 : below));
    const width = Math.min(Math.max(rect.width, searchable ? 300 : 240), window.innerWidth - 24);
    setPosition({left: Math.max(12, Math.min(rect.left, window.innerWidth - width - 12)), top: above ? Math.max(12, rect.top - Math.min(height, maxHeight) - 6) : rect.bottom + 6, width, maxHeight, transformOrigin: above ? 'bottom' : 'top'});
    const el = menu.current;
    if (el?.showPopover && !el.matches(':popover-open')) el.showPopover();
    search.current?.focus({preventScroll:true});
  }, [open, present]);
  useEffect(() => {
    if (!open) return;
    const outside = (e: PointerEvent) => {if (!menu.current?.contains(e.target as Node) && !trigger.current?.contains(e.target as Node)) close();};
    const reposition = (e: Event) => {if (!menu.current?.contains(e.target as Node)) close();};
    document.addEventListener('pointerdown', outside); window.addEventListener('resize', reposition); window.addEventListener('scroll', reposition, true);
    return () => {document.removeEventListener('pointerdown', outside); window.removeEventListener('resize', reposition); window.removeEventListener('scroll', reposition, true);};
  }, [open]);
  useEffect(() => {if (open) revealDropdownOption(menu.current, active);}, [active, open]);
  function choose(option?: Option) {
    if (!option || option.disabled || !native.current) return;
    native.current.value = option.value;
    native.current.dispatchEvent(new Event('change', {bubbles: true}));
    close(true);
  }
  function show() {setQuery(''); setActive(Math.max(0, options.findIndex(o => o.value === selected?.value))); setOpen(true);}
  function keys(e: KeyboardEvent<HTMLElement>) {
    if (e.key === 'Escape' && open) {e.preventDefault(); e.stopPropagation(); close(true); return;}
    if (e.key === 'Tab') {if (e.target === search.current) trigger.current?.focus({preventScroll:true}); close(); return;}
    if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(e.key)) {
      e.preventDefault();
      if (!open) {show(); return;}
      const direction = e.key === 'ArrowUp' || e.key === 'End' ? -1 : 1;
      let next = e.key === 'Home' ? -1 : e.key === 'End' ? filtered.length : active;
      for (let i = 0; i < filtered.length; i++) {next = (next + direction + filtered.length) % filtered.length; if (!filtered[next].disabled) break;}
      setActive(next); return;
    }
    if (e.key === 'Enter' || (e.key === ' ' && e.target !== search.current)) {e.preventDefault(); open ? choose(filtered[active]) : show(); return;}
    if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && e.target !== search.current) {
      e.preventDefault(); if (!open) show();
      const next = options.findIndex((o, i) => i > active && !o.disabled && o.label.toLowerCase().startsWith(e.key.toLowerCase()));
      setActive(next < 0 ? Math.max(0, options.findIndex(o => !o.disabled && o.label.toLowerCase().startsWith(e.key.toLowerCase()))) : next);
    }
  }
  return <span className={`themed-select ${className}`}>
    <select {...props} ref={native} id={`${triggerId}-native`} disabled={disabled} value={value} defaultValue={defaultValue} tabIndex={-1} aria-hidden="true" className="select-native" onInvalid={e => {e.preventDefault(); trigger.current?.focus({preventScroll:true}); show();}} onChange={e => {setInternal(e.target.value); onChange?.(e);}}>{children}</select>
    <button ref={trigger} id={triggerId} type="button" role="combobox" aria-label={props['aria-label'] || (!labelledBy ? selected?.label || 'Select an option' : undefined)} aria-labelledby={labelledBy} aria-expanded={open} aria-controls={open ? listId : undefined} aria-haspopup="listbox" aria-activedescendant={open && filtered[active] ? `${listId}-${active}` : undefined} aria-required={props.required} disabled={disabled} className="select-trigger" onKeyDown={keys} onClick={() => open ? close() : show()}><span>{selected?.label || 'Choose an option'}</span><ChevronDown size={15}/></button>
    {present && createPortal(<div ref={menu} data-phase={phase} inert={!open} aria-hidden={!open} popover="manual" className="select-menu" style={position} onKeyDown={keys}>
      {searchable && <div className="select-search"><Search size={15}/><input ref={search} aria-label="Search options" role="combobox" aria-expanded="true" aria-controls={listId} aria-activedescendant={filtered[active] ? `${listId}-${active}` : undefined} autoComplete="off" placeholder="Search options…" value={query} onChange={e => {setQuery(e.target.value); setActive(0);}}/></div>}
      <div id={listId} role="listbox" aria-label={props['aria-label'] || 'Options'} className="select-options">{filtered.map((option, i) => <div key={option.value} id={`${listId}-${i}`} role="option" aria-selected={option.value === selected?.value} aria-disabled={option.disabled} data-index={i} className={`select-option ${i === active ? 'focused' : ''}`} onPointerMove={() => setActive(i)} onPointerDown={e => e.preventDefault()} onClick={() => choose(option)}><span>{option.label}</span>{option.value === selected?.value && <Check size={15}/>}</div>)}{!filtered.length && <p className="select-no-results">No matching options</p>}</div>
    </div>, trigger.current?.closest('dialog') || document.body)}
  </span>;
}
