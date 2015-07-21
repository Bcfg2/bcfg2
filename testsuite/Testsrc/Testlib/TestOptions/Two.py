"""Test module for component loading."""
from Bcfg2.Options import Option


class Two(object):
    """Test class for component loading."""
    options = [Option('--test', cf=("config", "test"), dest="test", default="bar")]
