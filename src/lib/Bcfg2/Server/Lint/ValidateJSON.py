"""Validate JSON files.

Ensure that all JSON files in the Bcfg2 repository are
valid. Currently, the only plugins that uses JSON are Ohai and
Properties.
"""

import os
import sys

import Bcfg2.Server.Lint

try:
    import json
    # py2.4 json library is structured differently
    json.loads  # pylint: disable=W0104
except (ImportError, AttributeError):
    import simplejson as json


class ValidateJSON(Bcfg2.Server.Lint.ServerlessPlugin):
    """Ensure that all JSON files in the Bcfg2 repository are
    valid. Currently, the only plugins that uses JSON are Ohai and
    Properties. """

    def __init__(self, *args, **kwargs):
        Bcfg2.Server.Lint.ServerlessPlugin.__init__(self, *args, **kwargs)

        #: A list of file globs that give the path to JSON files.  The
        #: globs are extended :mod:`fnmatch` globs that also support
        #: ``**``, which matches any number of any characters,
        #: including forward slashes.
        self.globs = ["Properties/*.json", "Ohai/*.json"]
        self.files = self.get_files()

    def Run(self):
        for path in self.files:
            self.logger.debug("Validating JSON in %s" % path)
            try:
                json.load(open(path))
            except ValueError:
                self.LintError("json-failed-to-parse",
                               "%s does not contain valid JSON: %s" %
                               (path, sys.exc_info()[1]))

    @classmethod
    def Errors(cls):
        return {"json-failed-to-parse": "error"}

    def get_files(self):
        """Return a list of all JSON files to validate, based on
        :attr:`Bcfg2.Server.Lint.ValidateJSON.ValidateJSON.globs`. """
        rv = []
        for path in self.globs:
            if '/**/' in path:
                if self.files is not None:
                    rv.extend(self.list_matching_files(path))
                else:  # self.files is None
                    fpath, fname = path.split('/**/')
                    for root, _, files in os.walk(
                            os.path.join(Bcfg2.Options.setup.repository,
                                         fpath)):
                        rv.extend([os.path.join(root, f)
                                   for f in files if f == fname])
            else:
                rv.extend(self.list_matching_files(path))
        return rv
