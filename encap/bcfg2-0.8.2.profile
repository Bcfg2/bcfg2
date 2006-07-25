<?xml version="1.0"?>

<!-- $Id$ -->

<encap_profile
	profile_ver="1.0"
	pkgspec="bcfg2-0.8.2"
>

<environment
        variable="CC"
        value="gcc"
        type="set"
/>

<environment
        variable="PATH"
PLATFORM_IF_MATCH(solaris)
        value="/usr/local/lib/bcfg2/bin:/usr/local/bin:/usr/sfw/bin:/usr/ccs/bin:"
PLATFORM_ELSE
        value="/usr/local/lib/bcfg2/bin:/usr/local/bin:"
PLATFORM_ENDIF
        type="prepend"
/>

PLATFORM_IF_MATCH(linux)
PLATFORM_ELSE
<environment
        variable="MAKE"
        value="gmake"
        type="set"
/>
PLATFORM_ENDIF

<environment
        variable="LDFLAGS"
PLATFORM_IF_MATCH(linux)
        value="-L/usr/local/lib/bcfg2/lib -Wl,-rpath,/usr/local/lib/bcfg2/lib"
PLATFORM_ELSE_IF_MATCH(aix)
	value="-L/usr/local/lib/bcfg2/lib -Wl,-blibpath:/usr/local/lib/bcfg2/lib:/usr/lib"
PLATFORM_ELSE_IF_MATCH(solaris)
        value="-L/usr/local/lib/bcfg2/lib -R/usr/local/lib/bcfg2/lib:/usr/lib -YP,/usr/local/lib/bcfg2/lib:/usr/lib"
PLATFORM_ELSE
PLATFORM_ENDIF
        type="set"
/>

<environment
        variable="CPPFLAGS"
        value="-I/usr/local/lib/bcfg2/include"
        type="set"
/>

<source
url="http://www.pobox.com/users/dclark/mirror/bcfg2-0.8.2.tar.gz
     ftp://ftp.mcs.anl.gov/pub/bcfg/bcfg2-0.8.2.tar.gz"
>

<patch options="-p0"><![CDATA[
Index: src/lib/Options.py
===================================================================
--- src/lib/Options.py	(revision 1976)
+++ src/lib/Options.py	(working copy)
@@ -5,7 +5,7 @@
 # (option, env, cfpath, default value, option desc, boolean, arg desc)
 # ((option, arg desc, opt desc), env, cfpath, default, boolean)
 bootstrap = {'configfile': (('-C', '<configfile>', 'Path to config file'), 
-                             'BCFG2_CONF', False, '/etc/bcfg2.conf',  False)}
+                             'BCFG2_CONF', False, '/usr/local/etc/bcfg2.conf',  False)}
 
 class OptionFailure(Exception):
     pass
Index: src/lib/Server/Plugins/Cfg.py
===================================================================
--- src/lib/Server/Plugins/Cfg.py	(revision 1976)
+++ src/lib/Server/Plugins/Cfg.py	(working copy)
@@ -186,7 +186,7 @@
                 dfile = open(tempfile.mktemp(), 'w')
                 dfile.write(delta.data)
                 dfile.close()
-                ret = os.system("patch -uf %s < %s > /dev/null 2>&1"%(basefile.name, dfile.name))
+                ret = os.system("/usr/local/bin/b2patch -uf %s < %s > /dev/null 2>&1"%(basefile.name, dfile.name))
                 output = open(basefile.name, 'r').read()
                 [os.unlink(fname) for fname in [basefile.name, dfile.name]]
                 if ret >> 8 != 0:
Index: src/lib/Server/Component.py
===================================================================
--- src/lib/Server/Component.py	(revision 1976)
+++ src/lib/Server/Component.py	(working copy)
@@ -108,7 +108,7 @@
         if setup['configfile']:
             cfilename = setup['configfile']
         else:
