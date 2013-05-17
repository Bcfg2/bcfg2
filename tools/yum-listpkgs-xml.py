#!/usr/bin/python
import sys
sys.path.append('/usr/bin/')
sys.path.append('/usr/share/yum-cli')

import yummain


def mySimpleList(self, pkg):
    print("<Package name='%s' version='%s'/>" % (pkg.name, pkg.printVer()))


def myListPkgs(self, lst, description, outputType):
    """outputs based on whatever outputType is. Current options:
    'list' - simple pkg list
    'info' - similar to rpm -qi output"""

    if outputType in ['list', 'info']:
        thingslisted = 0
        if len(lst) > 0:
            thingslisted = 1
            from yum.misc import sortPkgObj
            lst.sort(sortPkgObj)
            for pkg in lst:
                if outputType == 'list':
                    self.simpleList(pkg)
                elif outputType == 'info':
                    self.infoOutput(pkg)
                else:
                    pass

        if thingslisted == 0:
            return 1, ['No Packages to list']

yummain.cli.output.YumOutput.listPkgs = myListPkgs
yummain.cli.output.YumOutput.simpleList = mySimpleList

try:
    sys.argv = [sys.argv[0], '-d', '0', 'list']
    yummain.main(sys.argv[1:])
except KeyboardInterrupt:
    sys.stderr.write("\n\nExiting on user cancel.")
    sys.exit(1)
