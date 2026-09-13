import { lazy,Suspense } from 'react';
import { Routes, Route } from 'react-router-dom';
const Landing = lazy(() => import('./Landing'));
const Help = lazy(() => import('./Help'));
const ProtectedApp = lazy(() => import('./ProtectedApp'));
export function App(){return <Suspense fallback={<div className="initial-loading"><div className="brand-logo">H</div><p>Opening HakiSense…</p></div>}><Routes><Route path="/" element={<Landing/>}/><Route path="/pricing" element={<Landing/>}/><Route path="/help" element={<Help/>}/><Route path="*" element={<ProtectedApp/>}/></Routes></Suspense>;}
