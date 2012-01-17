#!/usr/bin/env python

from setuptools import setup
from setuptools import Command
from fnmatch import fnmatch
from glob import glob
import os
import os.path
import sys

class BuildDTDDoc (Command):
    """Build DTD documentation"""

    description = "Build DTD documentation"

    # List of option tuples: long name, short name (None if no short
    # name), and help string.
    user_options = [
        ('links-file=', 'l', 'Links file'),
        ('source-dir=', 's', 'Source directory'),
        ('build-dir=', None, 'Build directory'),
        ('xslt=',      None, 'XSLT file'),
                   ]

    def initialize_options(self):
        """Set default values for all the options that this command
        supports."""

        self.build_links = False
        self.links_file = None
        self.source_dir = None
        self.build_dir  = None
        self.xslt       = None

    def finalize_options(self):
        """Set final values for all the options that this command
        supports."""
        if self.source_dir is None:
            if os.path.isdir('schemas'):
                for root, dirnames, filenames in os.walk('schemas'):
                    for filename in filenames:
                        if fnmatch(filename, '*.xsd'):
                            self.source_dir = root
                            self.announce('Using source directory %s' % root)
                            break
        self.ensure_dirname('source_dir')
        self.source_dir = os.path.abspath(self.source_dir)

        if self.build_dir is None:
            build = self.get_finalized_command('build')
            self.build_dir = os.path.join(build.build_base, 'dtd')
            self.mkpath(self.build_dir)

        if self.links_file is None:
            self.links_file = "links.xml"
            if os.path.isfile(os.path.join(self.source_dir, "links.xml")):
                self.announce("Using linksFile links.xml")
            else:
                self.build_links = True

        if self.xslt is None:
            xsl_files = glob(os.path.join(self.source_dir, '*.xsl'))
            if xsl_files:
                self.xslt = xsl_files[0]
                self.announce("Using XSLT file %s" % self.xslt)
        self.ensure_filename('xslt')

    def run (self):
        """Perform XSLT transforms, writing output to self.build_dir"""

        xslt = lxml.etree.parse(self.xslt).getroot()
        transform = lxml.etree.XSLT(xslt)

        if self.build_links:
            self.announce("Building linksFile %s" % self.links_file)
            links_xml = \
                lxml.etree.Element('links',
                                   attrib={'xmlns':"http://titanium.dstc.edu.au/xml/xs3p"})
            for filename in glob(os.path.join(self.source_dir, '*.xsd')):
                attrib = {'file-location':os.path.basename(filename),
                          'docfile-location':os.path.splitext(os.path.basename(filename))[0] + ".html"}
                links_xml.append(lxml.etree.Element('schema', attrib=attrib))
            open(os.path.join(self.source_dir, self.links_file),
                 "w").write(lxml.etree.tostring(links_xml))

        # build parameter dict
        params = {'printLegend':"'false'",
                  'printGlossary':"'false'",
                  'sortByComponent':"'false'",}
        if self.links_file is not None:
            params['linksFile'] = "'%s'" % self.links_file
            params['searchIncludedSchemas'] = "'true'"

        for filename in glob(os.path.join(self.source_dir, '*.xsd')):
            outfile = \
                os.path.join(self.build_dir,
                             os.path.splitext(os.path.basename(filename))[0] +
                             ".html")
            self.announce("Transforming %s to %s" % (filename, outfile))
            xml = lxml.etree.parse(filename).getroot()
            xhtml = str(transform(xml, **params))
            open(outfile, 'w').write(xhtml)

cmdclass = {}

try:
    from sphinx.setup_command import BuildDoc
    cmdclass['build_sphinx'] = BuildDoc
except ImportError:
    pass

try:
    import lxml.etree
    cmdclass['build_dtddoc'] = BuildDTDDoc
except ImportError:
    pass

py3lib = 'src/lib/Bcfg2Py3Incompat.py'
if sys.hexversion < 0x03000000 and os.path.exists(py3lib):
    os.remove(py3lib)

