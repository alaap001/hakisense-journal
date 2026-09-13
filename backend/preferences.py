"""User settings stored in the existing, user-scoped Setting records."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class Preferences(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    currency: Literal['INR'] = 'INR'
    timezone: Literal['Asia/Kolkata'] = 'Asia/Kolkata'
    language: Literal['en'] = 'en'
    landing_page: Literal['/overview', '/trades', '/calendar', '/analytics', '/notebook'] = '/overview'
    default_account_id: str | None = Field(default=None, min_length=1, max_length=64)
    date_range: Literal['all', '7', '30', '90', '365'] = 'all'
    reduce_motion: bool = False
    compact_tables: bool = False


class PreferencesInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    data: Preferences


class ProfileDetails(BaseModel):
    model_config = ConfigDict(extra='forbid')
    display_name: str = Field(min_length=1, max_length=100)

    @field_validator('display_name', mode='before')
    @classmethod
    def trim_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class ProfileInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    data: ProfileDetails


def effective_preferences(value, account_ids):
    """Old partial settings and removed accounts must not prevent sign-in."""
    result = Preferences().model_dump()
    for key, candidate in (value.items() if isinstance(value, dict) else []):
        if key not in result:
            continue
        try:
            result = Preferences.model_validate({**result, key: candidate}).model_dump()
        except ValidationError:
            continue
    if result['default_account_id'] not in account_ids:
        result['default_account_id'] = None
    return result
