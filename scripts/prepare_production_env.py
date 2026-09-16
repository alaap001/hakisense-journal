"""Prepare an ignored Render web-service environment file without exposing secrets.

Reads backend/.env and the root .env, copies only payment settings, and generates
a webhook secret only when none exists. Does not deploy or change database data.
"""
import argparse
import os
from pathlib import Path
import secrets
import sys
from urllib.parse import urlsplit

from dotenv import dotenv_values, set_key

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def prepare(origin='https://www.hakisense.in',render_host=None):
    from backend.config import config,normalize_database_url
    from dataclasses import replace
    source=ROOT/'backend/.env'
    values={**dotenv_values(ROOT/'.env'),**dotenv_values(source)}
    # Shell values take precedence, just as they do in the running backend.
    for key in tuple(values):
        if key in os.environ:values[key]=os.environ[key]
    if not (values.get('RAZORPAY_KEY_ID','').startswith('rzp_live_') and values.get('RAZORPAY_KEY_SECRET')):
        raise ValueError('Set the live Razorpay key pair in backend/.env first.')
    hosts=['www.hakisense.in','hakisense.in','127.0.0.1']
    host=urlsplit(origin).hostname
    if host and host not in hosts:hosts.insert(0,host)
    if render_host:
        if not render_host.endswith('.onrender.com') or any(c in render_host for c in '/:@?# '):
            raise ValueError('Use the Render hostname only, ending in .onrender.com.')
        hosts.append(render_host)
    database_url=normalize_database_url(values.get('DATABASE_URL',''))
    replace(config,environment='production',origin=origin,allowed_hosts=','.join(hosts),database_url=database_url).validate()
    generated=not values.get('RAZORPAY_WEBHOOK_SECRET')
    if generated:
        values['RAZORPAY_WEBHOOK_SECRET']=secrets.token_urlsafe(48)
        set_key(str(source),'RAZORPAY_WEBHOOK_SECRET',values['RAZORPAY_WEBHOOK_SECRET'])
        source.chmod(0o600)
    # A payment overlay for an existing deployment. Preserve its working DB/AI/Auth configuration.
    keys=('RAZORPAY_KEY_ID','RAZORPAY_KEY_SECRET','RAZORPAY_WEBHOOK_SECRET')
    output={key:values.get(key,'') or '' for key in keys}
    output.update(APP_ENV='production',APP_ORIGIN=origin,CHECKOUT_ENABLED='true',RAZORPAY_ALLOW_TEST_CHECKOUT='false')
    if render_host:output['ALLOWED_HOSTS']=','.join(hosts)
    path=ROOT/'backend/.env.production'
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as file:
        file.write('# PRIVATE: import into the existing Render web service. Never commit.\n')
        file.write('# Payment overlay only: retain existing DATABASE_URL, Auth, AI and ALLOWED_HOSTS settings.\n')
        for key,value in output.items():
            if '\n' in value or '\r' in value:raise ValueError('Environment values must be single-line: '+key)
            file.write(key+"='"+value.replace("'","\\'")+"'\n")
    path.chmod(0o600)
    print('Prepared backend/.env.production (0600); no secrets printed.')
    print('Webhook URL: '+origin+'/api/webhooks/razorpay')
    print('Webhook secret '+('generated and saved to backend/.env; copy it into Razorpay.' if generated else 'preserved; ensure Razorpay uses the same value.'))
    print('Deployment and merchant Product settings still require completion; this command does not activate production.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin',default='https://www.hakisense.in')
    parser.add_argument('--render-host',help='Existing service hostname, e.g. your-service.onrender.com')
    args=parser.parse_args()
    prepare(args.origin,args.render_host)
