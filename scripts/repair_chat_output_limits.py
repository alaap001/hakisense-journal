"""Repair the two reported chat-route ceilings, preserving all other configuration.

Read-only by default. --apply records a maintenance audit (nil system actor),
bumps the catalog revision and changes only the known 4098/4092 ceilings.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.config import config
from backend.db import make_engine, AIRoute, AdminAudit, PlatformConfig, utcnow

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()
engine = make_engine(config.migration_url or config.database_url)
try:
    with Session(engine) as db:
        state = db.scalar(select(PlatformConfig).where(PlatformConfig.key == 'product').with_for_update())
        for tier, expected in (('standard', 4098), ('advanced', 4092)):
            route = db.get(AIRoute, ('chat', tier))
            report = {'task': 'chat', 'tier': tier, 'before': route.max_output_tokens, 'after': 16000}
            if route.max_output_tokens != expected:
                print(json.dumps({**report, 'action': 'unchanged; ceiling no longer matches the reported route'}))
                continue
            print(json.dumps({**report, 'action': 'apply' if args.apply else 'preview'}))
            if args.apply:
                route.max_output_tokens = 16000
                db.add(AdminAudit(actor_id=str(UUID(int=0)), actor_role='maintenance',
                    action='routing.repair_output_ceiling', target='chat:'+tier,
                    reason='Requested AI chat failure repair: reasoning exhausted the old per-call ceiling before the answer completed. Restore shared workflow capacity.',
                    before={'max_output_tokens': expected}, after={'max_output_tokens': 16000},
                    idempotency_key='chat-output-repair-2026-09-15-'+tier,
                    request_hash=hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest()))
                state.revision += 1
                state.updated_at = utcnow()
        if args.apply:
            db.commit()
        else:
            db.rollback()
finally:
    engine.dispose()
