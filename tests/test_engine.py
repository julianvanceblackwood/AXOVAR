"""Real, deterministic C++ executable tests (stdlib only)."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BINARY = Path(sys.argv[1]).resolve()
ROOT = Path(sys.argv[2]).resolve()
sys.argv = [sys.argv[0]]


def run(filename, step=99):
    completed = subprocess.run([str(BINARY), '--scenario', str(ROOT / 'scenarios' / filename), str(step)],
                               text=True, capture_output=True, check=True)
    return json.loads(completed.stdout)


class CoreTests(unittest.TestCase):
    def test_normal_allows_with_three_independent_sources(self):
        state = run('NORMAL-001.csv')
        self.assertEqual(state['decision']['result'], 'ALLOW_SIMULATION')
        self.assertEqual(state['metrics']['independent_healthy_sources'], 3)
        self.assertEqual(state['step'], 9)
        self.assertLess(state['metrics']['post_trade_btc_exposure_pct'], 75)

    def test_adversarial_feed_blocks(self):
        state = run('DEGRADED-001.csv')
        self.assertEqual(state['decision']['result'], 'INSUFFICIENT_EVIDENCE')
        self.assertEqual(state['metrics']['independent_healthy_sources'], 1)
        self.assertGreater(state['metrics']['venue_disagreement_bps'], 150)
        self.assertTrue(any('SEQUENCE_GAP' in a for a in state['alerts']))
        self.assertTrue(any('UPSTREAM_CHANGED' in a for a in state['alerts']))

    def test_replay_same_inputs_same_bytes(self):
        a = subprocess.check_output([str(BINARY), '--scenario', str(ROOT/'scenarios/NORMAL-001.csv'), '9'])
        b = subprocess.check_output([str(BINARY), '--scenario', str(ROOT/'scenarios/NORMAL-001.csv'), '9'])
        self.assertEqual(a, b)

    def test_historical_knowledge_only(self):
        first = run('DEGRADED-001.csv', 3)
        self.assertEqual(first['decision']['result'], 'ALLOW_SIMULATION')
        self.assertEqual(len(first['events']), 3)
        self.assertFalse(any('DEGRADED_SOURCE' in a for a in first['alerts']))
        later = run('DEGRADED-001.csv', 6)
        self.assertNotEqual(first['decision']['result'], later['decision']['result'])

    def test_empty_replay_abstains(self):
        state=run('NORMAL-001.csv', 0)
        self.assertEqual(state['step'], 0)
        self.assertEqual(state['decision']['result'], 'INSUFFICIENT_EVIDENCE')
        self.assertEqual(state['venues'], [])

    def test_step_capped_at_total(self):
        self.assertEqual(run('NORMAL-001.csv', 1000)['step'], 9)

    def test_invalid_numeric_values_rejected(self):
        template = 'id,event_ms,receive_ms,venue,upstream,sequence,price_cents,health\nX1,1,1,A,U,1,{price},OK\n'
        for price in ['-1','nan','0','99999999999999999999']:
            with self.subTest(price=price), tempfile.TemporaryDirectory() as temp:
                path=Path(temp)/'invalid.csv'
                path.write_text(template.format(price=price))
                proc=subprocess.run([str(BINARY),'--scenario',str(path),'1'],capture_output=True,text=True)
                self.assertNotEqual(proc.returncode,0)

    def test_duplicate_event_identifiers_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'dup.csv'
            path.write_text('id,event_ms,receive_ms,venue,upstream,sequence,price_cents,health\n'
                            'X1,1,1,A,U,1,100,OK\nX1,2,2,A,U,2,101,OK\n')
            proc=subprocess.run([str(BINARY),'--scenario',str(path),'2'],capture_output=True)
            self.assertNotEqual(proc.returncode,0)

    def test_shared_upstream_counts_once(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'shared.csv'
            path.write_text('id,event_ms,receive_ms,venue,upstream,sequence,price_cents,health\n'
                            'X1,1,1,A,UP,1,10000000,OK\nX2,2,2,B,UP,1,10000100,OK\n')
            out=subprocess.check_output([str(BINARY),'--scenario',str(path),'2'])
            state=json.loads(out)
            self.assertEqual(state['metrics']['independent_healthy_sources'],1)
            self.assertEqual(state['decision']['result'],'INSUFFICIENT_EVIDENCE')
            self.assertTrue(any('SHARED_UPSTREAM' in a for a in state['alerts']))

    def test_exposure_limit_prevents_action(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'higher-price.csv'
            path.write_text('id,event_ms,receive_ms,venue,upstream,sequence,price_cents,health\n'
                            'X1,1,1,A,U1,1,20000000,OK\nX2,2,2,B,U2,1,20000000,OK\n')
            state=json.loads(subprocess.check_output([str(BINARY),'--scenario',str(path),'2']))
            self.assertEqual(state['decision']['result'],'DENY_SIMULATION')
            self.assertGreater(state['metrics']['post_trade_btc_exposure_pct'],75)

    def test_stale_source_abstention(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'stale.csv'
            path.write_text('id,event_ms,receive_ms,venue,upstream,sequence,price_cents,health\n'
                            'X1,1,1,A,U1,1,10000000,OK\nX2,5000,5000,B,U2,1,10001000,OK\n')
            state=json.loads(subprocess.check_output([str(BINARY),'--scenario',str(path),'2']))
            self.assertEqual(state['decision']['result'],'INSUFFICIENT_EVIDENCE')
            self.assertIn('STALE_SOURCE:A', state['alerts'])

if __name__ == '__main__': unittest.main(verbosity=2)
