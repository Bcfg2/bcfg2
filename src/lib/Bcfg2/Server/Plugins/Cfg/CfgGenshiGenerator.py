""" The CfgGenshiGenerator allows you to use the `Genshi
<http://genshi.edgewall.org>`_ templating system to generate
:ref:`server-plugins-generators-cfg` files. """

import re
import sys
import logging
import traceback
import Bcfg2.Server.Plugin
from Bcfg2.Server.Plugins.Cfg import CfgGenerator

LOGGER = logging.getLogger(__name__)

try:
    import genshi.core
    from genshi.template import TemplateLoader, NewTextTemplate
    from genshi.template.eval import UndefinedError
    HAS_GENSHI = True
except ImportError:
    TemplateLoader = None  # pylint: disable=C0103
    HAS_GENSHI = False


def removecomment(stream):
    """ A Genshi filter that removes comments from the stream.  This
    function is a generator.

    :param stream: The Genshi stream to remove comments from
    :type stream: genshi.core.Stream
    :returns: tuple of ``(kind, data, pos)``, as when iterating
              through a Genshi stream
    """
    for kind, data, pos in stream:
        if kind is genshi.core.COMMENT:
            continue
        yield kind, data, pos


class CfgGenshiGenerator(CfgGenerator):
    """ The CfgGenshiGenerator allows you to use the `Genshi
    <http://genshi.edgewall.org>`_ templating system to generate
    :ref:`server-plugins-generators-cfg` files. """

    #: Handle .genshi files
    __extensions__ = ['genshi']

    #: ``__loader_cls__`` is the class that will be instantiated to
    #: load the template files.  It must implement one public function,
    #: ``load()``, as :class:`genshi.template.TemplateLoader`.
    __loader_cls__ = TemplateLoader

    #: Ignore ``.genshi_include`` files so they can be used with the
    #: Genshi ``{% include ... %}`` directive without raising warnings.
    __ignore__ = ["genshi_include"]

    #: Low priority to avoid matching host- or group-specific
    #: .crypt.genshi files
    __priority__ = 50

    #: Error-handling in Genshi is pretty obtuse.  This regex is used
    #: to extract the first line of the code block that raised an
    #: exception in a Genshi template so we can provide a decent error
    #: message that actually tells the end user where an error
    #: occurred.
    pyerror_re = re.compile('<\w+ u?[\'"](.*?)\s*\.\.\.[\'"]>')

    def __init__(self, fname, spec, encoding):
        CfgGenerator.__init__(self, fname, spec, encoding)
        if not HAS_GENSHI:
            msg = "Cfg: Genshi is not available: %s" % fname
            LOGGER.error(msg)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
        self.loader = self.__loader_cls__()
        self.template = None
    __init__.__doc__ = CfgGenerator.__init__.__doc__

    def get_data(self, entry, metadata):
        fname = entry.get('realname', entry.get('name'))
        stream = \
            self.template.generate(name=fname,
                                   metadata=metadata,
                                   path=self.name).filter(removecomment)
        try:
            try:
                return stream.render('text', encoding=self.encoding,
                                     strip_whitespace=False)
            except TypeError:
                return stream.render('text', encoding=self.encoding)
        except UndefinedError:
            # a failure in a genshi expression _other_ than %{ python ... %}
            err = sys.exc_info()[1]
            stack = traceback.extract_tb(sys.exc_info()[2])
            for quad in stack:
                if quad[0] == self.name:
                    LOGGER.error("Cfg: Error rendering %s at '%s': %s: %s" %
                                 (fname, quad[2], err.__class__.__name__, err))
                    break
            raise
        except:
            self._handle_genshi_exception(fname, sys.exc_info())
    get_data.__doc__ = CfgGenerator.get_data.__doc__

    def _handle_genshi_exception(self, fname, exc):
        """ this is horrible, and I deeply apologize to whoever gets
        to maintain this after I go to the Great Beer Garden in the
        Sky.  genshi is incredibly opaque about what's being executed,
        so the only way I can find to determine which {% python %}
        block is being executed -- if there are multiples -- is to
        iterate through them and match the snippet of the first line
        that's in the traceback with the first non-empty line of the
        block. """

        # a failure in a %{ python ... %} block -- the snippet in
        # the traceback is just the beginning of the block.
        err = exc[1]
        stack = traceback.extract_tb(exc[2])
        lineno, func = stack[-1][1:3]
        execs = [contents
                 for etype, contents, _ in self.template.stream
                 if etype == self.template.EXEC]
        contents = None
        if len(execs) == 1:
            contents = execs[0]
        elif len(execs) > 1:
            match = self.pyerror_re.match(func)
            if match:
                firstline = match.group(0)
                for pyblock in execs:
                    if pyblock.startswith(firstline):
                        contents = pyblock
                        break
        # else, no EXEC blocks -- WTF?
        if contents:
            # we now have the bogus block, but we need to get the
            # offending line.  To get there, we do (line number
            # given in the exception) - (firstlineno from the
            # internal genshi code object of the snippet) + 1 =
            # (line number of the line with an error within the
            # block, with all multiple line breaks elided to a
            # single line break)
            real_lineno = lineno - contents.code.co_firstlineno
            src = re.sub(r'\n\n+', '\n', contents.source).splitlines()
            LOGGER.error("Cfg: Error rendering %s at '%s': %s: %s" %
                         (fname, src[real_lineno], err.__class__.__name__,
                          err))
        raise

    def handle_event(self, event):
        CfgGenerator.handle_event(self, event)
        if self.data is None:
            return
        try:
            self.template = self.loader.load(self.name, cls=NewTextTemplate,
                                             encoding=self.encoding)
        except:
            msg = "Cfg: Could not load template %s: %s" % (self.name,
                                                           sys.exc_info()[1])
            LOGGER.error(msg)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
    handle_event.__doc__ = CfgGenerator.handle_event.__doc__
