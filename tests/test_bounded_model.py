"""CI entry point for the bounded, independently checked policy explorer."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

BINARY=Path(sys.argv[1]).resolve()
ROOT=Path(sys.argv[2]).resolve()
sys.argv=[sys.argv[0]]
sys.path.insert(0,str(ROOT))

from verification.bounded_model import explore


class BoundedPolicyExploration(unittest.TestCase):
    def test_all_declared_traces_and_prefixes(self):
        summary=explore(BINARY)
        self.assertEqual(summary["bounded_traces"],408)
        self.assertEqual(summary["checked_prefixes"],1608)
        self.assertGreater(summary["allow"],0)
        self.assertGreater(summary["deny"],0)
        self.assertGreater(summary["abstain"],0)
        self.assertFalse(summary["formal_proof"])
        print("Bounded verification:",summary)


if __name__ == "__main__":
    unittest.main(verbosity=2)
