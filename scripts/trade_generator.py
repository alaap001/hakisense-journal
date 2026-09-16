"""Generator for 100 realistic dummy trades validated against TradeInput schema."""
import random
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pydantic import ValidationError
from backend.schemas import TradeInput

IST = ZoneInfo('Asia/Kolkata')

EQUITY_SYMBOLS = [
    ('RELIANCE', 2850.0, 3100.0, 'NSE'),
    ('HDFCBANK', 1550.0, 1750.0, 'NSE'),
    ('ICICIBANK', 1120.0, 1280.0, 'NSE'),
    ('TCS', 4100.0, 4450.0, 'NSE'),
    ('INFY', 1700.0, 1950.0, 'NSE'),
    ('SBIN', 780.0, 890.0, 'NSE'),
    ('ITC', 470.0, 520.0, 'NSE'),
    ('TATASTEEL', 140.0, 175.0, 'BSE'),
    ('LT', 3400.0, 3750.0, 'NSE'),
    ('BHARTIARTL', 1450.0, 1650.0, 'NSE'),
]

INDEX_OPTIONS = [
    ('NIFTY', 25, [24000, 24200, 24500, 24800, 25000, 25200, 25400]),
    ('BANKNIFTY', 15, [50000, 50500, 51000, 51500, 52000, 52500]),
]

CRYPTO_SYMBOLS = [
    ('BTCINR', 5400000.0, 6200000.0),
    ('ETHINR', 250000.0, 310000.0),
    ('SOLINR', 12000.0, 16000.0),
]

SETUPS = [
    'Opening Range Breakout',
    'VWAP Pullback',
    'Trend Continuation',
    'Support Bounce',
    'Resistance Rejection',
    'Mean Reversion',
    'Flag & Pole Breakout',
    'Liquidity Sweep',
]

EMOTIONS = [
    'Disciplined',
    'Calm',
    'Confident',
    'Patient',
    'Hesitant',
    'FOMO',
    'Impatient',
    'Greedy',
]

TAG_OPTIONS = [
    'intraday', 'swing', 'scalp', 'breakout', 'reversal',
    'expiry-special', 'high-volume', 'morning-drive', 'power-hour', 'earnings'
]

WIN_NOTES = [
    "Clean breakout above previous day high with surging volume. Scaled out at 2R target.",
    "Waited for the 5m pullback to 20 EMA. Perfect pin-bar entry, trailing stop protected gains.",
    "Captured the entire morning momentum leg. Exited into the buyer exhaustion candle.",
    "Key support held firm after testing 3 times. Excellent risk-reward ratio realized.",
    "VWAP reclaim with institutional volume spikes. Exited near daily R1 resistance.",
    "Flag breakout confirmed on 15m timeframe. Held patiently till final target.",
    "Gap up held nicely in first 30 minutes. Rode trend with partial profit taking.",
    "Liquidity sweep below key swing low followed by quick reclaim. Sniped the bottom.",
]

LOSS_NOTES = [
    "Failed breakout; false pump absorbed by heavy supply. Cut loss immediately at stop.",
    "Entered slightly late due to hesitation. Risk-to-reward compromised, stopped out.",
    "Market reversed sharply after RBI policy commentary. Disciplined stop loss respected.",
    "Attempted counter-trend scalp against strong trend. Lesson: don't fight the trend.",
    "Choppy range-bound action triggered trailing stop before bounce. Frustrating chop.",
    "Slight FOMO chasing the second green bar. Cut position before max loss hit.",
    "Resistance held stronger than anticipated. Volume dried up at breakout point.",
]

OPEN_NOTES = [
    "Swing position entered at strong daily demand zone. Target open at 1.8R, SL placed below pivot.",
    "Intraday continuation trade underway. First target hit, runners left with SL at cost.",
    "Position open ahead of weekly expiry. Implied volatility crush anticipated in option premium.",
]

