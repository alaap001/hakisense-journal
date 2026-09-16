import { Link } from 'react-router-dom';
import { ArrowRight, Check, Coins, Sparkles, Zap } from 'lucide-react';
import type { Catalog } from './types';
import './pricing.css';

const inr=(paise:number)=>new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:paise%100?2:0}).format(paise/100);
const number=(value:number)=>new Intl.NumberFormat('en-IN').format(value);
export function Pricing({catalog,introEligible=true,busy='',onRecharge,headingLevel=2}:{catalog:Catalog;introEligible?:boolean;busy?:string;onRecharge?:(code:string)=>void;headingLevel?:1|2}){
  const Heading=headingLevel===1?'h1':'h2';
  const regularPacks=catalog.packs.filter(pack=>!pack.first_purchase_only);
  // A first-purchase price for the same credits belongs on the regular pack's card.
  const displayedPacks=catalog.packs.filter(pack=>!pack.first_purchase_only||!regularPacks.some(regular=>regular.credits===pack.credits&&regular.amount_paise>pack.amount_paise));
  return <section className="plans-section recharge-section" id="plans" aria-labelledby="plans-title">
    <div className="plans-intro"><div><span className="section-kicker">YOUR JOURNAL. YOUR PACE.</span><Heading id="plans-title">Recharge your curiosity.<br/><span>Keep the commitment small.</span></Heading><p>All the tools are yours. Add credits when you want an AI perspective. No subscription, no automatic renewal.</p></div><div className="payg-promise"><Coins size={24}/><strong>{number(catalog.monthly_free_credits)} free credits / month</strong><span>Unlimited trade entries. No card needed.</span></div></div>
    <div className="recharge-grid">{displayedPacks.map(pack=>{
      const offer=introEligible&&!pack.first_purchase_only?catalog.packs.find(candidate=>candidate.first_purchase_only&&candidate.credits===pack.credits&&candidate.amount_paise<pack.amount_paise):undefined;
      const checkoutPack=offer||pack;
      const intro=checkoutPack.first_purchase_only, unavailable=intro&&!introEligible;
      const reference=offer?pack.amount_paise:pack.reference_amount_paise;
      const discount=offer?Math.round((1-offer.amount_paise/pack.amount_paise)*1000)/10:pack.discount_percent;
      const featured=pack.value_multiple>=8, value=pack.value_multiple>=3&&!intro;
      const label=unavailable?'First recharge already used':busy===checkoutPack.code?'Opening checkout…':onRecharge&&!checkoutPack.checkout_available?'Recharges coming soon':'Get '+number(pack.credits)+' credits';
      return <article key={pack.code} className={`plan-offer ${featured?'offer-advanced':value?'offer-pro':'offer-free'} ${unavailable?'offer-used':''}`}>
        <div className="offer-eyebrow"><span>{intro?'A LITTLE NUDGE TO START':featured?'MORE QUESTIONS. MORE ROOM.':value?'MAKE REVIEW A HABIT':'KEEP IT LIGHT'}</span>{featured?<Sparkles size={17}/>:<Zap size={17}/>}</div>
        <div className="offer-name"><h3>{pack.name}</h3>{intro?<span className="offer-tag">First recharge offer</span>:pack.value_multiple>1&&<span className="offer-tag">{pack.value_multiple}× value</span>}</div>
        <div className="offer-price-block">
          <div className="offer-discount">{discount>0?<><strong>Save {inr(reference-checkoutPack.amount_paise)}</strong><span>{discount}% off</span></>:<strong>Standard recharge</strong>}</div>
          <div className="offer-price">{discount>0&&<s aria-label={`${offer?'Regular price':'Value at standard credit rate'} ${inr(reference)}`}>{inr(reference)}</s>}<strong>{inr(checkoutPack.amount_paise)}</strong></div>
          <div className="offer-price-caption">{intro?'For your first recharge':'One-time payment'}</div>
          <p className="offer-equivalent">{offer?<><strong>{inr(pack.amount_paise)} thereafter.</strong> One offer per account.</>:intro?'First purchase only · one per account':`${inr(pack.amount_paise/pack.credits)} per credit`}</p>
        </div>
        <div className="offer-credits"><Coins size={24}/><div><strong>{number(pack.credits)}</strong> credits<span>Yours until you use them</span></div></div>
        {onRecharge?<button type="button" className="offer-cta" disabled={!!busy||unavailable||!checkoutPack.checkout_available} onClick={()=>onRecharge(checkoutPack.code)}>{label}<ArrowRight size={16}/></button>:<Link className="offer-cta" to={'/signup?pack='+encodeURIComponent(checkoutPack.code)}>{label}<ArrowRight size={16}/></Link>}
        <div className="offer-rule"/><ul className="offer-features"><li><Check size={16}/><span>Every existing journal feature unlocked</span></li><li><Check size={16}/><span>Standard & Advanced AI available</span></li><li><Check size={16}/><span>Pay only for the AI you use</span></li><li><Check size={16}/><span>Purchased credits never expire</span></li></ul>
      </article>;
    })}</div>
    <div className="payg-included"><div><span className="section-kicker">THE TOOLS ARE ALREADY YOURS</span><h3>Build your process without a paywall.</h3></div><div>{Object.entries(catalog.features).map(([key,name])=><span key={key}><Check size={15}/>{name}{key==='playbooks'?` · ${catalog.playbook_creation_credits} credit${catalog.playbook_creation_credits===1?'':'s'} to create`:''}</span>)}</div></div>
    <div className="plans-fineprint"><span><Check size={15}/>Trading entries are always free</span><span><Check size={15}/>Failed AI tasks are refunded</span><span><Check size={15}/>No recurring payments</span></div>
    <p className="plans-terms">{catalog.tax_policy} Discounts and value compare against a standard reference rate of {inr(catalog.reference_credit_paise)} per credit. {catalog.credit_policy} AI reviews cost 1–7 credits depending on the work needed. Standard and Advanced follow the same pricing. Unused credits are returned. Deep Researched Stock Analysis is coming soon and is not available yet.</p>
  </section>;
}
