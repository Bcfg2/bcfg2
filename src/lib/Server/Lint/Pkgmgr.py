import glob
import lxml.etree
import Bcfg2.Server.Lint

class Pkgmgr(Bcfg2.Server.Lint.ServerlessPlugin):
    """ find duplicate Pkgmgr entries with the same priority """

    def Run(self):
        pset = set()
        for pfile in glob.glob("%s/Pkgmgr/*.xml" % self.config['repo']):
            if self.HandlesFile(pfile):
                xdata = lxml.etree.parse(pfile).getroot()
                # get priority, type, group
                priority = xdata.get('priority')
                ptype = xdata.get('type')
                for pkg in xdata.xpath("//Package"):
                    if pkg.getparent().tag == 'Group':
                        grp = pkg.getparent().get('name')
                        if (type(grp) is not str and
                            grp.getparent().tag == 'Group'):
                            pgrp = grp.getparent().get('name')
                        else:
                            pgrp = 'none'
                    else:
                        grp = 'none'
                        pgrp = 'none'
                    ptuple = (pkg.get('name'), priority, ptype, grp, pgrp)
                    # check if package is already listed with same
                    # priority, type, grp
                    if ptuple in pset:
                        self.LintError("duplicate-package",
                                       "Duplicate Package %s, priority:%s, type:%s" %
                                         (pkg.get('name'), priority, ptype))
                    else:
                        pset.add(ptuple)
