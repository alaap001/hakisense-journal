from datetime import datetime, timedelta, timezone
import random
from sqlalchemy import select
from .db import database, Account, Trade, Record, Setting
from .schemas import TradeInput


def seed_demo():
    with database() as db:
        if db.get(Setting, 'initialized'):
            return
        db.add(Setting(key='initialized',value={'done':True}))
        import os
        if os.getenv('SEED_DEMO','true').lower() != 'true':
            db.add(Account(name='My trading account', initial_balance=25000))
            return
        accounts = [Account(id='demo-equities',name='Swing portfolio',broker='Paper · equities',initial_balance=25000,color='#b8ef78',is_demo=True),
                    Account(id='demo-futures',name='Futures account',broker='Paper · futures',initial_balance=15000,color='#a9baff',is_demo=True),
                    Account(id='demo-crypto',name='Crypto account',broker='Paper · crypto',initial_balance=10000,color='#eec378',is_demo=True)]
        db.add_all(accounts)
        db.flush()
        rng = random.Random(43)
        instruments=[('NVDA',118,'Stocks',1,0),('AAPL',214,'Stocks',1,0),('TSLA',242,'Stocks',1,0),('SPY',552,'Stocks',1,0),('AMD',152,'Stocks',1,0),('ES',5500,'Futures',50,1),('NQ',19500,'Futures',20,1),('BTCUSD',62000,'Crypto',1,2),('ETHUSD',3200,'Crypto',1,2),('SPY CALL',5.2,'Options',100,0),('EURUSD',1.085,'Forex',1,0),('SPX',5550,'Indices',1,0)]
        setups=['Breakout & retest','Opening range','Trend continuation','Mean reversion']
        today=datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)
        idx=0
        for offset in range(83,0,-1):
            day=today-timedelta(days=offset)
            if day.weekday()>=5:
                continue
            for _ in range(rng.choice([1,1,2,2,3])):
                symbol,price,asset,mult,acct=rng.choice(instruments)
                side=rng.choice(['Long','Long','Short'])
                quantity=rng.choice([20,30,50,75]) if asset in ('Stocks','Indices') else rng.choice([1,2,3]) if asset in ('Options','Futures') else .02 if asset=='Crypto' else 10000
                risk=rng.uniform(65,190)
                won=rng.random()<.61
                pnl=risk*rng.uniform(1.1,2.9) if won else -risk*rng.uniform(.5,1.1)
                entry=round(price*(1+rng.uniform(-.025,.025)),5)
                exit_price=round(entry+pnl/(quantity*mult)*(1 if side=='Long' else -1),6)
                if exit_price<=0:
                    exit_price=entry*.5
                entry_time=day+timedelta(hours=rng.choice([13,14,14,15,15,16,17,18]),minutes=rng.randrange(60))
                hold=rng.choice([12,24,38,52,85,125,210,400])
                emotion=rng.choice(['Focused','Focused','Confident','Neutral']) if won else rng.choice(['Anxious','FOMO','Neutral','Revenge'])
                setup=rng.choice(setups if won else setups+['Uncategorized','Mean reversion'])
                stop=entry-risk/(quantity*mult)*(1 if side=='Long' else -1)
                attributes={'delta':.52,'gamma':.03,'theta':-.08,'vega':.12,'iv':.28,'strike':550,'expiry':(day+timedelta(days=30)).date().isoformat(),'option_type':'Call'} if asset=='Options' else {}
                payload=TradeInput(account_id=accounts[acct].id,symbol=symbol,asset_type=asset,side=side,status='Closed',entry_price=entry,exit_price=exit_price,
                    quantity=quantity,multiplier=mult,entry_time=entry_time.isoformat(),exit_time=(entry_time+timedelta(minutes=hold)).isoformat(),commission=round(rng.uniform(.7,4.5),2),
                    stop_loss=max(0,stop),target_price=entry+abs(entry-stop)*2*(1 if side=='Long' else -1) if entry>abs(entry-stop)*2 else None,
                    risk_amount=round(risk,2),planned_entry=round(entry*(1+rng.uniform(-.0001,.0001)),6),setup=setup,emotion=emotion,rating=rng.choice([4,4,5]) if won else rng.choice([2,3,3]),
                    tags=['A+ setup','Patient entry'] if won else ['Review','Early entry'],notes='Waited for the retest and followed the planned entry. Review the exit against the original target.' if won else 'Entry was rushed. Review whether the setup had fully formed before committing risk.',
                    mfe=round(max(pnl,0)+rng.uniform(20,170),2),mae=round(abs(min(pnl,0))+rng.uniform(5,45),2),attributes=attributes)
                db.add(Trade(id=f'demo-trade-{idx}',**payload.model_dump(),is_demo=True))
                idx+=1
        db.add(Trade(**TradeInput(account_id=accounts[0].id,symbol='NVDA',entry_price=121.6,quantity=30,entry_time=(today-timedelta(days=1)+timedelta(hours=15)).isoformat(),status='Open',mark_price=123.8,stop_loss=119.5,target_price=128,setup='Trend continuation',emotion='Focused',notes='Waiting for follow-through. Mark is an example, not a live quote.').model_dump(),is_demo=True))
        for title,description,checklist in [
          ('Breakout & retest','A clean break of a key level, followed by a controlled retest.',['Mark the level before entry','Wait for a candle close above the level','Define invalidation at the retest low','Check that the target offers at least 2R']),
          ('Opening range','Trade a confirmed break of the first 15-minute range.',['Mark the first 15-minute high and low','Confirm volume expansion','Avoid entries into nearby resistance','One attempt per direction']),
          ('Trend continuation','Join an established trend after an orderly pullback.',['Check higher-timeframe direction','Wait for a pullback to structure','Confirm the trigger','Keep risk consistent']),
          ('Mean reversion','Review stretched moves back toward an established range.',['Confirm a range, not a strong trend','Wait for rejection','Record why price is stretched','Use a predefined target'])]:
            db.add(Record(kind='playbook',data={'title':title,'description':description,'checklist':checklist,'is_demo':True}))
        db.add(Record(kind='goal',data={'title':'Journal 20 trades','metric':'reviewed','target':20,'is_demo':True}))
        db.add(Record(kind='goal',data={'title':'Follow the plan','metric':'process','target':80,'is_demo':True}))
        db.add(Record(kind='note',data={'title':'A little more patience','date':(today-timedelta(days=1)).date().isoformat(),'body':'The best trades this week came after waiting for confirmation.\n\nFor the next session:\n- Let the opening range form.\n- Define the stop before sizing.\n- Take a break after two consecutive losses.','mood':'Focused','is_demo':True}))
