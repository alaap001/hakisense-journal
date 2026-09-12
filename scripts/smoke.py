"""Run the bounded offline core and administration checks."""
import sys
import unittest
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
suite=unittest.defaultTestLoader.discover(str(root/'tests'),pattern='test_*.py',top_level_dir=str(root))
result=unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
