#!/usr/bin/env python

'''This is a code copy of the old cfg repo code, fit into the generator framework'''

from os import listdir
from re import compile
from tempfile import mktemp
from string import join

from Error import CfgFileException
from Generator import Generator
from Types import ConfigFile

class oldcfg(Generator):
    __name__ = 'oldcfg'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __build__ = {'*':'fetchfile'}
    infore = compile('^owner:(\s)*(?P<owner>\w+)|group:(\s)*(?P<group>\w+)|perms:(\s)*(?P<perms>\w+)|encoding:(\s)*(?P<encoding>\w+)$')

    def fetchfile(self,name,client):
        pass

    def GetInfo(self,filename):
        encoding='ascii'
        for line in open("%s/%s/%s"%(self.data,filename,':info')).readlines():
            m = self.infore.match(line)
            if not m:
                continue
            else:
                d = m.groupdict()
                if d['owner']:
                    owner=d['owner']
                elif d['group']:
                    group=d['group']
                elif d['encoding']:
                    encoding=d['encoding']
                elif d['perms']:
                    perms=d['perms']
                    if len(perms) == 3:
                        perms="0%s"%perms
        return (owner,group,encoding,perms)

    def __cbuild__(self,filename,hostname,tags,bundles):
        cfgroot = self.data
        basename = filename.split('/')[-1]
        repfiles = listdir("%s/%s"%(cfgroot,filename))
        if ':info' not in repfiles:
            raise CfgFileException, ('info','%s/%s/:info'%(cfgroot,filename))
        
        (owner,group,encoding,perms) = self.GetInfo(filename)
        
        # These are templates for regexes used in repofile classification
        globalmatch='^%s$'
        bundlematch='^%s.B(?P<prio>\d)+_(?P<tag>%s)(.(?P<op>cat|udiff))?$'
        tagmatch='^%s.T(?P<prio>\d)+_(?P<tag>%s)(.(?P<op>cat|udiff))?$'
        hostmatch='^%s.H_%s(.(?P<op>cat|udiff))?$'

        g = compile(globalmatch%(basename))
        b = compile(bundlematch%(basename,join(bundles,'|')))
        t = compile(tagmatch%(basename,join(tags,'|')))
        h = compile(hostmatch%(basename,hostname))
        (gmatch,bmatches,tmatches,hmatch)=(None,[],[],None)
        try:
            [gmatch]=[g.match(e) for e in repfiles if g.match(e)]
        except ValueError:
            pass
        except OSError:
            raise CfgFileException, ('repository',"%s/%s"%(cfgroot,filename))
        try:
            bmatches=filter(lambda x:x,map(b.match, repfiles))
            bmatches.sort(self.order)
        except ValueError:
            pass
        try:
            tmatches=[t.match(e) for e in repfiles if t.match(e)]
            tmatches.sort(self.order)
            # now tmatches is ordered by 
        except ValueError:
            pass
        try:
            [hmatch]=[h.match(e) for e in repfiles if h.match(e)]
        except ValueError:
            pass

        base=None
        # First we find our base file
        if filter(lambda x:not x.group('op'), filter(lambda x:x,[hmatch])):
            base=hmatch
        elif filter(lambda x:not x.group('op'), bmatches):
            base=filter(lambda x:not x.group('op'), bmatches)[-1]
        elif filter(lambda x:not x.group('op'), tmatches):
            base=filter(lambda x:not x.group('op'), tmatches)[-1]
        elif gmatch:
            base=gmatch
        else:
            raise CfgFileException, ('basefile',filename)

        # Now we need to add all more specific deltas
        # all more specific files are deltas (since base is most specific)
        deltas=[]
        if g.match(base.group()):
            deltas=filter(lambda x:x,tmatches+[hmatch])
        elif b.match(base.group()):
            deltas=filter(lambda x:x,bmatches[bmatches.index(base)+1:]+tmatches+[hmatch])
        elif t.match(base.group()):
            deltas=filter(lambda x:x,tmatches[tmatches.index(base)+1:]+[hmatch])
        
        filedata=file("%s/%s/%s"%(cfgroot,filename,base.group())).read()
        for delta in deltas:
            filedata=self.ApplyDelta(filedata,"%s/%s/%s"%(cfgroot,filename,delta.group()),
                                     delta.group('op'))
        if ":preinstall" in repfiles:
            self.preinst=open("%s/%s/%s"%(cfgroot,filename,":preinstall")).read()
        if ":postinstall" in repfiles:
            self.postinst=open("%s/%s/%s"%(cfgroot,filename,':postinstall')).read()
            
        print filename,owner,group,perms,filedata
        return ConfigFile(filename,owner,group,perms,filedata)

    def order(self,t1,t2):
        if int(t1.group('prio')) > int(t2.group('prio')):
            return 1
        elif int(t1.group('prio')) < int(t2.group('prio')):
            return -1
        else:
            return 0

    def ApplyDelta(self,data,delta,mode):
        if mode == 'cat':
            tdata = data.split('\n')
            for line in filter(lambda x:x,split(file(delta).read(),'\n')):
                if line[0] == '-':
                    if line[1:] in data:
                        tdata.remove(line[1:])
                    else:
                        raise CfgFileException, ('delta',delta)
                elif line[0] == '+':
                    tdata.append(line[1:])
            return join(tdata,'\n')
        elif mode == 'udiff':
            basefile=open(mktemp(),'w')
            basefile.write(data)
            basefile.close()
            ret=system("patch -uf %s < %s > /dev/null 2>&1"%(basefile.name,delta))
            if ret>>8 != 0:
                raise CfgFileException, ('delta',delta)
            data=open(basefile.name,'r').read()
            unlink(basefile.name)
            return data
        
