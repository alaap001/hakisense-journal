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

    @field_validator('terms_url', 'privacy_url', 'refund_url')
    @classmethod
    def https_url(cls, value):
        if value and (urlsplit(value).scheme != 'https' or not urlsplit(value).hostname or urlsplit(value).username):
            raise ValueError('Use a complete HTTPS URL.')
        return value

    @field_validator('support_email')
    @classmethod
    def email(cls, value):
        if value and ('@' not in value or '\n' in value or '\r' in value):
            raise ValueError('Enter a valid support email.')
        return value


def defaults():
    return ProductSettings(support_email=config.support_email, legal_business_name=config.legal_name,
        legal_business_address=config.legal_address, terms_url=config.terms_url, privacy_url=config.privacy_url,
        refund_url=config.refund_url, checkout_enabled=config.checkout_enabled).model_dump()


def settings(db):
    from .db import PlatformConfig
    row = db.get(PlatformConfig, 'product')
    return ProductSettings.model_validate(row.value if row else defaults())


def checkout_ready(value):
    return bool(value.checkout_enabled and config.razorpay_key and config.razorpay_secret and config.razorpay_webhook_secret
                and value.support_email and value.legal_business_name and value.legal_business_address
                and value.terms_url and value.privacy_url and value.refund_url)


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
