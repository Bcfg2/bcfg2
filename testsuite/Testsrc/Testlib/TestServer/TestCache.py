import os
import sys

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

from Bcfg2.Server.Cache import *


class TestCache(Bcfg2TestCase):
    def test_cache(self):
        md_cache = Cache("Metadata")
        md_cache['foo.example.com'] = 'foo metadata'
        md_cache['bar.example.com'] = 'bar metadata'
        self.assertItemsEqual(list(iter(md_cache)),
                              ["foo.example.com", "bar.example.com"])

        probe_cache = Cache("Probes", "data")
        probe_cache['foo.example.com'] = 'foo probe data'
        probe_cache['bar.example.com'] = 'bar probe data'
        self.assertItemsEqual(list(iter(probe_cache)),
                              ["foo.example.com", "bar.example.com"])

        md_cache.expire("foo.example.com")
        self.assertItemsEqual(list(iter(md_cache)), ["bar.example.com"])
        self.assertItemsEqual(list(iter(probe_cache)),
                              ["foo.example.com", "bar.example.com"])

        probe_cache.expire("bar.example.com")
        self.assertItemsEqual(list(iter(md_cache)), ["bar.example.com"])
        self.assertItemsEqual(list(iter(probe_cache)),
                              ["foo.example.com"])

        probe_cache['bar.example.com'] = 'bar probe data'
        self.assertItemsEqual(list(iter(md_cache)), ["bar.example.com"])
        self.assertItemsEqual(list(iter(probe_cache)),
                              ["foo.example.com", "bar.example.com"])

        expire("bar.example.com")
        self.assertEqual(len(md_cache), 0)
        self.assertItemsEqual(list(iter(probe_cache)),
                              ["foo.example.com"])

        probe_cache2 = Cache("Probes", "data")
        self.assertItemsEqual(list(iter(probe_cache)),
                              list(iter(probe_cache2)))