def generate_trades(account_id, count=100):
    random.seed(42) # Deterministic yet rich dataset
    trades = []
    
    # Generate dates across June 1, 2026 to Sep 13, 2026
    start_date = datetime(2026, 6, 1, 9, 15, tzinfo=IST)
    end_date = datetime(2026, 9, 13, 15, 0, tzinfo=IST)
    total_days = (end_date - start_date).days
    
    for i in range(count):
        # Choose trade category: 55% Equity, 35% Options, 5% Futures, 5% Crypto
        cat = random.choices(['Equity', 'Options', 'Futures', 'Crypto'], weights=[55, 35, 5, 5])[0]
        
        # Pick status: last 10 trades can be Open / Partial, rest mostly Closed, 2 Canceled
        if i >= 94:
            status = 'Open'
        elif i in (91, 92, 93):
            status = 'Partial'
        elif i in (20, 55):
            status = 'Canceled'
        else:
            status = 'Closed'
            
        # Select date
        day_offset = int((i / count) * total_days) + random.randint(0, 1)
        day_offset = min(day_offset, total_days)
        trade_date = start_date + timedelta(days=day_offset)
        
        # If weekend and not crypto, advance to Monday
        if cat != 'Crypto' and trade_date.weekday() >= 5:
            trade_date += timedelta(days=(7 - trade_date.weekday()))
            
        # Entry time between 09:20 and 14:45
        entry_hour = random.choice([9, 10, 11, 12, 13, 14])
        entry_minute = random.randint(15 if entry_hour == 9 else 0, 55 if entry_hour < 14 else 30)
        entry_dt = trade_date.replace(hour=entry_hour, minute=entry_minute, second=random.randint(0, 59))
        
        # Duration: 15m to 240m for intraday, or 1-4 days for swing
        is_swing = (random.random() < 0.25 and cat in ('Equity', 'Crypto'))
        if is_swing:
            exit_dt = entry_dt + timedelta(days=random.randint(1, 4), hours=random.randint(1, 4))
        else:
            exit_minutes = random.randint(15, 180)
            exit_dt = entry_dt + timedelta(minutes=exit_minutes)
            if exit_dt.hour > 15 or (exit_dt.hour == 15 and exit_dt.minute > 25):
                exit_dt = exit_dt.replace(hour=15, minute=random.randint(15, 25))
                
        side = random.choices(['Long', 'Short'], weights=[65, 35])[0]
        
        # Determine win/loss (~58% win rate)
        is_win = (random.random() < 0.58) if status == 'Closed' else (random.random() < 0.6)
        
        setup = random.choice(SETUPS)
        emotion = random.choice(EMOTIONS[:4] if is_win else EMOTIONS[3:])
        rating = random.choices([4, 5, 3], weights=[50, 30, 20])[0] if is_win else random.choices([2, 1, 3], weights=[50, 30, 20])[0]
        
        if status == 'Open':
            notes = random.choice(OPEN_NOTES)
        elif is_win:
            notes = random.choice(WIN_NOTES)
        else:
            notes = random.choice(LOSS_NOTES)
            
        selected_tags = random.sample(TAG_OPTIONS, k=random.randint(1, 3))
        if is_swing and 'swing' not in selected_tags:
            selected_tags.append('swing')
        elif not is_swing and 'intraday' not in selected_tags:
            selected_tags.append('intraday')
            
        attributes = {
            'timeframe': random.choice(['5m', '15m', '1h', 'Daily']),
            'market_trend': random.choice(['Bullish', 'Bearish', 'Sideways']),
            'strategy': setup,
        }
        
        if cat == 'Equity':
            sym, min_p, max_p, exch = random.choice(EQUITY_SYMBOLS)
            entry_price = round(random.uniform(min_p, max_p), 2)
            quantity = random.randint(10, 100)
            multiplier = 1.0
            asset_type = 'Stocks'
            exchange = exch
            segment = 'Equity'
            expiry = None
            strike = None
            option_type = None
            lot_size = None
            
            # SL & Target
            p_diff = entry_price * random.uniform(0.01, 0.025)
            if side == 'Long':
                stop_loss = round(entry_price - p_diff, 2)
                target_price = round(entry_price + p_diff * 2.0, 2)
                if is_win:
                    exit_price = round(entry_price + p_diff * random.uniform(0.8, 2.2), 2)
                else:
                    exit_price = round(entry_price - p_diff * random.uniform(0.7, 1.1), 2)
            else:
                stop_loss = round(entry_price + p_diff, 2)
                target_price = round(entry_price - p_diff * 2.0, 2)
                if is_win:
                    exit_price = round(entry_price - p_diff * random.uniform(0.8, 2.2), 2)
                else:
                    exit_price = round(entry_price + p_diff * random.uniform(0.7, 1.1), 2)
                    
            mark_price = exit_price if status == 'Open' else None
            commission = 20.0 if status != 'Canceled' else 0.0
            fees = round(entry_price * quantity * 0.0008 + 15.0, 2) if status != 'Canceled' else 0.0
            
        elif cat == 'Options':
            sym, lsize, strikes = random.choice(INDEX_OPTIONS)
            lots = random.randint(1, 4)
            quantity = lots * lsize
            lot_size = lsize
            asset_type = 'Options'
            exchange = 'NSE'
            segment = 'Index options'
            strike = float(random.choice(strikes))
            option_type = random.choice(['CE', 'PE'])
            multiplier = 1.0
            
            # Find next monthly/weekly expiry
            exp_date = (entry_dt + timedelta(days=random.choice([2, 7, 14, 21]))).date()
            expiry = exp_date.isoformat()
            
            entry_price = round(random.uniform(120.0, 380.0), 2)
            p_diff = entry_price * random.uniform(0.2, 0.35)
            
            if side == 'Long':
                stop_loss = round(max(5.0, entry_price - p_diff), 2)
                target_price = round(entry_price + p_diff * 2.0, 2)
                if is_win:
                    exit_price = round(entry_price + p_diff * random.uniform(1.0, 2.5), 2)
                else:
                    exit_price = round(max(5.0, entry_price - p_diff * random.uniform(0.8, 1.0)), 2)
            else:
                stop_loss = round(entry_price + p_diff, 2)
                target_price = round(max(5.0, entry_price - p_diff * 2.0), 2)
                if is_win:
                    exit_price = round(max(5.0, entry_price - p_diff * random.uniform(1.0, 2.5)), 2)
                else:
                    exit_price = round(entry_price + p_diff * random.uniform(0.8, 1.0), 2)
                    
            mark_price = exit_price if status == 'Open' else None
            commission = 40.0 if status != 'Canceled' else 0.0
            fees = round(entry_price * quantity * 0.0012 + 25.0, 2) if status != 'Canceled' else 0.0
            
        elif cat == 'Futures':
            sym, lsize, _ = random.choice(INDEX_OPTIONS)
            lots = random.randint(1, 2)
            quantity = lots * lsize
            lot_size = lsize
            asset_type = 'Futures'
            exchange = 'NSE'
            segment = 'Index futures'
            strike = None
            option_type = None
            multiplier = 1.0
            
            exp_date = (entry_dt + timedelta(days=20)).date()
            expiry = exp_date.isoformat()
            
            base_p = 24500.0 if sym == 'NIFTY' else 51000.0
            entry_price = round(base_p + random.uniform(-300, 300), 2)
            p_diff = round(entry_price * 0.004, 2)
            
            if side == 'Long':
                stop_loss = round(entry_price - p_diff, 2)
                target_price = round(entry_price + p_diff * 2.0, 2)
                if is_win:
                    exit_price = round(entry_price + p_diff * random.uniform(1.0, 2.2), 2)
                else:
                    exit_price = round(entry_price - p_diff * random.uniform(0.8, 1.1), 2)
            else:
                stop_loss = round(entry_price + p_diff, 2)
                target_price = round(entry_price - p_diff * 2.0, 2)
                if is_win:
                    exit_price = round(entry_price - p_diff * random.uniform(1.0, 2.2), 2)
                else:
                    exit_price = round(entry_price + p_diff * random.uniform(0.8, 1.1), 2)
                    
            mark_price = exit_price if status == 'Open' else None
            commission = 40.0 if status != 'Canceled' else 0.0
            fees = round(entry_price * quantity * 0.0002 + 40.0, 2) if status != 'Canceled' else 0.0

        else: # Crypto
            sym, min_p, max_p = random.choice(CRYPTO_SYMBOLS)
            entry_price = round(random.uniform(min_p, max_p), 2)
            quantity = 0.02 if sym == 'BTCINR' else (0.5 if sym == 'ETHINR' else 5.0)
            multiplier = 1.0
            asset_type = 'Crypto'
            exchange = 'Crypto'
            segment = 'Crypto spot'
            expiry = None
            strike = None
            option_type = None
            lot_size = None
            
            p_diff = entry_price * random.uniform(0.02, 0.05)
            if side == 'Long':
                stop_loss = round(entry_price - p_diff, 2)
                target_price = round(entry_price + p_diff * 2.0, 2)
                if is_win:
                    exit_price = round(entry_price + p_diff * random.uniform(0.8, 2.0), 2)
                else:
                    exit_price = round(entry_price - p_diff * random.uniform(0.8, 1.0), 2)
            else:
                stop_loss = round(entry_price + p_diff, 2)
                target_price = round(entry_price - p_diff * 2.0, 2)
                if is_win:
                    exit_price = round(entry_price - p_diff * random.uniform(0.8, 2.0), 2)
                else:
                    exit_price = round(entry_price + p_diff * random.uniform(0.8, 1.0), 2)
                    
            mark_price = exit_price if status == 'Open' else None
            commission = round(entry_price * quantity * 0.002, 2) if status != 'Canceled' else 0.0
            fees = 10.0 if status != 'Canceled' else 0.0
            
        risk_amount = round(abs(entry_price - stop_loss) * quantity * multiplier, 2)
        planned_entry = round(entry_price + random.uniform(-0.5, 0.5), 2)
        
        if status == 'Closed':
            closed_quantity = quantity
            exit_time_str = exit_dt.isoformat()
            mark_price = None
        elif status == 'Partial':
            if lot_size:
                closed_quantity = quantity // 2
            else:
                closed_quantity = round(quantity * 0.5, 4)
            exit_time_str = exit_dt.isoformat()
            mark_price = exit_price
        elif status in ('Open', 'Canceled'):
            closed_quantity = 0.0
            exit_price = None
            exit_time_str = None
            if status == 'Canceled':
                mark_price = None
                commission = 0.0
                fees = 0.0

        # MFE and MAE
        if exit_price is not None:
            mfe = round(abs(exit_price - entry_price) * 1.25, 2)
            mae = round(abs(entry_price - stop_loss) * 0.4, 2)
        else:
            mfe = None
            mae = None
            
        raw_trade = {
            'account_id': account_id,
            'symbol': sym,
            'asset_type': asset_type,
            'exchange': exchange,
            'segment': segment,
            'expiry': expiry,
            'strike': strike,
            'option_type': option_type,
            'lot_size': lot_size,
            'side': side,
            'status': status,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'mark_price': mark_price,
            'quantity': quantity,
            'closed_quantity': closed_quantity,
            'multiplier': multiplier,
            'entry_time': entry_dt.isoformat(),
            'exit_time': exit_time_str,
            'commission': commission,
            'fees': fees,
            'stop_loss': stop_loss,
            'target_price': target_price,
            'risk_amount': risk_amount,
            'planned_entry': planned_entry,
            'setup': setup,
            'emotion': emotion,
            'rating': rating,
            'notes': notes,
            'tags': selected_tags,
            'attributes': attributes,
            'mfe': mfe,
            'mae': mae,
        }
        
        # Validate against schema
        validated = TradeInput(**raw_trade)
        trades.append(validated.model_dump())
        
    return trades

if __name__ == '__main__':
    dummy_acc = '8bc7b405-a065-41a3-a6be-1de15f63deb8'
    result = generate_trades(dummy_acc, 100)
    print(f"Generated and validated {len(result)} trades successfully!")
