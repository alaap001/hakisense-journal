"""Deterministic journal analytics. No prices or fills are inferred from a model."""
from collections import defaultdict
from .markets import india_time, india_date
from datetime import datetime
from decimal import Decimal
from math import sqrt
from statistics import mean, median, stdev


def D(value):
    return Decimal(str(value or 0))


def rounded(value):
    return float(D(value).quantize(Decimal('0.000001')))


def ratio(a, b):
    return rounded(a / b) if b else None


def enrich(t):
    t = dict(t)
    q, closed, mult = D(t['quantity']), D(t.get('closed_quantity')), D(t.get('multiplier', 1))
    sign = D(1 if t['side'] == 'Long' else -1)
    cost = D(t.get('commission')) + D(t.get('fees'))
    entry = D(t['entry_price'])
    canceled = t['status'] == 'Canceled'
    gross = (D(t['exit_price']) - entry) * closed * mult * sign if closed else D(0)
    realized = gross - cost * closed / q if closed else D(0)
    mark = t.get('mark_price')
    remaining = D(0) if canceled else q - closed
    unrealized = ((D(mark) - entry) * remaining * mult * sign - cost * remaining / q) if mark is not None and remaining else None
    risk = D(t.get('risk_amount')) or (abs(entry - D(t['stop_loss'])) * q * mult if t.get('stop_loss') is not None else D(0))
    exit_time = t.get('exit_time')
    hold = max(0, (datetime.fromisoformat(exit_time) - datetime.fromisoformat(t['entry_time'])).total_seconds() / 60) if exit_time else None
    slippage = (entry - D(t['planned_entry'])) * sign * q * mult if t.get('planned_entry') is not None else None
    t.update(net_pnl=rounded(realized), gross_pnl=rounded(gross), unrealized_pnl=rounded(unrealized) if unrealized is not None else None,
             total_fees=rounded(cost) if not canceled else 0, realized_fees=rounded(cost * closed / q) if closed else 0,
             remaining_quantity=rounded(remaining), r_multiple=ratio(realized, risk * closed / q) if closed else None,
             risk=rounded(risk), hold_minutes=rounded(hold) if hold is not None else None,
             slippage=rounded(slippage) if slippage is not None else None,
             pnl_date=india_date(exit_time or t['entry_time']))
    return t


def apply_filters(trades, filters):
    f = filters.model_dump() if hasattr(filters, 'model_dump') else filters
    result = []
    for t in trades:
        if any(f.get(k) and t.get(k) != f[k] for k in ['account_id','asset_type','side','status','setup','emotion']):
            continue
        if f.get('start') and india_date(t['entry_time']) < f['start']:
            continue
        if f.get('end') and india_date(t['entry_time']) > f['end']:
            continue
        if f.get('symbol') and f['symbol'].upper() not in t['symbol'].upper():
            continue
        if f.get('tag') and f['tag'] not in t['tags']:
            continue
        p, outcome = t['net_pnl'], f.get('outcome')
        if outcome and (not t['closed_quantity'] or not {'win':p>0,'loss':p<0,'breakeven':p==0}[outcome]):
            continue
        result.append(t)
    return result


