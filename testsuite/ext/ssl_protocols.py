try:
    from logilab.astng import MANAGER, builder, scoped_nodes, node_classes
    PYLINT=0
except ImportError:
    from astroid import MANAGER, scoped_nodes, node_classes
    PYLINT=1

def ssl_transform(module):
    if module.name == 'ssl':
        for proto in ('SSLv23', 'TLSv1'):
            module.locals['PROTOCOL_%s' % proto] = [node_classes.Const()]

def register(linter):
    if PYLINT == 0:
        if hasattr(MANAGER, 'register_transformer'):
            MANAGER.register_transformer(ssl_transform)
        else:
            safe = builder.ASTNGBuilder.string_build
            def _string_build(self, data, modname='', path=None):
                if modname == 'ssl':
                    data += '\n\nPROTOCOL_SSLv23 = 0\nPROTOCOL_TLSv1 = 0'
                return safe(self, data, modname, path)
            builder.ASTNGBuilder.string_build = _string_build
    else:
        MANAGER.register_transform(scoped_nodes.Module, ssl_transform)
