"""helper functions for option testing."""

import os
import tempfile

from Bcfg2.Compat import wraps, ConfigParser
from Bcfg2.Options import Parser, PathOption
from testsuite.common import Bcfg2TestCase


class make_config(object):  # pylint: disable=invalid-name
    """decorator to create a temporary config file from a dict.

    The filename of the temporary config file is added as the last
    positional argument to the function call.
    """
    def __init__(self, config_data=None):
        self.config_data = config_data or {}

    def __call__(self, func):
        @wraps(func)
        def inner(*args, **kwargs):
            """decorated function."""
            cfp = ConfigParser.ConfigParser()
            for section, options in self.config_data.items():
                cfp.add_section(section)
                for key, val in options.items():
                    cfp.set(section, key, val)
            fd, name = tempfile.mkstemp()
            config_file = os.fdopen(fd, 'w')
            cfp.write(config_file)
            config_file.close()

            args = list(args) + [name]
            try:
                rv = func(*args, **kwargs)
            finally:
                os.unlink(name)
            return rv

        return inner


def clean_environment(func):
    """decorator that unsets any environment variables used by options.

    The list of options is taken from the first argument, which is
    presumed to be ``self``.  The variables are restored at the end of
    the function.
    """
    @wraps(func)
    def inner(self, *args, **kwargs):
        """decorated function."""
        envvars = {}
        for opt in self.options:
            if opt.env is not None:
                envvars[opt.env] = os.environ.get(opt.env)
                if opt.env in os.environ:
                    del os.environ[opt.env]
        rv = func(self, *args, **kwargs)
        for name, val in envvars.items():
            if val is None and name in os.environ:
                del os.environ[name]
            elif val is not None:
                os.environ[name] = val
        return rv

    return inner


class OptionTestCase(Bcfg2TestCase):
    """test case that doesn't mock out config file reading."""

    @classmethod
    def setUpClass(cls):
        # ensure that the option parser actually reads config files
        Parser.unit_test = False
        Bcfg2TestCase.setUpClass()

    def setUp(self):
        Bcfg2TestCase.setUp(self)
        PathOption.repository = None

    @classmethod
    def tearDownClass(cls):
        Parser.unit_test = True
