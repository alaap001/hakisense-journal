import { authClient } from './authClient';
import { useStore, today } from './lib';

export type Preferences = {
  currency:'INR'; timezone:'Asia/Kolkata'; language:'en';
  landing_page:string; default_account_id:string|null; date_range:'all'|'7'|'30'|'90'|'365';
  reduce_motion:boolean; compact_tables:boolean;
};
export const defaultPreferences:Preferences = {
  currency:'INR', timezone:'Asia/Kolkata', language:'en', landing_page:'/overview',
  default_account_id:null, date_range:'all', reduce_motion:false, compact_tables:false,
};
export const landingPages = [['/overview','Overview'],['/trades','Trade journal'],['/calendar','Calendar'],['/analytics','Analytics'],['/notebook','Notebook']];
export function dateScope(range:string){
  if(range==='all')return {start:'',end:''};
  const start=new Date();start.setUTCDate(start.getUTCDate()-Number(range));
  return {start:new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit',day:'2-digit'}).format(start),end:today()};
}
export async function signOut(scope:'local'|'global'|'others'='local'){
  const {client}=await authClient();
  const {error}=await client.auth.signOut({scope});
  if(error)throw error;
  if(scope!=='others'){
    useStore.getState().reset();
    // A full navigation also discards component-local journal and conversation state.
    window.location.replace('/login');
  }
}
