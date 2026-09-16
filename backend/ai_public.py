"""Customer-facing AI responses. Operational diagnostics are available only in Admin."""
PROGRESS = {
    'queued': 'Your review will start shortly…',
    'coordinate': 'Understanding your question…',
    'gather': 'Reviewing the relevant trades…',
    'investigate': 'Reviewing the relevant trades…',  # Historical event replay.
    'review': 'Preparing your answer…',
    'write': 'Preparing your answer…',
    'stopping': 'Stopping your review…',
}


def result(value):
    if value is None:
        return None
    return {key: value[key] for key in ('thread_id', 'answer', 'chart', 'credits', 'job_id') if key in value}


def metadata(value):
    return {key: value[key] for key in ('chart', 'mode', 'job_id', 'credits') if key in (value or {})}


def pause(value):
    if not value:
        return None
    if value['kind'] != 'clarification':
        return {'kind': 'retry', 'question': 'This review was interrupted. Resume to try again.'}
    return {'kind': 'clarification', 'question': value['question']}


def event(kind, value):
    if kind == 'status':
        return {'stage': value.get('stage'), 'message': PROGRESS.get(value.get('stage'), 'Working on your review…')}
    if kind == 'pause':
        return pause(value)
    if kind == 'text':
        return {'delta': value.get('delta', '')}
    if kind == 'done':
        return {key: value[key] for key in ('status', 'credits') if key in value}
    # Old usage events retain their cursor but never expose their payload.
    return {}
