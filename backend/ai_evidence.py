"""Read-only, tenant-scoped evidence tools. Models never execute SQL or arbitrary code."""
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from .db import Trade, Account, database
from .analytics import enrich, apply_filters, statistics, group_rows, coach_checks
from .markets import IST
from .ai_contracts import TradeSelection, EvidenceRequest

NUMERIC_FIELDS = (
    'id', 'account_id', 'symbol', 'asset_type', 'side', 'status', 'entry_price', 'exit_price',
    'mark_price', 'quantity', 'closed_quantity', 'multiplier', 'entry_time', 'exit_time',
    'commission', 'fees', 'stop_loss', 'target_price', 'risk_amount', 'planned_entry',
    'setup', 'emotion', 'rating', 'tags', 'mfe', 'mae',
)
DETAIL_FIELDS = ('exchange', 'segment', 'expiry', 'strike', 'option_type', 'lot_size')
RECORD_FIELDS = ('id', 'symbol', 'asset_type', 'side', 'status', 'entry_time', 'exit_time',
                 'entry_price', 'exit_price', 'planned_entry', 'stop_loss', 'target_price', 'mark_price',
                 'quantity', 'closed_quantity', 'remaining_quantity', 'multiplier', 'net_pnl', 'gross_pnl', 'unrealized_pnl',
                 'risk', 'r_multiple', 'realized_fees', 'total_fees', 'slippage', 'setup', 'emotion',
                 'rating', 'tags', 'hold_minutes', 'mfe', 'mae')


def packed(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), default=str)


def fingerprint(value):
    return hashlib.sha256(packed(value).encode()).hexdigest()


def scoped(query, filters):
    f = filters.model_dump() if hasattr(filters, 'model_dump') else filters
    for key in ('account_id', 'asset_type', 'side', 'status', 'setup', 'emotion'):
        if f.get(key):
            query = query.where(getattr(Trade, key) == f[key])
    if f.get('symbol'):
        query = query.where(Trade.symbol.contains(f['symbol'].upper(), autoescape=True))
    for key, inclusive in (('start', True), ('end', False)):
        if f.get(key):
            date = datetime.strptime(f[key], '%Y-%m-%d').replace(tzinfo=IST)
            if not inclusive:
                date += timedelta(days=1)
            query = query.where(Trade.entry_time >= date.astimezone(timezone.utc) if inclusive else Trade.entry_time < date.astimezone(timezone.utc))
    if f.get('start') and f.get('end') and f['start'] > f['end']:
        raise ValueError('The start date must precede the end date')
    return query


def read_rows(user_id, scope, request, cohort_ids=None):
    fields = list(NUMERIC_FIELDS)
    if request.kind in ('records', 'notes_search', 'sequence'):
        fields += list(DETAIL_FIELDS)
        if request.include_notes or request.kind == 'notes_search':
            fields += ['notes']
        if request.include_rules:
            fields += ['playbook_snapshot']
    # Explicit tenant predicate also protects column projections independently of the ORM hook.
    query = select(*(getattr(Trade, k) for k in fields)).where(Trade.user_id == user_id)
    query = scoped(scoped(query, scope), request.filters)
    if cohort_ids is not None:
        query = query.where(Trade.id.in_(cohort_ids))
    if request.trade_ids:
        query = query.where(Trade.id.in_(request.trade_ids))
    if request.kind == 'notes_search' or request.search:
        if not request.search.strip():
            raise ValueError('A notes search needs a specific phrase')
        query = query.where(Trade.notes.icontains(request.search, autoescape=True))
    with database(user_id) as db:
        accounts = list(db.scalars(select(Account)))
        names = {a.id: a.name for a in accounts}
        selection = request.selection
        time_column = getattr(Trade, selection.time_field)
        if selection.time_field == 'exit_time':
            query = query.where(time_column.is_not(None))
        ordering = (time_column.desc(), Trade.id.desc()) if selection.order == 'newest' else (time_column.asc(), Trade.id.asc())
        query = query.order_by(*ordering)
        # Derived outcomes/tags/checks must be evaluated before selecting a cohort.
        # Only numeric columns are read for that step; unrelated notes never enter Python.
        derived = any(f.get('outcome') or f.get('tag') for f in (scope, request.filters.model_dump())) or request.check_id
        if derived and selection.count is not None:
            numeric_request = request.model_copy(update={'kind': 'metrics', 'include_notes': False, 'include_rules': False,
                'selection': TradeSelection(time_field=selection.time_field, order=selection.order), 'check_id': ''})
            candidates, _ = read_rows(user_id, scope, numeric_request, cohort_ids)
            if request.check_id:
                check = next((c for c in coach_checks(candidates) if c['id'] == request.check_id), None)
                if check is None:
                    raise ValueError('Unknown review check')
                candidates = [r for r in candidates if r['id'] in set(check['trade_ids'])]
            selected = candidates[selection.offset:selection.offset + selection.count]
            query = query.where(Trade.id.in_([r['id'] for r in selected]))
        elif selection.count is not None:
            query = query.offset(selection.offset).limit(selection.count)
        records = db.execute(query.execution_options(yield_per=1000)).mappings()
        rows = [enrich({**dict(t), 'account_name': names.get(t['account_id'], '')}) for t in records]
        rows = apply_filters(apply_filters(rows, scope), request.filters)
        account_id = scope.get('account_id') or request.filters.account_id
        balance = sum(a.initial_balance for a in accounts if not account_id or a.id == account_id)
    return rows, balance


