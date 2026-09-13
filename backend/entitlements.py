from datetime import datetime, timezone
from sqlalchemy import select
from fastapi import HTTPException
from .db import Profile, AITask, Account, Setting, serialize
from .markets import month_key, IST
from .config import config
from .catalog import FEATURE_NAMES, UPCOMING_FEATURE_NAMES


def upsert_ignore(db, model, values, keys):
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    insert = pg_insert if db.bind.dialect.name == 'postgresql' else sqlite_insert
    db.execute(insert(model).values(**values).on_conflict_do_nothing(index_elements=keys))


def provision(db, name='Trader'):
    user = db.info['user_id']
    upsert_ignore(db, Profile, {'user_id': user, 'display_name': name[:100] or 'Trader'}, ['user_id'])
    # Serializes onboarding and money/allowance changes for a user, across API processes.
    profile = db.scalar(select(Profile).where(Profile.user_id == user).with_for_update())
    if not db.get(Setting, (user,'preferences')):
        if not db.scalar(select(Account.id).where(Account.user_id==user).limit(1)):
            db.add(Account(user_id=user,name='My trading account',broker='Other / manual',currency='INR',initial_balance=0))
        db.add(Setting(user_id=user, key='preferences', value={'currency': 'INR', 'timezone': 'Asia/Kolkata'}))
        db.flush()
    return profile


def lock_user(db):
    profile = db.scalar(select(Profile).where(Profile.user_id == db.info['user_id']).with_for_update())
    if not profile:
        return provision(db)
    return profile


def aware(dt):
    return dt.replace(tzinfo=dt.tzinfo or timezone.utc) if dt else None


def consume_trades(db, count):
    # Every account has unlimited free journal entries; no wallet mutation is needed.
    lock_user(db)


def require_feature(db, feature):
    if feature not in FEATURE_NAMES:
        raise HTTPException(403, 'This feature is unavailable.')


def snapshot(db):
    from sqlalchemy import func
    from .db import Trade
    from .runtime_settings import settings
    from .wallet import get_wallet, intro_eligible
    product = settings(db)
    row = get_wallet(db)
    year, month = map(int, row.free_month.split('-'))
    start = datetime(year, month, 1, tzinfo=IST)
    reset = datetime(year + (month == 12), 1 if month == 12 else month + 1, 1, tzinfo=IST)
    return {'billing_model':'pay_as_you_go', 'label':'Pay as you go',
        'credits':{'remaining':max(0,row.balance), 'allowance':row.free_allocation+max(0,row.purchased_balance),
            'free_remaining':row.free_balance, 'purchased_remaining':max(0,row.purchased_balance),
            'debt':max(0,-row.balance), 'purchased_debt':max(0,-row.purchased_balance),
            'used':row.spent, 'period':row.free_month, 'resets_at':reset.isoformat(), 'revision':row.revision},
        'trades':{'used':db.scalar(select(func.count()).select_from(Trade).where(Trade.created_at>=start,Trade.is_demo.is_(False))), 'limit':None},
        'features':list(FEATURE_NAMES),
        'intro_eligible':intro_eligible(db,row), 'ai_available':bool(config.openrouter_key and product.ai_enabled)}


def public_catalog(db):
    from .runtime_settings import settings, checkout_ready
    product = settings(db)
    from .db import CreditPack
    packs = []
    for pack in db.scalars(select(CreditPack).where(CreditPack.active.is_(True)).order_by(CreditPack.sort_order, CreditPack.code)):
        item = serialize(pack)
        reference = pack.credits * product.reference_credit_paise
        item.update({'checkout_available':checkout_ready(product), 'reference_amount_paise':reference,
            'discount_percent':round(max(0,1-pack.amount_paise/reference)*100,1),
            'value_multiple':round(reference/pack.amount_paise,2)})
        packs.append(item)
    tasks = []
    for task in db.scalars(select(AITask)):
        tasks.append({**serialize(task),'advanced_credits':task.credits*product.advanced_credit_multiplier})
    return {'billing_model':'pay_as_you_go', 'packs':packs, 'tasks':tasks,
        'features':FEATURE_NAMES, 'upcoming_features':UPCOMING_FEATURE_NAMES,
        'monthly_free_credits':product.monthly_free_credits, 'playbook_creation_credits':product.playbook_creation_credits,
        'reference_credit_paise':product.reference_credit_paise,
        'advanced_credit_multiplier':product.advanced_credit_multiplier,
        'brand_name':product.brand_name, 'currency':'INR',
        'credit_policy':'Purchased credits do not expire. Monthly free credits refresh on the first in IST; unused free credits expire. Free credits are spent first. Failed AI tasks are refunded.',
        'tax_policy':'Displayed recharge prices include applicable taxes. One-time payments; no automatic renewal.',
        'legal':{'business_name':product.legal_business_name,'support_email':product.support_email,'privacy':product.privacy_url,'terms':product.terms_url,'refunds':product.refund_url}}
