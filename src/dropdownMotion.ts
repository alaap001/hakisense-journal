import { useLayoutEffect, useState } from 'react';

/** Keep the noninteractive closing surface for 140ms, then remove its portal. */
export function useDropdownPresence(open: boolean) {
  const [retained, setRetained] = useState(open);
  useLayoutEffect(() => {
    if (open) { setRetained(true); return; }
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { setRetained(false); return; }
    const timer = window.setTimeout(() => setRetained(false), 140);
    return () => clearTimeout(timer);
  }, [open]);
  return { present: open || retained, phase: open ? 'open' : 'closing' };
}

/** Never scroll the document or other ancestors to reveal a listbox option. */
export function revealDropdownOption(menu: HTMLElement | null, index: number) {
  const list = menu?.querySelector<HTMLElement>('.select-options');
  const option = list?.querySelector<HTMLElement>(`[data-index="${index}"]`);
  if (!list || !option) return;
  const item = option.getBoundingClientRect();
  const bounds = list.getBoundingClientRect();
  if (item.top < bounds.top) list.scrollTop -= bounds.top - item.top;
  else if (item.bottom > bounds.bottom) list.scrollTop += item.bottom - bounds.bottom;
}
