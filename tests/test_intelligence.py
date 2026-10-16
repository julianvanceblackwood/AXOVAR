"""Tests for the read-only Intelligence boundary; no Ollama installation needed."""
import json
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BINARY = Path(sys.argv[1]).resolve()
ROOT = Path(sys.argv[2]).resolve()
sys.argv = [sys.argv[0]]
sys.path.insert(0, str(ROOT))
from server.app import Session, create_handler
from server import intelligence


class IntelligenceUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = ThreadingHTTPServer(('127.0.0.1', 0), create_handler(ROOT, BINARY, Session()))
        cls.thread = threading.Thread(target=cls.service.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.service.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.service.shutdown()
        cls.thread.join(timeout=5)
        cls.service.server_close()

    def post(self, url, payload, origin=None, content_type='application/json'):
        request = Request(self.base + url, method='POST',
                          headers={'Content-Type': content_type},
                          data=json.dumps(payload).encode())
        if origin:
            request.add_header('Origin', origin)
        with urlopen(request, timeout=5) as response:
            return json.loads(response.read())

    def get(self, url):
        with urlopen(self.base + url, timeout=5) as response:
            return json.loads(response.read())

    def setUp(self):
        self.post('/api/replay/scenario', {'scenario': 'DEGRADED-001'})
        self.post('/api/replay/end', {})

    def test_deterministic_evidence_answer(self):
        response = self.post('/api/intelligence/ask', {'question': 'Why was the decision made?', 'use_model': False})
        self.assertEqual(response['mode'], 'evidence-only')
        self.assertIn('INSUFFICIENT_EVIDENCE', response['answer'])
        self.assertTrue(response['synthetic'])
        self.assertGreater(len(response['evidence_ids']), 0)

    def test_source_dependencies_are_explained(self):
        response = self.post('/api/intelligence/ask', {'question': 'Are the sources independent?', 'use_model': False})
        self.assertIn('upstream', response['answer'])
        self.assertIn('fixture assertions', response['answer'])

    def test_limited_general_question_is_not_fabricated(self):
        response = self.post('/api/intelligence/ask', {'question': 'What is the live Bitcoin price?', 'use_model': False})
        self.assertIn('cannot provide a live market price', response['answer'])
        self.assertTrue(response['synthetic'])

    def test_question_validation(self):
        for bad in ('', 'x', 'x' * 1001):
            with self.subTest(bad=len(bad)), self.assertRaises(HTTPError) as ctx:
                self.post('/api/intelligence/ask', {'question': bad, 'use_model': False})
            self.assertEqual(ctx.exception.code, 400)

    def test_rejects_cross_origin(self):
        with self.assertRaises(HTTPError) as ctx:
            self.post('/api/intelligence/ask', {'question': 'Why is evidence missing?'}, origin='https://example.com')
        self.assertEqual(ctx.exception.code, 403)

    def test_rejects_incorrect_type_and_content_type(self):
        with self.assertRaises(HTTPError) as ctx:
            self.post('/api/intelligence/ask', {'question': 'Why?', 'use_model': 'yes'})
        self.assertEqual(ctx.exception.code, 400)
        with self.assertRaises(HTTPError) as ctx:
            self.post('/api/intelligence/ask', {'question': 'Why?'}, content_type='text/plain')
        self.assertEqual(ctx.exception.code, 415)

    def test_model_is_never_authoritative(self):
        with patch.object(intelligence, '_model_request', return_value={
            'message': {'content': 'A research hypothesis, not a trade instruction.'}
        }) as mocked:
            response = self.post('/api/intelligence/ask', {'question': 'Explain observed risk.'})
            self.assertEqual(response['mode'], 'local-model')
            self.assertIn('research hypothesis', response['answer'])
            payload = mocked.call_args.args[1]
            self.assertEqual(payload['model'], 'gemma3:4b')
            self.assertEqual(payload['stream'], False)
            self.assertNotIn('tools', payload)
            self.assertNotIn('raw', payload['messages'][1]['content'].split('Question:')[0])
        self.assertEqual(self.get('/api/state')['decision']['result'], 'INSUFFICIENT_EVIDENCE')

    def test_status_when_model_not_installed(self):
        with patch.object(intelligence, '_model_request', side_effect=OSError('offline')):
            status = self.get('/api/intelligence/status')
        self.assertFalse(status['available'])
        self.assertEqual(status['mode'], 'evidence-only')
        self.assertTrue(status['read_only'])

    def test_model_failure_degrades_to_evidence_mode(self):
        with patch.object(intelligence, '_model_request', side_effect=OSError('offline')):
            answer = self.post('/api/intelligence/ask', {'question': 'Why was the decision made?'})
        self.assertEqual(answer['mode'], 'evidence-only')
        self.assertIn('INSUFFICIENT_EVIDENCE', answer['answer'])

    def test_unprocessed_market_does_not_claim_evidence(self):
        self.post('/api/replay/reset', {})
        response = self.post('/api/intelligence/ask', {'question': 'Why was the decision made?', 'use_model': False})
        self.assertIn('No market events', response['answer'])
        self.assertEqual(response['evidence_ids'], [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
