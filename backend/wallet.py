"""All persistent credit movements use this service within the caller's transaction."""
from sqlalchemy import select
from fastapi import HTTPException
from .db import CreditWallet, WalletEntry, CreditPurchase, utcnow
from .entitlements import lock_user
from .markets import month_key
from .runtime_settings import settings


def entry(db, key):
    return db.scalar(select(WalletEntry).where(WalletEntry.user_id == db.info['user_id'], WalletEntry.event_key == key))


def append(db, row, key, *, free=0, purchased=0, reason, details=None):
    previous = entry(db, key)
    if previous:
        return previous
    if row.free_balance + free < 0:
        raise RuntimeError('Free credit bucket cannot be negative')
    row.free_balance += free
    row.purchased_balance += purchased
    row.balance = row.free_balance + row.purchased_balance
    row.revision += 1
    row.updated_at = utcnow()
    item = WalletEntry(user_id=row.user_id, sequence=row.revision, event_key=key,
        amount=free+purchased, free_delta=free, purchased_delta=purchased,
        balance_after=row.balance, reason=reason, details=details or {})
    db.add(item)
    db.flush()
    return item


def get_wallet(db, at=None):
    lock_user(db)
    user, period = db.info['user_id'], month_key(at)
    row = db.get(CreditWallet, user)
    product = settings(db)
    allowance = product.monthly_free_credits
    if row is None:
        row = CreditWallet(user_id=user, free_month=period, free_allocation=allowance,
            free_balance=0, purchased_balance=0, balance=0, spent=0, revision=0)
        db.add(row)
        db.flush()
        append(db, row, 'free:'+period, free=allowance, reason='Monthly free credits', details={'month':period})
    elif row.free_month != period:
        append(db, row, 'expire:'+row.free_month, free=-row.free_balance,
            reason='Unused monthly free credits expired', details={'month':row.free_month})
        row.free_month, row.free_allocation = period, allowance
        append(db, row, 'free:'+period, free=allowance, reason='Monthly free credits', details={'month':period})
    return row


def spend(db, key, amount, reason, details=None):
    row = get_wallet(db)
    previous = entry(db, key)
    if previous:
        return previous
    if not isinstance(amount, int) or amount < 0:
        raise ValueError('Credit cost must be a nonnegative integer')
    if row.balance < amount:
        raise HTTPException(402, {'code':'insufficient_credits', 'message':f'This action needs {amount} credits. You have {max(0,row.balance)} available. Recharge your wallet to continue.', 'upgrade':True})
    free = min(row.free_balance, amount)
    row.spent += amount
    return append(db, row, key, free=-free, purchased=-(amount-free), reason=reason,
        details={**(details or {}), 'free_month':row.free_month})


def refund_spend(db, original_key, refund_key, reason):
    row = get_wallet(db)
    if entry(db, refund_key):
        return
    original = entry(db, original_key)
    if original:
        free, purchased = -original.free_delta, -original.purchased_delta
        # A failure after rollover restores credits as non-expiring compensation.
        if original.details.get('free_month') != row.free_month:
            purchased += free
            free = 0
        amount = -original.amount
    else:
        raise RuntimeError('Cannot refund a missing wallet reservation')
    row.spent = max(0, row.spent-amount)
    append(db, row, refund_key, free=free, purchased=purchased, reason=reason)


def intro_eligible(db, row=None):
    row = row or get_wallet(db)
    return not row.first_purchase_id and not db.scalar(
        select(CreditPurchase.id).where(CreditPurchase.user_id == row.user_id, CreditPurchase.payment_id.is_not(None)).limit(1))


def settle_reservations(db, job_id, charged, *, failed=False):
    """Capture once; release unused holds to their original source, never mint expired free credits."""
    row = get_wallet(db)
    key = 'settle:' + job_id
    if entry(db, key):
        return
    holds = list(db.scalars(select(WalletEntry).where(
        WalletEntry.event_key.like('reserve:' + job_id + '%')).order_by(WalletEntry.sequence)))
    total = -sum(h.amount for h in holds)
    if not isinstance(charged, int) or not 0 <= charged <= total:
        raise ValueError('Settlement must fit the authorized reservation')
    remaining, free_return, purchased_return, expired = charged, 0, 0, 0
    for hold in holds:
        free, purchased = -hold.free_delta, -hold.purchased_delta
        take_free = min(remaining, free)
        remaining -= take_free
        take_purchased = min(remaining, purchased)
        remaining -= take_purchased
        unused_free = free - take_free
        if hold.details.get('free_month') == row.free_month:
            free_return += unused_free
        elif failed:
            # Existing failure policy: compensate lost credits after a platform failure.
            purchased_return += unused_free
        else:
            expired += unused_free
        purchased_return += purchased - take_purchased
    row.spent -= total - charged
    append(db, row, key, free=free_return, purchased=purchased_return,
           reason='AI credits refunded' if failed else f'AI settled at {charged} credits · unused reservation released',
           details={'job_id': job_id, 'reserved': total, 'charged': charged, 'expired_free_released': expired})
