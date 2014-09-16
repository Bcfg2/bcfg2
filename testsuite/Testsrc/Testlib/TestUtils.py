import os
import sys
from Bcfg2.Utils import *

# add all parent testsuite directories to sys.path to allow (most)
# relative imports in python 2.4
path = os.path.dirname(__file__)
while path != "/":
    if os.path.basename(path).lower().startswith("test"):
        sys.path.append(path)
    if os.path.basename(path) == "testsuite":
        break
    path = os.path.dirname(path)
from common import *


class TestPackedDigitRange(Bcfg2TestCase):
    def test_ranges(self):
        # test cases.  tuples of (ranges, included numbers, excluded
        # numbers)
        # tuples of (range description, numbers that are included,
        # numebrs that are excluded)
        tests = [(["0-3"], ["0", 1, "2", 3], [4]),
                 (["1"], [1], [0, "2"]),
                 (["10-11"], [10, 11], [0, 1]),
                 (["9-9"], [9], [8, 10]),
                 (["0-100"], [0, 10, 99, 100], []),
                 (["1", "3", "5"], [1, 3, 5], [0, 2, 4, 6]),
                 (["1-5", "7"], [1, 3, 5, 7], [0, 6, 8]),
                 (["1-5", 7, "9-11"], [1, 3, 5, 7, 9, 11], [0, 6, 8, 12]),
                 (["1-5,   7,9-11  "], [1, 3, 5, 7, 9, 11], [0, 6, 8, 12]),
                 (["852-855", "321-497", 763], [852, 855, 321, 400, 497, 763],
                  [851, 320, 766, 999]),
                 (["0-"], [0, 1, 100, 100000], []),
                 ([1, "5-10", "1000-"], [1, 5, 10, 1000, 10000000],
                  [4, 11, 999])]
        for ranges, inc, exc in tests:
            rng = PackedDigitRange(*ranges)
            for test in inc:
                self.assertIn(test, rng)
                self.assertTrue(rng.includes(test))
            for test in exc:
                self.assertNotIn(test, rng)
                self.assertFalse(rng.includes(test))
