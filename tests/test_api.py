import json
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BINARY=Path(sys.argv[1]).resolve()
ROOT=Path(sys.argv[2]).resolve()
sys.argv=[sys.argv[0]]
sys.path.insert(0,str(ROOT))
from server.app import Session, create_handler

class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service=ThreadingHTTPServer(('127.0.0.1',0),create_handler(ROOT,BINARY,Session()))
        cls.port=cls.service.server_port
        cls.thread=threading.Thread(target=cls.service.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.service.shutdown()
        cls.thread.join(timeout=5)
        cls.service.server_close()

    def get(self,path):
        with urlopen(f'http://127.0.0.1:{self.port}'+path, timeout=3) as r:
            return json.loads(r.read())

    def post(self,path,data=None,origin=None):
        req=Request(f'http://127.0.0.1:{self.port}'+path,
                    data=json.dumps(data or {}).encode(),headers={'Content-Type':'application/json'},method='POST')
        if origin:req.add_header('Origin',origin)
        with urlopen(req,timeout=3) as r:return json.loads(r.read())

    def test_health_and_scenarios(self):
        self.assertTrue(self.get('/api/health')['simulation_only'])
        self.assertEqual(len(self.get('/api/scenarios')['scenarios']),2)

    def test_replay_sequence(self):
        self.post('/api/replay/scenario',{'scenario':'NORMAL-001'})
        self.assertEqual(self.get('/api/state')['step'],0)
        self.assertEqual(self.post('/api/replay/step')['step'],1)
        self.assertEqual(self.post('/api/replay/end')['step'],9)
        self.assertEqual(self.post('/api/replay/reset')['step'],0)

    def test_raw_sha256_and_evidence(self):
        self.post('/api/replay/scenario',{'scenario':'DEGRADED-001'})
        raw=self.get('/api/raw')
        self.assertEqual(len(raw['fixture_sha256']),64)
        self.assertEqual(len(raw['records']),9)
        state=self.post('/api/replay/end')
        self.assertEqual(state['decision']['result'],'INSUFFICIENT_EVIDENCE')

    def test_invalid_scenario_rejected(self):
        with self.assertRaises(HTTPError) as ctx:self.post('/api/replay/scenario',{'scenario':'../private'})
        self.assertEqual(ctx.exception.code,400)

    def test_cross_origin_rejected(self):
        with self.assertRaises(HTTPError) as ctx:self.post('/api/replay/step',origin='https://untrusted.example')
        self.assertEqual(ctx.exception.code,403)

if __name__=='__main__':unittest.main(verbosity=2)
