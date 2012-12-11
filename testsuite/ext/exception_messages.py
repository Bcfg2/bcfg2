from logilab import astng
from pylint.interfaces import IASTNGChecker
from pylint.checkers import BaseChecker
from pylint.checkers.utils import safe_infer


class ExceptionMessageChecker(BaseChecker):
    __implements__ = IASTNGChecker

    name = 'Exception Messages'
    msgs = \
        {'R9901': ('Exception raised without arguments',
                   'Used when an exception is raised without any arguments')}
    options = (
        ('exceptions-without-args',
         dict(default=('NotImplementedError',),
              type='csv',
              metavar='<exception names>',
              help='List of exception names that may be raised without arguments')),)
    # this is important so that your checker is executed before others
    priority = -1

    def visit_raise(self, node):
        if node.exc is None:
            return
        if isinstance(node.exc, astng.Name):
            raised = safe_infer(node.exc)
            if (isinstance(raised, astng.Class) and
                raised.name not in self.config.exceptions_without_args):
                self.add_message('R9901', node=node.exc)


def register(linter):
    """required method to auto register this checker"""
    linter.register_checker(ExceptionMessageChecker(linter))
