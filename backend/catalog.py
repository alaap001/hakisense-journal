"""Bootstrap credit prices. Runtime values are read from PostgreSQL."""
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
UPCOMING_FEATURE_NAMES = {'deep_stock_research': 'Deep Researched Stock Analysis'}

PACKS = [
    {'code': 'first_recharge', 'name': 'First recharge', 'credits': 50, 'amount_paise': 2400, 'first_purchase_only': True, 'sort_order': 0},
    {'code': 'starter_50', 'name': 'Starter', 'credits': 50, 'amount_paise': 5000, 'sort_order': 1},
    {'code': 'review_600', 'name': 'Review', 'credits': 600, 'amount_paise': 19900, 'sort_order': 2},
    {'code': 'deep_dive_4000', 'name': 'Deep dive', 'credits': 4000, 'amount_paise': 50000, 'sort_order': 3},
]
