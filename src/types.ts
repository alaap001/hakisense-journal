export type Account = { id: string; name: string; broker: string; currency: string; initial_balance: number; color: string; is_demo: boolean };
export type Trade = {
  exchange: string; segment: string; expiry: string|null; strike: number|null; option_type: string|null; lot_size: number|null;
  id: string; account_id: string; account_name?: string; symbol: string; asset_type: string; side: string; status: string;
  entry_price: number; exit_price: number | null; mark_price: number | null; quantity: number; closed_quantity: number; multiplier: number;
  entry_time: string; exit_time: string | null; commission: number; fees: number; stop_loss: number | null; target_price: number | null;
  risk_amount: number | null; planned_entry: number | null; playbook_id: string | null; playbook_snapshot: Record<string,any>; setup: string; emotion: string; rating: number; notes: string; tags: string[];
  attributes: Record<string, any>; mfe: number | null; mae: number | null; is_demo: boolean; net_pnl: number; gross_pnl: number;
  unrealized_pnl: number | null; r_multiple: number | null; risk: number; hold_minutes: number | null; total_fees: number; pnl_date: string;
};
export type Filters = { account_id: string; start: string; end: string; symbol: string; asset_type: string; side: string; status: string; setup: string; emotion: string; tag: string; outcome: string };
export type MetricMap = Record<string, number | null>;
export type Group = MetricMap & { name: any };
export type Check = { id: string; title: string; sample: number; impact: number; confidence: string; status: string; action: string; trade_ids: string[]; net_pnl: number };
export type Analysis = { metrics: MetricMap; equity: any[]; daily: any[]; groups: Record<string, any[]>; checks: Check[] };
export type Doc = { id: string; kind: string; data: Record<string, any>; created_at: string };
export type CreditPack = {code:string;name:string;credits:number;amount_paise:number;first_purchase_only:boolean;checkout_available:boolean;reference_amount_paise:number;discount_percent:number;value_multiple:number};
export type Catalog = {payment_mode?:'test'|'live'|'unconfigured';test_checkout_admin_only?:boolean;ai_pricing:Pick<AIPricing,'min_credits'|'max_credits'|'description'>;reference_credit_paise:number;billing_model:string;packs:CreditPack[];monthly_free_credits:number;playbook_creation_credits:number;advanced_credit_multiplier:number;brand_name:string;upcoming_features:Record<string,string>;tasks:{code:string;name:string;credits:number;advanced_credits:number;enabled:boolean}[];features:Record<string,string>;credit_policy:string;tax_policy:string;legal:Record<string,string>};
export type Billing = {billing_model:string;intro_eligible:boolean;label:string;credits:{free_remaining:number;purchased_remaining:number;debt:number;purchased_debt:number;revision:number;remaining:number;allowance:number;used:number;period:string;resets_at:string};trades:{used:number;limit:number|null};features:string[];ai_available:boolean;};
export type OnboardingState = {version:number;revision:number;status:'pending'|'in_progress'|'completed'|'skipped'|'not_required';step:string;started_at:string|null;finished_at:string|null};
export type Workspace = {onboarding:OnboardingState;admin_role: 'owner'|'admin'|'support'|null;product:{brand_name:string;announcement:string};accounts:Account[];settings:Record<string,any>;currency:string;timezone:string;user:{id:string;name:string;email:string};billing:Billing;catalog:Catalog;markets:{brokers:{id:string;name:string;markets:string[];connection:string}[];exchanges:string[];segments:string[];symbols:string[]}};

export type AIPricing = {version:string;input_limit:number;output_limit:number;min_credits:number;max_credits:number;buckets:{input_tokens:number;output_tokens:number;credits:number}[];description:string};
export type AIResult = {thread_id:string;answer:string;chart:any;credits:number;job_id:string};
export type AIJob = {cancel_requested:boolean;id:string;status:string;task:string;credits:number;revision:number;event_sequence:number;pause:{kind:string;question:string}|null;result:AIResult|null;error:string|null};
