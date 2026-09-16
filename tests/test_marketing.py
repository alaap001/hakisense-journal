"""Small checks around the public catalog and upcoming-vs-available feature boundary."""
import unittest
from tests import test_core as core
from backend import db as store
from backend.main import app


class MarketingCatalog(unittest.TestCase):
    setUp = core.ProductionCore.setUp
    tearDown = core.ProductionCore.tearDown

    def test_public_catalog_has_current_offers_without_private_provider_ids(self):
        app.dependency_overrides.clear()
        response = self.client.get('/api/catalog')
        self.assertEqual(response.status_code, 200)
        catalog = response.json()
        self.assertNotIn('prices',catalog)
        self.assertEqual([(p['credits'],p['amount_paise']) for p in catalog['packs']],[(50,2400),(50,5000),(600,19900),(4000,50000)])
        self.assertTrue(all('provider_id' not in p for p in catalog['packs']))
        self.assertTrue(all(not p['checkout_available'] for p in catalog['packs']))
        self.assertNotIn('users', catalog)

    def test_upcoming_research_is_not_an_available_feature(self):
        public=self.client.get('/api/catalog').json()
        self.assertNotIn('deep_stock_research',public['features'])
        self.assertIn('deep_stock_research',public['upcoming_features'])
        self.assertNotIn('deep_stock_research',self.client.get('/api/workspace').json()['billing']['features'])
