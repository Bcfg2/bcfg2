import os
import sys

# add all parent testsuite directories to sys.path to allow (most)
# relative imports in python 2.4
_path = os.path.dirname(__file__)
while _path != '/':
    if os.path.basename(_path).lower().startswith("test"):
        sys.path.append(_path)
    if os.path.basename(_path) == "testsuite":
        break
    _path = os.path.dirname(_path)
from common import *


try:
    from sphinx.application import Sphinx
    HAS_SPHINX = True
except ImportError:
    HAS_SPHINX = False


TEST_SPHINX = bool(os.environ.get('TEST_SPHINX', 'no') != 'no')


class DocTest(Bcfg2TestCase):
    top = os.path.join(os.path.dirname(__file__), '..', '..')
    source_dir = os.path.join(top, 'doc/')
    doctree_dir = os.path.join(top, 'build', 'doctree')

    @skipUnless(HAS_SPHINX, 'Sphinx not found')
    @skipUnless(TEST_SPHINX, 'Documentation testing disabled')
    def test_html_documentation(self):
        output_dir = os.path.join(self.top, 'build', 'html')

        app = Sphinx(self.source_dir, self.source_dir, output_dir,
                     self.doctree_dir, buildername='html',
                     warningiserror=True)
        app.build(force_all=True)
