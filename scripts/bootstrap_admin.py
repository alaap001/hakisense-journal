"""Operator-only first-owner setup. Never exposed as an HTTP endpoint."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import psycopg
from backend.config import config

parser=argparse.ArgumentParser(description='Assign the first HakiSense owner to an existing verified account.')
parser.add_argument('--email',required=True,help='Your existing, verified HakiSense sign-in email')
args=parser.parse_args()
with psycopg.connect(config.migration_url,sslmode='require',connect_timeout=10) as connection:
    with connection.cursor() as cursor:
        cursor.execute("SELECT key FROM journal.platform_config WHERE key='product' FOR UPDATE")
        cursor.execute("SELECT count(*) FROM journal.admin_members WHERE active AND role='owner'")
        if cursor.fetchone()[0]:
            raise SystemExit('An owner already exists. Use Administration → Staff to change roles.')
        cursor.execute('SELECT id,email_confirmed_at FROM auth.users WHERE lower(email)=lower(%s)',(args.email.strip(),))
        rows=cursor.fetchall()
        if len(rows)!=1 or not rows[0][1]:
            raise SystemExit('Choose an existing account with a verified email. No access was changed.')
        user_id=rows[0][0]
        cursor.execute('SELECT suspended FROM journal.profiles WHERE user_id=%s',(user_id,))
        profile=cursor.fetchone()
        if profile and profile[0]:
            raise SystemExit('The account is suspended. Resolve that before granting owner access.')
        cursor.execute("INSERT INTO journal.admin_members(user_id,role,active) VALUES (%s,'owner',true) ON CONFLICT(user_id) DO UPDATE SET role='owner',active=true",(user_id,))
        cursor.execute('INSERT INTO journal.admin_audit(id,actor_id,actor_role,action,target,reason,before,after,idempotency_key,request_hash) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
            (str(uuid4()),user_id,'operator','owner.bootstrap',str(user_id),'Initial owner assigned using the protected operator command','{}',json.dumps({'user_id':str(user_id),'role':'owner','active':True}),str(uuid4()),hashlib.sha256(str(user_id).encode()).hexdigest()))
print('Owner access assigned. Sign in or refresh HakiSense, then open /admin. No secrets were printed.')
