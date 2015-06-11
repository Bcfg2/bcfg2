try:
    from logilab.astng import MANAGER, scoped_nodes, node_classes
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
        MANAGER.register_transformer(ssl_transform)
    else:
        MANAGER.register_transform(scoped_nodes.Module, ssl_transform)
