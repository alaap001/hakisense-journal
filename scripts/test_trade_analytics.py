"""Test analytics calculations on the generated trades."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.trade_generator import generate_trades
from backend.analytics import enrich, statistics

dummy_acc = '8bc7b405-a065-41a3-a6be-1de15f63deb8'
raw_trades = generate_trades(dummy_acc, 100)

enriched = [enrich(t) for t in raw_trades]
stats = statistics(enriched, balance=500000)

print("Metrics summary:")
for k, v in stats['metrics'].items():
    print(f"  {k}: {v}")
print(f"Equity curve points: {len(stats['equity'])}")
print(f"Daily points: {len(stats['daily'])}")

