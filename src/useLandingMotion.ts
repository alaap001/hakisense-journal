import { useEffect, useState } from 'react';
import type { RefObject } from 'react';

/** Progressive enhancement: normal document flow and fully visible content without motion. */
export function useLandingMotion(root: RefObject<HTMLDivElement | null>, route: string) {
  const [systemReduced, setSystemReduced] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const [userPaused, setUserPaused] = useState(false);
  const paused = systemReduced || userPaused;

  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setSystemReduced(query.matches);
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);

  useEffect(() => {
    const element = root.current;
    if (!element) return;
    element.dataset.motion = paused ? 'off' : 'on';
    if (paused) return;

    const selector = '.chapter-copy, .entry-example, .analysis-example, .ai-heading, .ai-prompts, .ai-response, .section-heading, .practice-card, .india-heading, .india-grid article, .free-card, .faq-section > div, .closing-section .landing-container';
    const targets = [...element.querySelectorAll<HTMLElement>(selector)];
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('has-entered');
        observer.unobserve(entry.target);
      });
    }, { threshold: 0, rootMargin: '0px 0px -36px 0px' });
    targets.forEach(target => {
      if (target.getBoundingClientRect().top < innerHeight - 36) { target.classList.add('has-entered'); return; }
      target.classList.add('scroll-reveal');
      observer.observe(target);
    });
    const revealFocused = (event: FocusEvent) => {
      if (event.target instanceof Element) event.target.closest('.scroll-reveal')?.classList.add('has-entered');
    };
    element.addEventListener('focusin', revealFocused);
    return () => { observer.disconnect(); element.removeEventListener('focusin', revealFocused); };
  }, [root, route, paused]);

  useEffect(() => {
    const element = root.current;
    if (!element) return;
    let frame = 0;
    const finePointer = window.matchMedia('(pointer: fine) and (min-width: 851px)');
    const hero = element.querySelector<HTMLElement>('.landing-hero');
    const chapters = [...element.querySelectorAll<HTMLElement>('[data-story-chapter]')];
    const links = [...element.querySelectorAll<HTMLElement>('[data-story-link]')];
    const update = () => {
      frame = 0;
      const range = document.documentElement.scrollHeight - innerHeight;
      element.style.setProperty('--reading-progress', String(range > 0 ? Math.min(1, Math.max(0, scrollY / range)) : 0));
      if (hero) {
        const rect = hero.getBoundingClientRect();
        // Read geometry before writes. Only the hero needs per-frame parallax.
        const progress = Math.max(0, Math.min(1, -rect.top / rect.height));
        element.style.setProperty('--hero-drift', `${!paused && finePointer.matches ? progress * 65 : 0}px`);
        element.style.setProperty('--orbit-drift', `${!paused && finePointer.matches ? progress * -100 : 0}px`);
      }
      let current = '';
      for (const chapter of chapters) {
        if (chapter.getBoundingClientRect().top <= innerHeight * .48) current = chapter.id;
      }
      links.forEach(link => {
        const active = link.dataset.storyLink === current;
        link.classList.toggle('is-current', active);
        if (active) link.setAttribute('aria-current', 'location'); else link.removeAttribute('aria-current');
      });
    };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(update); };
    const resize = new ResizeObserver(schedule);
    resize.observe(element);
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule, { passive: true });
    update();
    return () => { cancelAnimationFrame(frame); resize.disconnect(); window.removeEventListener('scroll', schedule); window.removeEventListener('resize', schedule); };
  }, [root, route, paused]);

  return { paused, systemReduced, toggleMotion: () => setUserPaused(value => !value) };
}