def statistics(trades, balance=0):
    closed = sorted([t for t in trades if t['closed_quantity'] > 0 and t['status'] != 'Canceled'], key=lambda t:t.get('exit_time') or t['entry_time'])
    ps = [t['net_pnl'] for t in closed]
    wins, losses = [p for p in ps if p > 0], [p for p in ps if p < 0]
    total, n = sum(ps), len(ps)
    gp, gl = sum(wins), abs(sum(losses))
    equity = peak = 0
    maxdd = maxddpct = 0
    streak = bestwin = bestloss = 0
    daily = defaultdict(lambda:{'net_pnl':0,'count':0,'wins':0,'gross_pnl':0})
    curve = [{'date':'Start','pnl':0,'equity':balance,'drawdown':0}]
    for t in closed:
        p = t['net_pnl']
        equity += p
        peak = max(peak, equity)
        maxdd = max(maxdd, peak-equity)
        if balance + peak > 0:
            maxddpct = max(maxddpct, (peak-equity)/(balance+peak)*100)
        streak = (max(streak,0)+1 if p>0 else min(streak,0)-1 if p<0 else 0)
        bestwin, bestloss = max(bestwin,streak), max(bestloss,-streak)
        day = daily[t['pnl_date']]
        day['net_pnl'] += p
        day['gross_pnl'] += t['gross_pnl']
        day['count'] += 1
        day['wins'] += int(p>0)
    running = top = 0
    for day, row in sorted(daily.items()):
        running += row['net_pnl']
        top = max(top, running)
        curve.append({'date':day,'pnl':rounded(running),'equity':rounded(balance+running),'drawdown':rounded(running-top)})
    days = [v['net_pnl'] for v in daily.values()]
    rs = [t['r_multiple'] for t in closed if t['r_multiple'] is not None]
    holds = [t['hold_minutes'] for t in closed if t['hold_minutes'] is not None]
    risk_total = sum(t['risk'] * t['closed_quantity']/t['quantity'] for t in closed)
    metrics = {
      'net_pnl':rounded(total), 'gross_pnl':rounded(sum(t['gross_pnl'] for t in closed)),
      'count':n, 'total_positions':len(trades), 'open_count':sum(t['status'] in ('Open','Partial') for t in trades),
      'win_rate':ratio(len(wins)*100,n) or 0,'wins':len(wins),'losses':len(losses),'breakeven':sum(p==0 for p in ps),
      'profit_factor':ratio(gp,gl), 'gross_profit':rounded(gp),'gross_loss':rounded(gl),
      'avg_win':rounded(mean(wins)) if wins else 0,'avg_loss':rounded(mean(losses)) if losses else 0,
      'avg_pnl':rounded(mean(ps)) if ps else 0, 'median_pnl':rounded(median(ps)) if ps else 0,
      'payoff_ratio':ratio(mean(wins),abs(mean(losses))) if wins and losses else None,
      'largest_win':max(wins,default=0),'largest_loss':min(losses,default=0),
      'max_drawdown':rounded(maxdd),'max_drawdown_pct':rounded(maxddpct),'recovery_factor':ratio(total,maxdd),
      'fees':rounded(sum(t['realized_fees'] for t in closed)), 'avg_fees':ratio(sum(t['realized_fees'] for t in closed),n) or 0,
      'avg_r':rounded(mean(rs)) if rs else None, 'total_r':rounded(sum(rs)) if rs else None,'r_sample':len(rs),
      'avg_hold':rounded(mean(holds)) if holds else None,'median_hold':rounded(median(holds)) if holds else None,
      'max_win_streak':bestwin,'max_loss_streak':bestloss,'active_days':len(days),
      'positive_days':sum(p>0 for p in days), 'negative_days':sum(p<0 for p in days),
      'best_day':max(days,default=0), 'worst_day':min(days,default=0),'avg_day':rounded(mean(days)) if days else 0,
      'pnl_stddev':rounded(stdev(ps)) if len(ps)>1 else None,
      'active_day_sharpe':rounded(mean(days)/stdev(days)*sqrt(252)) if len(days)>1 and stdev(days)>0 else None,
      'return_pct':ratio(total*100,balance), 'net_risk_return':ratio(total,risk_total),
      'unrealized_pnl':rounded(sum(t['unrealized_pnl'] or 0 for t in trades)),
      'unmarked_positions':sum(t['remaining_quantity']>0 and t.get('mark_price') is None for t in trades),
      'equity':rounded(balance+total),
      'mfe_avg':rounded(mean([t['mfe'] for t in closed if t.get('mfe') is not None])) if any(t.get('mfe') is not None for t in closed) else None,
      'mae_avg':rounded(mean([t['mae'] for t in closed if t.get('mae') is not None])) if any(t.get('mae') is not None for t in closed) else None,
    }
    return {'metrics':metrics,'equity':curve,'daily':[{'date':k,**{f:rounded(v) for f,v in val.items()}} for k,val in sorted(daily.items())]}


DIMENSIONS = ['symbol','setup','emotion','asset_type','side','weekday','hour','month','account','tag','hold_bucket','rating']