setup(cmdclass=cmdclass,
      name="Bcfg2",
      version="1.2.1",
      description="Bcfg2 Server",
      author="Narayan Desai",
      author_email="desai@mcs.anl.gov",
      packages=["Bcfg2",
                "Bcfg2.Client",
                "Bcfg2.Client.Tools",
                'Bcfg2.Server',
                "Bcfg2.Server.Admin",
                "Bcfg2.Server.Hostbase",
                "Bcfg2.Server.Hostbase.hostbase",
                "Bcfg2.Server.Lint",
                "Bcfg2.Server.Plugins",
                "Bcfg2.Server.Plugins.Packages",
                "Bcfg2.Server.Reports",
                "Bcfg2.Server.Reports.reports",
                "Bcfg2.Server.Reports.reports.templatetags",
                "Bcfg2.Server.Snapshots",
                ],
      install_requires = ["lxml",
                          "M2Crypto",
                          ],
      package_dir = {"Bcfg2": "src/lib"},
      package_data = {"Bcfg2.Server.Reports.reports":["fixtures/*.xml",
                "templates/*.html", "templates/*/*.html",
                "templates/*/*.inc" ] },
      scripts = glob("src/sbin/*"),
      data_files = [("share/bcfg2/schemas",
                     glob("schemas/*.xsd")),
                    ("share/bcfg2/xsl-transforms",
                     glob("reports/xsl-transforms/*.xsl")),
                    ("share/bcfg2/xsl-transforms/xsl-transform-includes",
                     glob("reports/xsl-transforms/xsl-transform-includes/*.xsl")),
                    ("share/bcfg2", glob("reports/reports.wsgi")),
                    ("share/man/man1", glob("man/bcfg2.1")),
                    ("share/man/man5", glob("man/*.5")),
                    ("share/man/man8", glob("man/*.8")),
                    ("share/bcfg2/Hostbase/templates",
                     glob("src/lib/Server/Hostbase/hostbase/webtemplates/*.*")),
                    ("share/bcfg2/Hostbase/templates/hostbase",
                     glob("src/lib/Server/Hostbase/hostbase/webtemplates/hostbase/*")),
                    ("share/bcfg2/Hostbase/repo",
                     glob("src/lib/Server/Hostbase/templates/*")),
                    ("share/bcfg2/site_media",
                     glob("reports/site_media/*")),
                    ],
      entry_points = {
          "bcfg2.plugin": [
              "Account = Bcfg2.Server.Plugins.Account:Account",
              "BB = Bcfg2.Server.Plugins.BB:BB",
              "Bundler = Bcfg2.Server.Plugins.Bundler:Bundler",
              "Bzr = Bcfg2.Server.Plugins.Bzr:Bzr",
              "Cfg = Bcfg2.Server.Plugins.Cfg:Cfg",
              "Cvs = Bcfg2.Server.Plugins.Cvs:Cvs",
              "DBStats = Bcfg2.Server.Plugins.DBStats:DBStats",
              "Darcs = Bcfg2.Server.Plugins.Darcs:Darcs",
              "Decisions = Bcfg2.Server.Plugins.Decisions:Decisions",
              "Defaults = Bcfg2.Server.Plugins.Defaults:Defaults",
              "Deps = Bcfg2.Server.Plugins.Deps:Deps",
              "Editor = Bcfg2.Server.Plugins.Editor:Editor",
              "FileProbes = Bcfg2.Server.Plugins.FileProbes:FileProbes",
              "Fossil = Bcfg2.Server.Plugins.Fossil:Fossil",
              "Git = Bcfg2.Server.Plugins.Git:Git",
              "GroupPatterns = Bcfg2.Server.Plugins.GroupPatterns:GroupPatterns",
              "Guppy = Bcfg2.Server.Plugins.Guppy:Guppy",
              "Hg = Bcfg2.Server.Plugins.Hg:Hg",
              "Hostbase = Bcfg2.Server.Plugins.Hostbase:Hostbase",
              "Ldap = Bcfg2.Server.Plugins.Ldap:Ldap",
              "Metadata = Bcfg2.Server.Plugins.Metadata:Metadata",
              "NagiosGen = Bcfg2.Server.Plugins.NagiosGen:NagiosGen",
              "Ohai = Bcfg2.Server.Plugins.Ohai:Ohai",
              "Packages = Bcfg2.Server.Plugins.Packages:Packages",
              "Pkgmgr = Bcfg2.Server.Plugins.Pkgmgr:Pkgmgr",
              "Probes = Bcfg2.Server.Plugins.Probes:Probes",
              "Properties = Bcfg2.Server.Plugins.Properties:Properties",
              "Rules = Bcfg2.Server.Plugins.Rules:Rules",
              "SGenshi = Bcfg2.Server.Plugins.SGenshi:SGenshi",
              "SSHbase = Bcfg2.Server.Plugins.SSHbase:SSHbase",
              "SSLCA = Bcfg2.Server.Plugins.SSLCA:SSLCA",
              "Snapshots = Bcfg2.Server.Plugins.Snapshots:Snapshots",
              "Statistics = Bcfg2.Server.Plugins.Statistics:Statistics",
              "Svcmgr = Bcfg2.Server.Plugins.Svcmgr:Svcmgr",
              "Svn = Bcfg2.Server.Plugins.Svn:Svn",
              "Svn2 = Bcfg2.Server.Plugins.Svn2:Svn2",
              "TCheetah = Bcfg2.Server.Plugins.TCheetah:TCheetah",
              "TGenshi = Bcfg2.Server.Plugins.TGenshi:TGenshi",
              "Trigger = Bcfg2.Server.Plugins.Trigger:Trigger",
          ],
          "bcfg2.packages.source": [
              "Apt = Bcfg2.Server.Plugins.Packages.Apt:AptSource",
              "Pac = Bcfg2.Server.Plugins.Packages.Pac:PacSource",
              "Yum = Bcfg2.Server.Plugins.Packages.Yum:YumSource",
          ],
          "bcfg2.packages.collection": [
              "Apt = Bcfg2.Server.Plugins.Packages.Apt:AptCollection",
              "Pac = Bcfg2.Server.Plugins.Packages.Pac:PacCollection",
              "Yum = Bcfg2.Server.Plugins.Packages.Yum:YumCollection",
          ],
          "bcfg2.client.tools": [
              "Blast = Bcfg2.Client.Tools.Blast:Blast",
              "Action = Bcfg2.Client.Tools.Action:Action",
              "POSIX = Bcfg2.Client.Tools.POSIX:POSIX",
              "SMF = Bcfg2.Client.Tools.SMF:SMF",
              "RPMng = Bcfg2.Client.Tools.RPMng:RPMng",
              "launchd = Bcfg2.Client.Tools.launchd:launchd",
              "Pacman = Bcfg2.Client.Tools.Pacman:Pacman",
              "YUMng = Bcfg2.Client.Tools.YUMng:YUMng",
              "MacPorts = Bcfg2.Client.Tools.MacPorts:MacPorts",
              "VCS = Bcfg2.Client.Tools.VCS:VCS",
              "YUM24 = Bcfg2.Client.Tools.YUM24:YUM24",
              "Systemd = Bcfg2.Client.Tools.Systemd:Systemd",
              "FreeBSDPackage = Bcfg2.Client.Tools.FreeBSDPackage:FreeBSDPackage",
              "APK = Bcfg2.Client.Tools.APK:APK",
              "Encap = Bcfg2.Client.Tools.Encap:Encap",
              "Chkconfig = Bcfg2.Client.Tools.Chkconfig:Chkconfig",
              "SYSV = Bcfg2.Client.Tools.SYSV:SYSV",
              "RcUpdate = Bcfg2.Client.Tools.RcUpdate:RcUpdate",
              "FreeBSDInit = Bcfg2.Client.Tools.FreeBSDInit:FreeBSDInit",
              "APT = Bcfg2.Client.Tools.APT:APT",
              "Portage = Bcfg2.Client.Tools.Portage:Portage",
              "IPS = Bcfg2.Client.Tools.IPS:IPS",
              "Upstart = Bcfg2.Client.Tools.Upstart:Upstart",
              "DebInit = Bcfg2.Client.Tools.DebInit:DebInit",
          ],
          "bcfg2.admin": [
              "Backup = Bcfg2.Server.Admin.Backup:Backup",
              "Bundle = Bcfg2.Server.Admin.Bundle:Bundle",
              "Client = Bcfg2.Server.Admin.Client:Client",
              "Compare = Bcfg2.Server.Admin.Compare:Compare",
              "Group = Bcfg2.Server.Admin.Group:Group",
              "Init = Bcfg2.Server.Admin.Init:Init",
              "Minestruct = Bcfg2.Server.Admin.Minestruct:Minestruct",
              "Perf = Bcfg2.Server.Admin.Perf:Perf",
              "Pull = Bcfg2.Server.Admin.Pull:Pull",
              "Query = Bcfg2.Server.Admin.Query:Query",
              "Reports = Bcfg2.Server.Admin.Reports:Reports",
              "Snapshots = Bcfg2.Server.Admin.Snapshots:Snapshots",
              "Tidy = Bcfg2.Server.Admin.Tidy:Tidy",
              "Viz = Bcfg2.Server.Admin.Viz:Viz",
              "Xcmd = Bcfg2.Server.Admin.Xcmd:Xcmd",
          ],
          "bcfg2.lint": [
              "Bundles = Bcfg2.Server.Lint.Bundles:Bundles",
              "Comments = Bcfg2.Server.Lint.Comments:Comments",
              "Duplicates = Bcfg2.Server.Lint.Duplicates:Duplicates",
              "Genshi = Bcfg2.Server.Lint.Genshi:Genshi",
              "GroupPatterns = Bcfg2.Server.Lint.GroupPatterns:GroupPatterns",
              "InfoXML = Bcfg2.Server.Lint.InfoXML:InfoXML",
              "MergeFiles = Bcfg2.Server.Lint.MergeFiles:MergeFiles",
              "Pkgmgr = Bcfg2.Server.Lint.Pkgmgr:Pkgmgr",
              "RequiredAttrs = Bcfg2.Server.Lint.RequiredAttrs:RequiredAttrs",
              "Validate = Bcfg2.Server.Lint.Validate:Validate",
          ]
      }
      )
