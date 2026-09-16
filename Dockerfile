FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html tsconfig.json vite.config.ts ./
COPY src ./src
COPY public ./public
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_ENV=production
WORKDIR /app
RUN groupadd --system hakisense && useradd --system --gid hakisense --home-dir /app hakisense
COPY backend/requirements.lock /app/backend/requirements.lock
RUN pip install --no-cache-dir -r backend/requirements.lock
ENV TIKTOKEN_CACHE_DIR=/app/tokenizer-cache
RUN python -c "import tiktoken; tiktoken.get_encoding('o200k_base')" && chmod -R a+rX /app/tokenizer-cache
COPY backend /app/backend
COPY scripts /app/scripts
COPY migrations /app/migrations
COPY alembic.ini /app/alembic.ini
COPY --from=frontend /build/dist /app/dist
USER hakisense
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import os, urllib.request; port=int(os.getenv('PORT') or '8000'); urllib.request.urlopen(f'http://127.0.0.1:{port}/api/ready',timeout=4)"
# Render supplies PORT and WEB_CONCURRENCY at runtime. exec preserves shutdown signals.
CMD ["sh", "-c", "exec python -m uvicorn backend.main:app --host 0.0.0.0 --port \"${PORT:-8000}\" --workers \"${WEB_CONCURRENCY:-1}\" --no-access-log --timeout-graceful-shutdown 200"]
