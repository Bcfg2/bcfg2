#!/usr/bin/env python

from distutils.core import setup

setup(name="Bcfg2.Server",
      version="0.2",
      description="Bcfg2 Server",
      author="Narayan Desai",
      author_email="desai@mcs.anl.gov",
      packages=["Bcfg2", 'Bcfg2.Server', "Bcfg2.Client"],
      package_dir = {'Bcfg2':'src/lib'}, 
      scripts = ['src/sbin/Bcfg2Server', 'src/sbin/bcfg2']
     )
