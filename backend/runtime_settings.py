"""Validated product configuration. PostgreSQL is the runtime source of truth."""
from typing import Literal
from urllib.parse import urlsplit
from pydantic import BaseModel, Field, ConfigDict, field_validator
from fastapi import HTTPException
from .config import config


class ProductSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    brand_name: str = Field(default='HakiSense', min_length=1, max_length=60)
    support_email: str = Field(default='', max_length=200)
    legal_business_name: str = Field(default='', max_length=200)
    legal_business_address: str = Field(default='', max_length=1000)
    terms_url: str = Field(default='', max_length=500)
    privacy_url: str = Field(default='', max_length=500)
    refund_url: str = Field(default='', max_length=500)
    ai_enabled: bool = True
    checkout_enabled: bool = False
    maintenance_enabled: bool = False
    maintenance_message: str = Field(default='We are making improvements. Please try again shortly.', max_length=500)
    announcement: str = Field(default='', max_length=500)
    api_requests_per_minute: int = Field(default=240, ge=30, le=1200)
    ai_requests_per_minute: int = Field(default=12, ge=1, le=60)
    report_trade_limit: int = Field(default=20000, ge=100, le=50000)
    monthly_free_credits: int = Field(default=50, ge=0, le=100000)
    playbook_creation_credits: int = Field(default=1, ge=0, le=1000)
    advanced_credit_multiplier: int = Field(default=3, ge=1, le=20)
    reference_credit_paise: int = Field(default=100, ge=1, le=100000)

    @field_validator('terms_url', 'privacy_url', 'refund_url')
    @classmethod
    def https_url(cls, value):
        if value:
            u = urlsplit(value)
            if config.environment in ('development', 'test') and u.scheme in ('http', 'https') and u.hostname in ('localhost', '127.0.0.1'):
                return value
            if u.scheme != 'https' or not u.hostname or u.username:
                raise ValueError('Use a complete HTTPS URL.')
        return value

    @field_validator('support_email')
    @classmethod
    def email(cls, value):
        if value and ('@' not in value or '\n' in value or '\r' in value):
            raise ValueError('Enter a valid support email.')
        return value


def defaults():
    origin = config.origin.rstrip('/')
    return ProductSettings(
        support_email=config.support_email or 'contact@hakisense.in',
        legal_business_name=config.legal_name or 'HakiSense',
        legal_business_address=config.legal_address or 'Sector 14, Sonepat, Haryana',
        terms_url=config.terms_url or f'{origin}/terms',
        privacy_url=config.privacy_url or f'{origin}/privacy',
        refund_url=config.refund_url or f'{origin}/refunds',
        checkout_enabled=config.checkout_enabled,
    ).model_dump()


def settings(db):
    from .db import PlatformConfig
    row = db.get(PlatformConfig, 'product')
    base = defaults()
    if not row:
        return ProductSettings.model_validate(base)
    merged = {**base}
    for k, v in row.value.items():
        if v not in ('', None):
            merged[k] = v
    if config.checkout_enabled:
        merged['checkout_enabled'] = True
    return ProductSettings.model_validate(merged)


def checkout_blockers(value):
    missing=[]
    if not value.checkout_enabled:missing.append('Enable recharge checkout in Product settings.')
    if not config.razorpay_key:missing.append('Set RAZORPAY_KEY_ID on the API service.')
    if not config.razorpay_secret:missing.append('Set RAZORPAY_KEY_SECRET on the API service.')
    # Local test checkout can verify synchronously without a public webhook or merchant policies.
    if config.razorpay_key.startswith('rzp_test_') and (config.environment in ('development','test') or config.razorpay_allow_test_checkout):
        return missing
    if not config.razorpay_webhook_secret:missing.append('Set RAZORPAY_WEBHOOK_SECRET to match the Razorpay webhook secret.')
    for field,label in (('support_email','support email'),('legal_business_name','legal business name'),
        ('legal_business_address','legal business address'),('terms_url','Terms URL'),
        ('privacy_url','Privacy URL'),('refund_url','Refund policy URL')):
        if not getattr(value,field):missing.append('Set '+label+' in Product settings.')
    return missing


def checkout_ready(value):
    return not checkout_blockers(value)


def routing(db, task_code, tier):
    from .db import AIRoute, AIModel
    row = db.get(AIRoute, (task_code, tier))
    if not row or not row.enabled:
        raise HTTPException(503, 'This AI task is temporarily unavailable. No credits were used.')
    for model_id in (row.model_id, row.planner_model_id or row.model_id):
        model = db.get(AIModel, model_id)
        if not model or not model.enabled:
            raise HTTPException(503, 'This AI model is temporarily unavailable. No credits were used.')
    return {'model_id': row.model_id, 'planner_model_id': row.planner_model_id or row.model_id,
            'max_output_tokens': row.max_output_tokens, 'timeout_seconds': row.timeout_seconds,
            'temperature': row.temperature, 'reasoning_effort': row.reasoning_effort,
            'instructions': row.instructions, 'task_code': task_code, 'tier': tier}
