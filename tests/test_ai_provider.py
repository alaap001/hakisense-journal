"""Provider transport failures must not cause duplicate paid generations."""
import asyncio
import json
import unittest
from unittest.mock import patch
import httpx
from tests import test_core  # Isolated configuration, never real provider credentials.
from backend import ai_runtime


class ProviderTransport(unittest.TestCase):
    def setUp(self):
        ai_runtime._reasoning_required.clear()

    def tearDown(self):
        ai_runtime._reasoning_required.clear()

    def run_stream(self, handler):
        self.text, self.ids = [], []
        async def text(value): self.text.append(value)
        async def identity(value): self.ids.append(value)
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with patch('backend.ai_runtime.httpx.AsyncClient', return_value=client):
            return asyncio.run(ai_runtime.provider_stream('fixture/model', [{'role': 'user', 'content': 'Hi'}],
                {'reasoning_effort': 'none'}, 4000, text, identity))

    @staticmethod
    def success():
        # Native usage arrives after the answer's finish frame, as with OpenRouter.
        frames = [
            {'id': 'generation-fixture', 'choices': [{'delta': {'content': 'Hello!'}, 'finish_reason': 'stop'}]},
            {'choices': [], 'usage': {'prompt_tokens': 100, 'completion_tokens': 30,
                                    'completion_tokens_details': {'reasoning_tokens': 20}}},
        ]
        return httpx.Response(200, text=''.join('data: '+json.dumps(frame)+'\n\n' for frame in frames)+'data: [DONE]\n\n')

    def test_mandatory_reasoning_rejection_is_corrected_before_generation(self):
        sent = []
        def handle(request):
            sent.append(json.loads(request.content))
            if len(sent) == 1:
                return httpx.Response(400, json={'error': {'code': 400,
                    'message': 'Reasoning is mandatory for this endpoint and cannot be disabled.'}})
            return self.success()
        result = self.run_stream(handle)
        self.assertEqual(len(sent), 2)
        self.assertEqual(sent[0]['reasoning'], {'enabled': False})
        self.assertEqual(sent[1]['reasoning'], {'effort': 'low'})
        self.assertEqual(result[0], 'Hello!')
        self.assertEqual(result[1]['output_tokens'], 30)
        self.assertEqual(self.ids, ['generation-fixture'])
        self.assertEqual(self.text, ['Hello!'])
        self.run_stream(handle)
        self.assertEqual(len(sent), 3)
        self.assertEqual(sent[-1]['reasoning'], {'effort': 'low'})

    def test_other_rejections_are_not_retried_and_credentials_are_redacted(self):
        requests = []
        def handle(request):
            requests.append(request)
            return httpx.Response(400, json={'error': {'code': 400,
                'message': 'Invalid option. Bearer sk-private-token'}})
        with self.assertRaises(ai_runtime.ProviderFailure) as failure:
            self.run_stream(handle)
        self.assertEqual(len(requests), 1)
        self.assertIn('Invalid option', str(failure.exception))
        self.assertNotIn('sk-private-token', str(failure.exception))

    def test_uncertain_timeout_is_never_replayed(self):
        requests = []
        def handle(request):
            requests.append(request)
            raise httpx.ReadTimeout('Timed out', request=request)
        with self.assertRaises(httpx.ReadTimeout): self.run_stream(handle)
        self.assertEqual(len(requests), 1)

    def test_stream_failure_after_generation_is_never_replayed(self):
        requests = []
        def handle(request):
            requests.append(request)
            return httpx.Response(200, text='data: {"id":"started","choices":[]}\n\ndata: {"error":{"message":"Failed"}}\n\n')
        with self.assertRaises(ai_runtime.ProviderFailure): self.run_stream(handle)
        self.assertEqual(len(requests), 1)
        self.assertEqual(self.ids, ['started'])
