import { useEffect, useRef, useState } from 'react';
import type { CSSProperties, PointerEvent } from 'react';
import { ArrowUpRight, BookOpen, Check, MoveHorizontal, Pause, Play, RotateCcw, Sparkles } from 'lucide-react';

const examples = [
  { symbol: 'NIFTY', market: 'Index options', setup: 'Opening range breakout', time: '09:25 IST', result: '+2.4R', positive: true,
    values: [40,44,37,49,46,54,45,40,48,60,55,63,59,73,67,81,77,87,79,91,86,98,91,105],
    notes: ['The first move is not the only move. Waiting for my setup.', 'The retest is forming. Entry only after confirmation.', 'Waited for the retest. Kept the stop where the setup failed.'],
    lesson: 'The entry was patient. Keep that part.' },
  { symbol: 'RELIANCE', market: 'NSE equity', setup: 'Breakout without confirmation', time: '11:10 IST', result: '−1.0R', positive: false,
    values: [70,74,68,82,77,88,82,95,100,91,96,89,97,83,80,86,71,77,68,74,60,65,54,48],
    notes: ['Watching the breakout. My plan says wait for the close.', 'Entered early. The candle has not confirmed the move.', 'Exited at the planned stop. Next time, wait for confirmation.'],
    lesson: 'A losing trade. A risk rule respected.' },
  { symbol: 'BTC', market: 'Crypto', setup: 'Range reclaim', time: '19:40 IST', result: '+1.8R', positive: true,
    values: [80,73,77,63,67,53,61,52,65,72,66,79,74,85,78,91,83,95,89,103,96,108,100,110],
    notes: ['Price is testing the range. Waiting for a reclaim.', 'The reclaim is in. Managing the position to the plan.', 'Scaled out at the midpoint. Left the rest to the plan.'],
    lesson: 'Manage the position before the emotion.' },
];

