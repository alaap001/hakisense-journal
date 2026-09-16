"""The planner selects evidence; the answer agent reads the resulting facts."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .schemas import FilterInput, QueryPlan


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid')

    @field_validator('*', mode='before')
    @classmethod
    def optional_nulls(cls, value, info):
        # Models commonly express an unused optional field as null. Treat it as
        # omitted, while still rejecting null for required fields and bad values.
        field = cls.model_fields[info.field_name]
        if value is None and not field.is_required():
            return field.get_default(call_default_factory=True)
        return value


class TradeSelection(Contract):
    count: int | None = Field(default=None, gt=0, description='Only when the user requests a number of trades, e.g. latest 3. Null means all matches.')
    order: Literal['newest', 'oldest'] = 'newest'
    time_field: Literal['entry_time', 'exit_time'] = 'entry_time'
    offset: int = Field(default=0, ge=0, description='Skip this many matching trades, e.g. 3 for the previous three.')


class EvidenceFilters(FilterInput, Contract):
    model_config = ConfigDict(extra='forbid')
    status: Literal['', 'Open', 'Closed', 'Partial', 'Canceled'] = ''
    side: Literal['', 'Long', 'Short'] = ''

    @field_validator('status', 'side', mode='before')
    @classmethod
    def canonical_case(cls, value):
        return value.strip().capitalize() if isinstance(value, str) else value


class EvidenceRequest(Contract):
    kind: Literal['metrics', 'groups', 'checks', 'records', 'sequence', 'notes_search']
    purpose: str = Field(min_length=1, max_length=500)
    filters: EvidenceFilters = Field(default_factory=EvidenceFilters)
    dimension: QueryPlan.model_fields['dimension'].annotation = 'setup'
    metric: QueryPlan.model_fields['metric'].annotation = 'net_pnl'
    trade_ids: list[str] = Field(default_factory=list)
    include_notes: bool = False
    include_rules: bool = False
    search: str = Field(default='', max_length=200)
    check_id: str = ''
    selection: TradeSelection = Field(default_factory=TradeSelection)


class Plan(Contract):
    task: str = Field(min_length=1, max_length=1000)
    analysis: Literal['review', 'calculation'] = Field(default='review', description='Review means interpreting trades, patterns, habits or performance and requires individual records with notes. Calculation is ONLY a specific numeric fact, table or chart without qualitative interpretation.')
    scope: EvidenceFilters = Field(default_factory=EvidenceFilters)
    coverage: Literal['none', 'aggregate', 'targeted', 'exhaustive'] = 'aggregate'
    clarification: str = Field(default='', max_length=1000)
    requests: list[EvidenceRequest] = Field(default_factory=list)
    selection: TradeSelection = Field(default_factory=TradeSelection, description='The cohort for the whole question. All tools use this same selection.')
