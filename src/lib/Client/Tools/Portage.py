'''This is the bcfg2 support for the Gentoo Portage system, largely cribbed from the
APT one'''
__revision__ = '$Revision: $'

import re
import Bcfg2.Client.Tools

class Portage(Bcfg2.Client.Tools.PkgTool):
    '''The Gentoo toolset implements package and service operations and inherits
    the rest from Toolset.Toolset'''
    __name__ = 'Portage'
    __execs__ = ['/usr/bin/emerge', '/usr/bin/equery']
    __important__ = ["/etc/make.conf", "/etc/make.globals", \
    	             "/etc/make.profile/make.defaults", "/etc/make.profile/packages" ]
    __handles__ = [('Package', 'ebuild')]
    __req__ = {'Package': ['name', 'version']}
    pkgtype = 'ebuild'
    '''requires a working PORTAGE_BINHOST in make.conf'''
    pkgtool = ('emerge --getbinpkgonly =%s', ('%s-%s', ['name', 'version']))
    
    def __init__(self, logger, cfg, setup, states):
        Bcfg2.Client.Tools.PkgTool.__init__(self, logger, cfg, setup, states)
        self.cfg = cfg
        if not self.setup['dryrun']:
            self.cmd.run("emerge -q --sync")
        self.installed = {}
        self.RefreshPackages()
    def RefreshPackages(self):
        '''Refresh memory hashes of packages'''
        cache = self.cmd.run("equery -q list")
        self.installed = {}
        for pkg in cache:
	    # there has got to be a better way...
            name = re.split("-[0-9]", pkg)[0]
            version = re.sub(name+"-", "", pkg)
            self.installed[name] = version

    def VerifyPackage(self, entry, modlist):
        '''Verify package for entry'''
        if not entry.attrib.has_key('version'):
            self.logger.info("Cannot verify unversioned package %s" %
                             (entry.attrib['name']))
            return False
        if self.installed.has_key(entry.attrib['name']):
            if self.installed[entry.attrib['name']] == entry.attrib['version']:
                if not self.setup['quick'] and entry.get('verify', 'true') == 'true':
		    # mrj - there's probably a "python way" to avoid the grep...?
                    output = self.cmd.run("/usr/bin/equery check =%s | grep '!!!'" \
		    	% entry.get('name'))[1]
                    if [filename for filename in output if filename not in modlist]:
                        return False
                return True
            else:
                entry.set('current_version', self.installed[entry.get('name')])
                return False
        entry.set('current_exists', 'false')
        return False

    def RemovePackages(self, packages):
        '''Deal with extra configuration detected'''
        if len(packages) > 0:
            self.logger.info('Removing packages:')
            self.logger.info(packages)
            self.cmd.run("emerge --unmerge --quiet %s" % " ".join(packages))
            self.RefreshPackages()
            self.extra = self.FindExtraPackages()
              
        
