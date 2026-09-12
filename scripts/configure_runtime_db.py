"""Create a restricted runtime credential and save it directly to backend/.env."""
import sys
import secrets
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, quote
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import set_key
import psycopg
from psycopg import sql
from backend.config import config

if config.database_url:
    raise SystemExit('DATABASE_URL is already configured; leaving the existing credential unchanged.')
url = urlsplit(config.migration_url)
if 'gdyhnquqflgnjqlnhqog' not in config.migration_url:
    raise SystemExit('Migration connection does not identify the configured HakiSense project.')
password = secrets.token_urlsafe(40)
with psycopg.connect(config.migration_url, connect_timeout=10, sslmode='require') as connection:
    with connection.cursor() as cursor:
        cursor.execute("SELECT rolsuper,rolbypassrls,rolcreaterole FROM pg_roles WHERE rolname='hakisense_app'")
        role = cursor.fetchone()
        if not role or any(role):
            raise SystemExit('The restricted application role has not been safely initialized.')
        cursor.execute(sql.SQL('ALTER ROLE hakisense_app PASSWORD {}').format(sql.Literal(password)))
        cursor.execute('GRANT CONNECT ON DATABASE postgres TO hakisense_app')
runtime_url = urlunsplit((url.scheme, 'hakisense_app:' + quote(password, safe='') + '@' + url.netloc.rsplit('@',1)[-1], url.path, url.query, ''))
path = Path(__file__).resolve().parents[1] / 'backend' / '.env'
set_key(str(path), 'DATABASE_URL', runtime_url)
path.chmod(0o600)
print('Restricted DATABASE_URL saved to backend/.env. No credentials were printed.')
