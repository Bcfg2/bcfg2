#!/usr/bin/env python

from distutils.core import setup
from glob import glob

setup(name="Bcfg2.Server",
      version="0.2",
      description="Bcfg2 Server",
      author="Narayan Desai",
      author_email="desai@mcs.anl.gov",
      packages=["Bcfg2", 'Bcfg2.Server', "Bcfg2.Server.Generators", "Bcfg2.Server.Structures", "Bcfg2.Client"],
      package_dir = {'Bcfg2':'src/lib'}, 
      scripts = ['src/sbin/Bcfg2Server', 'src/sbin/bcfg2', 'src/sbin/ValidateBcfg2Repo', 'src/sbin/StatReports', 'src/sbin/GenerateHostInfo'],
      data_files = [('share/bcfg2/schemas',
                     glob('schemas/*.xsd')),
                    ('share/bcfg2/web-rprt-srcs',
                     ['reports/web-rprt-srcs/boxypastel.css','reports/web-rprt-srcs/main.js']),
                    ('share/bcfg2/xsl-transforms',
                     glob('reports/xsl-transforms/*.xsl')),
                    ('share/bcfg2/xsl-transforms/xsl-transform-includes',
                     glob('reports/xsl-transforms/xsl-transform-includes/*.xsl')),
                    ('share/man/man1', ['man/bcfg2.1']),
                    ('share/man/man8', ['man/Bcfg2Server.8', 'man/ValidateBcfg2Repo.8'])]
      )
