"""Bounded payment recovery pass: python -m backend.reconcile_payments --limit 50.

Schedule every five minutes in deployment. Webhooks remain the immediate path.
This command retrieves existing payments; it never initiates a charge.
"""
import argparse
import logging
from datetime import timedelta
from sqlalchemy import select
from .db import database,PurchaseIndex,utcnow
from .recharges import reconcile_purchase


def run(limit=50):
    with database(system=True) as db:
        rows=list(db.scalars(select(PurchaseIndex).where(PurchaseIndex.checked_at<utcnow()-timedelta(minutes=5))
            .order_by(PurchaseIndex.checked_at).limit(limit)))
    completed,failed=0,0
    for row in rows:
        try:
            reconcile_purchase(row.id,row.user_id)
            completed+=1
        except Exception as exc:
            failed+=1
            logging.warning('payment_reconciliation_failed purchase_id=%s error_type=%s',row.id,type(exc).__name__)
            # Rotate uncertain/error rows too so one outage cannot starve later purchases.
            with database(system=True) as db:
                index=db.get(PurchaseIndex,row.id)
                if index:index.checked_at=utcnow()
    return {'checked':len(rows),'completed':completed,'pending_or_failed':failed}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit',type=int,choices=range(1,201),default=50,metavar='1..200')
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    result=run(args.limit)
    print(result)
    raise SystemExit(1 if result['pending_or_failed'] else 0)
