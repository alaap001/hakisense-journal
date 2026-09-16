"""Test creating user via Supabase Auth Admin API and check user details."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from dotenv import dotenv_values
from backend.config import config

secret = dotenv_values(Path(__file__).resolve().parents[1] / 'backend' / '.env').get('SUPABASE_SECRET_KEY')
headers = {'apikey': secret, 'Authorization': 'Bearer ' + secret}

with httpx.Client(timeout=15) as client:
    resp = client.get(config.supabase_url + '/auth/v1/admin/users', headers=headers)
    print("Admin users status:", resp.status_code)
    if resp.is_success:
        users = resp.json().get('users', [])
        print(f"Total users found: {len(users)}")
        for u in users:
            print(f"  - ID: {u['id']}, Email: {u.get('email')}, Confirmed: {bool(u.get('email_confirmed_at'))}")

