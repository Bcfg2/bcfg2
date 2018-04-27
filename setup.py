#!/usr/bin/env python

from setuptools import setup
from glob import glob
import sys

version_file = 'src/lib/Bcfg2/version.py'
try:
    # python 2
    execfile(version_file)
except NameError:
    # py3k
    exec(compile(open(version_file).read(), version_file, 'exec'))

inst_reqs = [
    'lockfile',
    'lxml',
    'python-daemon',
    'argparse'
]

# Use the backported ssl module on < python2.6
if sys.version_info[:2] < (2, 6):
    inst_reqs.append('ssl')

setup(name="Bcfg2",
      version=__version__,  # Defined in src/lib/Bcfg2/version.py
      description="Bcfg2 Server",
      author="Narayan Desai",
      author_email="desai@mcs.anl.gov",
      # nosetests
      test_suite='nose.collector',
      packages=["Bcfg2",
                "Bcfg2.Options",
                "Bcfg2.Client",
                "Bcfg2.Client.Tools",
                "Bcfg2.Client.Tools.POSIX",
                "Bcfg2.Reporting",
                "Bcfg2.Reporting.Storage",
                "Bcfg2.Reporting.Transport",
                "Bcfg2.Reporting.migrations",
                "Bcfg2.Reporting.templatetags",
                'Bcfg2.Server',
                "Bcfg2.Server.FileMonitor",
                "Bcfg2.Server.Lint",
                "Bcfg2.Server.migrations",
                "Bcfg2.Server.Plugin",
                "Bcfg2.Server.Plugins",
                "Bcfg2.Server.Plugins.Packages",
                "Bcfg2.Server.Plugins.Cfg",
                "Bcfg2.Server.Reports",
                "Bcfg2.Server.Reports.reports",
                ],
      install_requires=inst_reqs,
      tests_require=['mock', 'nose'],
      package_dir={'': 'src/lib', },
      package_data={'Bcfg2.Reporting': ['templates/*.html',
                                        'templates/*/*.html',
                                        'templates/*/*.inc']},
      scripts=glob('src/sbin/*'),
      data_files=[('share/bcfg2/schemas',
                   glob('schemas/*.xsd')),
                  ('share/bcfg2/xsl-transforms',
                   glob('reports/xsl-transforms/*.xsl')),
                  ('share/bcfg2/xsl-transforms/xsl-transform-includes',
                   glob('reports/xsl-transforms/xsl-transform-includes/*.xsl')),
                  ('share/bcfg2', glob('reports/reports.wsgi')),
                  ('share/man/man1', glob("man/bcfg2.1")),
                  ('share/man/man5', glob("man/*.5")),
                  ('share/man/man8', glob("man/*.8")),
                  ('share/bcfg2/site_media',
                   glob('reports/site_media/*')),
                  ]
      )
