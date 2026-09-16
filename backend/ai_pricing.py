"""Versioned whole-workflow token buckets. Provider currency prices do not set credits."""
VERSION = 'workflow-buckets-v1'
INPUT_LIMIT = 100_000
OUTPUT_LIMIT = 16_000
BUCKETS = (
    (8_000, 2_000, 1), (16_000, 4_000, 2), (32_000, 6_000, 3),
    (64_000, 8_000, 4), (128_000, 16_000, 7),
)


def charge(input_tokens, output_tokens):
    if min(input_tokens, output_tokens) < 0:
        raise ValueError('Token counts cannot be negative')
    if input_tokens > INPUT_LIMIT or output_tokens > OUTPUT_LIMIT:
        raise ValueError('Workflow token limit exceeded')
    if input_tokens == output_tokens == 0:
        return 0
    return next(cost for ins, outs, cost in BUCKETS if input_tokens <= ins and output_tokens <= outs)


def allowance(max_credits):
    fitting = [(min(ins, INPUT_LIMIT), outs) for ins, outs, cost in BUCKETS if cost <= max_credits]
    if not fitting:
        raise ValueError('Choose a credit limit of 1, 2, 3, 4 or 7')
    return fitting[-1]


def policy():
    return {'version': VERSION, 'input_limit': INPUT_LIMIT, 'output_limit': OUTPUT_LIMIT,
            'buckets': [{'input_tokens': i, 'output_tokens': o, 'credits': c} for i, o, c in BUCKETS],
            'min_credits': 1, 'max_credits': 7,
            'description': 'The smallest bucket covering total input AND output across all agents. Same buckets for Standard and Advanced. Cached input counts as input; reasoning is included in output. No per-agent rounding.'}


def public_policy():
    return {'min_credits': 1, 'max_credits': 7, 'description': 'Reviews cost 1–7 credits based on the work needed.'}