def select_cohort(user_id, scope, selection):
    """Resolve a requested count once, shared by metrics and details in the graph."""
    request = EvidenceRequest(kind='metrics', purpose='Select requested trades', selection=selection)
    rows, _ = read_rows(user_id, scope, request)
    return [row['id'] for row in rows]


def execute(user_id, scope, request, cohort_ids=None):
    rows, balance = read_rows(user_id, scope, request, cohort_ids)
    source_ids = [t['id'] for t in rows]
    if request.check_id:
        check = next((c for c in coach_checks(rows) if c['id'] == request.check_id), None)
        if check is None:
            raise ValueError('Unknown review check')
        if request.kind in ('records', 'notes_search', 'sequence'):
            ids = set(check['trade_ids'])
            rows = [r for r in rows if r['id'] in ids]
            source_ids = [t['id'] for t in rows]
    population = {'scope': scope, 'filters': request.filters.model_dump(), 'ids': request.trade_ids, 'search': request.search,
                  'check': request.check_id, 'selection': request.selection.model_dump(), 'cohort_ids': cohort_ids}
    metadata = {'scope': scope, 'additional_filters': request.filters.model_dump(), 'matched': len(rows),
                'population_key': fingerprint(population),
                'numeric_hash': fingerprint([{k: row.get(k) for k in NUMERIC_FIELDS} for row in rows]),
                'date_basis': 'entry date, Asia/Kolkata; realized P&L uses closed quantities and allocated fees',
                'as_of': datetime.now(timezone.utc).isoformat(), 'source_hash': fingerprint(rows),
                'missing_notes': sum(not t.get('notes', '').strip() for t in rows) if 'notes' in (rows[0] if rows else {}) else None}
    if request.kind == 'metrics':
        payload = {'metrics': statistics(rows, balance)['metrics']}
    elif request.kind == 'groups':
        groups = group_rows(rows, request.dimension)
        payload = {'dimension': request.dimension, 'metric': request.metric,
                   'rows': [{k: r[k] for k in dict.fromkeys(('name', 'count', 'net_pnl', request.metric))} for r in groups]}
    elif request.kind == 'checks':
        checks = coach_checks(rows)
        payload = {'checks': [{k: v for k, v in c.items() if k != 'trade_ids'} for c in checks if not request.check_id or c['id'] == request.check_id]}
    else:
        columns = list(RECORD_FIELDS) + list(DETAIL_FIELDS)
        if request.include_notes or request.kind == 'notes_search':
            columns += ['notes']
        books = {}
        if request.include_rules:
            columns += ['rule_ref']
            for row in rows:
                book = row.get('playbook_snapshot') or {}
                ref = fingerprint(book)[:16]
                books[ref] = book
                row['rule_ref'] = ref
        payload = {'columns': columns, 'rows': [[r.get(k) for k in columns] for r in rows], 'rules': books,
                   'metrics': statistics(rows, balance)['metrics']}
    return {'kind': request.kind, 'purpose': request.purpose, 'metadata': metadata, 'data': payload,
            'source_ids': source_ids if request.kind in ('records', 'notes_search', 'sequence') else [],
            'source_hashes': {t['id']: fingerprint({'notes': t.get('notes', ''), 'rules': t.get('playbook_snapshot', {})}) for t in rows} if request.include_notes else {}}


def model_artifact(artifact):
    # Hashes and audit metadata remain in the checkpoint, never repeated in model context.
    return {'kind': artifact['kind'], 'purpose': artifact['purpose'], 'matched': artifact['metadata']['matched'],
            'data': artifact['data']}


def compact_artifact(artifact):
    """Lossless projection: omit empty columns and send repeated notes only once."""
    result = deepcopy(model_artifact(artifact))
    data = result['data']
    if 'columns' not in data:
        return result
    keep = [i for i, _ in enumerate(data['columns']) if any(row[i] not in (None, '', [], {}) for row in data['rows'])]
    data['columns'] = [data['columns'][i] for i in keep]
    data['rows'] = [[row[i] for i in keep] for row in data['rows']]
    if 'notes' in data['columns']:
        idx = data['columns'].index('notes')
        notes, refs = {}, {}
        for row in data['rows']:
            note = row[idx]
            if not note:
                continue
            if note not in refs:
                refs[note] = 'n' + str(len(refs) + 1)
                notes[refs[note]] = note
            row[idx] = refs[note]
        data['columns'][idx] = 'note_ref'
        data['notes'] = notes
    return result


