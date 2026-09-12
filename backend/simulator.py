import math
import random
from datetime import datetime, timedelta, timezone
from .markets import IST


def sample_candles():
    rng=random.Random(19)
    start=datetime(2026,7,14,9,15,tzinfo=IST)
    price=25000
    candles=[]
    for i in range(375):
        opening=price
        price=max(1,price+math.sin(i/25)*3.5+rng.gauss(.5,13))
        candles.append({'time':(start+timedelta(minutes=i)).isoformat(),'open':round(opening,4),'high':round(max(opening,price)+rng.uniform(1,16),4),
                        'low':round(min(opening,price)-rng.uniform(1,16),4),'close':round(price,4),'volume':rng.randrange(500,15000)})
    return candles


def session_state(candles, symbol='NIFTY PRACTICE', source='Synthetic practice candles', balance=100000):
    return {'symbol':symbol,'source':source,'candles':candles,'cursor':min(30,len(candles)-1),'initial_balance':balance,'balance':balance,'position':None,'trades':[],'exported':False}


def visible(data):
    result={k:v for k,v in data.items() if k!='candles'}
    result['candles']=data['candles'][:data['cursor']+1]
    result['total_bars']=len(data['candles'])
    result['finished']=data['cursor']>=len(data['candles'])-1
    p=data.get('position')
    price=data['candles'][data['cursor']]['close']
    result['unrealized']=(price-p['entry_price'])*p['quantity']*p['multiplier']*(1 if p['side']=='Long' else -1) if p else 0
    return result


def close_position(data, price, reason):
    p=data['position']
    pnl=(price-p['entry_price'])*p['quantity']*p['multiplier']*(1 if p['side']=='Long' else -1)-p.get('fees',0)
    data['trades'].append({**p,'exit_price':price,'exit_time':data['candles'][data['cursor']]['time'],'net_pnl':round(pnl,6),'reason':reason})
    data['balance']=round(data['balance']+pnl,6)
    data['position']=None


def step(data, count=1):
    for _ in range(min(count,100)):
        if data['cursor']>=len(data['candles'])-1:
            break
        data['cursor']+=1
        c=data['candles'][data['cursor']]
        p=data.get('position')
        if not p:
            continue
        stop,target=p.get('stop_loss'),p.get('target_price')
        long=p['side']=='Long'
        # Gaps fill at the open. Intrabar stop/target ambiguity resolves stop-first.
        if stop is not None and ((long and c['open']<=stop) or (not long and c['open']>=stop)):
            close_position(data,c['open'],'Stop gap')
        elif target is not None and ((long and c['open']>=target) or (not long and c['open']<=target)):
            close_position(data,c['open'],'Target gap')
        elif stop is not None and ((long and c['low']<=stop) or (not long and c['high']>=stop)):
            close_position(data,stop,'Stop loss')
        elif target is not None and ((long and c['high']>=target) or (not long and c['low']<=target)):
            close_position(data,target,'Take profit')
    return data
