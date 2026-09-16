"""Check live columns of journal.trades in Supabase."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import psycopg
from backend.config import config

with psycopg.connect(config.migration_url, sslmode='require', connect_timeout=15) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'journal' AND table_name = 'trades'
            ORDER BY ordinal_position
        """)
        cols = cur.fetchall()
        for c in cols:
            print(f"{c[0]}: {c[1]} (nullable: {c[2]})")

