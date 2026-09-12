from datetime import datetime, timezone
from sqlalchemy import select
from fastapi import HTTPException
from .db import Trade, Account, serialize
from .analytics import enrich
from .markets import IST

def journal_rows(db, filters=None):
    query = select(Trade).order_by(Trade.entry_time.desc())
    if filters:
        from datetime import timedelta
        f = filters.model_dump() if hasattr(filters, 'model_dump') else filters
        for key in ('account_id', 'asset_type', 'side', 'status', 'setup', 'emotion'):
            if f.get(key):
                query = query.where(getattr(Trade, key) == f[key])
        if f.get('symbol'):
            query = query.where(Trade.symbol.contains(f['symbol'].upper(), autoescape=True))
        try:
            if f.get('start'):
                query = query.where(Trade.entry_time >= datetime.fromisoformat(f['start']).replace(tzinfo=IST).astimezone(timezone.utc))
            if f.get('end'):
                query = query.where(Trade.entry_time < (datetime.fromisoformat(f['end']).replace(tzinfo=IST) + timedelta(days=1)).astimezone(timezone.utc))
        except ValueError:
            raise HTTPException(400, 'Use valid YYYY-MM-DD dates.')
    from .runtime_settings import settings
    limit = settings(db).report_trade_limit
    rows = list(db.scalars(query.limit(limit+1)))
    if len(rows) > limit:
        raise HTTPException(422, f'This view exceeds {limit:,} trades. Select a narrower account or date range.')
    names = {a.id: a.name for a in db.scalars(select(Account))}
    return [enrich({**serialize(t), 'account_name': names.get(t.account_id, '')}) for t in rows]
