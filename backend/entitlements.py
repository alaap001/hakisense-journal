from datetime import datetime, timezone
from sqlalchemy import select
from fastapi import HTTPException
from .db import Profile, Plan, Price, AITask, Subscription, Wallet, CreditEntry, Account, Setting, AccessGrant, serialize, uid
from .markets import month_key, IST
from .config import config
from .catalog import FEATURE_NAMES


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
    if not db.get(Subscription, user):
        db.add(Subscription(user_id=user))
        db.add(Account(user_id=user, name='My trading account', broker='Other / manual', currency='INR', initial_balance=0))
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


def available_credits(row):
    # Keep admin credits usable after a downgrade without forgiving prior plan usage.
    base_spent = row.spent - row.bonus_spent
    return max(0, max(0, row.allocation - base_spent) + row.adjustment - row.bonus_spent)


def active_plan(db, at=None):
    sub = db.get(Subscription, db.info['user_id'])
    at = at or datetime.now(timezone.utc)
    code = sub.plan_code if sub and sub.paid_until and aware(sub.paid_until) > at and sub.status not in ('revoked', 'refunded') else 'free'
    grant = db.get(AccessGrant, db.info['user_id'])
    if grant and aware(grant.expires_at) > at:
        code = grant.plan_code
    plan = db.get(Plan, code)
    if not plan:
        raise HTTPException(503, 'Plan configuration is unavailable. Please try again later.')
    return plan


def wallet(db, at=None):
    lock_user(db)
    plan = active_plan(db, at)
    period = month_key(at)
    user = db.info['user_id']
    row = db.get(Wallet, (user, period))
    if row is None:
        row = Wallet(user_id=user, month=period, plan_code=plan.code, allocation=plan.monthly_credits, adjustment=0, bonus_spent=0, balance=plan.monthly_credits, spent=0, trade_count=0)
        db.add(row)
        db.add(CreditEntry(month=period, event_key='grant:' + period, amount=plan.monthly_credits,
                           balance_after=plan.monthly_credits, reason='Monthly credit allowance'))
    elif row.allocation != plan.monthly_credits or row.plan_code != plan.code:
        row.allocation = plan.monthly_credits
        new_balance = available_credits(row)
        difference = new_balance - row.balance
        row.allocation, row.balance, row.plan_code = plan.monthly_credits, new_balance, plan.code
        db.add(CreditEntry(month=period, event_key='adjust:' + uid(), amount=difference, balance_after=new_balance, reason='Plan allowance adjustment'))
    db.flush()
    return row, plan


def consume_trades(db, count):
    if count <= 0:
        return
    row, plan = wallet(db)
    if plan.trade_limit is not None and row.trade_count + count > plan.trade_limit:
        raise HTTPException(402, {'code': 'trade_limit', 'message': f'Your plan includes {plan.trade_limit} new trades this month. {max(0, plan.trade_limit - row.trade_count)} remain.', 'upgrade': True})
    row.trade_count += count


def require_feature(db, feature):
    if feature not in active_plan(db).features:
        raise HTTPException(403, {'code': 'subscription_required', 'feature': feature, 'message': f'{FEATURE_NAMES.get(feature, feature)} is not included in your current plan. View Plan & credits for available options.', 'upgrade': True})


def snapshot(db):
    from .runtime_settings import settings
    product = settings(db)
    row, plan = wallet(db)
    sub = db.get(Subscription, db.info['user_id'])
    year, month = map(int, row.month.split('-'))
    reset = datetime(year + (month == 12), 1 if month == 12 else month + 1, 1, tzinfo=IST)
    grant = db.get(AccessGrant, db.info['user_id'])
    return {'plan': serialize(plan), 'credits': {'remaining': row.balance, 'allowance': max(0,row.allocation + row.adjustment), 'adjustment': row.adjustment, 'used': row.spent,
            'period': row.month, 'resets_at': reset.isoformat()}, 'trades': {'used': row.trade_count, 'limit': plan.trade_limit},
            'subscription': serialize(sub), 'features': plan.features,
            'access_grant': serialize(grant) if grant and aware(grant.expires_at) > datetime.now(timezone.utc) else None,
            'ai_available': bool(config.openrouter_key and product.ai_enabled)}


def public_catalog(db):
    from .runtime_settings import settings, checkout_ready
    product = settings(db)
    prices = []
    for price in db.scalars(select(Price).where(Price.active.is_(True))):
        p = serialize(price)
        p.pop('provider_plan_id', None)
        p['checkout_available'] = bool(checkout_ready(product) and price.provider_plan_id)
        prices.append(p)
    return {'plans': [serialize(p) for p in db.scalars(select(Plan).where(Plan.active.is_(True)))], 'prices': prices,
            'tasks': [serialize(t) for t in db.scalars(select(AITask))], 'features': FEATURE_NAMES,
            'currency': 'INR', 'credit_policy': 'Credits refresh on the first of each month in IST. Unused credits expire. Failed AI tasks are refunded.',
            'tax_policy': 'Displayed subscription prices include applicable taxes.',
            'legal': {'business_name': product.legal_business_name, 'support_email': product.support_email, 'privacy': product.privacy_url, 'terms': product.terms_url, 'refunds': product.refund_url}}
