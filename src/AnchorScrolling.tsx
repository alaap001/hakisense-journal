import { useEffect, useRef } from 'react';
import { useLocation, useNavigate, useNavigationType } from 'react-router-dom';

/** Smooth only intentional anchor navigation. Route resets and listbox scrolling stay immediate. */
export function AnchorScrolling() {
  const location = useLocation();
  const navigationType = useNavigationType();
  const navigate = useNavigate();
  const initialized = useRef(false);
  const repeatScroll = useRef<(() => void) | null>(null);

  useEffect(() => {
    const wasInitialized = initialized.current;
    initialized.current = true;
    if (!location.hash) { repeatScroll.current = null; return; }
    let id: string;
    try { id = decodeURIComponent(location.hash.slice(1)); } catch { return; }
    if (id === 'how-it-works') id = 'the-process';
    const move = (smooth: boolean) => {
      const target = document.getElementById(id);
      if (!target) return false;
      const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches || document.querySelector('.landing')?.getAttribute('data-motion') === 'off';
      // Native scrolling owns the animation and user interruption; never run an easing loop.
      target.scrollIntoView({ behavior: smooth && !reduced ? 'smooth' : 'instant', block: 'start' });
      const temporaryTabIndex = !target.hasAttribute('tabindex');
      if (temporaryTabIndex) {
        target.setAttribute('tabindex', '-1');
        target.addEventListener('blur', () => target.removeAttribute('tabindex'), { once: true });
      }
      target.focus({ preventScroll: true });
      return true;
    };
    repeatScroll.current = () => { move(true); };
    let observer: MutationObserver | undefined;
    let timeout = 0;
    const frame = requestAnimationFrame(() => {
      if (move(wasInitialized && navigationType !== 'POP')) return;
      // Lazy routes may commit after this effect. Observe only until their target exists.
      observer = new MutationObserver(() => { if (move(wasInitialized && navigationType !== 'POP')) { observer?.disconnect(); clearTimeout(timeout); } });
      observer.observe(document.getElementById('root')!, { childList: true, subtree: true });
      timeout = window.setTimeout(() => observer?.disconnect(), 3000);
    });
    return () => { cancelAnimationFrame(frame); observer?.disconnect(); clearTimeout(timeout); repeatScroll.current = null; };
  }, [location.key, location.hash, navigationType]);

  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.defaultPrevented) return;
      const link = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>('a[href]') : null;
      if (!link || link.hasAttribute('download') || (link.target && link.target !== '_self')) return;
      const url = new URL(link.href, window.location.href);
      if (url.origin !== window.location.origin || url.pathname !== location.pathname || url.search !== location.search || !url.hash) return;
      event.preventDefault();
      if (url.hash === location.hash) repeatScroll.current?.();
      else navigate({ pathname: url.pathname, search: url.search, hash: url.hash });
    };
    document.addEventListener('click', onClick, true);
    return () => document.removeEventListener('click', onClick, true);
  }, [location.pathname, location.search, location.hash, navigate]);
  return null;
}
