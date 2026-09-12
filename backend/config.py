"""Deployment configuration. Secrets never appear in public configuration."""
import os
import json
from urllib.parse import quote, unquote, urlsplit
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / 'backend' / '.env')
load_dotenv(ROOT / '.env')
AI_MODELS = json.loads((ROOT / 'backend' / 'ai_models.json').read_text())


def normalize_database_url(value):
    # Accept pasted connection strings whose password contains an unescaped @.
    # Credentials are re-encoded before reaching psycopg; never log the source URL.
    if not value or '://' not in value or '@' not in value:
        return value
    scheme, rest = value.split('://', 1)
    credentials, location = rest.rsplit('@', 1)
    if ':' not in credentials:
        return value
    username, password = credentials.split(':', 1)
    return f'{scheme}://{quote(unquote(username), safe="")}:{quote(unquote(password), safe="")}@{location}'


@dataclass(frozen=True)
class Config:
    environment: str = os.getenv('APP_ENV', 'development')
    database_url: str = normalize_database_url(os.getenv('DATABASE_URL', ''))
    migration_url: str = normalize_database_url(os.getenv('MIGRATION_DATABASE_URL') or os.getenv('DIRECT_URL', ''))
    supabase_url: str = os.getenv('SUPABASE_URL', 'https://gdyhnquqflgnjqlnhqog.supabase.co').rstrip('/')
    supabase_key: str = os.getenv('SUPABASE_PUBLISHABLE_KEY', 'sb_publishable_f9KihvZ88fWBUd50fBx7bg_Bnhf8Y0E')
    origin: str = os.getenv('APP_ORIGIN', 'http://127.0.0.1:5173').rstrip('/')
    allowed_hosts: str = os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost,testserver')
    openrouter_key: str = os.getenv('OPENROUTER_API_KEY', '')
    standard_model: str = os.getenv('AI_STANDARD_MODEL', AI_MODELS['standard'])
    advanced_model: str = os.getenv('AI_ADVANCED_MODEL', AI_MODELS['advanced'])
    razorpay_key: str = os.getenv('RAZORPAY_KEY_ID', '')
    razorpay_secret: str = os.getenv('RAZORPAY_KEY_SECRET', '')
    razorpay_webhook_secret: str = os.getenv('RAZORPAY_WEBHOOK_SECRET', '')
    checkout_enabled: bool = os.getenv('CHECKOUT_ENABLED', 'false').lower() == 'true'
    support_email: str = os.getenv('SUPPORT_EMAIL', '')
    legal_name: str = os.getenv('LEGAL_BUSINESS_NAME', '')
    legal_address: str = os.getenv('LEGAL_BUSINESS_ADDRESS', '')
    privacy_url: str = os.getenv('PRIVACY_POLICY_URL', '')
    terms_url: str = os.getenv('TERMS_URL', '')
    refund_url: str = os.getenv('REFUND_POLICY_URL', '')

    def validate(self):
        if self.database_url and not self.database_url.startswith(('postgresql://', 'postgresql+psycopg://')):
            if not (self.environment == 'test' and self.database_url.startswith('sqlite:')):
                raise RuntimeError('HakiSense requires PostgreSQL. SQLite is allowed only in isolated tests.')
        if '[YOUR-PASSWORD]' in self.database_url:
            raise RuntimeError('DATABASE_URL contains an unconfigured password placeholder.')
        if self.environment == 'production':
            if urlsplit(self.database_url).username in ('postgres', 'supabase_admin'):
                raise RuntimeError('Use a restricted application login for DATABASE_URL; keep the admin connection in MIGRATION_DATABASE_URL.')
            if not self.database_url or not self.origin.startswith('https://') or '*' in self.allowed_hosts:
                raise RuntimeError('Production requires PostgreSQL, an HTTPS APP_ORIGIN and explicit ALLOWED_HOSTS.')
        # Product switches, policies and AI routing are validated when saved in PostgreSQL.
        # Environment values below are bootstrap defaults, not a runtime override.


config = Config()
