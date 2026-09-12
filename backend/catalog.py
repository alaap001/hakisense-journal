"""Initial commercial catalog. Migrations seed it; runtime reads PostgreSQL."""
FREE_FEATURES = ['journal', 'analytics', 'calendar', 'notebook', 'import_export', 'accounts']
PAID_FEATURES = FREE_FEATURES + ['replay', 'playbooks', 'saved_views']
PLANS = [
    {'code': 'free', 'name': 'Free', 'monthly_credits': 50, 'trade_limit': 100, 'model_tier': 'standard', 'features': FREE_FEATURES, 'active': True},
    {'code': 'pro', 'name': 'Pro', 'monthly_credits': 1000, 'trade_limit': None, 'model_tier': 'standard', 'features': PAID_FEATURES, 'active': True},
    {'code': 'advanced', 'name': 'Advanced', 'monthly_credits': 8000, 'trade_limit': None, 'model_tier': 'advanced', 'features': PAID_FEATURES, 'active': True},
]
PRICES = [
    {'code': 'pro_monthly', 'plan_code': 'pro', 'interval': 'month', 'amount_paise': 40000, 'currency': 'INR', 'tax_inclusive': True, 'active': True},
    {'code': 'pro_annual', 'plan_code': 'pro', 'interval': 'year', 'amount_paise': 249900, 'currency': 'INR', 'tax_inclusive': True, 'active': True},
    {'code': 'advanced_annual', 'plan_code': 'advanced', 'interval': 'year', 'amount_paise': 899900, 'currency': 'INR', 'tax_inclusive': True, 'active': True},
]
TASKS = [
    {'code': 'chat', 'name': 'Ask your journal', 'credits': 2, 'enabled': True},
    {'code': 'trade_note', 'name': 'Draft a trade review', 'credits': 1, 'enabled': True},
    {'code': 'summary', 'name': 'Performance summary', 'credits': 2, 'enabled': True},
    {'code': 'query', 'name': 'Query and chart', 'credits': 4, 'enabled': True},
    {'code': 'daily', 'name': 'Next-session preparation', 'credits': 3, 'enabled': True},
    {'code': 'coach', 'name': 'Detailed coaching review', 'credits': 5, 'enabled': True},
]
FEATURE_NAMES = {'journal': 'Trade journal', 'analytics': 'Analytics & risk tools', 'calendar': 'Trading calendar',
                 'notebook': 'Notebook', 'import_export': 'File imports & exports', 'accounts': 'Broker accounts',
                 'replay': 'Market replay', 'playbooks': 'Strategy playbooks', 'saved_views': 'Saved journal views'}