-            cfilename = '/etc/bcfg2.conf'
+            cfilename = '/usr/local/etc/bcfg2.conf'
         self.cfile.read([cfilename])
         if not self.cfile.has_section('communication'):
             print "Configfile missing communication section"
Index: src/lib/Client/Solaris.py
===================================================================
--- src/lib/Client/Solaris.py	(revision 1976)
+++ src/lib/Client/Solaris.py	(working copy)
@@ -28,7 +28,7 @@
     and standard SMF services'''
     pkgtool = {'sysv':("/usr/sbin/pkgadd %s -d %%s -n %%%%s", (("%s", ["name"]))),
                'blast':("/opt/csw/bin/pkg-get install %s", ("%s", ["name"])),
-               'encap':("/local/sbin/epkg -l -q %s", ("%s", ["url"]))}
+               'encap':("/usr/local/bin/epkg -l -q %s", ("%s", ["url"]))}
     splitter = regcompile('.*/(?P<name>[\w-]+)\-(?P<version>[\w\.-]+)')
     ptypes = {}
     __name__ = 'Solaris'
@@ -71,7 +71,7 @@
             self.installed[pkg] = version
             self.ptypes[pkg] = 'sysv'
         # try to find encap packages
-        for pkg in glob("/local/encap/*"):
+        for pkg in glob("/usr/local/encap/*"):
             match = self.splitter.match(pkg)
             if match:
                 self.installed[match.group('name')] = match.group('version')
@@ -141,7 +141,7 @@
         if entry.get('type') in ['sysv', 'blast'] or entry.get('type')[:4] == 'sysv':
             cmdrc = self.saferun("/usr/bin/pkginfo -q -v \"%s\" %s" % (entry.get('version'), entry.get('name')))[0]
         elif entry.get('type') in ['encap']:
-            cmdrc = self.saferun("/local/sbin/epkg -q -k %s-%s >/dev/null" %
+            cmdrc = self.saferun("/usr/local/bin/epkg -q -k %s-%s >/dev/null" %
                                  (entry.get('name'), entry.get('version')))[0]
         if cmdrc != 0:
             self.logger.debug("Package %s version incorrect" % entry.get('name'))
@@ -190,7 +190,7 @@
                     if not self.saferun("/usr/sbin/pkgrm -n %s" % " ".join(sysvrmpkgs))[0]:
                         [self.pkgwork['remove'].remove(pkg) for pkg in sysvrmpkgs]
                 if enrmpkgs:
-                    if not self.saferun("/local/sbin/epkg -l -q -r %s" % " ".join(enrmpkgs))[0]:
+                    if not self.saferun("/usr/local/bin/epkg -l -q -r %s" % " ".join(enrmpkgs))[0]:
                         [self.pkgwork['remove'].remove(pkg) for pkg in enrmpkgs]
             else:
                 self.logger.info("Need to remove packages: %s" % (self.pkgwork['remove']))
Index: src/lib/Client/Proxy.py
===================================================================
--- src/lib/Client/Proxy.py	(revision 1976)
+++ src/lib/Client/Proxy.py	(working copy)
@@ -123,7 +123,7 @@
 class SafeProxy:
     '''Wrapper for proxy'''
     _cfile = ConfigParser.ConfigParser()
-    _cfpath = '/etc/bcfg2.conf'
+    _cfpath = '/usr/local/etc/bcfg2.conf'
     _cfile.read([_cfpath])
     try:
         _components = _cfile._sections['components']
Index: src/sbin/bcfg2
===================================================================
--- src/sbin/bcfg2	(revision 1976)
+++ src/sbin/bcfg2	(working copy)
@@ -51,8 +51,8 @@
                        False, False, False, False),
             'help': (('-h', False, "print this help message"),
                      False, False, False, True),
-            'setup': (('-C', '<configfile>', "use given config file (default /etc/bcfg2.conf)"),
-                      False, False, '/etc/bcfg2.conf', False),
+            'setup': (('-C', '<configfile>', "use given config file (default /usr/local/etc/bcfg2.conf)"),
+                      False, False, '/usr/local/etc/bcfg2.conf', False),
             'server': (('-S', '<server url>', 'the server hostname to connect to'),
                        False, ('components', 'bcfg2'), 'https://localhost:6789', False),
             'user': (('-u', '<user>', 'the user to provide for authentication'),
Index: src/sbin/GenerateHostInfo
===================================================================
--- src/sbin/GenerateHostInfo	(revision 1976)
+++ src/sbin/GenerateHostInfo	(working copy)
@@ -12,7 +12,7 @@
 
 if __name__ == '__main__':
     c = ConfigParser()
-    c.read(['/etc/bcfg2.conf'])
+    c.read(['/usr/local/etc/bcfg2.conf'])
     configpath = "%s/etc/report-configuration.xml" % c.get('server', 'repository')
     clientdatapath = "%s/Metadata/clients.xml" % c.get('server', 'repository')
     sendmailpath = c.get('statistics','sendmailpath')
Index: src/sbin/bcfg2-server
===================================================================
--- src/sbin/bcfg2-server	(revision 1976)
+++ src/sbin/bcfg2-server	(working copy)
@@ -182,7 +182,7 @@
         'daemon': (('-D', '<pidfile>', 'daemonize the server, storing PID'),
                    False, False, False, False),
         'configfile': (('-C', '<conffile>', 'use this config file'),
-                       False, False, '/etc/bcfg2.conf', False),
+                       False, False, '/usr/local/etc/bcfg2.conf', False),
         'client': (('-c', '<client>', 'hard set the client name (for debugging)'),
                    False, False, False, False)
         }
Index: src/sbin/StatReports
===================================================================
--- src/sbin/StatReports	(revision 1976)
+++ src/sbin/StatReports	(working copy)
@@ -147,12 +147,12 @@
 
 if __name__ == '__main__':
     c = ConfigParser()
-    c.read(['/etc/bcfg2.conf'])
+    c.read(['/usr/local/etc/bcfg2.conf'])
     configpath = "%s/etc/report-configuration.xml" % c.get('server', 'repository')
     statpath = "%s/etc/statistics.xml" % c.get('server', 'repository')
     clientsdatapath = "%s/Metadata/clients.xml" % c.get('server', 'repository')
-    transformpath = "/usr/share/bcfg2/xsl-transforms/"
-    #websrcspath = "/usr/share/bcfg2/web-rprt-srcs/"
+    transformpath = "/usr/local/lib/bcfg2/share/bcfg2/xsl-transforms/"
+    #websrcspath = "/usr/local/lib/bcfg2/share/bcfg2/web-rprt-srcs/"
 
     try:
         opts, args = getopt(argv[1:], "hc:s:", ["help", "config=", "stats="])
Index: src/sbin/bcfg2-info
===================================================================
--- src/sbin/bcfg2-info	(revision 1976)
+++ src/sbin/bcfg2-info	(working copy)
@@ -169,7 +169,7 @@
     if '-c' in sys.argv:
         cfile = sys.argv[-1]
     else:
-        cfile = '/etc/bcfg2.conf'
+        cfile = '/usr/local/etc/bcfg2.conf'
     try:
         bcore = Bcfg2.Server.Core.Core({}, cfile)
     except Bcfg2.Server.Core.CoreInitError, msg:
Index: src/sbin/bcfg2-repo-validate
===================================================================
--- src/sbin/bcfg2-repo-validate	(revision 1976)
+++ src/sbin/bcfg2-repo-validate	(working copy)
@@ -11,11 +11,11 @@
         verbose = True
         sys.argv.remove('-v')
     cf = ConfigParser.ConfigParser()
-    cf.read(['/etc/bcfg2.conf'])
+    cf.read(['/usr/local/etc/bcfg2.conf'])
     try:
         prefix = cf.get('server', 'prefix')
     except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
-        prefix = '/usr'
+        prefix = '/usr/local/lib/bcfg2'
     if verbose:
         print "Using installation prefix %s" % (prefix)
     schemadir = "%s/share/bcfg2/schemas" % (prefix)
@@ -55,7 +55,7 @@
                 datafile = lxml.etree.parse(open(filename))
             except SyntaxError:
                 print "%s ***FAILS*** to parse \t\t<----" % (filename)
-                os.system("xmllint %s" % filename)
+                os.system("/usr/local/bin/b2xmllint %s" % filename)
                 failures = 1
                 continue
             except IOError:
@@ -67,6 +67,6 @@
                     print "%s checks out" % (filename)
             else:
                 print "%s ***FAILS*** to verify \t\t<----" % (filename)
-                os.system("xmllint --schema %s %s" % (schemaname % schemadir, filename))
+                os.system("/usr/local/bin/b2xmllint --schema %s %s" % (schemaname % schemadir, filename))
                 failures = 1
     raise SystemExit, failures
Index: reports/brpt/settings.py
===================================================================
--- reports/brpt/settings.py	(revision 1976)
+++ reports/brpt/settings.py	(working copy)
@@ -1,7 +1,8 @@
 # Django settings for brpt project.
 from ConfigParser import ConfigParser, NoSectionError, NoOptionError
 c = ConfigParser()
-c.read(['/etc/bcfg2.conf'])#This needs to be configurable one day somehow
+c.read(['/usr/local/etc/bcfg2.conf']) # This needs to be configurable one day somehow
+                                      # Using something other than patch(1) - dclark
 sqlitedbpath = "%s/etc/brpt.sqlite" % c.get('server', 'repository')
 
 DEBUG = True

]]></patch>

<configure>
:
</configure>

<build>
/usr/local/lib/bcfg2/bin/python setup.py build \
--build-base=${builddir}/build
</build>

<install>
/usr/local/lib/bcfg2/bin/python setup.py install \
--prefix=${ENCAP_SOURCE}/${ENCAP_PKGNAME}/lib/bcfg2
</install>

<clean>
/usr/local/lib/bcfg2/bin/python setup.py clean
</clean>

</source>

<prepackage type="set"><![CDATA[
mkdir bin 2>/dev/null || exit 0
ln -sf ../lib/bcfg2/bin/GenerateHostInfo bin/
ln -sf ../lib/bcfg2/bin/StatReports bin/
ln -sf ../lib/bcfg2/bin/bcfg2 bin/
ln -sf ../lib/bcfg2/bin/bcfg2-info bin/
ln -sf ../lib/bcfg2/bin/bcfg2-repo-validate bin/
ln -sf ../lib/bcfg2/bin/bcfg2-server bin/
mkdir share 2>/dev/null || exit 0
mkdir share/bcfg2  2>/dev/null || exit 0
(cp ${builddir}/doc/manual.pdf share/bcfg2/ || true)
cp -r ${builddir}/examples share/bcfg2/
mkdir var 2>/dev/null || exit 0
mkdir var/encap 2>/dev/null || exit 0
touch var/encap/${ENCAP_PKGNAME}
]]></prepackage>

<encapinfo>
description Bcfg2 - Provides a declarative interface to system configuration
prereq pkgspec >= bcfg2-zlib-1.2.3
prereq pkgspec >= bcfg2-libiconv-1.9.2
prereq pkgspec >= bcfg2-gettext-0.14.5
prereq pkgspec >= bcfg2-patch-2.5.9
prereq pkgspec >= bcfg2-openssl-0.9.8b
prereq pkgspec >= bcfg2-libstdc++-0.1
prereq pkgspec >= bcfg2-libgcc-0.1
prereq pkgspec >= bcfg2-python-2.4.3
prereq pkgspec >= bcfg2-pyopenssl-0.6
prereq pkgspec >= bcfg2-libxml2-2.6.26
prereq pkgspec >= bcfg2-libxslt-1.1.17
prereq pkgspec >= bcfg2-lxml-1.0.1
</encapinfo>

</encap_profile>
