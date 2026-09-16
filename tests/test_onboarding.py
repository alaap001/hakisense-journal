"""Authenticated tour lifecycle, persistence, rollout and stale-tab boundaries."""
import unittest
from tests import test_core as core
from backend.onboarding import STEPS
from backend import db as store


class OnboardingTests(unittest.TestCase):
    setUp = core.ProductionCore.setUp
    tearDown = core.ProductionCore.tearDown

    def read(self):
        response = self.client.get('/api/onboarding')
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def act(self, action, state=None, status=200):
        state = state or self.read()
        response = self.client.put('/api/onboarding', json={
            'action': action, 'version': state['version'], 'revision': state['revision']})
        self.assertEqual(response.status_code, status, response.text)
        return response.json()

    def test_first_workspace_resumes_and_completion_persists(self):
        initial = self.work['onboarding']
        self.assertEqual(initial['status'], 'pending')
        self.assertEqual(initial['step'], STEPS[0])
        self.assertEqual(self.read(), initial)
        for step in STEPS[1:]:
            saved = self.act('next')
            self.assertEqual(saved['step'], step)
            self.assertEqual(saved['status'], 'in_progress')
            self.assertIsNotNone(saved['started_at'])
            self.assertEqual(self.client.get('/api/workspace').json()['onboarding'], saved)
        finished = self.act('complete')
        self.assertEqual(finished['status'], 'completed')
        self.assertIsNotNone(finished['finished_at'])
        self.assertEqual(self.read(), finished)
        self.assertEqual(self.client.get('/api/workspace').json()['onboarding'], finished)

    def test_skip_back_and_explicit_restart(self):
        self.act('next')
        self.assertEqual(self.act('back')['step'], STEPS[0])
        skipped = self.act('skip')
        self.assertEqual(skipped['status'], 'skipped')
        self.assertEqual(self.client.get('/api/workspace').json()['onboarding'], skipped)
        self.act('next', status=409)
        restarted = self.act('restart')
        self.assertEqual(restarted['status'], 'in_progress')
        self.assertEqual(restarted['step'], STEPS[0])
        self.assertIsNone(restarted['finished_at'])
        self.assertGreater(restarted['revision'], skipped['revision'])

    def test_old_workspace_is_opt_in(self):
        # Represents an account provisioned before this feature existed.
        with store.database(self.a) as db:
            db.delete(store.get_setting(db, 'onboarding'))
        old = self.client.get('/api/workspace').json()['onboarding']
        self.assertEqual(old['status'], 'not_required')
        self.assertEqual(self.read(), old)
        self.assertEqual(self.act('restart')['status'], 'in_progress')

    def test_tenant_state_cannot_leak_or_be_overwritten(self):
        a = self.act('next')
        self.actor = self.b
        self.assertEqual(self.read()['status'], 'pending')
        b = self.act('skip')
        self.actor = self.a
        self.assertEqual(self.read(), a)
        payload = {'action': 'skip', 'version': 1, 'revision': a['revision'], 'user_id': self.b}
        self.assertEqual(self.client.put('/api/onboarding', json=payload).status_code, 422)
        self.actor = self.b
        self.assertEqual(self.read(), b)

    def test_stale_or_duplicate_requests_cannot_undo_progress(self):
        stale = self.read()
        saved = self.act('next', stale)
        self.act('next', stale, status=409)
        self.act('skip', stale, status=409)
        self.assertEqual(self.read(), saved)
        finished = self.act('skip')
        self.act('restart', saved, status=409)
        self.assertEqual(self.read(), finished)

    def test_invalid_transitions_and_generic_settings_cannot_bypass_api(self):
        initial = self.read()
        self.act('back', status=422)
        self.act('complete', status=422)
        payload = {'action': 'next', 'version': 1, 'revision': 0}
        for changes in ({'action':'invented'}, {'version':2}, {'revision':-1}, {'revision':'0'},
                        {'step':'wallet'}, {'status':'completed'}, {'finished_at':'yesterday'}):
            self.assertEqual(self.client.put('/api/onboarding', json={**payload, **changes}).status_code, 422)
        self.assertEqual(self.client.put('/api/settings/onboarding', json={'data':{'status':'completed'}}).status_code, 400)
        self.assertEqual(self.read(), initial)

    def test_authentication_required(self):
        core.app.dependency_overrides.clear()
        self.assertEqual(self.client.get('/api/onboarding').status_code, 401)
        self.assertEqual(self.client.put('/api/onboarding', json={'action':'skip','version':1,'revision':0}).status_code, 401)
