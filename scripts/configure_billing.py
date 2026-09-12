"""Validate and bind pre-created Razorpay plans; never creates a charge or subscription."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import psycopg
from backend.config import config
from backend.payments import provider

parser=argparse.ArgumentParser()
parser.add_argument('price_code',choices=['pro_monthly','pro_annual','advanced_annual'])
parser.add_argument('razorpay_plan_id')
args=parser.parse_args()
if not args.razorpay_plan_id.startswith('plan_') or not args.razorpay_plan_id.replace('_','').isalnum():
    raise SystemExit('Choose a valid Razorpay plan ID.')
with psycopg.connect(config.migration_url,sslmode='require',connect_timeout=10) as connection:
    with connection.cursor() as cursor:
        cursor.execute('SELECT amount_paise, interval FROM journal.prices WHERE code=%s', (args.price_code,))
        amount, interval=cursor.fetchone()
        remote=provider.plan(args.razorpay_plan_id)
        if remote.get('item',{}).get('amount')!=amount or remote.get('item',{}).get('currency')!='INR' or remote.get('period')!=('monthly' if interval=='month' else 'yearly') or remote.get('interval')!=1:
            raise SystemExit('Provider amount, currency or interval does not match the backend price. Nothing changed.')
        cursor.execute('UPDATE journal.prices SET provider_plan_id=%s WHERE code=%s', (args.razorpay_plan_id,args.price_code))
print('Verified provider plan linked to',args.price_code,'without creating a payment.')
