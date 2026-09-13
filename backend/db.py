"""Tenant-scoped persistence; PostgreSQL is the production authority."""
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import (create_engine, String, Text, Boolean, JSON, Numeric, Integer, DateTime,
                        UniqueConstraint, ForeignKeyConstraint, Index, CheckConstraint, MetaData, Uuid, event, text)
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session as SASession, with_loader_criteria
from .config import ROOT, config


def uid():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc).isoformat()


def utcnow():
    return datetime.now(timezone.utc)


class ISOTime(TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return value.replace(tzinfo=value.tzinfo or timezone.utc) if value else None

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=value.tzinfo or timezone.utc).astimezone(timezone.utc).isoformat() if value else None


class Base(DeclarativeBase):
    metadata = MetaData(schema='journal')


class Tenant:
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)


class TenantSession(SASession):
    pass


@event.listens_for(TenantSession, 'do_orm_execute')
def scope_queries(state):
    if state.session.info.get('admin_actor'):
        return
    user = state.session.info.get('user_id')
    if state.is_select or state.is_update or state.is_delete:
        state.statement = state.statement.options(with_loader_criteria(Tenant, lambda row: row.user_id == user, include_aliases=True))


@event.listens_for(TenantSession, 'before_flush')
def own_changes(db, *_):
    user = db.info.get('user_id')
    for row in db.new | db.dirty | db.deleted:
        if isinstance(row, Tenant):
            if db.info.get('admin_actor'):
                if row in db.new and not row.user_id and user:
                    row.user_id = user
                if not row.user_id:
                    raise RuntimeError('Administrative tenant writes require an explicit target')
                continue
            if not user:
                raise RuntimeError('A verified tenant is required')
            if row in db.new and not row.user_id:
                row.user_id = user
            if row.user_id != user:
                raise RuntimeError('Cross-tenant write rejected')


def make_engine(url):
    if url.startswith('postgresql://'):
        url = url.replace('postgresql://', 'postgresql+psycopg://', 1)
    if url.startswith('sqlite:'):
        return create_engine(url, connect_args={'check_same_thread': False}, execution_options={'schema_translate_map': {'journal': None}})
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5, pool_timeout=15,
                         pool_recycle=600, connect_args={'prepare_threshold': None, 'connect_timeout': 10, 'sslmode': 'require'})


engine = make_engine(config.database_url) if config.database_url else None
Session = sessionmaker(bind=engine, class_=TenantSession, expire_on_commit=False)
class Account(Tenant, Base):
    __tablename__ = 'accounts'
    __table_args__ = (UniqueConstraint('user_id', 'id'),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String)
    broker: Mapped[str] = mapped_column(String, default='Manual')
    currency: Mapped[str] = mapped_column(String, default='INR')
    initial_balance: Mapped[float] = mapped_column(Numeric(28, 8, asdecimal=False), default=100000)
    color: Mapped[str] = mapped_column(String, default='#a6d96a')
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Trade(Tenant, Base):
    __tablename__ = 'trades'
    __table_args__ = (ForeignKeyConstraint(['user_id', 'account_id'], ['journal.accounts.user_id', 'journal.accounts.id']), ForeignKeyConstraint(['user_id','playbook_id'],['journal.records.user_id','journal.records.id']), UniqueConstraint('user_id', 'fingerprint'), Index('ix_trade_user_entry', 'user_id', 'entry_time'))
    exchange: Mapped[str] = mapped_column(String, default='NSE')
    segment: Mapped[str] = mapped_column(String, default='Equity')
    expiry: Mapped[str | None] = mapped_column(String, nullable=True)
    strike: Mapped[float | None] = mapped_column(Numeric(28, 8, asdecimal=False), nullable=True)
    option_type: Mapped[str | None] = mapped_column(String, nullable=True)
    lot_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    account_id: Mapped[str] = mapped_column(String, index=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    asset_type: Mapped[str] = mapped_column(String, default='Stocks')
    side: Mapped[str] = mapped_column(String, default='Long')
    status: Mapped[str] = mapped_column(String, default='Closed', index=True)
    entry_price: Mapped[float] = mapped_column(Numeric(28, 8, asdecimal=False))
    exit_price: Mapped[float | None] = mapped_column(Numeric(28, 8, asdecimal=False), nullable=True)
    mark_price: Mapped[float | None] = mapped_column(Numeric(28, 8, asdecimal=False), nullable=True)
    quantity: Mapped[float] = mapped_column(Numeric(28, 8, asdecimal=False))
    closed_quantity: Mapped[float] = mapped_column(Numeric(28, 8, asdecimal=False), default=0)
    multiplier: Mapped[float] = mapped_column(Numeric(28, 8, asdecimal=False), default=1)
    entry_time: Mapped[str] = mapped_column(ISOTime(), index=True)
    exit_time: Mapped[str | None] = mapped_column(ISOTime(), nullable=True)
    commission: Mapped[float] = mapped_column(Numeric(28, 8, asdecimal=False), default=0)
    fees: Mapped[float] = mapped_column(Numeric(28, 8, asdecimal=False), default=0)
    stop_loss: Mapped[float | None] = mapped_column(Numeric(28, 8, asdecimal=False), nullable=True)
    target_price: Mapped[float | None] = mapped_column(Numeric(28, 8, asdecimal=False), nullable=True)
    risk_amount: Mapped[float | None] = mapped_column(Numeric(28, 8, asdecimal=False), nullable=True)
    planned_entry: Mapped[float | None] = mapped_column(Numeric(28, 8, asdecimal=False), nullable=True)
    setup: Mapped[str] = mapped_column(String, default='Uncategorized')
    playbook_id: Mapped[str | None] = mapped_column(String, nullable=True)
    playbook_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, server_default='{}')
    emotion: Mapped[str] = mapped_column(String, default='Neutral')
    rating: Mapped[int] = mapped_column(default=3)
    notes: Mapped[str] = mapped_column(Text, default='')
    tags: Mapped[list] = mapped_column(JSON, default=list)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    mfe: Mapped[float | None] = mapped_column(Numeric(28, 8, asdecimal=False), nullable=True)
    mae: Mapped[float | None] = mapped_column(Numeric(28, 8, asdecimal=False), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    fingerprint: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(ISOTime(), default=now)


class Record(Tenant, Base):
    __tablename__ = 'records'
    __table_args__ = (UniqueConstraint('user_id','id'),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String, index=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(ISOTime(), default=now)


class Message(Tenant, Base):
    __tablename__ = 'messages'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    thread_id: Mapped[str] = mapped_column(String, index=True)
    role: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(ISOTime(), default=now)


class Setting(Tenant, Base):
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    __tablename__ = 'settings'
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)


class Profile(Tenant, Base):
    __tablename__ = 'profiles'
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100), default='Trader')
    suspended: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)