def group_rows(trades, dimension='symbol'):
    groups = defaultdict(list)
    for t in trades:
        dt = india_time(t['entry_time'])
        h = t['hold_minutes'] or 0
        key = {'weekday':dt.strftime('%a'),'hour':dt.strftime('%H:00'),'month':dt.strftime('%Y-%m'),
               'account':t.get('account_name',t['account_id']), 'hold_bucket':'< 15m' if h<15 else '15–60m' if h<60 else '1–4h' if h<240 else '4h–1d' if h<1440 else '1d+',
               'rating':str(t.get('rating',3))}.get(dimension,t.get(dimension,'Unknown'))
        keys = t.get('tags') or ['Untagged'] if dimension == 'tag' else [key]
        for key in keys:
            groups[str(key)].append(t)
    rows = [{'name':key,**statistics(ts)['metrics']} for key,ts in groups.items()]
    if dimension in ['month','hour']:
        return sorted(rows,key=lambda r:r['name'])
    if dimension == 'weekday':
        return sorted(rows,key=lambda r:['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].index(r['name']))
    return sorted(rows,key=lambda r:r['net_pnl'],reverse=True)


def coach_checks(trades):
    closed = sorted([t for t in trades if t['closed_quantity']>0],key=lambda t:t['entry_time'])
    m = statistics(trades)['metrics']
    after_loss = [b for a,b in zip(closed,closed[1:]) if a['net_pnl']<0 and a.get('exit_time') and 0 <= (datetime.fromisoformat(b['entry_time'])-datetime.fromisoformat(a['exit_time'])).total_seconds()<900]
    days = defaultdict(list)
    for t in closed:
        days[india_date(t['entry_time'])].append(t)
    groups = {d:group_rows(closed,d) for d in ['setup','weekday','symbol','hour']}
    def weakest(d):
        rows = [r for r in groups[d] if r['count']>=3]
        key = min(rows,key=lambda r:r['net_pnl'])['name'] if rows else None
        return [t for t in closed if (india_time(t['entry_time']).strftime('%a') if d=='weekday' else india_time(t['entry_time']).strftime('%H:00') if d=='hour' else t[d])==key]
    specs = [
      ('fast_reentry','Fast re-entry after a loss',after_loss,'Review entries within 15 minutes of a losing exit; timing alone does not establish revenge trading.'),
      ('overtrading','Trades after the fifth entry',[t for ts in days.values() for t in ts[5:]],'Compare later entries with your first five trades before setting a daily limit.'),
      ('unplanned','Trades without a setup',[t for t in closed if t['setup'] in ('','Uncategorized')],'Assign a setup before placing your next trade.'),
      ('fomo','FOMO entries',[t for t in closed if t['emotion']=='FOMO'],'Review whether these entries followed your written trigger.'),
      ('revenge','Self-reported revenge trades',[t for t in closed if t['emotion']=='Revenge'],'Use a written reset routine after a loss.'),
      ('anxious','Anxious entries',[t for t in closed if t['emotion']=='Anxious'],'Review size and clarity of the setup when you felt anxious.'),
      ('missing_stop','Missing risk plan',[t for t in closed if not t['risk']],'Record a stop or explicit risk amount to make R-based review possible.'),
      ('fees','High transaction costs',[t for t in closed if t['realized_fees']>abs(t['gross_pnl'])*.2],'Compare costs with gross outcomes, especially on small trades.'),
      ('setup','Weakest setup with 3+ trades',weakest('setup'),'Review examples before changing a setup; small samples are uncertain.'),
      ('weekday','Weakest weekday with 3+ trades',weakest('weekday'),'Compare market conditions and setup mix across weekdays.'),
      ('symbol','Weakest symbol with 3+ trades',weakest('symbol'),'Review instrument-specific sizing and execution.'),
      ('hour','Weakest entry hour with 3+ trades',weakest('hour'),'Compare performance by entry hour (IST).'),
      ('low_rating','Low process ratings',[t for t in closed if t['rating']<=2],'Review process mistakes independently of whether the trade won.'),
      ('slippage','Adverse entry slippage',[t for t in closed if (t['slippage'] or 0)>0],'Compare planned versus executed entries; the difference is observed cost.'),
      ('giveback','Large favorable-excursion giveback',[t for t in closed if t.get('mfe') and t['net_pnl']<t['mfe']*.3],'Review exits against supplied MFE; a perfect hindsight exit is not an achievable baseline.'),
      ('oversize','Risk above twice the median',[t for t in closed if t['risk']>2*median([x['risk'] for x in closed if x['risk']>0])] if any(x['risk']>0 for x in closed) else [],'Review whether unusually large risk was part of your plan.'),
    ]
    findings=[]
    for key,title,ts,action in specs:
        loss = max(0,-sum(t['net_pnl'] for t in ts))
        if key=='slippage':
            loss=sum(t['slippage'] or 0 for t in ts)
        if key=='fees':
            loss=sum(t['realized_fees'] for t in ts)
        n=len(ts)
        findings.append({'id':key,'title':title,'sample':n,'impact':rounded(loss),'confidence':'Higher' if n>=30 else 'Moderate' if n>=10 else 'Low',
                         'status':'review' if loss>0 else 'observed' if n else 'no_data','action':action,'trade_ids':[t['id'] for t in ts],
                         'net_pnl':rounded(sum(t['net_pnl'] for t in ts))})
    return sorted(findings,key=lambda f:f['impact'],reverse=True)
