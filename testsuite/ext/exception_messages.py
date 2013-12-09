try:
    from logilab import astng as ast
    from pylint.interfaces import IASTNGChecker as IChecker
    PYLINT = 0  # pylint 0.something
except ImportError:
    import astroid as ast
    from pylint.interfaces import IAstroidChecker as IChecker
    PYLINT = 1  # pylint 1.something
from pylint.checkers import BaseChecker
from pylint.checkers.utils import safe_infer

if PYLINT == 0:
    # this is not quite correct; later versions of pylint 0.* wanted a
    # three-tuple for messages as well
    msg = ('Exception raised without arguments',
           'Used when an exception is raised without any arguments')
else:
    msg = ('Exception raised without arguments',
           'exception-without-args',
           'Used when an exception is raised without any arguments')
msgs = {'R9901': msg}


class ExceptionMessageChecker(BaseChecker):
    __implements__ = IChecker

    name = 'Exception Messages'
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
        if isinstance(node.exc, ast.Name):
            raised = safe_infer(node.exc)
            if (isinstance(raised, ast.Class) and
                raised.name not in self.config.exceptions_without_args):
                self.add_message('R9901', node=node.exc)


def register(linter):
    """required method to auto register this checker"""
    linter.register_checker(ExceptionMessageChecker(linter))
