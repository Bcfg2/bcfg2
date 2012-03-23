"""IncludeHelper makes it easier to include group- and host-specific files in a template.

Synopsis:

  {% python
  import os
  include = metadata.TemplateHelper['include'].IncludeHelper
  custom = include(metadata, path).files(os.path.basename(name))
  %}\
  {% for file in custom %}\
  
  ########## Start ${include.specificity(file)} ##########
  {% include ${file} %}
  ########## End ${include.specificity(file)} ##########
  {% end %}\

This would let you include files with the same base name; e.g. in a
template for ''foo.conf'', the include files would be called
''foo.conf.G_<group>.genshi_include''.  If a template needs to include
different files in different places, you can do that like so:

  inc = metadata.TemplateHelper['include'].IncludeHelper(metadata, path)
  custom_bar = inc.files("bar")
  custom_baz = inc.files("baz")

This would result in two different sets of custom files being used,
one drawn from ''bar.conf.G_<group>.genshi_include'' and the other
from ''baz.conf.G_<group>.genshi_include''.

==== Methods ====


=== files ===

Usage:



"""

import os
import re
import Bcfg2.Options

__export__ = ["IncludeHelper"]

class IncludeHelper (object):
    def __init__(self, metadata, path):
        """ Constructor.

        The template path can be found in the ''path'' variable that is set for all Genshi templates."""
        self.metadata = metadata
        self.path = path
    
    def _get_basedir(self):
        setup = Bcfg2.Options.OptionParser({'repo':
                                            Bcfg2.Options.SERVER_REPOSITORY})
        setup.parse('--')
        return os.path.join(setup['repo'], os.path.dirname(self.path))
    
    def files(self, fname):
        """ Return a list of files to include for this host.  Files
        are found in the template directory based on the following
        patterns:

          * ''<prefix>.H_<hostname>.genshi_include'': Host-specific files
          * ''<prefix>.G_<group>.genshi_include'': Group-specific files

        Note that there is no numeric priority on the group-specific
        files.  All matching files are returned by
        ''IncludeHelper.files()''. """
        files = []
        hostfile = os.path.join(self._get_basedir(),
                                "%s.H_%s.genshi_include" %
                                (fname, self.metadata.hostname))
        if os.path.isfile(hostfile):
            files.append(hostfile)
            
        for group in self.metadata.groups:
            filename = os.path.join(self._get_basedir(),
                                    "%s.G_%s.genshi_include" % (fname, group))
            if os.path.isfile(filename):
                files.append(filename)

        return sorted(files)

    @staticmethod
    def specificity(fname):
        """ Get a string describing the specificity of the given file """
        match = re.search(r'(G|H)_(.*)\.genshi_include', fname)
        if match:
            if match.group(1) == "G":
                stype = "group"
            else:
                stype = "host"
            return "%s-specific configs for %s" % (stype, match.group(2))
        return "Unknown specificity"
