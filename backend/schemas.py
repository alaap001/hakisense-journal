from datetime import datetime, timezone
from typing import Literal, Any
from .markets import IST, EXCHANGES, SEGMENTS
from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator

ASSETS = ['Stocks', 'Options', 'Futures', 'Crypto', 'Indices']


class AccountInput(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    name: str = Field(min_length=1, max_length=100)
    broker: str = Field(default='Other / manual', max_length=100)
    currency: Literal['INR'] = 'INR'
    initial_balance: float = Field(default=0, ge=0)
    color: str = Field(default='#a6d96a', pattern=r'^#[0-9a-fA-F]{6}$')


class TradeInput(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra='ignore')
    account_id: str
    symbol: str = Field(min_length=1, max_length=40)
    asset_type: Literal['Stocks', 'Options', 'Futures', 'Crypto', 'Indices'] = 'Stocks'
    exchange: Literal['NSE', 'BSE', 'MCX', 'Crypto'] = 'NSE'
    segment: str = Field(default='Equity', max_length=50)
    expiry: str | None = None
    strike: float | None = Field(default=None, gt=0)
    option_type: Literal['CE', 'PE'] | None = None
    lot_size: int | None = Field(default=None, ge=1, le=1000000)
    side: Literal['Long', 'Short'] = 'Long'
    status: Literal['Open', 'Closed', 'Partial', 'Canceled'] = 'Closed'
    entry_price: float = Field(gt=0)
    exit_price: float | None = Field(default=None, ge=0)
    mark_price: float | None = Field(default=None, ge=0)
    quantity: float = Field(gt=0)
    closed_quantity: float = Field(default=0, ge=0)
    multiplier: float = Field(default=1, gt=0)
    entry_time: str
    exit_time: str | None = None
    commission: float = Field(default=0, ge=0)
    fees: float = Field(default=0, ge=0)
    stop_loss: float | None = Field(default=None, ge=0)
    target_price: float | None = Field(default=None, ge=0)
    risk_amount: float | None = Field(default=None, gt=0)
    planned_entry: float | None = Field(default=None, ge=0)
    playbook_id: str | None = Field(default=None, max_length=100)
    setup: str = Field(default='Uncategorized', max_length=100)
    emotion: str = Field(default='Neutral', max_length=50)
    rating: int = Field(default=3, ge=1, le=5)
    notes: str = Field(default='', max_length=10000)
    tags: list[str] = Field(default_factory=list, max_length=30)
    attributes: dict[str, Any] = Field(default_factory=dict)
    mfe: float | None = Field(default=None, ge=0)
    mae: float | None = Field(default=None, ge=0)

    @field_validator('symbol')
    @classmethod
    def symbol_upper(cls, value):
        value = value.strip().upper()
        if not value:
            raise ValueError('Symbol cannot be blank')
        return value

    @field_validator('entry_time', 'exit_time')
    @classmethod
    def valid_date(cls, value):
        if not value:
            return None
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        # Unzoned Indian broker exports and form input are interpreted as IST.
        return dt.replace(tzinfo=dt.tzinfo or IST).astimezone(timezone.utc).isoformat()

    @model_validator(mode='after')
    def check_position(self):
        import json
        if len(json.dumps(self.attributes)) > 16000 or any(len(t) > 100 for t in self.tags):
            raise ValueError('Custom attributes or tags exceed the allowed size')
        if self.segment not in SEGMENTS:
            raise ValueError('Choose a supported market segment')
        if self.asset_type == 'Crypto' and self.exchange != 'Crypto':
            raise ValueError('Crypto trades require the Crypto exchange')
        if self.asset_type in ('Options', 'Futures') and self.exchange in ('NSE', 'BSE'):
            if not self.lot_size or not self.expiry:
                raise ValueError('Indian derivatives require the contract expiry and applicable lot size')
            if self.multiplier != 1 or self.quantity % self.lot_size != 0:
                raise ValueError('Enter Indian derivative quantity in units (a whole number of lots), with multiplier 1')
            if self.status == 'Partial' and self.closed_quantity % self.lot_size != 0:
                raise ValueError('Closed quantity must be a whole number of contract lots')
            if self.asset_type == 'Options' and (not self.strike or not self.option_type):
                raise ValueError('Options require strike and CE/PE')
        if self.expiry:
            self.expiry = datetime.fromisoformat(self.expiry).date().isoformat()
        if not self.entry_time:
            raise ValueError('Entry time is required')
        if self.status == 'Closed':
            self.closed_quantity = self.quantity
        elif self.status in ('Open', 'Canceled'):
            self.closed_quantity = 0
            self.exit_price = None
            self.exit_time = None
        elif not 0 < self.closed_quantity < self.quantity:
            raise ValueError('A partial trade needs closed quantity between zero and total quantity')
        if self.status in ('Closed', 'Partial') and (self.exit_price is None or not self.exit_time):
            raise ValueError('Closed and partial trades require an exit price and exit time')
        if self.exit_time and self.exit_time < self.entry_time:
            raise ValueError('Exit time cannot precede entry time')
        return self


class FilterInput(BaseModel):
    account_id: str = ''
    start: str = ''
    end: str = ''
    symbol: str = ''
    asset_type: str = ''
    side: str = ''
    status: str = ''
    setup: str = ''
    emotion: str = ''
    tag: str = ''
    outcome: Literal['', 'win', 'loss', 'breakeven'] = ''


class QueryPlan(BaseModel):
    dimension: Literal['symbol', 'setup', 'emotion', 'asset_type', 'side', 'weekday', 'hour', 'month', 'account', 'tag', 'hold_bucket', 'rating'] = 'symbol'
    metric: Literal['net_pnl', 'count', 'win_rate', 'avg_pnl', 'profit_factor', 'fees', 'avg_r'] = 'net_pnl'
    filters: FilterInput = Field(default_factory=FilterInput)


class AIRequest(BaseModel):
    model_tier: Literal['standard', 'advanced'] = 'standard'
    expected_credits: int | None = Field(default=None, ge=0, le=100000)
    message: str = Field(min_length=1, max_length=12000)
    thread_id: str | None = None
    mode: Literal['chat', 'query', 'coach', 'daily', 'summary', 'trade_note'] = 'chat'
    filters: FilterInput = Field(default_factory=FilterInput)
    trade_id: str | None = None
    pricing_version: str | None = None
    max_credits: Literal[1, 2, 3, 4, 7] | None = None
    check_id: str | None = Field(default=None, max_length=50)


class AIContinue(BaseModel):
    revision: int = Field(ge=0)
    answer: str = Field(default='', max_length=12000)
    max_credits: Literal[1, 2, 3, 4, 7] | None = None


class AINoteAppend(BaseModel):
    job_id: str
    expected_notes: str = Field(max_length=10000)
    draft: str = Field(min_length=1, max_length=10000)


class RecordInput(BaseModel):
    expected_credits: int | None = Field(default=None, ge=0, le=1000)
    data: dict[str, Any]

    @field_validator('data')
    @classmethod
    def bounded_data(cls, value):
        import json
        if len(json.dumps(value)) > 200000:
            raise ValueError('Record exceeds the allowed size')
        return value


class PlaybookData(BaseModel):
    model_config = ConfigDict(extra='ignore', strict=True)
    title: str = Field(min_length=1,max_length=100)
    description: str = Field(default='',max_length=4000)
    checklist: list[str] = Field(default_factory=list,max_length=100)

    @field_validator('title')
    @classmethod
    def title_text(cls,value):
        if not value.strip():raise ValueError('Title is required')
        return value.strip()

    @field_validator('checklist')
    @classmethod
    def rules(cls,value):
        if any(not x.strip() or len(x)>500 for x in value):raise ValueError('Each rule must contain 1–500 characters')
        return [x.strip() for x in value]
