#!/usr/bin/env python

from distutils.core import setup

setup(name="Bcfg2.Server",
      version="0.2",
      description="Bcfg2 Server",
      author="Narayan Desai",
      author_email="desai@mcs.anl.gov",
      packages=["Bcfg2", 'Bcfg2.Server', "Bcfg2.Server.Generators", "Bcfg2.Server.Structures", "Bcfg2.Client"],
      package_dir = {'Bcfg2':'src/lib'}, 
      scripts = ['src/sbin/Bcfg2Server', 'src/sbin/bcfg2', 'src/sbin/ValidateBcfg2Repo', 'src/sbin/StatReports'],
      data_files = [('share/bcfg2/schemas', ['schemas/atom.xsd', 'schemas/base.xsd', 'schemas/bundle.xsd', 'schemas/metadata.xsd', 'schemas/pkglist.xsd', 'schemas/services.xsd', 'schemas/translation.xsd', 'schemas/report-configuration.xsd']), ('reports/web-rprt-srcs', ['reports/web-rprt-srcs/boxypastel.css','reports/web-rprt-srcs/main.js']), ('reports/xsl-transforms', ['reports/xsl-transforms/nodes-digest-email.xsl', 'reports/xsl-transforms/nodes-digest-html.xsl', 'reports/xsl-transforms/nodes-digest-rss.xsl', 'reports/xsl-transforms/nodes-individual-email.xsl', 'reports/xsl-transforms/overview-stats-email.xsl', 'reports/xsl-transforms/overview-stats-html.xsl', 'reports/xsl-transforms/overview-stats-rss.xsl']), ('reports/xsl-transforms/xsl-transform-includes', ['reports/xsl-transforms/xsl-transform-includes/html-templates.xsl', 'reports/xsl-transforms/xsl-transform-includes/text-templates.xsl']), ('share/man/man1', ['man/bcfg2.1']), ('share/man/man8', ['man/Bcfg2Server.8', 'man/ValidateBcfg2Repo.8'])]
     )
