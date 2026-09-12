import { lazy,Suspense } from 'react';
import { AuthBoundary } from './Auth';
import { Loading } from './ui';
const WorkspaceApp=lazy(()=>import('./WorkspaceApp'));
export function App(){return <AuthBoundary>{session=><Suspense fallback={<div className="initial-loading"><Loading/></div>}><WorkspaceApp key={session.user.id}/></Suspense>}</AuthBoundary>;}
