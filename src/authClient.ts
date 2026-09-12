import { createClient, type SupabaseClient } from '@supabase/supabase-js';
export type PublicConfig = {supabase_url:string;supabase_publishable_key:string;support_email:string;brand_name:string;password_min_length:number;policies:Record<string,string>};
let clientPromise:Promise<{client:SupabaseClient;config:PublicConfig}>|undefined;
export function authClient(){
  if(!clientPromise)clientPromise=(async()=>{
    const response=await fetch('/api/config');
    if(!response.ok)throw new Error('HakiSense is temporarily unavailable. Please try again.');
    const config:PublicConfig=await response.json();
    const client=createClient(config.supabase_url,config.supabase_publishable_key,{auth:{persistSession:true,autoRefreshToken:true,detectSessionInUrl:true,flowType:'pkce'}});
    return {client,config};
  })().catch(error=>{clientPromise=undefined;throw error;});
  return clientPromise;
}
