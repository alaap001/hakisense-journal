"""Read-only checks for configured Supabase Auth and supported model IDs."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from backend.config import config, AI_MODELS
with httpx.Client(timeout=20) as client:
    response = client.get(config.supabase_url + '/auth/v1/settings', headers={'apikey': config.supabase_key})
    print('Supabase Auth settings HTTP:', response.status_code)
    if response.is_success:
        data = response.json()
        print('Auth configuration:', {k: data.get(k) for k in ('disable_signup', 'mailer_autoconfirm')})
        print('Email sign-in:', data.get('external', {}).get('email'))
    response = client.get('https://openrouter.ai/api/v1/models')
    response.raise_for_status()
    models = {item['id'] for item in response.json()['data']}
    print('Configured model IDs in current OpenRouter catalog:', {model: model in models for model in AI_MODELS['available']})