class AITask(Base):
    __tablename__ = 'ai_tasks'
    code: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    credits: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)








class AIJob(Tenant, Base):
    __tablename__ = 'ai_jobs'
    __table_args__ = (UniqueConstraint('user_id', 'idempotency_key'), UniqueConstraint('user_id', 'id'))
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    idempotency_key: Mapped[str] = mapped_column(String(100))
    request_hash: Mapped[str] = mapped_column(String(64))
    request: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String, default='queued')
    task_code: Mapped[str] = mapped_column(String)
    credits: Mapped[int] = mapped_column(Integer)
    month: Mapped[str] = mapped_column(String(7))
    model: Mapped[str] = mapped_column(String)
    bonus_credits: Mapped[int] = mapped_column(Integer, default=0, server_default='0')
    routing_config: Mapped[dict] = mapped_column(JSON, default=dict, server_default='{}')
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# Internal routing tables contain no journal text and are never exposed through Supabase's Data API.
class JobQueue(Base):
    __tablename__ = 'job_queue'
    __table_args__ = (ForeignKeyConstraint(['user_id','job_id'], ['journal.ai_jobs.user_id','journal.ai_jobs.id'], ondelete='CASCADE'),)
    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)








class WebhookEvent(Base):
    __tablename__ = 'webhook_events'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_type: Mapped[str] = mapped_column(String)
    body_hash: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RateBucket(Base):
    __tablename__ = 'rate_buckets'
    key: Mapped[str] = mapped_column(String, primary_key=True)
    hits: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AdminMember(Base):
    __tablename__ = 'admin_members'
    __table_args__ = (CheckConstraint("role IN ('owner','admin','support')"),)
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    role: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserDirectory(Base):
    __tablename__ = 'user_directory'
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sign_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AdminAudit(Base):
    __tablename__ = 'admin_audit'
    __table_args__ = (UniqueConstraint('actor_id', 'idempotency_key'), Index('ix_admin_audit_created', 'created_at'))
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    actor_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    actor_role: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String(100))
    target: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str] = mapped_column(String(1000))
    before: Mapped[dict] = mapped_column(JSON, default=dict)
    after: Mapped[dict] = mapped_column(JSON, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(100))
    request_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PlatformConfig(Base):
    __tablename__ = 'platform_config'
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AIModel(Base):
    __tablename__ = 'ai_models'
    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class AIRoute(Base):
    __tablename__ = 'ai_routes'
    __table_args__ = (ForeignKeyConstraint(['task_code'], ['journal.ai_tasks.code']),
        ForeignKeyConstraint(['model_id'], ['journal.ai_models.id']),
        ForeignKeyConstraint(['planner_model_id'], ['journal.ai_models.id']),
        CheckConstraint("tier IN ('standard','advanced')"))
    task_code: Mapped[str] = mapped_column(String, primary_key=True)
    tier: Mapped[str] = mapped_column(String, primary_key=True)
    model_id: Mapped[str] = mapped_column(String(200))
    planner_model_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    max_output_tokens: Mapped[int] = mapped_column(Integer, default=2400)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=90)
    temperature: Mapped[float] = mapped_column(Numeric(4, 2, asdecimal=False), default=0.2)
    reasoning_effort: Mapped[str] = mapped_column(String(20), default='low')
    instructions: Mapped[str] = mapped_column(Text, default='')
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)




