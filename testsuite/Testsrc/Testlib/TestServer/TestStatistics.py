import os
import sys
from mock import Mock, MagicMock, patch

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

from Bcfg2.Server.Statistics import *


class TestStatistic(Bcfg2TestCase):
    def test_stat(self):
        stat = Statistic("test", 1)
        self.assertEqual(stat.get_value(), ("test", (1.0, 1.0, 1.0, 1)))
        stat.add_value(10)
        self.assertEqual(stat.get_value(), ("test", (1.0, 10.0, 5.5, 2)))
        stat.add_value(100)
        self.assertEqual(stat.get_value(), ("test", (1.0, 100.0, 37.0, 3)))
        stat.add_value(12.345)
        self.assertEqual(stat.get_value(), ("test", (1.0, 100.0, 30.83625, 4)))
        stat.add_value(0.655)
        self.assertEqual(stat.get_value(), ("test", (0.655, 100.0, 24.8, 5)))


class TestStatistics(Bcfg2TestCase):
    def test_stats(self):
        stats = Statistics()
        self.assertEqual(stats.display(), dict())
        stats.add_value("test1", 1)
        self.assertEqual(stats.display(), dict(test1=(1.0, 1.0, 1.0, 1)))
        stats.add_value("test2", 1.23)
        self.assertEqual(stats.display(), dict(test1=(1.0, 1.0, 1.0, 1),
                                               test2=(1.23, 1.23, 1.23, 1)))
        stats.add_value("test1", 10)
        self.assertEqual(stats.display(), dict(test1=(1.0, 10.0, 5.5, 2),
                                               test2=(1.23, 1.23, 1.23, 1)))
