import { lazy,Suspense } from 'react';
import { Routes, Route } from 'react-router-dom';
import { AnchorScrolling } from './AnchorScrolling';
const Landing = lazy(() => import('./Landing'));
const Help = lazy(() => import('./Help'));
const Legal = lazy(() => import('./Legal'));
const ProtectedApp = lazy(() => import('./ProtectedApp'));
export function App(){return <><AnchorScrolling/><Suspense fallback={<div className="initial-loading"><div className="brand-logo">H</div><p>Opening HakiSense…</p></div>}><Routes><Route path="/" element={<Landing/>}/><Route path="/pricing" element={<Landing/>}/><Route path="/help" element={<Help/>}/><Route path="/terms" element={<Legal page="terms"/>}/><Route path="/privacy" element={<Legal page="privacy"/>}/><Route path="/refunds" element={<Legal page="refunds"/>}/><Route path="*" element={<ProtectedApp/>}/></Routes></Suspense></>;}
