from pylint.__pkginfo__ import version as pylint_version
from logilab.astng.__pkginfo__ import version as astng_version

def register(linter):
    if pylint_version < '0.24.0':
        import pylint.utils
        orig_check_message_id = pylint.utils.MessagesHandlerMixIn.check_message_id
        def check_message_id(self, msgid):
            # translate the new message ids back into the old ones
            replacements = {'12': '65', '13': '99'}
            new = msgid[1:3]
            if new in replacements:
                msgid = msgid[0] + replacements[new] + msgid[3:]
            return orig_check_message_id(self, msgid)
        pylint.utils.MessagesHandlerMixIn.check_message_id = check_message_id

        def ignore(meth, msgid, *args, **kwargs):
            # ignore non-existent message ids in disable/enable comments
            ignore = ['W1401', 'R0924']
            if msgid in ignore:
                return
            return meth(msgid, *args, **kwargs)
        linter._options_methods['disable'] = lambda *args, **kwargs: ignore(linter.disable, *args, **kwargs)
        linter._options_methods['enable'] = lambda *args, **kwargs: ignore(linter.enable, *args, **kwargs)

    if pylint_version < '0.22.0':
        import pylint.checkers.exceptions
        orig_visit_raise = pylint.checkers.exceptions.ExceptionsChecker.visit_raise
        def visit_raise(self, node):
            if not hasattr(node, 'type') and hasattr(node, 'exc'):
                node.type = node.exc
            return orig_visit_raise(self, node)
        pylint.checkers.exceptions.ExceptionsChecker.visit_raise = visit_raise

    if astng_version < '0.23':
        import logilab.astng.scoped_nodes
        from logilab.astng.bases import InferenceContext, InferenceError

        # backport import bug fix (e642ba33ba1bdde04ac9f0c75a25dc40131c55e7)
        def ancestors(self, recurs=True, context=None):
            yielded = set([self])
            if context is None:
                context = InferenceContext()
            for stmt in self.bases:
                path = set(context.path)
                try:
                    for baseobj in stmt.infer(context):
                        if not isinstance(baseobj, logilab.astng.scoped_nodes.Class):
                            # duh ?
                            continue
                        if baseobj in yielded:
                            continue # cf xxx above
                        yielded.add(baseobj)
                        yield baseobj
                        if recurs:
                            for grandpa in baseobj.ancestors(True, context):
                                if grandpa in yielded:
                                    continue # cf xxx above
                                yielded.add(grandpa)
                                yield grandpa
                except InferenceError:
                    # XXX log error ?
                    pass
                context.path = path
        logilab.astng.scoped_nodes.Class.ancestors = ancestors

        # support for classpropery (d110bcf2de4b8bc48e41638cf430f17c5714ffbc)
        try:
            from logilab.astng.rebuilder import TreeRebuilder
        except:
            try:
                from logilab.astng._nodes_ast import TreeRebuilder
            except:
                from logilab.astng._nodes_compiler import TreeRebuilder
        from logilab.astng import nodes

        orig_visit_function = TreeRebuilder.visit_function
        def visit_function(self, node, parent):
            newnode = orig_visit_function(self, node, parent)
            if newnode.decorators is not None:
                for decorator_expr in newnode.decorators.nodes:
                    if isinstance(decorator_expr, nodes.Name):
                        if decorator_expr.name == 'classproperty':
                            newnode.type = 'classmethod'
            return newnode
        TreeRebuilder.visit_function = visit_function

    if astng_version < '0.22':
        from logilab.astng import nodes
        from logilab.astng.bases import _infer_stmts, copy_context, path_wrapper, \
            InferenceError, NotFoundError
        from logilab.astng._exceptions import ASTNGBuildingException
        import logilab.astng.scoped_nodes
        from logilab.astng.node_classes import List, DelName

        # backport of 11886551cfdcf969f0a661f8ab63c1fa1a6dd399 with
        # a bit revert of af896e299ce5e381a928a77a9c28941cad90a243
        def infer_from(self, context=None, asname=True):
            name = context.lookupname
            if name is None:
                raise InferenceError()
            if asname:
                name = self.real_name(name)
            module = self.do_import_module(self.modname)
            try:
                context = copy_context(context)
                context.lookupname = name
                return _infer_stmts(module.getattr(name, ignore_locals=module is self.root()), context)
            except NotFoundError:
                raise InferenceError(name)
        nodes.From.infer = path_wrapper(infer_from)

        def getattr(self, name, context=None, ignore_locals=False):
            if name in self.special_attributes:
                if name == '__file__':
                    return [cf(self.file)] + self.locals.get(name, [])
                if name == '__path__' and self.package:
                    return [List()] + self.locals.get(name, [])
                return std_special_attributes(self, name)
            if not ignore_locals and name in self.locals:
                return self.locals[name]
            if self.package:
                try:
                    return [self.import_module(name, relative_only=True)]
                except (KeyboardInterrupt, SystemExit):
                    raise
                except:
                    pass
            raise NotFoundError(name)
        logilab.astng.scoped_nodes.Module.getattr = logilab.astng.scoped_nodes.remove_nodes(getattr, DelName)

    if astng_version < '0.21.1':
        # backport of 3d463da455e33e7ddc53a295b6a33db7b9e4288b
        from logilab.astng.scoped_nodes import Function
        from logilab.astng.rebuilder import RebuildVisitor
        from logilab.astng.bases import YES, Instance

        orig_init = Function.__init__
        def init(self, name, doc):
            orig_init(self, name, doc)
            self.instance_attrs = {}
        Function.__init__ = init

        orig_getattr = Function.getattr
        def getattr(self, name, context=None):
            if name != '__module__' and name in self.instance_attrs:
                return self.instance_attrs[name]
            return orig_getattr(self, name, context)
        Function.getattr = getattr

        def delayed_assattr(self, node):
            """visit a AssAttr node -> add name to locals, handle members
            definition
            """
            try:
                frame = node.frame()
                for infered in node.expr.infer():
                    if infered is YES:
                        continue
                    try:
                        if infered.__class__ is Instance:
                            infered = infered._proxied
                            iattrs = infered.instance_attrs
                        elif isinstance(infered, Instance):
                            # Const, Tuple, ... we may be wrong, may be not, but
                            # anyway we don't want to pollute builtin's namespace
                            continue
                        elif infered.is_function:
                            iattrs = infered.instance_attrs
                        else:
                            iattrs = infered.locals
                    except AttributeError:
                        # XXX log error
                        #import traceback
                        #traceback.print_exc()
                        continue
                    values = iattrs.setdefault(node.attrname, [])
                    if node in values:
                        continue
                    # get assign in __init__ first XXX useful ?
                    if frame.name == '__init__' and values and not \
                           values[0].frame().name == '__init__':
                        values.insert(0, node)
                    else:
                        values.append(node)
            except InferenceError:
                pass
        RebuildVisitor.delayed_assattr = delayed_assattr

    if astng_version < '0.20.4':
        try:
            from logilab.astng._nodes_ast import TreeRebuilder, _lineno_parent
        except:
            from logilab.astng._nodes_compiler import TreeRebuilder
            _lineno_parent = (lambda *args: TreeRebuilder._set_infos(None, *args))
        from logilab.astng import nodes
        from logilab.astng.bases import NodeNG, Instance
        from logilab.astng.mixins import ParentAssignTypeMixin

        class Set(NodeNG, Instance, ParentAssignTypeMixin):
            _astng_fields = ('elts',)
            elts = None

            def pytype(self):
                return '__builtin__.set'

            def itered(self):
                return self.elts

        def visit_set(self, node, parent):
            newnode = Set()
            _lineno_parent(node, newnode, parent)
            newnode.elts = [self.visit(child, newnode) for child in node.elts]
            newnode.set_line_info(newnode.last_child())
            return newnode
        TreeRebuilder.visit_set = visit_set

        def visit_setcomp(self, node, parent):
            newnode = nodes.SetComp()
            _lineno_parent(node, newnode, parent)
            newnode.elt = self.visit(node.elt, newnode)
            newnode.generators = [self.visit(child, newnode)
                                  for child in node.generators]
            newnode.set_line_info(newnode.last_child())
            return newnode
        TreeRebuilder.visit_setcomp = visit_setcomp

        class DictComp(NodeNG):
            _astng_fields = ('key', 'value', 'generators')
            key = None
            value = None
            generators = None

        def visit_dictcomp(self, node, parent):
            newnode = DictComp()
            _lineno_parent(node, newnode, parent)
            newnode.key = self.visit(node.key, newnode)
            newnode.value = self.visit(node.value, newnode)
            newnode.generators = [self.visit(child, newnode)
                                  for child in node.generators]
            newnode.set_line_info(newnode.last_child())
            return newnode
        TreeRebuilder.visit_dictcomp = visit_dictcomp

        # backport of bfe9e5c53cfb75c3b45ebb5cb8e8902464782c7d
        from logilab.astng.node_classes import From
        orig_from_init = From.__init__
        def from_init(self,  fromname, names, level=0):
            orig_from_init(self, fromname or '', names, level)
        From.__init__ = from_init

        # partial backport of 6d59ad07d722d01e458aaf8fd14fd7dfc7ebaa6e
        from logilab.astng.scoped_nodes import Module
        orig_absolute_modname = Module.absolute_modname
        def absolute_modname(self, modname, level):
            result = orig_absolute_modname(self, modname, level)
            if result[-1] == '.':
                return result[:-1]
            return result
        Module.absolute_modname = absolute_modname

        # python2.4 compatibility (no super on old-style classes)
        from logilab.astng.bases import Proxy, UnboundMethod

        def unbound_igetattr(self, name, context=None):
            if name == 'im_func':
                return iter((self._proxied,))
            return Proxy.igetattr(self, name, context)
        UnboundMethod.igetattr = unbound_igetattr

        def unbound_getattr(self, name, context=None):
            if name == 'im_func':
                return [self._proxied]
            return Proxy.getattr(self, name, context)
        UnboundMethod.getattr = unbound_getattr
