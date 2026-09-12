from alembic import context
from sqlalchemy import create_engine, pool, text
from backend.config import config
from backend.db import Base

url = config.migration_url or config.database_url
if not url or not url.startswith(('postgresql://', 'postgresql+psycopg://')):
    raise RuntimeError('Set MIGRATION_DATABASE_URL to a PostgreSQL migration-role connection.')
url = url.replace('postgresql://', 'postgresql+psycopg://', 1)
if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True, include_schemas=True, version_table_schema='journal')
    with context.begin_transaction():
        context.execute('CREATE SCHEMA IF NOT EXISTS journal')
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool, connect_args={'prepare_threshold': None, 'connect_timeout': 10, 'sslmode': 'require'})
    with engine.connect() as connection:
        connection.execute(text('CREATE SCHEMA IF NOT EXISTS journal'))
        connection.commit()
        context.configure(connection=connection, target_metadata=Base.metadata, include_schemas=True, version_table_schema='journal')
        with context.begin_transaction():
            # One migrator owns the schema transition, even if multiple deployments start together.
            connection.execute(text("SELECT pg_advisory_xact_lock(hashtext('hakisense_migrations'))"))
            context.run_migrations()
