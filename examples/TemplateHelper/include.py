""" IncludeHelper makes it easier to include group- and host-specific
files in a template.

Synopsis:

  {% python
  import os
  custom = IncludeHelper(metadata, path).files(os.path.basename(name))
  %}\
  {% for file in custom %}\

  ########## Start ${describe_specificity(file)} ##########
  {% include ${file} %}
  ########## End ${describe_specificity(file)} ##########
  {% end %}\

This would let you include files with the same base name; e.g. in a
template for ''foo.conf'', the include files would be called
''foo.conf.G_<group>.genshi_include''.  If a template needs to include
different files in different places, you can do that like so:

  inc = IncludeHelper(metadata, path)
  custom_bar = inc.files("bar")
  custom_baz = inc.files("baz")

This would result in two different sets of custom files being used,
one drawn from ''bar.conf.G_<group>.genshi_include'' and the other
from ''baz.conf.G_<group>.genshi_include''.

"""

import os
import re

__default__ = ["IncludeHelper", "get_specificity", "describe_specificity"]


class IncludeHelper(object):
    def __init__(self, metadata, path):
        """ Constructor.

        The template path can be found in the ''path'' variable that
        is set for all Genshi templates. """
        self.metadata = metadata
        self.path = path

    def get_basedir(self):
        return os.path.dirname(self.path)

    def files(self, fname, groups=None):
        """ Return a list of files to include for this host.  Files
        are found in the template directory based on the following
        patterns:

          * ''<prefix>.H_<hostname>.genshi_include'': Host-specific files
          * ''<prefix>.G_<group>.genshi_include'': Group-specific files
          * ''<prefix>.genshi_include'': Non-specific includes

        Note that there is no numeric priority on the group-specific
        files; all matching files are returned by
        ``IncludeHelper.files()``.  If you wish to only include files
        for a subset of groups, pass the ``groups`` keyword argument.
        Host-specific files are always included in the return
        value. """
        files = []
        hostfile = os.path.join(self.get_basedir(),
                                "%s.H_%s.genshi_include" %
                                (fname, self.metadata.hostname))
        if os.path.isfile(hostfile):
            files.append(hostfile)

        allfile = os.path.join(self.get_basedir(), "%s.genshi_include" % fname)
        if os.path.isfile(allfile):
            files.append(allfile)

        if groups is None:
            groups = sorted(self.metadata.groups)

        for group in groups:
            filename = os.path.join(self.get_basedir(),
                                    "%s.G_%s.genshi_include" % (fname, group))
            if os.path.isfile(filename):
                files.append(filename)

        return files


SPECIFICITY_RE = re.compile(r'(G|H)_(.*)\.genshi_include')


def get_specificity(fname):
    """ Get a tuple of (<type>, <parameter>) describing the
    specificity of the given file.  Specificity types are "host",
    "group", or "all".  The parameter will be either a hostname, a
    group name, or None (for "all"). """
    match = SPECIFICITY_RE.search(fname)
    if match:
        if match.group(1) == "G":
            stype = "group"
        else:
            stype = "host"
        return (stype, match.group(2))
    return ("all", None)


def describe_specificity(fname):
    """ Get a string describing the specificity of the given file """
    (stype, param) = get_specificity(fname)
    if stype != "all":
        return "%s-specific configs for %s" % (stype, param)
    else:
        return "Generic configs for all clients"