def sample_records(artifact, count=80):
    """Keep varied examples, not just recent trades or the biggest winners.

    Called only if the complete evidence cannot fit. Metrics retain their full
    cohort denominator. The sample is for qualitative examples, never estimates.
    """
    result = deepcopy(artifact)
    data = result['data']
    if 'columns' not in data or len(data['rows']) <= count:
        return result
    rows, columns = data['rows'], data['columns']
    def value(i, key, default=None):
        return rows[i][columns.index(key)] if key in columns else default
    chosen = set()
    # Retain both ends of the period and extreme realized outcomes.
    for indices in (range(min(4, len(rows))), range(max(0, len(rows)-4), len(rows)),
                    sorted(range(len(rows)), key=lambda i: value(i, 'net_pnl', 0) or 0)[:4],
                    sorted(range(len(rows)), key=lambda i: value(i, 'net_pnl', 0) or 0)[-4:]):
        chosen.update(indices)
    groups = {}
    for i in range(len(rows)):
        pnl = value(i, 'net_pnl', 0) or 0
        outcome = 'unrealized' if not value(i, 'closed_quantity', 0) else 'win' if pnl > 0 else 'loss' if pnl < 0 else 'breakeven'
        groups.setdefault((outcome, value(i, 'setup'), value(i, 'emotion')), []).append(i)
    # Round-robin across outcome/setup/emotion groups and spread over their dates.
    queues = []
    for indices in groups.values():
        size = min(count, len(indices))
        queues.append([indices[round(j*(len(indices)-1)/max(1, size-1))] for j in range(size)])
    for rank in range(count):
        for indices in queues:
            if rank < len(indices) and len(chosen) < count:
                chosen.add(indices[rank])
    data['rows'] = [rows[i] for i in sorted(chosen)]
    for column, mapping in (('note_ref', 'notes'), ('rule_ref', 'rules')):
        if column in columns:
            refs = {row[columns.index(column)] for row in data['rows']}
            data[mapping] = {k: v for k, v in data.get(mapping, {}).items() if k in refs}
    result['detail'] = 'sample; complete cohort metrics, selected individual records and notes'
    result['record_coverage'] = {'total': len(rows), 'included': len(data['rows']),
                                 'selection': 'period endpoints, extreme results, and examples across outcomes, setups and recorded emotions; not a statistical sample'}
    return result


def answer_evidence(artifacts, fits):
    """Keep complete records when they fit; retain detailed examples if they do not.

    There is no fixed 80-trade cap. It is the fallback detail target for large
    reviews, alongside metrics for every match. Oversized notes use labelled
    excerpts, without paid compression calls or customer limit prompts.
    """
    complete = {key: {**compact_artifact(a), 'detail': 'complete'} for key, a in artifacts.items()}
    def representations(evidence):
        return {k: ('sample_excerpts' if 'excerpts' in a['detail'] else 'sample') if 'record_coverage' in a
                else 'excerpts' if 'excerpts' in a['detail'] else 'complete' for k, a in evidence.items()}
    if fits(complete):
        return complete, representations(complete)

    detailed = {key: sample_records(a) for key, a in complete.items()}
    if fits(detailed):
        return detailed, representations(detailed)

    def excerpts(size):
        result = deepcopy(detailed)
        for a in result.values():
            data = a['data']
            if 'columns' not in data:
                continue
            a['detail'] = 'excerpts; complete numerical totals, partial notes and rules'
            def clip(value):
                if len(value) <= size:
                    return value
                half = size // 2
                return value[:half] + '\n[excerpt omitted]\n' + (value[-half:] if half else '')
            data['notes'] = {k: clip(v) for k, v in data.get('notes', {}).items()}
            data['rules'] = {k: clip(packed(v)) for k, v in data.get('rules', {}).items()}
        return result

    minimum = excerpts(0)
    if fits(minimum):
        # Choose the largest uniform excerpt size that fits, retaining every row.
        low, high = 0, max((len(packed(a['data'])) for a in detailed.values()), default=0)
        best = minimum
        while low <= high:
            mid = (low + high) // 2
            candidate = excerpts(mid)
            if fits(candidate):
                best, low = candidate, mid + 1
            else:
                high = mid - 1
        return best, representations(best)

    summary = {}
    for key, a in artifacts.items():
        if a['kind'] in ('records', 'sequence', 'notes_search'):
            summary[key] = {'kind': 'metrics', 'purpose': a['purpose'], 'matched': a['metadata']['matched'],
                'detail': 'summary; complete numerical totals, individual records and notes not reviewed',
                'data': {'metrics': a['data']['metrics']}}
        else:
            summary[key] = complete[key]
    return summary, {k: 'summary' if a['kind'] in ('records', 'sequence', 'notes_search') else 'complete' for k, a in artifacts.items()}
