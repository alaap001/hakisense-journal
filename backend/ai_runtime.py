"""One metered provider boundary for every specialist. No automatic paid retries."""
import asyncio
import json
import time
import math
import logging
import re
import tiktoken
from dataclasses import dataclass
import httpx
from sqlalchemy import select
from .db import database, AIJob, AICall, utcnow
from .config import config
from .ai_pricing import allowance, charge
from .ai_evidence import fingerprint, packed
from .jobs import emit

log = logging.getLogger('hakisense.ai')
_reasoning_required = set()


class WorkflowCancelled(Exception):
    pass


class ProviderFailure(Exception):
    def __init__(self, message, *, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class CapacityExceeded(ProviderFailure):
    """An internal pre-dispatch limit, never a request for customer clarification."""


@dataclass
class HumanInput(Exception):
    kind: str
    question: str


def input_bound(messages):
    # Preflight estimate, not a billing receipt. OpenRouter routes use different native
    # tokenizers; reserve headroom for framing/tokenization and verify every actual receipt.
    # Keep direct context intact; this does not split the evidence into token-sized bins.
    encoding = tiktoken.get_encoding('o200k_base')
    return math.ceil(sum(len(encoding.encode(m['content'], disallowed_special=())) + 16 for m in messages) * 1.15) + 128


def normalize_usage(raw):
    i, o = raw.get('prompt_tokens'), raw.get('completion_tokens')
    if not isinstance(i, int) or not isinstance(o, int) or min(i, o) < 0:
        raise ProviderFailure('Provider usage receipt is incomplete')
    # Reasoning and cached tokens are subsets, not extra charges.
    return {'input_tokens': i, 'output_tokens': o,
            'cached_tokens': (raw.get('prompt_tokens_details') or {}).get('cached_tokens', 0),
            'reasoning_tokens': (raw.get('completion_tokens_details') or {}).get('reasoning_tokens', 0),
            'provider_cost': raw.get('cost')}


async def provider_stream(model_id, messages, route, max_output, on_text, on_id):
    body = {'model': model_id, 'messages': messages, 'stream': True, 'max_tokens': max_output,
            'temperature': route.get('temperature', .2), 'provider': {'require_parameters': True},
            'reasoning': {'enabled': False} if route.get('reasoning_effort', 'low') == 'none' else {'effort': route.get('reasoning_effort', 'low')}}
    if model_id in _reasoning_required and body['reasoning'].get('enabled') is False:
        body['reasoning'] = {'effort': 'low'}
    headers = {'Authorization': 'Bearer ' + config.openrouter_key, 'HTTP-Referer': config.origin, 'X-Title': 'HakiSenseJournal'}
    content, receipt, generation, finish = '', None, None, None
    async with httpx.AsyncClient(timeout=httpx.Timeout(route.get('timeout_seconds', 90), connect=15)) as client:
        for attempt in range(2):
            async with client.stream('POST', 'https://openrouter.ai/api/v1/chat/completions', headers=headers, json=body) as response:
                if response.status_code != 200:
                    await response.aread()
                    try:
                        error = response.json().get('error', {})
                        error_code = error.get('code', 'unknown')
                        reason = str(error.get('message', 'No provider explanation'))[:1000]
                        metadata = error.get('metadata') or {}
                        raw_error = metadata.get('raw')
                        if isinstance(raw_error, str):
                            try:
                                raw_error = json.loads(raw_error)
                            except ValueError:
                                raw_error = None
                        if isinstance(raw_error, dict):
                            nested = raw_error.get('error', raw_error)
                            if isinstance(nested, dict):
                                explanation = nested.get('message') or nested.get('Message')
                                if isinstance(explanation, str):
                                    reason += ': ' + explanation[:1000]
                        if isinstance(metadata.get('provider_name'), str):
                            reason += ' [provider=' + metadata['provider_name'][:100] + ']'
                        reason = reason.replace(config.openrouter_key, '[redacted]') if config.openrouter_key else reason
                        reason = re.sub(r'(?i)(bearer\s+|sk-)[\w-]+', '[redacted]', reason).replace('\n', ' ')
                    except (ValueError, AttributeError):
                        error_code, reason = 'unknown', 'Non-JSON provider error'
                    if (attempt == 0 and response.status_code == 400 and body.get('reasoning', {}).get('enabled') is False
                            and 'reasoning is mandatory' in reason.lower()):
                        # This request was rejected before generation. Only correct this
                        # confirmed parameter error; never replay an uncertain paid call.
                        _reasoning_required.add(model_id)
                        body['reasoning'] = {'effort': 'low'}
                        log.info('ai_provider_parameter_adjusted model=%s reason=mandatory_reasoning', model_id)
                        continue
                    raise ProviderFailure(f'Provider request failed (HTTP {response.status_code}, code {error_code}): {reason}',
                                          status_code=response.status_code)
                data = []
                async for line in response.aiter_lines():
                    if line.startswith('data:'):
                        data.append(line[5:].lstrip())
                        continue
                    if line or not data:
                        continue
                    raw = '\n'.join(data)
                    data = []
                    if raw == '[DONE]':
                        break
                    chunk = json.loads(raw)
                    if chunk.get('error'):
                        raise ProviderFailure('Provider stream failed')
                    if chunk.get('id') and not generation:
                        generation = chunk['id']
                        await on_id(generation)
                    for choice in chunk.get('choices', []):
                        delta = choice.get('delta', {}).get('content')
                        if isinstance(delta, str) and delta:
                            content += delta
                            await on_text(delta)
                        if choice.get('finish_reason'):
                            finish = choice['finish_reason']
                    if chunk.get('usage'):
                        receipt = normalize_usage(chunk['usage'])
                # Usage can arrive after finish_reason. Always read through the final frame.
            break
        if receipt is None and generation:
            response = await client.get('https://openrouter.ai/api/v1/generation', params={'id': generation}, headers=headers)
            if response.status_code == 200:
                info = response.json().get('data', {})
                receipt = normalize_usage({'prompt_tokens': info.get('native_tokens_prompt'),
                    'completion_tokens': info.get('native_tokens_completion'), 'cost': info.get('total_cost')})
    if receipt is None:
        raise ProviderFailure('Provider usage is unavailable; no successful settlement is allowed')
    return content, receipt, generation, finish


class Runtime:
    def __init__(self, user_id, job_id, revision, route, maximum):
        self.user_id, self.job_id, self.revision = user_id, job_id, revision
        self.route, self.maximum = route, maximum

    def active(self, allow_stopping=False):
        with database(self.user_id) as db:
            job = db.get(AIJob, self.job_id)
            if not job or job.status != 'running' or (job.cancel_requested and not allow_stopping) or job.revision != self.revision:
                raise WorkflowCancelled()
            return dict(job.usage)

    async def progress(self, stage, message, **details):
        await asyncio.to_thread(emit, self.user_id, self.job_id, 'status', {'stage': stage, 'message': message, **details}, self.revision)

    def checkpoint(self, state):
        with database(self.user_id) as db:
            job = db.scalar(select(AIJob).where(AIJob.id == self.job_id).with_for_update())
            if not job or job.status != 'running' or job.cancel_requested or job.revision != self.revision:
                raise WorkflowCancelled()
            job.checkpoint, job.heartbeat_at = state, utcnow()

    def prepare_call(self, key, agent, model_id, messages):
        usage = self.active()
        digest = fingerprint(messages)
        with database(self.user_id) as db:
            previous = db.get(AICall, (self.job_id, key))
            if previous:
                if previous.request_hash != digest:
                    raise ProviderFailure('Paid call identity changed')
                if previous.status == 'completed':
                    return previous.response
                raise ProviderFailure('An uncertain paid call cannot be replayed automatically')
            db.add(AICall(job_id=self.job_id, call_key=key, agent=agent, model=model_id, request_hash=digest))
        return None

    def generation(self, key, value):
        with database(self.user_id) as db:
            row = db.get(AICall, (self.job_id, key))
            row.generation_id = value

    def record(self, key, content, receipt, generation, finish):
        with database(self.user_id) as db:
            job = db.scalar(select(AIJob).where(AIJob.id == self.job_id).with_for_update())
            call = db.get(AICall, (self.job_id, key))
            if call.status == 'completed':
                return
            call.response, call.usage, call.generation_id = content, receipt, generation
            call.status = 'completed' if finish == 'stop' and content.strip() else 'incomplete'
            previous = job.usage
            job.usage = {**previous,
                'input_tokens': previous.get('input_tokens', 0) + receipt['input_tokens'],
                'output_tokens': previous.get('output_tokens', 0) + receipt['output_tokens'],
                'cached_tokens': previous.get('cached_tokens', 0) + receipt.get('cached_tokens', 0),
                'reasoning_tokens': previous.get('reasoning_tokens', 0) + receipt.get('reasoning_tokens', 0),
                'calls': previous.get('calls', 0) + 1}
            total = dict(job.usage)
        # Never continue/settle a provider overrun as a successful in-budget result.
        if charge(total['input_tokens'], total['output_tokens']) > self.maximum:
            raise ProviderFailure('Provider exceeded authorized usage')
        if finish != 'stop' or not content.strip():
            raise ProviderFailure(f'Provider returned incomplete output (agent={call.agent}, finish={finish}, '
                                  f'output={receipt["output_tokens"]}, reasoning={receipt.get("reasoning_tokens", 0)}, '
                                  f'answer_characters={len(content)})')

    def fit_checker(self, system, context):
        remaining = allowance(self.maximum)[0] - self.active()['input_tokens']
        def fits(evidence):
            messages = [{'role': 'system', 'content': system},
                        {'role': 'user', 'content': packed({**context, 'evidence': evidence})}]
            return input_bound(messages) <= remaining
        return fits

    async def call(self, agent, key, system, context, *, schema=None, final=False):
        messages = [{'role': 'system', 'content': system}, {'role': 'user', 'content': packed(context)}]
        model_id = self.route['model_id'] if agent == 'writer' else self.route.get('planner_model_id', self.route['model_id'])
        # A saved completed call is safe to reuse even when its usage leaves no room for a new call.
        with database(self.user_id) as db:
            previous = db.get(AICall, (self.job_id, key))
            if previous and previous.status == 'completed' and previous.request_hash == fingerprint(messages):
                return self.parse(previous.response, schema)
        usage = await asyncio.to_thread(self.active)
        ins, outs = allowance(self.maximum)
        bound = input_bound(messages)
        if usage['input_tokens'] + bound > ins:
            raise CapacityExceeded('Input preflight exceeded the remaining allowance')
        # Planning is a small intent/selection task. Keep most output for the answer.
        reserve = 0 if final else outs * 3 // 4
        available = outs - usage['output_tokens'] - reserve
        if available < 256:
            raise CapacityExceeded('Output allowance exhausted')
        output = min(available, self.route.get('max_output_tokens', 4000))
        saved = await asyncio.to_thread(self.prepare_call, key, agent, model_id, messages)
        if saved is not None:
            return self.parse(saved, schema)
        pending, last_flush = '', time.monotonic()
        async def on_text(text):
            nonlocal pending, last_flush
            if final:
                pending += text
            if time.monotonic()-last_flush >= .2:
                await asyncio.to_thread(self.active, True)
                if pending:
                    await asyncio.to_thread(emit, self.user_id, self.job_id, 'text', {'delta': pending}, self.revision)
                    pending = ''
                last_flush = time.monotonic()
        async def on_id(value):
            await asyncio.to_thread(self.generation, key, value)
        call_route = {**self.route, 'reasoning_effort': 'none'} if agent == 'coordinator' else self.route
        log.info('ai_call_started job_id=%s agent=%s model=%s input_estimate=%s output_ceiling=%s', self.job_id, agent, model_id, bound, output)
        content, receipt, generation, finish = await provider_stream(model_id, messages, call_route, output, on_text, on_id)
        await asyncio.to_thread(self.record, key, content, receipt, generation, finish)
        log.info('ai_call_completed job_id=%s agent=%s generation_id=%s input=%s output=%s finish=%s',
                 self.job_id, agent, generation, receipt['input_tokens'], receipt['output_tokens'], finish)
        if pending:
            await asyncio.to_thread(emit, self.user_id, self.job_id, 'text', {'delta': pending}, self.revision)
        return self.parse(content, schema)

    @staticmethod
    def parse(content, schema):
        if schema:
            value = content.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip()
            return schema.model_validate_json(value).model_dump()
        return content
