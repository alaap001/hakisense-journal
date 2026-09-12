"""Shared rate limits and bounded HTTP input without process-local authority."""
import hashlib
import json
import time
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from starlette.responses import JSONResponse
from .db import RateBucket


def rate_limit(db, subject, limit, seconds):
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    insert = pg_insert if db.bind.dialect.name == 'postgresql' else sqlite_insert
    bucket = int(time.time()) // seconds
    key = hashlib.sha256(f'{subject}:{seconds}:{bucket}'.encode()).hexdigest()
    statement = insert(RateBucket).values(key=key, hits=1, expires_at=datetime.now(timezone.utc) + timedelta(seconds=seconds * 2))
    statement = statement.on_conflict_do_update(index_elements=['key'], set_={'hits': RateBucket.hits + 1}).returning(RateBucket.hits)
    hits = db.scalar(statement)
    if hits > limit:
        raise HTTPException(429, 'Too many requests. Please wait a moment.', headers={'Retry-After': str(seconds)})


class BodyLimit:
    def __init__(self, app, limit=20 * 1024 * 1024):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = dict(scope['headers'])
        try:
            declared = int(headers.get(b'content-length', b'0'))
        except ValueError:
            declared = self.limit + 1
        if declared > self.limit:
            return await JSONResponse({'detail': 'Request is too large.'}, status_code=413)(scope, receive, send)
        # Spool at most the configured cap, including clients using chunked transfer.
        messages, size = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            size += len(message.get('body', b''))
            if size > self.limit:
                return await JSONResponse({'detail': 'Request is too large.'}, status_code=413)(scope, receive, send)
            messages.append(message)
            if not message.get('more_body'):
                break
        async def replay():
            return messages.pop(0) if messages else await receive()
        await self.app(scope, replay, send)
