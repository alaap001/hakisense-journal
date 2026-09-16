"""One opt-in live 90-trade review; synthetic data and an isolated local database."""
import asyncio
import json
import os
import sys
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if '--run' not in sys.argv:
    raise SystemExit('Pass --run to send one synthetic review to the configured AI provider.')
key = os.getenv('OPENROUTER_API_KEY') or dotenv_values(ROOT/'backend/.env').get('OPENROUTER_API_KEY') or dotenv_values(ROOT/'.env').get('OPENROUTER_API_KEY')
if not key:
    raise SystemExit('Provider key is not configured')

# This import configures a temporary SQLite database before importing the app.
from tests.test_ai_workflows import Workflows
from backend import ai_runtime, db as store
from backend.jobs import enqueue
from backend.schemas import AIRequest
from backend.worker import run_one
from sqlalchemy import select

fixture = Workflows()
fixture.setUp()
ai_runtime.config = replace(ai_runtime.config, openrouter_key=key)
provider = ai_runtime.provider_stream
captured = []


async def capture(model, messages, *args):
    captured.append({'model': model, 'context': json.loads(messages[-1]['content'])})
    return await provider(model, messages, *args)


try:
    fixture.seed(410, notes='UNRELATED_OLD_NOTE', day='2025-09-10')
    fixture.seed(90)
    with store.database(fixture.a) as db:
        recent = list(db.scalars(select(store.Trade).where(store.Trade.entry_time >= '2026-09-01').order_by(store.Trade.id)))
        for i, trade in enumerate(recent):
            trade.symbol = f'FIXTURE{i}'
            trade.stop_loss = 95
            trade.exit_price = 110 if i % 2 else 96
            trade.setup = ['Breakout', 'Reversal', 'Trend'][i % 3]
            trade.notes = f'Trade {i}: waited for confirmation before entry. Exited according to the recorded plan.'
        expected_ids = {t.id for t in recent}
        job = enqueue(db, AIRequest(message='tell me about my last 90 trades'), 'live-review-evidence')
    with patch('backend.ai_runtime.provider_stream', side_effect=capture):
        asyncio.run(run_one())
    with store.database(fixture.a) as db:
        saved = db.get(store.AIJob, job.id)
        report = {'status': saved.status, 'error': saved.error, 'usage': saved.usage,
                  'credits': saved.credits, 'result': saved.result}
        if captured and 'evidence' in captured[-1]['context']:
            evidence = captured[-1]['context']['evidence']
            records = [a for a in evidence.values() if 'columns' in a['data']]
            rows = [dict(zip(a['data']['columns'], row)) for a in records for row in a['data']['rows']]
            report['writer_evidence'] = [{'kind': a['kind'], 'matched': a['matched'], 'detail': a['detail'],
                'rows': len(a['data'].get('rows', [])), 'columns': a['data'].get('columns', [])} for a in evidence.values()]
            assert {r['id'] for r in rows} == expected_ids
            assert all('note_ref' in r and 'net_pnl' in r and 'r_multiple' in r for r in rows)
            assert 'UNRELATED_OLD_NOTE' not in json.dumps(evidence)
            assert all(a['data']['notes'] for a in records)
        Path('/tmp/hakisense-review-evidence-live.json').write_text(json.dumps(report, indent=2))
        print(json.dumps({k: v for k, v in report.items() if k != 'result'}), flush=True)
        assert saved.status == 'succeeded', 'See the synthetic report for the provider failure.'
        assert len(captured) == 2
        assert saved.result['coverage']['records_inspected'] == 90
        assert saved.result['answer'].strip()
finally:
    fixture.tearDown()
