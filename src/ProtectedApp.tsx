import { lazy, Suspense } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { AuthBoundary } from './Auth';
import { Loading } from './ui';
const WorkspaceApp = lazy(() => import('./WorkspaceApp'));
export default function ProtectedApp() {
  const {pathname,search} = useLocation();
  const authRoute = ['/login','/signup','/auth/callback','/auth/reset'].includes(pathname);
  return <AuthBoundary>{session => authRoute ? <Navigate to={new URLSearchParams(search).has('pack') ? '/billing' : '/home'} replace/> : <Suspense fallback={<div className="initial-loading"><Loading/></div>}><WorkspaceApp key={session.user.id}/></Suspense>}</AuthBoundary>;
}
