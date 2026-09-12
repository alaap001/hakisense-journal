"""Read-only deployment connection check; never prints credentials."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.config import config
import psycopg
from urllib.parse import urlsplit

url = config.migration_url or config.database_url
if not url:
    raise SystemExit('No database connection is configured.')
try:
    with psycopg.connect(url, connect_timeout=10, sslmode='require') as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT current_user, current_database(), current_setting('server_version'), to_regnamespace('journal') IS NOT NULL")
            print('Database connection:', cursor.fetchone())
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='journal' ORDER BY tablename")
            print('Existing journal tables:', [r[0] for r in cursor.fetchall()])
except Exception as error:
    message = str(error)
    for secret in (url, urlsplit(url).password, config.openrouter_key, config.razorpay_secret):
        if secret:
            message = message.replace(secret, '[redacted]')
    print(type(error).__name__ + ': ' + message[:1200])
    raise SystemExit(2)
