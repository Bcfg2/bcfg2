import re
import sys
import logging
import traceback
import Bcfg2.Server.Plugin
from Bcfg2.Server.Plugins.Cfg import CfgGenerator

logger = logging.getLogger(__name__)

try:
    import genshi.core
    from genshi.template import TemplateLoader, NewTextTemplate
    from genshi.template.eval import UndefinedError
    have_genshi = True
except ImportError:
    TemplateLoader = None
    have_genshi = False

# snipped from TGenshi
def removecomment(stream):
    """A genshi filter that removes comments from the stream."""
    for kind, data, pos in stream:
        if kind is genshi.core.COMMENT:
            continue
        yield kind, data, pos


class CfgGenshiGenerator(CfgGenerator):
    __extensions__ = ['genshi']
    __loader_cls__ = TemplateLoader
    pyerror_re = re.compile('<\w+ u?[\'"](.*?)\s*\.\.\.[\'"]>')

    def __init__(self, fname, spec, encoding):
        CfgGenerator.__init__(self, fname, spec, encoding)
        if not have_genshi:
            msg = "Cfg: Genshi is not available: %s" % fname
            logger.error(msg)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
        self.loader = self.__loader_cls__()
        self.template = None

    @classmethod
    def ignore(cls, event, basename=None):
        return (event.filename.endswith(".genshi_include") or
                CfgGenerator.ignore(event, basename=basename))

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
                    logger.error("Cfg: Error rendering %s at '%s': %s: %s" %
                                 (fname, quad[2], err.__class__.__name__, err))
                    break
            raise
        except:
            # a failure in a %{ python ... %} block -- the snippet in
            # the traceback is just the beginning of the block.
            err = sys.exc_info()[1]
            stack = traceback.extract_tb(sys.exc_info()[2])
            (filename, lineno, func, text) = stack[-1]
            # this is horrible, and I deeply apologize to whoever gets
            # to maintain this after I go to the Great Beer Garden in
            # the Sky.  genshi is incredibly opaque about what's being
            # executed, so the only way I can find to determine which
            # {% python %} block is being executed -- if there are
            # multiples -- is to iterate through them and match the
            # snippet of the first line that's in the traceback with
            # the first non-empty line of the block.
            execs = [contents
                     for etype, contents, loc in self.template.stream
                     if etype == self.template.EXEC]
            contents = None
            if len(execs) == 1:
                contents = execs[0]
            elif len(execs) > 1:
                match = pyerror_re.match(func)
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
                logger.error("Cfg: Error rendering %s at '%s': %s: %s" %
                             (fname, src[real_lineno], err.__class__.__name__,
                              err))
            raise

    def handle_event(self, event):
        if event.code2str() == 'deleted':
            return
        CfgGenerator.handle_event(self, event)
        try:
            self.template = self.loader.load(self.name, cls=NewTextTemplate,
                                             encoding=self.encoding)
        except Exception:
            msg = "Cfg: Could not load template %s: %s" % (self.name,
                                                           sys.exc_info()[1])
            logger.error(msg)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
            