/** Entirely local, synthetic examples. Controls never call journal or AI endpoints. */
export function HeroExperience({ motionPaused }: { motionPaused: boolean }) {
  const [market, setMarket] = useState(0);
  const [position, setPosition] = useState(17);
  const [playing, setPlaying] = useState(false);
  const [inView, setInView] = useState(true);
  const scene = useRef<HTMLElement>(null);
  const tiltFrame = useRef(0);
  const example = examples[market];
  const phase = position < 8 ? 0 : position < 16 ? 1 : 2;
  const y = (value: number) => 181 - (value - 25) * 1.65;
  const currentX = 12 + position * 20;

  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      setInView(entry.isIntersecting);
      if (!entry.isIntersecting) setPlaying(false);
    });
    if (scene.current) observer.observe(scene.current);
    const stop = () => { if (document.hidden) setPlaying(false); };
    document.addEventListener('visibilitychange', stop);
    return () => { observer.disconnect(); document.removeEventListener('visibilitychange', stop); cancelAnimationFrame(tiltFrame.current); };
  }, []);

  useEffect(() => {
    if (motionPaused) setPlaying(false);
  }, [motionPaused]);

  useEffect(() => {
    if (!playing || !inView || motionPaused) return;
    const timer = window.setInterval(() => setPosition(value => Math.min(23, value + 1)), 380);
    return () => clearInterval(timer);
  }, [playing, inView, motionPaused]);

  useEffect(() => { if (position === 23) setPlaying(false); }, [position]);

  const tilt = (event: PointerEvent<HTMLElement>) => {
    if (motionPaused || event.pointerType !== 'mouse') return;
    const element = event.currentTarget;
    const rect = element.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width - .5;
    const yy = (event.clientY - rect.top) / rect.height - .5;
    cancelAnimationFrame(tiltFrame.current);
    tiltFrame.current = requestAnimationFrame(() => {
      element.style.setProperty('--tilt-x', `${-yy * 5}deg`);
      element.style.setProperty('--tilt-y', `${x * 5}deg`);
      element.style.setProperty('--light-x', `${(x + .5) * 100}%`);
      element.style.setProperty('--light-y', `${(yy + .5) * 100}%`);
    });
  };
  const resetTilt = () => {
    cancelAnimationFrame(tiltFrame.current);
    scene.current?.style.setProperty('--tilt-x', '0deg');
    scene.current?.style.setProperty('--tilt-y', '0deg');
  };
  const chooseMarket = (index: number) => { setMarket(index); setPosition(17); setPlaying(false); };
  const scrub = (value: number) => { setPosition(value); setPlaying(false); };

  return <figure ref={scene} className="hero-scene" onPointerMove={tilt} onPointerLeave={resetTilt}>
    <div className="hero-orbit orbit-one" aria-hidden="true"/><div className="hero-orbit orbit-two" aria-hidden="true"/>
    <div className="scene-parallax"><div className="scene-perspective"><div className="hero-terminal">
      <div className="terminal-masthead"><span><span className="mini-monogram">H</span>THE SESSION, REVISITED</span><span className="terminal-example"><span/>INTERACTIVE EXAMPLE</span></div>
      <div className="terminal-inner">
        <div className="market-selector" role="group" aria-label="Choose a sample trade">{examples.map((item,index) => <button type="button" key={item.symbol} aria-pressed={market === index} onClick={() => chooseMarket(index)}>{item.symbol}</button>)}</div>
        <div className="terminal-instrument" key={example.symbol}><div><span>{example.market} <i/> {example.time}</span><h2>{example.symbol}<small> / JOURNAL</small></h2><p>{example.setup}</p></div><div className={`terminal-result${example.positive ? '' : ' is-loss'}`}><span>FINAL RESULT</span><strong>{example.result}</strong></div></div>
        <div className="hero-candle-chart">
          <div className="chart-readout"><span><span/>REVISIT THE DECISION</span><span>{['The setup', 'The entry', 'The reflection'][phase]}</span></div>
          <svg viewBox="0 0 484 205" preserveAspectRatio="none" role="img" aria-label={`${example.symbol} illustrative chart, candle ${position + 1} of 24 selected. Use the slider to revisit the trade.`}
            onPointerMove={event => { if (event.pointerType !== 'mouse' || playing) return; const rect = event.currentTarget.getBoundingClientRect(); setPosition(Math.max(0, Math.min(23, Math.round(((event.clientX - rect.left) / rect.width * 484 - 12) / 20)))); }}>
            <defs><linearGradient id="hero-chart-wash" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#c5e89e" stopOpacity=".14"/><stop offset="100%" stopColor="#c5e89e" stopOpacity="0"/></linearGradient></defs>
            {[30,75,120,165].map(line => <line key={line} x1="0" x2="484" y1={line} y2={line} className="candle-grid"/>)}
            <path className="candle-area" d={`M 12 190 L ${example.values.slice(0,position + 1).map((v,i)=>`${12+i*20} ${y(v)}`).join(' L ')} L ${currentX} 190 Z`} fill="url(#hero-chart-wash)"/>
            <g key={example.symbol}>{example.values.map((value,index) => {
              const previous = index ? example.values[index - 1] : value - 3;
              const up = value >= previous;
              return <g key={index} className={`hero-candle ${index > position ? 'candle-future' : ''}`} style={{'--candle-delay': `${index * 22}ms`} as CSSProperties}>
                <line x1={12+index*20} x2={12+index*20} y1={y(Math.max(value,previous)+4)} y2={y(Math.min(value,previous)-4)} stroke={up?'#c5e99d':'#d99986'}/>
                <rect x={8+index*20} y={y(Math.max(value,previous))} width="8" height={Math.max(3,Math.abs(value-previous)*1.65)} rx="1" fill={up?'#c5e99d':'#d99986'}/>
              </g>;
            })}</g>
            <line className="candle-crosshair" x1={currentX} x2={currentX} y1="12" y2="190"/>
            <circle className="candle-point" cx={currentX} cy={y(example.values[position])} r="4"/>
            <text x="0" y="203">SETUP</text><text x="219" y="203">EXECUTION</text><text x="425" y="203">REVIEW</text>
          </svg>
          <div className="hero-chart-controls"><button type="button" className="hero-play" aria-label={playing?'Pause sample trade replay':motionPaused?'Advance sample trade replay':'Play sample trade replay'} onClick={() => { if(motionPaused) {scrub(position===23?0:position+1);return;} if(!playing&&position===23)setPosition(0); setPlaying(value=>!value); }}>{playing?<Pause size={15}/>:<Play size={15}/>}</button><label><span className="sr-only">Explore sample trade candles</span><input type="range" min="0" max="23" value={position} aria-valuetext={`Candle ${position + 1} of 24: ${['setup','entry','reflection'][phase]}`} onChange={event=>scrub(Number(event.target.value))}/></label><span className="candle-counter">{String(position+1).padStart(2,'0')} / 24</span><button type="button" className="hero-reset" aria-label="Reset hero replay" onClick={()=>scrub(0)}><RotateCcw size={14}/></button></div>
          <div className="chart-instruction"><MoveHorizontal size={13}/>Hover the chart or drag to revisit the trade</div>
        </div>
        <div className="terminal-note"><BookOpen size={17}/><div><span>YOUR POST-TRADE NOTE</span><p key={`${market}-${phase}`}>{example.notes[phase]}</p></div></div>
      </div>
      <div className="terminal-status"><span><Check size={13}/>Context captured</span><span>Your process, in focus <ArrowUpRight size={13}/></span></div>
    </div></div></div>
    <div className="hero-takeaway"><span className="takeaway-symbol"><Sparkles size={19}/></span><div><span>THE LESSON TO TAKE FORWARD</span><p key={market}>{example.lesson}</p></div></div>
    <figcaption><span className="scene-caption-mark">↗</span><span>REFLECT. REFINE. REPEAT.</span><span>Synthetic examples · No live data</span></figcaption>
  </figure>;
}
