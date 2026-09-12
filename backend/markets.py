"""Stable market conventions. Contract lots and prices must come from trade records."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

IST = ZoneInfo('Asia/Kolkata')
BROKERS = [
    {'id': 'zerodha', 'name': 'Zerodha', 'markets': ['NSE', 'BSE', 'MCX']},
    {'id': 'groww', 'name': 'Groww', 'markets': ['NSE', 'BSE']},
    {'id': 'upstox', 'name': 'Upstox', 'markets': ['NSE', 'BSE', 'MCX']},
    {'id': 'angelone', 'name': 'Angel One', 'markets': ['NSE', 'BSE', 'MCX']},
    {'id': 'dhan', 'name': 'Dhan', 'markets': ['NSE', 'BSE', 'MCX']},
    {'id': 'icicidirect', 'name': 'ICICI Direct', 'markets': ['NSE', 'BSE']},
    {'id': 'fyers', 'name': 'FYERS', 'markets': ['NSE', 'BSE', 'MCX']},
    {'id': 'coindcx', 'name': 'CoinDCX', 'markets': ['Crypto']},
    {'id': 'coinswitch', 'name': 'CoinSwitch', 'markets': ['Crypto']},
    {'id': 'delta', 'name': 'Delta Exchange India', 'markets': ['Crypto']},
    {'id': 'manual', 'name': 'Other / manual', 'markets': ['NSE', 'BSE', 'MCX', 'Crypto']},
]
EXCHANGES = ['NSE', 'BSE', 'MCX', 'Crypto']
SEGMENTS = ['Equity', 'Index reference', 'Index futures', 'Index options', 'Stock futures', 'Stock options', 'Commodity', 'Crypto spot', 'Crypto derivatives']
SYMBOLS = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX', 'BANKEX', 'RELIANCE', 'HDFCBANK', 'ICICIBANK', 'INFY', 'TCS', 'SBIN', 'ITC', 'BTCINR', 'ETHINR', 'SOLINR']


def india_time(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00')) if isinstance(value, str) else value
    return dt.replace(tzinfo=dt.tzinfo or IST).astimezone(IST)


def india_date(value):
    return india_time(value).date().isoformat()


def month_key(value=None):
    return india_time(value or datetime.now(timezone.utc)).strftime('%Y-%m')


def catalog():
    return {'currency': 'INR', 'timezone': 'Asia/Kolkata', 'brokers': [{**b, 'connection': 'file_import'} for b in BROKERS],
            'exchanges': EXCHANGES, 'segments': SEGMENTS, 'symbols': SYMBOLS,
            'equity_session': {'opens': '09:15', 'closes': '15:30', 'timezone': 'Asia/Kolkata'},
            'contract_note': 'Use the lot size applicable to your contract and trade date. No live contract master or price feed is connected.'}
