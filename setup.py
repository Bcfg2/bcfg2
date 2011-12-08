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
      version="1.2.0",
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
      install_requires = ["lxml"],
      package_dir = {'Bcfg2': 'src/lib'},
      package_data = {'Bcfg2.Server.Reports.reports':['fixtures/*.xml',
                'templates/*.html', 'templates/*/*.html',
                'templates/*/*.inc' ] },
      scripts = glob('src/sbin/*'),
      data_files = [('share/bcfg2/schemas',
                     glob('schemas/*.xsd')),
                    ('share/bcfg2/xsl-transforms',
                     glob('reports/xsl-transforms/*.xsl')),
                    ('share/bcfg2/xsl-transforms/xsl-transform-includes',
                     glob('reports/xsl-transforms/xsl-transform-includes/*.xsl')),
                    ('share/bcfg2', glob('reports/reports.wsgi')),
                    ('share/man/man1', glob("man/bcfg2.1")),
                    ('share/man/man5', glob("man/*.5")),
                    ('share/man/man8', glob("man/*.8")),
                    ('share/bcfg2/Hostbase/templates',
                     glob('src/lib/Server/Hostbase/hostbase/webtemplates/*.*')),
                    ('share/bcfg2/Hostbase/templates/hostbase',
                     glob('src/lib/Server/Hostbase/hostbase/webtemplates/hostbase/*')),
                    ('share/bcfg2/Hostbase/repo',
                     glob('src/lib/Server/Hostbase/templates/*')),
                    ('share/bcfg2/site_media',
                     glob('reports/site_media/*')),
                    ]
      )
