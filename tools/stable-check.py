#!/usr/bin/env python

import os, sys

def do_merge(revision_string):
    os.system("svnmerge merge -r %s" % revision_string)
    os.system("svn commit -F  svnmerge-commit-message.txt")
    os.system("svn up")

if __name__ == '__main__':
    os.popen('svn up').read()
    avail = os.popen('svnmerge avail').read().strip()
    if not avail:
        raise SystemExit, 0
    if '-' in avail:
        start, stop = [int(x) for x in avail.split('-')]
    else:
        start = stop = int(avail)

    bf = []
    other = []
    for rev in range(start, stop + 1):
        log = os.popen("svn log https://svn.mcs.anl.gov/repos/bcfg/trunk/bcfg2 -r %s" % rev).read()
        if "[bugfix]" in log:
            bf.append(rev)
        else:
            other.append(rev)
        if '-v' in sys.argv:
            print log,

    mrevs = ','.join([str(x) for x in bf])
    if '-c' in sys.argv:
        print "Revisions %s need merging" % (mrevs)
    elif '-f' in sys.argv:
        do_merge(mrevs)
    else:
        a = raw_input('Merge revisions %s: [yN] ' % mrevs)
        if a in ['y', 'Y']:
            do_merge(mrevs)
