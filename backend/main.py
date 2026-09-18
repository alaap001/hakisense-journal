"""Stateless API/web process. Migrations and workers run as separate processes."""
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from .config import config, ROOT
from .db import database, engine
from .journal_routes import api
from .billing import router as billing_router, webhooks
from .recharges import router as recharge_router
from .jobs import router as jobs_router
from .admin import router as admin_router
from .security import BodyLimit
from .markets import catalog

log = logging.getLogger('hakisense.api')


@asynccontextmanager
async def lifespan(app):
    config.validate()
    if config.environment == 'production':
        with database(system=True) as db:
            # Fail deployment before receiving traffic if migrations or restricted role are missing.
            role = db.execute(text('SELECT current_user, rolbypassrls, rolsuper FROM pg_roles WHERE rolname = current_user')).one()
            if role[0] != 'hakisense_api' or role[1] or role[2]:
                raise RuntimeError('Database runtime role must enforce row-level security.')
            db.execute(text('SELECT code FROM journal.credit_packs LIMIT 1'))
            db.execute(text('SELECT pricing_version FROM journal.ai_jobs LIMIT 1'))
            db.execute(text('SELECT job_id FROM journal.ai_events LIMIT 1'))
    yield
    if engine:
        engine.dispose()


app = FastAPI(title='HakiSenseJournal', version='1.0.0', lifespan=lifespan,
              docs_url=None if config.environment == 'production' else '/docs', redoc_url=None,
              openapi_url=None if config.environment == 'production' else '/openapi.json')
app.add_middleware(BodyLimit)
app.add_middleware(CORSMiddleware, allow_origins=[config.origin], allow_credentials=False,
                   allow_methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'], allow_headers=['Authorization', 'Content-Type', 'Idempotency-Key'],
                   expose_headers=['X-Request-ID', 'Retry-After'])
app.add_middleware(TrustedHostMiddleware, allowed_hosts=[h.strip() for h in config.allowed_hosts.split(',') if h.strip()])


@app.middleware('http')
async def response_headers(request: Request, call_next):
    request_id = str(uuid4())
    request.state.request_id = request_id
    started = time.monotonic()
    response = await call_next(request)
    response.headers['X-Request-ID'] = request_id
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    response.headers['X-Frame-Options'] = 'DENY'
    if request.url.path.startswith('/api') or request.url.path == '/health':
        response.headers['Cache-Control'] = 'no-store'
    if config.environment == 'production':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Content-Security-Policy'] = f"default-src 'self'; script-src 'self' https://checkout.razorpay.com; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https://*.razorpay.com; font-src 'self'; connect-src 'self' {config.supabase_url} https://*.razorpay.com; frame-src https://*.razorpay.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'"
    log.info('request id=%s method=%s status=%s duration_ms=%d', request_id, request.method, response.status_code, (time.monotonic()-started)*1000)
    return response


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc):
    original = getattr(exc, 'orig', None)
    log.error('database_error request_id=%s type=%s db_type=%s sqlstate=%s',
              getattr(request.state, 'request_id', ''), type(exc).__name__,
              type(original).__name__, getattr(original, 'sqlstate', None))
    if isinstance(exc, IntegrityError):
        return JSONResponse({'detail': 'This record conflicts with existing data. Refresh and try again.'}, status_code=409)
    return JSONResponse({'detail': 'The service is temporarily unavailable. Please try again shortly.'}, status_code=503)


@app.exception_handler(Exception)
async def internal_error(request: Request, exc):
    log.error('internal_error request_id=%s type=%s', getattr(request.state, 'request_id', ''), type(exc).__name__)
    return JSONResponse({'detail': 'Something went wrong. Please try again.', 'request_id': getattr(request.state, 'request_id', '')}, status_code=500)


@app.api_route('/health', methods=['GET', 'HEAD'])
@app.api_route('/api/health', methods=['GET', 'HEAD'])
async def health():
    return {'status': 'ok'}


@app.get('/api/ready')
def ready():
    with database(system=True) as db:
        db.execute(text('SELECT code FROM journal.credit_packs LIMIT 1'))
    return {'status': 'ready'}


@app.get('/api/config')
def public_config():
    from .runtime_settings import settings
    with database(system=True) as db:
        product = settings(db)
    return {'supabase_url': config.supabase_url, 'supabase_publishable_key': config.supabase_key,
            'markets': catalog(), 'support_email': product.support_email, 'brand_name': product.brand_name,
            'password_min_length': 8,
            'policies': {'privacy': product.privacy_url, 'terms': product.terms_url, 'refunds': product.refund_url}}


@app.get('/api/catalog')
def marketing_catalog():
    from .entitlements import public_catalog
    with database(system=True) as db:
        return public_catalog(db)


app.include_router(api)
app.include_router(billing_router)
app.include_router(recharge_router)
app.include_router(jobs_router)
app.include_router(admin_router)
app.include_router(webhooks)

# The production image serves the compiled SPA and API from one origin.
dist = ROOT / 'dist'
if dist.is_dir():
    app.mount('/assets', StaticFiles(directory=dist / 'assets'), name='assets')

    @app.get('/{path:path}', include_in_schema=False)
    def spa(path: str):
        if path.startswith('api/'):
            return JSONResponse({'detail': 'Not found'}, status_code=404)
        candidate = (dist / path).resolve()
        if candidate.is_relative_to(dist.resolve()) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(dist / 'index.html', headers={'Cache-Control': 'no-cache'})
