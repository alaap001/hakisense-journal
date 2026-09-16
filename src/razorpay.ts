export type RazorpayPayment = {
  razorpay_payment_id:string;
  razorpay_order_id:string;
  razorpay_signature:string;
};

export type CheckoutOrder = {
  order_id:string; amount:number; currency:string; key_id:string; name:string; description:string;
};

type CheckoutOptions = CheckoutOrder & {
  key:string;
  handler:(payment:RazorpayPayment)=>void;
  modal:{ondismiss:()=>void};
  retry:{enabled:boolean};
};
type CheckoutInstance = {
  open:()=>void;
  close:()=>void;
  on:(event:'payment.failed',callback:(response:{error?:{description?:string}})=>void)=>void;
};
declare global {
  interface Window { Razorpay?:new(options:CheckoutOptions)=>CheckoutInstance }
}

let loading:Promise<void>|undefined;
export function loadRazorpay():Promise<void>{
  if(window.Razorpay)return Promise.resolve();
  if(loading)return loading;
  loading=new Promise<void>((resolve,reject)=>{
    const script=document.createElement('script');
    const fail=()=>{clearTimeout(timer);script.remove();reject(new Error('Razorpay checkout could not load. Check your connection and try again.'));};
    const timer=window.setTimeout(fail,20000);
    script.src='https://checkout.razorpay.com/v1/checkout.js';
    script.async=true;
    script.onload=()=>{if(!window.Razorpay){fail();return;}clearTimeout(timer);resolve();};
    script.onerror=fail;
    document.head.appendChild(script);
  }).catch(error=>{loading=undefined;throw error;});
  return loading;
}

export async function openCheckout(order:CheckoutOrder):Promise<RazorpayPayment|null>{
  await loadRazorpay();
  return new Promise((resolve,reject)=>{
    let completed=false;
    const checkout=new window.Razorpay!({...order,key:order.key_id,retry:{enabled:false},
      handler:payment=>{if(!completed){completed=true;resolve(payment);}},
      modal:{ondismiss:()=>{if(!completed){completed=true;resolve(null);}}}});
    checkout.on('payment.failed',response=>{
      if(completed)return;
      completed=true;
      checkout.close();
      reject(new Error(response.error?.description||'Payment failed. You can retry your pending recharge.'));
    });
    checkout.open();
  });
}