class CreditWallet(Tenant, Base):
    __tablename__ = 'credit_wallets'
    __table_args__ = (CheckConstraint('free_balance >= 0 AND free_allocation >= 0 AND spent >= 0 AND revision >= 0'),
                     CheckConstraint('balance = free_balance + purchased_balance'))
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    free_month: Mapped[str] = mapped_column(String(7))
    free_allocation: Mapped[int] = mapped_column(Integer, default=0)
    free_balance: Mapped[int] = mapped_column(Integer, default=0)
    purchased_balance: Mapped[int] = mapped_column(Integer, default=0)
    # May be negative ONLY after a refund/chargeback. Ordinary spending cannot create debt.
    balance: Mapped[int] = mapped_column(Integer, default=0)
    spent: Mapped[int] = mapped_column(Integer, default=0)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    first_purchase_id: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WalletEntry(Tenant, Base):
    __tablename__ = 'wallet_entries'
    __table_args__ = (UniqueConstraint('user_id', 'event_key'), UniqueConstraint('user_id', 'sequence'),
                     CheckConstraint('amount = free_delta + purchased_delta'))
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    sequence: Mapped[int] = mapped_column(Integer)
    event_key: Mapped[str] = mapped_column(String(200))
    amount: Mapped[int] = mapped_column(Integer)
    free_delta: Mapped[int] = mapped_column(Integer)
    purchased_delta: Mapped[int] = mapped_column(Integer)
    balance_after: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(1000))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CreditPack(Base):
    __tablename__ = 'credit_packs'
    __table_args__ = (CheckConstraint("amount_paise > 0 AND credits > 0 AND currency = 'INR'"),)
    code: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    credits: Mapped[int] = mapped_column(Integer)
    amount_paise: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default='INR')
    first_purchase_only: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class CreditPurchase(Tenant, Base):
    __tablename__ = 'credit_purchases'
    __table_args__ = (UniqueConstraint('user_id', 'idempotency_key'),
        CheckConstraint('amount_paise > 0 AND credits > 0 AND credited >= 0 AND credited <= credits'),
        Index('ix_credit_purchases_pending', 'status', 'checked_at'))
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    idempotency_key: Mapped[str] = mapped_column(String(100))
    pack_code: Mapped[str] = mapped_column(String(80))
    pack_name: Mapped[str] = mapped_column(String(100))
    amount_paise: Mapped[int] = mapped_column(Integer)
    credits: Mapped[int] = mapped_column(Integer)
    first_purchase_only: Mapped[bool] = mapped_column(Boolean, default=False)
    provider_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    payment_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    payment_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default='creating')
    credited: Mapped[int] = mapped_column(Integer, default=0)
    refunded_paise: Mapped[int] = mapped_column(Integer, default=0)
    dispute_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dispute_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    settlement_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# Minimal trusted webhook/worker routing; never exposes journal content or email.
class PurchaseIndex(Base):
    __tablename__ = 'purchase_index'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    provider_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    payment_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


def serialize(obj):
    def scalar(value):
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, datetime):
            return value.isoformat()
        return value
    # Tenant identities are never accepted back from API payloads.
    return {c.name: scalar(getattr(obj, c.name)) for c in obj.__table__.columns if c.name != 'user_id'}


def get_setting(db, key):
    return db.get(Setting, (db.info['user_id'], key))


@contextmanager
def database(user_id=None, system=False):
    if engine is None:
        from fastapi import HTTPException
        raise HTTPException(503, 'The service is being configured. Please try again shortly.')
    with Session(info={'user_id': user_id}) as db:
        try:
            if engine.dialect.name == 'postgresql':
                db.execute(text('SET LOCAL ROLE hakisense_api'))
                db.execute(text("SELECT set_config('app.user_id', :user, true)"), {'user': user_id or ''})
                db.execute(text("SET LOCAL statement_timeout = '20000'"))
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise


@contextmanager
def admin_database(actor_id):
    """Private admin role; RLS policies independently check the active actor membership."""
    with Session(info={'admin_actor': actor_id}) as db:
        try:
            if engine.dialect.name == 'postgresql':
                db.execute(text('SET LOCAL ROLE hakisense_admin'))
                db.execute(text("SELECT set_config('app.actor_id', :actor, true)"), {'actor': actor_id})
                db.execute(text("SET LOCAL statement_timeout = '20000'"))
            member = db.get(AdminMember, actor_id)
            if not member or not member.active:
                from fastapi import HTTPException
                raise HTTPException(403, 'Administrator access is required.')
            db.info['admin_role'] = member.role
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise


def init_db():
    if config.environment != 'test':
        raise RuntimeError('Use versioned migrations to create the production schema.')
    Base.metadata.create_all(engine)
