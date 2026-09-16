"""Inspect Supabase database users, accounts, and trade counts."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import psycopg
from backend.config import config


def inspect():
    with psycopg.connect(config.migration_url, sslmode='require', connect_timeout=15) as conn:
        with conn.cursor() as cur:
            print("=== Registered Users in auth.users ===")
            cur.execute("SELECT id, email, created_at FROM auth.users ORDER BY created_at DESC")
            users = cur.fetchall()
            for u in users:
                cur.execute("SELECT id, name, initial_balance FROM journal.accounts WHERE user_id=%s", (u[0],))
                accounts = cur.fetchall()
                cur.execute("SELECT count(*) FROM journal.trades WHERE user_id=%s", (u[0],))
                trade_count = cur.fetchone()[0]
                print(f"User: {u[1]} (ID: {u[0]})")
                print(f"  Accounts: {accounts}")
                print(f"  Total Trades: {trade_count}")
                print()


if __name__ == '__main__':
    inspect()

