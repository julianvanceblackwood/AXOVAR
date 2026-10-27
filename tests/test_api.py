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
        health = self.get('/api/health')
        self.assertTrue(health['simulation_only'])
        self.assertEqual(health['stage'], 'G0-G5 research')
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

    def test_host_header_rebinding_rejected(self):
        url=f'http://127.0.0.1:{self.port}'
        for path,method,data in (('/api/state','GET',None),
                                  ('/api/replay/step','POST',b'{}')):
            for host in ('attacker.example', f'attacker.example:{self.port}',
                         f'127.0.0.1:{self.port}@attacker.example'):
                with self.subTest(path=path,host=host):
                    request=Request(url+path,method=method,data=data,
                                    headers={'Host':host,'Content-Type':'application/json'})
                    with self.assertRaises(HTTPError) as ctx:
                        urlopen(request,timeout=3)
                    self.assertEqual(ctx.exception.code,403)

    def test_failed_replay_is_atomic(self):
        import subprocess
        handler = create_handler(ROOT, BINARY, session := Session())
        original = handler.data

        def fault(self, scenario, step):
            if step > 0 or scenario == 'DEGRADED-001':
                raise subprocess.SubprocessError('injected engine fault')
            return original(self, scenario, step)

        handler.data = fault
        service = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        worker = threading.Thread(target=service.serve_forever, daemon=True)
        worker.start()
        base = f'http://127.0.0.1:{service.server_port}'
        try:
            for route, body in (
                ('/api/replay/step', {}),
                ('/api/replay/scenario', {'scenario': 'DEGRADED-001'})
            ):
                with self.subTest(route=route):
                    request = Request(base + route, data=json.dumps(body).encode(),
                                      headers={'Content-Type': 'application/json'},
                                      method='POST')
                    with self.assertRaises(HTTPError) as ctx:
                        urlopen(request, timeout=3)
                    self.assertEqual(ctx.exception.code, 500)
                    self.assertEqual((session.scenario, session.step),
                                     ('NORMAL-001', 0))
            with urlopen(base + '/api/state', timeout=3) as response:
                self.assertEqual(json.loads(response.read())['step'], 0)
        finally:
            service.shutdown()
            worker.join(timeout=5)
            service.server_close()

    def test_invalid_engine_json_is_server_error(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        with patch('server.app.subprocess.run',
                   return_value=SimpleNamespace(stdout='invalid json')):
            request = Request(f'http://127.0.0.1:{self.port}/api/state')
            with self.assertRaises(HTTPError) as ctx:
                urlopen(request, timeout=3)
            self.assertEqual(ctx.exception.code, 500)

    def test_cross_origin_rejected(self):
        with self.assertRaises(HTTPError) as ctx:self.post('/api/replay/step',origin='https://untrusted.example')
        self.assertEqual(ctx.exception.code,403)

if __name__=='__main__':unittest.main(verbosity=2)
