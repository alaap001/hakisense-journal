"""Opt-in live selection regression using only an isolated synthetic 500-trade journal."""
import asyncio
import json
import os
import sys
from dataclasses import replace
from pathlib import Path
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if '--run' not in sys.argv:
    raise SystemExit('Pass --run for two live synthetic reviews. No customer records are read.')
key = os.getenv('OPENROUTER_API_KEY') or dotenv_values(ROOT/'backend/.env').get('OPENROUTER_API_KEY') or dotenv_values(ROOT/'.env').get('OPENROUTER_API_KEY')
if not key:
    raise SystemExit('Provider key is not configured')
from tests.test_ai_workflows import Workflows
from backend import db as store, ai_runtime
from backend.jobs import enqueue
from backend.schemas import AIRequest
from backend.worker import run_one
from sqlalchemy import select

fixture = Workflows()
fixture.setUp()
ai_runtime.config = replace(ai_runtime.config, openrouter_key=key)
reports = []
try:
    fixture.seed(497, notes='UNRELATED_OLD_NOTE', day='2025-09-10')
    fixture.seed(3, notes='Entered at the planned level. Stayed with the recorded exit plan.', day='2026-09-10')
    with store.database(fixture.a) as db:
        recent = list(db.scalars(select(store.Trade).where(store.Trade.entry_time >= '2026-09-01').order_by(store.Trade.id)))
        for i, trade in enumerate(recent):
            trade.symbol = ['ALPHA', 'BETA', 'GAMMA'][i]
            trade.entry_time = f'2026-09-10T0{i+4}:00:00+00:00'
            trade.exit_time = f'2026-09-10T0{i+4}:30:00+00:00'
            trade.exit_price = [110, 95, 108][i]
        expected = {t.id for t in recent}
    for index, question in enumerate(('hi, tell me about my last 3 trades', 'Could you walk me through my three most recent closed positions?')):
        with store.database(fixture.a) as db:
            job = enqueue(db, AIRequest(message=question), 'live-selection-'+str(index))
        asyncio.run(run_one())
        with store.database(fixture.a) as db:
            saved = db.get(store.AIJob, job.id)
            calls = [{'agent': c.agent, 'model': c.model, 'usage': c.usage, 'response': c.response}
                     for c in db.scalars(select(store.AICall).where(store.AICall.job_id == job.id).order_by(store.AICall.created_at))]
            report = {'question': question, 'status': saved.status, 'credits': saved.credits, 'usage': saved.usage,
                      'error': saved.error, 'pause': saved.pause, 'result': saved.result, 'calls': calls}
            reports.append(report)
            Path('/tmp/hakisense-selection-live.json').write_text(json.dumps(reports, indent=2))
            print(json.dumps({k: v for k, v in report.items() if k not in ('result', 'calls')}), flush=True)
            assert saved.status == 'succeeded', 'Review did not complete; inspect the synthetic report.'
            retrieved = {i for a in saved.result['sources'].values() for i in a['trade_ids']}
            assert retrieved == expected, 'The wrong trade cohort was read'
            assert saved.result['coverage']['records_inspected'] == 3
            assert len(calls) == 2
            assert saved.usage['input_tokens'] < 15000, 'A three-trade answer should have a small prompt'
            answer = saved.result['answer']
            assert all(symbol in answer.upper() for symbol in ('ALPHA', 'BETA', 'GAMMA')), 'Missing requested trade'
            assert not any(word in answer.lower() for word in ('input token', 'output token', '100k', 'workflow', 'evidence_id'))
    print('Both live queries selected exactly the expected 3 of 500 trades, answered with 2 agents, and settled actual credits.', flush=True)
finally:
    fixture.tearDown()
