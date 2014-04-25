""" ``bcfg2-lint`` plugin to check all given :ref:`AWSTags
<server-plugins-connectors-awstags>` patterns for validity."""

import re
import sys
import Bcfg2.Server.Lint


class AWSTags(Bcfg2.Server.Lint.ServerPlugin):
    """ ``bcfg2-lint`` plugin to check all given :ref:`AWSTags
    <server-plugins-connectors-awstags>` patterns for validity. """

    def Run(self):
        cfg = self.core.plugins['AWSTags'].config
        for entry in cfg.xdata.xpath('//Tag'):
            self.check(entry, "name")
            if entry.get("value"):
                self.check(entry, "value")

    @classmethod
    def Errors(cls):
        return {"pattern-fails-to-initialize": "error"}

    def check(self, entry, attr):
        """ Check a single attribute (``name`` or ``value``) of a
        single entry for validity. """
        try:
            re.compile(entry.get(attr))
        except re.error:
            self.LintError("pattern-fails-to-initialize",
                           "'%s' regex could not be compiled: %s\n    %s" %
                           (attr, sys.exc_info()[1], entry.get("name")))
